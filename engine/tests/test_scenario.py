import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from salesbench_engine.scenario import run_demo


class ScenarioTests(unittest.TestCase):
    def test_complete_two_round_scenario_has_expected_economic_results(self):
        result = run_demo(7)
        self.assertEqual(result["checks"], "passed")
        self.assertEqual(result["step"], 1)
        self.assertEqual(result["cup_price_cents"], 300)
        self.assertEqual(result["balances_cents"], {"supplier": 800, "seller": 2250, "buyer": 950, "observer": 1000})
        self.assertEqual(result["inventory"], {"cup": 2, "bag": 1})
        self.assertEqual(result["counts"], {"procurements": 2, "listings": 2, "public_messages": 2, "private_messages": 2, "events": 14})

    def test_same_seed_reproduces_all_output_without_touching_global_rng(self):
        global_state = random.getstate()
        first = run_demo(7)
        self.assertEqual(first, run_demo(7))
        self.assertEqual(random.getstate(), global_state)
        self.assertNotEqual(first["cup_price_cents"], run_demo(42)["cup_price_cents"])

    def test_installed_cli_runs_outside_repo_without_site_platform_packages(self):
        # -I drops current-dir/PYTHONPATH imports. The engine must be installed.
        # Engine's own venv has no FastAPI/SQLAlchemy/HTTP clients.
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-I", "-m", "salesbench_engine.scenario", "--seed", "7"], cwd=directory, env=env, capture_output=True, text=True, check=True, timeout=20)
        self.assertEqual(json.loads(result.stdout), run_demo(7))
        self.assertEqual(result.stderr, "")

    def test_engine_source_imports_only_standard_library_and_its_own_package(self):
        import ast
        import salesbench_engine

        root = Path(salesbench_engine.__file__).parent
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                for name in names:
                    self.assertIn(name, sys.stdlib_module_names | {"salesbench_engine"}, f"Platform dependency in {path.name}")
