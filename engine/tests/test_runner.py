import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from salesbench_engine import Engine
from salesbench_engine.actions import CreateListing, Procure, Purchase, SendPrivate, SendPublic, UpdateListing, Wait
from salesbench_engine.runner import LLMDriver, MarketConfig, ModelResponse, ModelSettings, Phase, Runner, RuntimeConfig, ScriptedDriver, replay
from salesbench_engine.runner.codec import InvalidBatch, canonical, data, encode_batch, parse_batch
from salesbench_engine.runner.demo import run_demo
from salesbench_engine.runner.drivers import DriverReply
from salesbench_engine.runner.journal import ActionExecutor, IdempotencyConflict, Journal
from salesbench_engine.runner.protocol import BUYER_ACTION, PROCUREMENT, SELLER_STRATEGY, WaveContext
from salesbench_engine.runner.replay import ReplayMismatch, logical_records
from salesbench_engine.runner.scheduler import priority
from test_domain import make_setup


def market_script(obs):
    if obs.context.wave == PROCUREMENT.name:
        return (Procure("cup-offer", 1, 100),)
    if obs.context.wave == SELLER_STRATEGY.name:
        return (CreateListing(obs.actor_id + "/cup", "cup", 300, "TEST cup"),)
    listing = next(v.listing for v in obs.state.public.listings if v.listing.id == "seller/cup")
    return (Purchase(listing.id, 1, listing.unit_price_cents, listing.offer_revision),)


