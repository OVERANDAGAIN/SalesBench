import json
import unittest

from salesbench_engine.actions import Wait
from salesbench_engine.runner import LLMDriver, ModelResponse, ModelSettings, Phase, ScriptedDriver
from salesbench_engine.runner.codec import encode_batch
from salesbench_engine.runner.protocol import BUYER_ACTION
from test_runner import make_runner, market_script


class DriverTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_request_contains_authorized_snapshot_schema_and_limits(self):
        seen = []

        class FakeAdapter:
            def count_input_tokens(self, request):
                seen.append(request)
                return 120

            async def generate(self, request):
                self_request = json.loads(request.user)
                assert set(self_request) == {"observation", "action_schema"}
                return ModelResponse(encode_batch((Wait(),)), "fake-model-revision", 120, 9)

        settings = ModelSettings("test-provider", "test-model", 200, 20, 0.2)
        driver = LLMDriver(FakeAdapter(), settings)
        runner = make_runner(drivers={"seller": ScriptedDriver(market_script), "other-seller": ScriptedDriver(market_script),
                                      "buyer": driver, "other-buyer": ScriptedDriver()})
        await runner.run()
        self.assertEqual(runner.phase, Phase.COMPLETED)
        self.assertEqual(len(seen), 1)
        request = seen[0]
        self.assertEqual(request.settings, settings)
        payload = json.loads(request.user)
        own = payload["observation"]["state"]["own"]
        self.assertEqual(own["account"]["actor_id"], "buyer")
        self.assertEqual(own["offers"], [])
        self.assertEqual(own["inventory"], [])
        self.assertIsNone(payload["observation"]["procurement"])
        self.assertEqual(set(payload["action_schema"]), set(BUYER_ACTION.allowed_actions))
        self.assertIn("expected_offer_revision", payload["action_schema"]["purchase"])
        row = next(r for r in runner.journal.records if r["kind"] == "driver_reply" and r["actor_id"] == "buyer")
        self.assertEqual(row["reply"]["input_tokens"], 120)
        self.assertEqual(row["reply"]["output_tokens"], 9)
        self.assertEqual(row["reply"]["model_version"], "fake-model-revision")

    async def test_input_and_output_token_budgets_fail_before_any_wave_commit(self):
        for fault in ("input", "output"):
            with self.subTest(fault=fault):
                calls = []

                class FakeAdapter:
                    def count_input_tokens(self, request):
                        return 201 if fault == "input" else 120

                    async def generate(self, request):
                        calls.append(request)
                        return ModelResponse(encode_batch((Wait(),)), output_tokens=21)

                driver = LLMDriver(FakeAdapter(), ModelSettings("test", "test", 200, 20))
                runner = make_runner(drivers={"seller": driver, "other-seller": ScriptedDriver(market_script),
                                              "buyer": ScriptedDriver(), "other-buyer": ScriptedDriver()})
                await runner.run()
                self.assertEqual(runner.phase, Phase.FAILED)
                self.assertEqual(runner.economic_state().events, ())
                self.assertEqual(len(calls), 0 if fault == "input" else 1)
                reply = next(r["reply"] for r in runner.journal.records if r["kind"] == "driver_reply" and r["actor_id"] == "seller")
                self.assertEqual(reply["error"], fault.upper() + "_TOKEN_BUDGET")

    async def test_malformed_model_output_is_audited_invalid_batch_not_wait_or_technical_failure(self):
        class FakeAdapter:
            def count_input_tokens(self, request):
                return 100

            async def generate(self, request):
                return ModelResponse("I choose to buy, but this is not JSON.", output_tokens=12)

        runner = make_runner(drivers={"seller": ScriptedDriver(market_script), "other-seller": ScriptedDriver(market_script),
                                      "buyer": LLMDriver(FakeAdapter(), ModelSettings("fake", "fake")),
                                      "other-buyer": ScriptedDriver()})
        await runner.run()
        self.assertEqual(runner.phase, Phase.COMPLETED)
        self.assertEqual(runner.observe("buyer").previous_outcomes[0].reason, "INVALID_JSON")
        self.assertFalse(any(e.actor_id == "buyer" and e.kind == "waited" for e in runner.economic_state().events))
        reply = next(r["reply"] for r in runner.journal.records if r["kind"] == "driver_reply" and r["actor_id"] == "buyer")
        self.assertEqual(reply["raw_output"], "I choose to buy, but this is not JSON.")
