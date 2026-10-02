from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "monotone_core_check.py"


class MonotoneCoreCheckTests(unittest.TestCase):
    def test_independent_imports(self):
        tree = ast.parse(SCRIPT.read_text())
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules += [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module.split(".")[0])
        self.assertTrue(
            set(modules) <= {"__future__", "argparse", "json", "pathlib"}
        )

    def test_all_monotone_predicates_and_executed_negative_control(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.json"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--max-atoms",
                    "4",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(output.read_text())
            self.assertNotIn("schema_version", data)
            self.assertEqual(data["status"], "PASS")
            self.assertEqual(data["totals"]["counterexamples"], 0)
            self.assertGreaterEqual(data["totals"]["upward_predicates"], 168)

            control = data["negative_control"]
            self.assertTrue(control["passed"])
            overwrite = control["executed_overwrite_state_machine"]
            self.assertFalse(overwrite["upward_closed"])
            self.assertEqual(overwrite["sufficient_set_intersection"], "{}")
            self.assertEqual(overwrite["deletion_core"], "{b}")
            self.assertTrue(overwrite["deletion_core_sufficient"])
            self.assertEqual(overwrite["minimal_sufficient_sets"], ["{}"])
            self.assertTrue(overwrite["theorem_failure_observed"])

            restored = control["restored_monotone_positive_control"]
            self.assertTrue(restored["upward_closed"])
            self.assertEqual(restored["sufficient_set_intersection"], "{a}")
            self.assertEqual(restored["deletion_core"], "{a}")
            self.assertEqual(restored["minimal_sufficient_sets"], ["{a}"])
            self.assertTrue(restored["principal_filter"])
            self.assertTrue(restored["positive_control_passed"])


if __name__ == "__main__":
    unittest.main()
