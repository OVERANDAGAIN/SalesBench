from copy import deepcopy
import unittest

from salesbench_engine.runner import Phase, ScriptedDriver
from salesbench_engine.runner.recovery import restore_committed
from salesbench_engine.runner.replay import ReplayMismatch, logical_records
from test_runner import make_runner, market_script


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_committed_boundary_recovers_and_continues_identical_protocol(self):
        direct = make_runner()
        await direct.run()
        stepped = make_runner()
        while stepped.phase != Phase.COMPLETED:
            before = stepped.journal.records
            opportunities = stepped.pending_observations()
            self.assertEqual(stepped.journal.records, before)
            restored = await restore_committed(before, {a: ScriptedDriver(market_script) for a in stepped._drivers})
            self.assertEqual(restored.pending_observations(), opportunities)
            self.assertEqual(restored.economic_state(), stepped.economic_state())
            self.assertEqual(restored.journal.records, before)
            await restored.advance_boundary()
            stepped = restored
        self.assertEqual(stepped.economic_state(), direct.economic_state())
        self.assertEqual(logical_records(stepped.journal.records), logical_records(direct.journal.records))
        restored = await restore_committed(stepped.journal.records, stepped._drivers)
        self.assertEqual(restored.phase, Phase.COMPLETED)

    async def test_recovery_rejects_uncommitted_suffix_source_mismatch_and_tamper(self):
        runner = make_runner()
        await runner.advance_boundary()
        trace = runner.journal.records
        cases = [trace[:-1], deepcopy(trace), deepcopy(trace)]
        cases[1][0]["source_digest"] = "another-code-version"
        next(r for r in cases[2] if r["kind"] == "action_result")["result"]["ok"] = False
        for bad in cases:
            with self.subTest(length=len(bad)), self.assertRaises(ReplayMismatch):
                await restore_committed(bad, runner._drivers)

    async def test_busy_or_terminal_runner_cannot_start_another_boundary(self):
        runner = make_runner()
        runner._busy = True
        with self.assertRaises(RuntimeError):
            await runner.advance_boundary()
        with self.assertRaises(RuntimeError):
            runner.pending_observations()
        runner._busy = False
        await runner.run()
        self.assertIsNone(runner.next_boundary)
        self.assertEqual(runner.pending_observations(), {})
        with self.assertRaises(RuntimeError):
            await runner.advance_boundary()
