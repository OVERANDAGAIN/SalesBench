import unittest

from salesbench_engine.actions import Procure, SendPrivate, Wait
from salesbench_engine.models import View
from salesbench_engine.policies import ScriptedDecision, ScriptedPolicy
from test_transitions import stocked_engine


class PolicyTests(unittest.TestCase):
    def test_delayed_reply_uses_engine_step_and_cannot_mutate_engine_on_decide(self):
        engine = stocked_engine()
        engine.execute("buyer", SendPrivate("seller", "A question"))
        policy = ScriptedPolicy((ScriptedDecision(1, SendPrivate("buyer", "Scripted reply")),))
        observation = engine.observe("seller", View.PRIVATE)
        before = engine.snapshot()
        self.assertIsInstance(policy.decide(observation), Wait)
        self.assertEqual(engine.snapshot(), before)
        engine.advance()
        before = engine.snapshot()
        action = policy.decide(engine.observe("seller", View.PRIVATE))
        self.assertEqual(engine.snapshot(), before)
        self.assertTrue(engine.execute("seller", action).ok)
        messages = engine.observe("buyer", View.PRIVATE).messages
        self.assertEqual([m.step for m in messages], [0, 1])
        self.assertIsInstance(policy.decide(engine.observe("seller")), Wait)

    def test_policy_proposals_do_not_bypass_engine_role_checks(self):
        engine = stocked_engine()
        policy = ScriptedPolicy((ScriptedDecision(0, Procure("cup-offer", 1, 100)),))
        before = engine.snapshot()
        result = engine.execute("buyer", policy.decide(engine.observe("buyer")))
        self.assertEqual(result.code, "FORBIDDEN")
        self.assertEqual(engine.snapshot(), before)

    def test_supplier_uses_the_same_policy_contract_with_own_observation(self):
        engine = stocked_engine()
        policy = ScriptedPolicy((ScriptedDecision(0, Wait()),))
        observation = engine.observe("supplier", View.SELF)
        self.assertEqual(len(observation.offers), 2)
        self.assertTrue(engine.execute("supplier", policy.decide(observation)).ok)

    def test_misordered_or_invalid_script_steps_are_rejected(self):
        for decisions in (
            (ScriptedDecision(2, Wait()), ScriptedDecision(1, Wait())),
            (ScriptedDecision(-1, Wait()),),
            (ScriptedDecision(True, Wait()),),
        ):
            with self.subTest(decisions=decisions), self.assertRaises(ValueError):
                ScriptedPolicy(decisions)
