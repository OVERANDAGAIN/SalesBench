"""Round/Tick/Wave coordinator. Economic arbitration stays in Engine.execute."""

import asyncio
from time import perf_counter
from typing import Mapping

from ..actions import Purchase
from ..environment import Engine
from ..models import MarketSetup, View
from .codec import InvalidBatch, action_data, digest, parse_batch
from .drivers import Driver, DriverReply
from .journal import ActionExecutor, ExecutionFault, Journal, source_digest
from .protocol import (
    ActionOutcome, AuthorizedState, Boundary, DecisionObservation, ENGINE_RULES_VERSION,
    MarketConfig, Phase, PROCUREMENT, PROTOCOL_VERSION, PublicSnapshot,
    RESOLVER_VERSION, Role, RuntimeConfig, WaveContext, WaveDefinition,
)


def priority(config: MarketConfig, context: WaveContext, purpose: str, actor_id: str) -> str:
    """No action ID, provider setting, wall time, Python hash, or arrival order."""
    return digest({"algorithm": RESOLVER_VERSION, "purpose": purpose,
                   "seed": config.resolution_seed, "design_id": config.design_id,
                   "round": context.round, "tick": context.tick, "wave": context.wave, "actor_id": actor_id})


class Runner:
    def __init__(self, setup: MarketSetup, drivers: Mapping[str, Driver], *,
                 config: MarketConfig = MarketConfig(), runtime: RuntimeConfig = RuntimeConfig()):
        if setup.experiment.steps_per_demo_day is not None:
            raise ValueError("Runner rounds have no demo-day mapping")
        if not setup.sellers or not setup.buyers:
            raise ValueError("Runner requires Sellers and Buyers")
        expected = {a.id for a in (*setup.sellers, *setup.buyers)}
        if set(drivers) != expected:
            raise ValueError("Exactly one driver per Seller/Buyer is required")
        self.config = config
        self.runtime = runtime
        self.phase = Phase.CREATED
        self.context: WaveContext | None = None
        self._setup = setup
        self._engine = Engine(setup)
        self._drivers = dict(drivers)
        self.journal = Journal()
        self._executor = ActionExecutor(self._engine, self.journal)
        self._feedback = {actor: () for actor in sorted(expected)}
        self._version = -1
        self._published: dict[str, AuthorizedState] = {}
        self._supply = {}
        self._busy = False
        self._cursor = 0
        self._round_start = None
        self._plan = tuple(self._boundaries())
        self.journal.append("manifest", protocol=PROTOCOL_VERSION, resolver=RESOLVER_VERSION,
                            engine_rules=ENGINE_RULES_VERSION, source_digest=source_digest(),
                            setup=setup, market_config=config, runtime_config=runtime,
                            drivers={actor: self._drivers[actor].configuration() for actor in sorted(expected)})
        self._publish("initial")

    def _boundaries(self):
        for round_number in range(1, self.config.max_rounds + 1):
            yield Boundary(WaveContext(round_number, 0, PROCUREMENT.name), PROCUREMENT)
            for tick in range(1, self.config.ticks_per_round + 1):
                for wave in self.config.waves:
                    yield Boundary(WaveContext(round_number, tick, wave.name), wave)
            yield Boundary(WaveContext(round_number, self.config.ticks_per_round, self.config.waves[-1].name), None)

    @property
    def published_version(self) -> int:
        return self._version

    @property
    def next_boundary(self) -> Boundary | None:
        if self.phase in (Phase.COMPLETED, Phase.FAILED):
            return None
        return self._plan[self._cursor]

    def pending_observations(self) -> dict[str, DecisionObservation]:
        """Prepare the next opportunity from the last publication, without running it."""
        if self._busy:
            raise RuntimeError("Cannot prepare a boundary while Runner is executing")
        boundary = self.next_boundary
        if boundary is None or boundary.wave is None:
            return {}
        roster = self._setup.sellers if boundary.wave.role == Role.SELLER else self._setup.buyers
        return {actor.id: self._decision(actor.id, boundary.wave, boundary.context)
                for actor in sorted(roster, key=lambda a: a.id)}

    def observe(self, actor_id: str) -> AuthorizedState:
        """Last completely published state only, including while a Wave commits."""
        return self._published[actor_id]

    def economic_state(self):
        """Trusted host audit export; do not give this object/method to drivers."""
        return self._engine.snapshot()

    def _publish(self, boundary: str):
        version = self._version + 1
        first = next(iter(self._feedback))
        market = self._engine.observe(first)
        public = PublicSnapshot(version, market.time, self._setup.sellers, market.listings,
                                self._engine.observe(first, View.PUBLIC).messages)
        published = {actor: AuthorizedState(
            public, self._engine.observe(actor, View.SELF), self._engine.observe(actor, View.PRIVATE),
            self._feedback[actor],
        ) for actor in self._feedback}
        supply = {seller.id: self._engine.observe(seller.id, View.SUPPLIERS) for seller in self._setup.sellers}
        self.journal.append("published", context=self.context, boundary=boundary, version=version,
                            public=public, state_digest=digest(self._engine.snapshot()))
        # One reference swap: no actor can observe an incremental projection.
        self._published = published
        self._supply = supply
        self._version = version

    def _phase(self, phase: Phase):
        self.phase = phase
        self.journal.append("phase", phase=phase, context=self.context)

    def _ordered(self, actors, purpose: str):
        order = sorted(actors, key=lambda actor: (priority(self.config, self.context, purpose, actor), actor))
        self.journal.append("resolution", context=self.context, purpose=purpose,
                            order=order, priorities={actor: priority(self.config, self.context, purpose, actor) for actor in order})
        return order

    def _decision(self, actor: str, wave: WaveDefinition, context: WaveContext | None = None) -> DecisionObservation:
        context = context or self.context
        opportunity = digest({"design_id": self.config.design_id, "experiment_id": self._setup.experiment.id,
                              "context": context, "actor_id": actor})
        return DecisionObservation(context, opportunity, wave, self._published[actor],
                                   self._supply[actor] if wave == PROCUREMENT else None)

    async def _collect(self, observations):
        semaphore = asyncio.Semaphore(self.runtime.concurrency)

        async def invoke(actor, observation):
            async with semaphore:
                start = perf_counter()
                try:
                    async with asyncio.timeout(self.runtime.timeout_seconds):
                        reply = await self._drivers[actor].decide(observation)
                    if not isinstance(reply, DriverReply):
                        raise TypeError("Driver must return DriverReply")
                except TimeoutError:
                    reply = DriverReply(error="DRIVER_TIMEOUT")
                except Exception as error:
                    # Arbitrary exception messages may contain credentials/HTTP payloads.
                    reply = DriverReply(error=f"DRIVER_ERROR:{type(error).__name__}")
                return actor, reply, perf_counter() - start

        tasks = [asyncio.create_task(invoke(actor, obs)) for actor, obs in observations.items()]
        try:
            collected = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        replies = {}
        for actor, reply, elapsed in sorted(collected):
            replies[actor] = reply
            self.journal.append("driver_reply", context=self.context, actor_id=actor,
                                opportunity_id=observations[actor].opportunity_id, reply=reply, elapsed_seconds=elapsed)
        return replies

    async def _wave(self, wave: WaveDefinition):
        self._phase(Phase.COLLECTING)
        roster = self._setup.sellers if wave.role == Role.SELLER else self._setup.buyers
        observations = {actor.id: self._decision(actor.id, wave) for actor in sorted(roster, key=lambda a: a.id)}
        for actor, observation in observations.items():
            self.journal.append("observation", actor_id=actor, observation=observation)
        replies = await self._collect(observations)
        failures = {actor: reply.error for actor, reply in replies.items() if reply.error is not None}
        if failures:
            self.journal.append("collection_failed", context=self.context, failures=failures)
            raise ExecutionFault("", "WAVE_COLLECTION_FAILED")
        batches = {}
        outcomes = {actor: [] for actor in observations}
        for actor, reply in replies.items():
            try:
                batches[actor] = parse_batch(reply.raw_output, wave, actor)
                self.journal.append("admission", context=self.context, actor_id=actor, status="accepted",
                                    actions=[{"action_id": f"{observations[actor].opportunity_id}:{i}", "action": action_data(action)}
                                             for i, action in enumerate(batches[actor])])
            except InvalidBatch as error:
                outcomes[actor].append(ActionOutcome(observations[actor].opportunity_id, "invalid_batch", str(error)))
                self.journal.append("admission", context=self.context, actor_id=actor, status="invalid_batch", reason=str(error))
        self._phase(Phase.EXECUTING)

        def execute_at(actor, index):
            action_id = f"{observations[actor].opportunity_id}:{index}"
            result = self._executor.execute(action_id, actor, self.context, batches[actor][index])
            outcomes[actor].append(ActionOutcome(action_id, "succeeded" if result.ok else "business_failed", result=result))
            if not result.ok:
                for rest in range(index + 1, len(batches[actor])):
                    skipped = ActionOutcome(f"{observations[actor].opportunity_id}:{rest}", "skipped", f"PRIOR_BUSINESS_FAILURE:{action_id}:{result.code}")
                    outcomes[actor].append(skipped)
                    self.journal.append("skipped", context=self.context, actor_id=actor, outcome=skipped)
            return result.ok

        pending_purchases = {}
        purpose = "procurement" if wave == PROCUREMENT else ("buyer_messages" if wave.role == Role.BUYER else "seller_actions")
        for actor in self._ordered(batches, purpose):
            for index, action in enumerate(batches[actor]):
                if isinstance(action, Purchase):
                    pending_purchases[actor] = index
                elif not execute_at(actor, index):
                    break
        if wave.max_purchases:
            # A SINGLE global order resolves shared stock across different listings.
            for actor in self._ordered(pending_purchases, "purchase"):
                execute_at(actor, pending_purchases[actor])
        for actor in observations:
            self._feedback[actor] = tuple(outcomes[actor])
            self.journal.append("opportunity_result", context=self.context, actor_id=actor, outcomes=outcomes[actor])
        self._phase(Phase.PUBLISHING)
        self._publish("wave_completed")

    async def run(self):
        if self.phase != Phase.CREATED or self._busy:
            raise RuntimeError("Runner is single-use; replay into a fresh Runner")
        while self.phase not in (Phase.COMPLETED, Phase.FAILED):
            await self.advance_boundary()
        return self.economic_state()

    async def advance_boundary(self):
        """Run one existing Wave or Round close, for a trusted transactional host.

        This computes a candidate in memory, NOT a durable commit. A platform
        must discard this instance on commit failure and restore its transcript.
        """
        if self._busy or self.phase in (Phase.COMPLETED, Phase.FAILED):
            raise RuntimeError("No runnable boundary or Runner already executing")
        self._busy = True
        try:
            boundary = self._plan[self._cursor]
            self.context = boundary.context
            if boundary.wave is not None:
                if boundary.wave == PROCUREMENT:
                    self._round_start = self._engine.snapshot()
                await self._wave(boundary.wave)
            else:
                self._phase(Phase.CLOSING_ROUND)
                result = self._engine.advance(1)
                round_end = self._engine.snapshot()
                new_orders = round_end.orders[len(self._round_start.orders):]
                self.journal.append("round_closed", round=self.context.round, result=result,
                                    statistics={"order_count": len(new_orders), "units_sold": sum(o.quantity for o in new_orders),
                                                "gross_sales_cents": sum(o.total_cents for o in new_orders),
                                                "procurement_count": len(round_end.procurements) - len(self._round_start.procurements)},
                                    state_digest=digest(round_end))
                self._publish("round_closed")
            self._cursor += 1
            if self._cursor == len(self._plan):
                self._phase(Phase.COMPLETED)
        except asyncio.CancelledError:
            self._fail("RUN_CANCELLED")
            raise
        except ExecutionFault as error:
            self._fail(error.code, error.action_id)
        except Exception as error:
            self._fail(f"RUNNER_ERROR:{type(error).__name__}")
        finally:
            self._busy = False
        return self.economic_state()

    def _fail(self, code, action_id=None):
        failed_phase = self.phase
        self._phase(Phase.FAILED)
        self.journal.append("aborted", context=self.context, code=code, action_id=action_id,
                            failed_phase=failed_phase, published_version=self._version,
                            state_digest=digest(self._engine.snapshot()))