def make_runner(script=market_script, *, config=None, runtime=None, drivers=None, setup=None):
    setup = setup or make_setup()
    return Runner(setup, drivers or {a.id: ScriptedDriver(script) for a in (*setup.sellers, *setup.buyers)},
                  config=config or MarketConfig(max_rounds=1, ticks_per_round=1), runtime=runtime or RuntimeConfig())


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_round_procurement_tick_wave_and_no_early_exit_on_wait(self):
        runner = make_runner(lambda obs: (Wait(),), config=MarketConfig(max_rounds=2, ticks_per_round=3))
        state = await runner.run()
        self.assertEqual(runner.phase, Phase.COMPLETED)
        self.assertEqual(state.time.step, 2)
        rows = runner.journal.records
        observations = [r["observation"] for r in rows if r["kind"] == "observation"]
        self.assertEqual(sum(o["context"]["wave"] == PROCUREMENT.name for o in observations), 4)
        self.assertEqual(sum(o["context"]["wave"] == SELLER_STRATEGY.name for o in observations), 12)
        self.assertEqual(sum(o["context"]["wave"] == BUYER_ACTION.name for o in observations), 12)
        self.assertEqual([r["result"]["step"] for r in rows if r["kind"] == "round_closed"], [1, 2])
        for o in observations:
            self.assertEqual(o["state"]["public"]["time"]["step"], o["context"]["round"] - 1)
        with self.assertRaises(RuntimeError):
            await runner.run()

    async def test_frozen_public_private_isolation_feedback_and_same_tick_price(self):
        seen = []

        def script(obs):
            seen.append(obs)
            if obs.context.wave == PROCUREMENT.name:
                self.assertIsNotNone(obs.procurement)
                return (Procure("cup-offer", 3 if obs.actor_id == "seller" else 1, 100),)
            self.assertIsNone(obs.procurement)
            if obs.context.wave == SELLER_STRATEGY.name:
                if obs.context.tick == 1:
                    return (CreateListing(obs.actor_id + "/cup", "cup", 300, "Cup"),
                            UpdateListing(obs.actor_id + "/cup", unit_price_cents=350),
                            SendPrivate("buyer", "Secret from " + obs.actor_id))
                return (SendPublic(obs.actor_id, "Next tick"),)
            if obs.actor_id == "buyer" and obs.context.tick == 1:
                item = next(v.listing for v in obs.state.public.listings if v.listing.id == "seller/cup")
                self.assertEqual((item.unit_price_cents, item.offer_revision), (350, 2))
                return (SendPublic("seller", "A public question"), Purchase(item.id, 1, 350, 2))
            return (Wait(),)

        runner = make_runner(script, config=MarketConfig(max_rounds=1, ticks_per_round=2))
        await runner.run()
        self.assertEqual(runner.phase, Phase.COMPLETED)
        for name in (SELLER_STRATEGY.name, BUYER_ACTION.name):
            for tick in (1, 2):
                group = [o for o in seen if o.context.wave == name and o.context.tick == tick]
                self.assertIs(group[0].state.public, group[1].state.public)
                self.assertNotEqual(group[0].state.own.account.actor_id, group[1].state.own.account.actor_id)
        seller_obs = next(o for o in seen if o.actor_id == "seller" and o.context.tick == 1)
        other_seller = next(o for o in seen if o.actor_id == "other-seller" and o.context.tick == 1)
        self.assertEqual(seller_obs.state.own.inventory[0].quantity, 3)
        self.assertEqual(other_seller.state.own.inventory[0].quantity, 1)
        self.assertEqual(seller_obs.state.own.offers, ())
        other_buyer = next(o for o in seen if o.actor_id == "other-buyer" and o.context.tick == 1)
        self.assertEqual(other_buyer.state.inbox.messages, ())
        self.assertEqual(other_buyer.state.own.orders, ())
        self.assertEqual(other_buyer.state.public.messages, ())  # Same-Wave buyer messages invisible.
        next_buyer = next(o for o in seen if o.actor_id == "buyer" and o.context.tick == 2)
        self.assertEqual(len(next_buyer.state.inbox.messages), 2)
        self.assertEqual(next_buyer.state.own.account.balance_cents, 650)
        self.assertTrue(any(m.text == "A public question" for m in next_buyer.state.public.messages))
        self.assertEqual([r.status for r in next_buyer.state.previous_outcomes], ["succeeded", "succeeded"])
        public = data(next_buyer.state.public)
        self.assertFalse({"account", "orders", "offers", "events", "inventory"} & public.keys())
        with self.assertRaises(FrozenInstanceError):
            next_buyer.state.own.account.balance_cents = 1

    async def test_fast_driver_cannot_execute_and_mid_commit_observations_remain_published(self):
        ready, release = asyncio.Event(), asyncio.Event()

        class GatedDriver(ScriptedDriver):
            async def decide(self, obs):
                if obs.context.wave == SELLER_STRATEGY.name and obs.actor_id == "seller":
                    ready.set()
                    await release.wait()
                return await super().decide(obs)

        setup = make_setup()
        runner = make_runner(drivers={a.id: GatedDriver(market_script) for a in (*setup.sellers, *setup.buyers)})
        execute = runner._engine.execute
        probes = []

        def probe(actor, action):
            if isinstance(action, CreateListing):
                before = runner.observe(actor)
                result = execute(actor, action)
                probes.append(before.public.version)
                self.assertIs(runner.observe(actor), before)
                self.assertEqual(before.public.listings, ())
                return result
            return execute(actor, action)

        with patch.object(runner._engine, "execute", side_effect=probe):
            task = asyncio.create_task(runner.run())
            await asyncio.wait_for(ready.wait(), 2)
            await asyncio.sleep(0)  # Give the other driver a chance to finish.
            self.assertEqual(runner.economic_state().listings, ())
            self.assertEqual(runner.phase, Phase.COLLECTING)
            release.set()
            await task
        self.assertEqual(probes, [1, 1])
        self.assertEqual(len(runner.economic_state().listings), 2)

    async def test_llm_return_order_driver_order_provider_and_concurrency_do_not_change_market(self):
        async def run(reverse, concurrency):
            completed = []

            class FakeAdapter:
                def count_input_tokens(self, request):
                    return 100

                async def generate(self, request):
                    obs = json.loads(request.user)["observation"]
                    actor = obs["state"]["own"]["actor"]["id"]
                    slow = actor.startswith("other-") != reverse
                    await asyncio.sleep(0.008 if slow else 0)
                    completed.append((obs["context"]["wave"], actor))
                    wave = obs["context"]["wave"]
                    actions = (Procure("cup-offer", 1, 100),) if wave == PROCUREMENT.name else (
                        (CreateListing(actor + "/cup", "cup", 300, "TEST cup"),) if wave == SELLER_STRATEGY.name
                        else (Purchase("seller/cup", 1, 300, 1),))
                    return ModelResponse(encode_batch(actions), "fake-v1", 100, 30)

            actors = [a.id for a in (*make_setup().sellers, *make_setup().buyers)]
            if reverse:
                actors.reverse()
            drivers = {a: LLMDriver(FakeAdapter(), ModelSettings("fake-B" if reverse else "fake-A", "test-model")) for a in actors}
            runner = make_runner(drivers=drivers, runtime=RuntimeConfig(concurrency=concurrency))
            await runner.run()
            self.assertEqual(runner.phase, Phase.COMPLETED)
            return runner, completed

        a, fast_a = await run(False, 4)
        b, fast_b = await run(True, 4)
        c, _ = await run(False, 1)
        self.assertNotEqual(fast_a, fast_b)
        for other in (b, c):
            self.assertEqual(a.economic_state(), other.economic_state())
            self.assertEqual(logical_records(a.journal.records), logical_records(other.journal.records))
        self.assertEqual(len(a.economic_state().orders), 1)

    async def test_global_purchase_order_across_listings_sharing_last_stock(self):
        def script(obs):
            if obs.context.wave == SELLER_STRATEGY.name and obs.actor_id == "seller":
                return (CreateListing("seller/cup", "cup", 300, "Cup"), CreateListing("seller/alt", "cup", 200, "Same stock"))
            if obs.context.wave == BUYER_ACTION.name:
                return (Purchase("seller/alt" if obs.actor_id == "buyer" else "seller/cup", 1, 200 if obs.actor_id == "buyer" else 300, 1),)
            return market_script(obs)

        runner = make_runner(script)
        state = await runner.run()
        order = next(r["order"] for r in runner.journal.records if r["kind"] == "resolution" and r["purpose"] == "purchase")
        self.assertEqual([o.buyer_id for o in state.orders], order[:1])
        self.assertEqual(next(i.quantity for i in state.inventory if i.seller_id == "seller"), 0)
        self.assertEqual([r["result"]["code"] for r in runner.journal.records if r["kind"] == "action_result" and not r["result"]["ok"]], ["OUT_OF_STOCK"])
        self.assertEqual(sum(a.balance_cents for a in state.accounts), 4000)

    async def test_failed_purchase_candidate_does_not_block_next_and_no_partial_fill(self):
        config = MarketConfig(max_rounds=1, ticks_per_round=1)
        context = WaveContext(1, 1, BUYER_ACTION.name)
        first = min(("buyer", "other-buyer"), key=lambda a: priority(config, context, "purchase", a))

        def script(obs):
            if obs.context.wave == BUYER_ACTION.name:
                return (Purchase("seller/cup", 2 if obs.actor_id == first else 1, 300, 1),)
            return market_script(obs)

        runner = make_runner(script, config=config)
        state = await runner.run()
        self.assertEqual(len(state.orders), 1)
        self.assertNotEqual(state.orders[0].buyer_id, first)
        self.assertEqual(next(a.balance_cents for a in state.accounts if a.actor_id == first), 1000)

    async def test_stale_price_or_aba_revision_fails_without_preventing_current_offer_purchase(self):
        for expected_price, expected_code in ((250, "PRICE_CHANGED"), (300, "STALE_LISTING")):
            with self.subTest(expected_code=expected_code):
                def script(obs):
                    if obs.context.wave == SELLER_STRATEGY.name:
                        return (CreateListing(obs.actor_id + "/cup", "cup", 300, "Cup"),
                                UpdateListing(obs.actor_id + "/cup", unit_price_cents=400),
                                UpdateListing(obs.actor_id + "/cup", unit_price_cents=300))
                    if obs.context.wave == BUYER_ACTION.name:
                        return (Purchase("seller/cup", 1, expected_price if obs.actor_id == "buyer" else 300,
                                         1 if obs.actor_id == "buyer" else 3),)
                    return market_script(obs)

                runner = make_runner(script)
                state = await runner.run()
                self.assertEqual([(o.buyer_id, o.offer_revision) for o in state.orders], [("other-buyer", 3)])
                result = runner.observe("buyer").previous_outcomes[0].result
                self.assertEqual(result.code, expected_code)
                self.assertEqual(runner.observe("buyer").own.account.balance_cents, 1000)

    async def test_resolution_seed_is_separate_from_market_seed_and_opportunity_identity(self):
        first = make_runner()
        setup = make_setup()
        changed = replace(setup, experiment=replace(setup.experiment, id="another-run-id", seed=999))
        second = make_runner(setup=changed)
        await first.run()
        await second.run()
        self.assertEqual(first.economic_state().orders, second.economic_state().orders)
        self.assertEqual([r for r in logical_records(first.journal.records) if r["kind"] == "resolution"],
                         [r for r in logical_records(second.journal.records) if r["kind"] == "resolution"])
        first_id = next(r["action_id"] for r in first.journal.records if r["kind"] == "action_attempt")
        second_id = next(r["action_id"] for r in second.journal.records if r["kind"] == "action_attempt")
        self.assertNotEqual(first_id, second_id)
        context = WaveContext(1, 1, BUYER_ACTION.name)
        self.assertNotEqual(priority(first.config, context, "purchase", "buyer"),
                            priority(replace(first.config, resolution_seed=999), context, "purchase", "buyer"))

    async def test_business_failure_keeps_prefix_skips_tail_and_other_actors_continue(self):
        def script(obs):
            if obs.context.wave == SELLER_STRATEGY.name and obs.actor_id == "seller":
                return (CreateListing("seller/cup", "cup", 300, "Cup"), UpdateListing("missing", active=False), SendPublic("seller", "Must skip"))
            if obs.context.wave == BUYER_ACTION.name and obs.actor_id == "buyer":
                return (SendPrivate("other-buyer", "Forbidden"), Purchase("seller/cup", 1, 300, 1))
            return market_script(obs)

        runner = make_runner(script)
        state = await runner.run()
        self.assertEqual(runner.phase, Phase.COMPLETED)
        self.assertEqual([o.buyer_id for o in state.orders], ["other-buyer"])
        self.assertFalse(any(m.text == "Must skip" for m in state.messages))
        skipped = [r for r in runner.journal.records if r["kind"] == "skipped"]
        self.assertEqual(len(skipped), 2)
        self.assertTrue(all(r["outcome"]["reason"].startswith("PRIOR_BUSINESS_FAILURE:") for r in skipped))
        self.assertEqual([o.status for o in runner.observe("seller").previous_outcomes], ["succeeded", "business_failed", "skipped"])

    async def test_invalid_whole_batch_consumes_opportunity_and_other_actor_continues(self):
        class InvalidDriver(ScriptedDriver):
            async def decide(self, obs):
                if obs.context.wave == SELLER_STRATEGY.name:
                    return DriverReply(encode_batch((CreateListing("seller/cup", "cup", 300, "Cup"), Wait())))
                return await super().decide(obs)

        runner = make_runner(drivers={"seller": InvalidDriver(market_script), "other-seller": ScriptedDriver(market_script),
                                      "buyer": ScriptedDriver(), "other-buyer": ScriptedDriver()})
        await runner.run()
        self.assertEqual(runner.phase, Phase.COMPLETED)
        self.assertEqual([x.id for x in runner.economic_state().listings], ["other-seller/cup"])
        self.assertEqual(runner.observe("seller").previous_outcomes[0].reason, "WAIT_MUST_BE_ALONE")

    async def test_procurement_once_per_round_and_forbidden_inside_seller_tick(self):
        def script(obs):
            return (Procure("cup-offer", 1, 100),) if obs.actor_id.endswith("seller") else (Wait(),)

        runner = make_runner(script, config=MarketConfig(max_rounds=2, ticks_per_round=3))
        state = await runner.run()
        self.assertEqual(len(state.procurements), 4)
        self.assertEqual(len([r for r in runner.journal.records if r["kind"] == "admission" and r["status"] == "invalid_batch"]), 12)

    async def test_technical_timeout_and_error_abort_wave_without_wait_or_advance(self):
        for fault in ("timeout", "error"):
            with self.subTest(fault=fault):
                class BrokenDriver(ScriptedDriver):
                    async def decide(self, obs):
                        if obs.context.wave == SELLER_STRATEGY.name:
                            if fault == "timeout":
                                await asyncio.sleep(2)
                            raise RuntimeError("fake credential should never enter journal")
                        return await super().decide(obs)

                drivers = {a.id: ScriptedDriver(market_script) for a in (*make_setup().sellers, *make_setup().buyers)}
                drivers["seller"] = BrokenDriver(market_script)
                runner = make_runner(drivers=drivers, runtime=RuntimeConfig(timeout_seconds=0.02))
                state = await runner.run()
                self.assertEqual(runner.phase, Phase.FAILED)
                self.assertEqual(state.time.step, 0)
                self.assertEqual(state.listings, ())
                self.assertEqual(len(state.procurements), 2)
                self.assertNotIn("fake credential", canonical(runner.journal.records))
                self.assertFalse(any(e.kind == "waited" for e in state.events))
                restored = await replay(runner.journal.records)
                self.assertEqual(restored.economic_state(), state)

    async def test_execution_fault_keeps_prefix_unpublished_and_replays_recorded_boundary(self):
        runner = make_runner()
        execute = runner._engine.execute
        count = 0

        def fail_second_listing(actor, action):
            nonlocal count
            if isinstance(action, CreateListing):
                count += 1
                if count == 2:
                    raise RuntimeError("implementation failure")
            return execute(actor, action)

        with patch.object(runner._engine, "execute", side_effect=fail_second_listing):
            state = await runner.run()
        self.assertEqual(runner.phase, Phase.FAILED)
        self.assertEqual(len(state.listings), 1)
        self.assertEqual(state.time.step, 0)
        self.assertEqual(runner.observe("buyer").public.listings, ())
        self.assertEqual(runner.observe("buyer").public.version, 1)
        self.assertEqual((await replay(runner.journal.records)).economic_state(), state)

    async def test_recorded_trace_replay_ignores_clock_checks_economics_and_detects_tampering(self):
        runner = await run_demo()
        self.assertEqual(runner.phase, Phase.COMPLETED)
        rows = runner.journal.records
        for row in rows:
            row["recorded_at"] = "different wall clock"
            if row["kind"] == "driver_reply":
                row["elapsed_seconds"] = 99999
        restored = await replay(rows)
        self.assertEqual(restored.economic_state(), runner.economic_state())
        changed = deepcopy(rows)
        target = next(r for r in changed if r["kind"] == "action_result" and "accounts" in r["changes"])
        target["changes"]["accounts"][0]["balance_cents"] += 1
        with self.assertRaises(ReplayMismatch):
            await replay(changed)
        changed = deepcopy(rows)
        next(r for r in changed if r["kind"] == "driver_reply")["reply"]["raw_output"] = encode_batch((Wait(),))
        with self.assertRaises(ReplayMismatch):
            await replay(changed)
        self.assertNotEqual(rows, runner.journal.records)  # Export is a copy.

    async def test_cancellation_is_terminal_and_cancels_outstanding_driver(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()

        class BlockingDriver(ScriptedDriver):
            async def decide(self, obs):
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        setup = make_setup()
        runner = make_runner(drivers={a.id: BlockingDriver() for a in (*setup.sellers, *setup.buyers)})
        task = asyncio.create_task(runner.run())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(cancelled.is_set())
        self.assertEqual(runner.phase, Phase.FAILED)
        self.assertEqual(runner.economic_state().events, ())


class AdmissionAndIdempotencyTests(unittest.TestCase):
    def test_batch_structural_and_role_failures_reject_entire_batch(self):
        cases = [
            ('{"actions":[]}', BUYER_ACTION, "ACTION_BUDGET"),
            (encode_batch((Wait(), Wait())), BUYER_ACTION, "WAIT_MUST_BE_ALONE"),
            (encode_batch((Purchase("seller/cup", 1, 300, 1), SendPublic("seller", "After"))), BUYER_ACTION, "PURCHASE_MUST_BE_SINGLE_AND_LAST"),
            (encode_batch((Purchase("seller/cup", 1, 300, 1), Purchase("seller/cup", 1, 300, 1))), BUYER_ACTION, "PURCHASE_MUST_BE_SINGLE_AND_LAST"),
            (encode_batch(tuple(SendPublic("seller", "Hi") for _ in range(3))), BUYER_ACTION, "MESSAGE_BUDGET"),
            (encode_batch((Procure("cup-offer", 1, 100),)), BUYER_ACTION, "ACTION_NOT_ALLOWED"),
            ('{"actions":[{"type":"wait","actor_id":"other-buyer"}]}', BUYER_ACTION, "INVALID_FIELDS"),
            ('{"actions":[{"type":"purchase","quantity":true}]}', BUYER_ACTION, "INVALID_FIELDS"),
            ('{"actions":[{"type":"purchase"}]}', BUYER_ACTION, "MISSING_FIELDS"),
            ('{"actions":[{"type":"wait","type":"wait"}]}', BUYER_ACTION, "DUPLICATE_JSON_KEY"),
            (encode_batch((CreateListing("other-seller/x", "cup", 300, "X"),)), SELLER_STRATEGY, "LISTING_NAMESPACE"),
            (encode_batch((CreateListing("seller/sub/x", "cup", 300, "X"),)), SELLER_STRATEGY, "LISTING_NAMESPACE"),
            (encode_batch((Procure("cup-offer", 1, 100), Procure("cup-offer", 1, 100))), PROCUREMENT, "ACTION_BUDGET"),
        ]
        for raw, wave, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(InvalidBatch, reason):
                parse_batch(raw, wave, "seller" if wave.role == "seller" else "buyer")

    def test_duplicate_concurrent_actions_and_failures_are_cached_conflicts_rejected(self):
        engine, journal = Engine(make_setup()), Journal()
        executor = ActionExecutor(engine, journal)
        context = WaveContext(1, 0, PROCUREMENT.name)
        action = Procure("cup-offer", 1, 100)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: executor.execute("id-1", "seller", context, action), range(20)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(len(engine.snapshot().procurements), 1)
        self.assertEqual(len(journal.records), 2)
        with self.assertRaises(IdempotencyConflict):
            executor.execute("id-1", "seller", context, Procure("cup-offer", 2, 100))
        with self.assertRaises(IdempotencyConflict):
            executor.execute("id-1", "other-seller", context, action)
        bad = Procure("missing", 1, 100)
        first = executor.execute("id-2", "seller", context, bad)
        self.assertFalse(first.ok)
        self.assertIs(executor.execute("id-2", "seller", context, bad), first)

    def test_configuration_rejects_unsupported_waves_and_invalid_runtime(self):
        for kwargs in ({"waves": (BUYER_ACTION, SELLER_STRATEGY)}, {"max_rounds": True}, {"resolution_seed": "1"},
                       {"waves": (replace(SELLER_STRATEGY, max_messages=4), BUYER_ACTION)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MarketConfig(**kwargs)
        with self.assertRaises(ValueError):
            RuntimeConfig(timeout_seconds=float("nan"))
        with self.assertRaises(ValueError):
            make_runner(setup=make_setup(steps_per_demo_day=2))

    def test_installed_cli_journal_replay_outside_repo(self):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "trace.json"
            first = subprocess.run([sys.executable, "-I", "-m", "salesbench_engine.runner.demo", "--journal", str(journal)],
                                   cwd=directory, env=env, text=True, capture_output=True, check=True, timeout=20)
            second = subprocess.run([sys.executable, "-I", "-m", "salesbench_engine.runner.demo", "--replay", str(journal)],
                                    cwd=directory, env=env, text=True, capture_output=True, check=True, timeout=20)
        a, b = json.loads(first.stdout), json.loads(second.stdout)
        self.assertFalse(a.pop("replay_verified"))
        self.assertTrue(b.pop("replay_verified"))
        self.assertEqual(a, b)
        self.assertEqual(a["step"], 2)
