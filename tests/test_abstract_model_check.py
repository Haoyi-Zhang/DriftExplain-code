from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "abstract_model_check.py"


class AbstractModelCheckTests(unittest.TestCase):
    def test_model_checker_has_no_project_imports(self):
        tree = ast.parse(SCRIPT.read_text())
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module.split(".")[0])
        self.assertTrue(
            set(imported)
            <= {"__future__", "itertools", "argparse", "json", "pathlib", "typing"}
        )

    def test_bounded_model_check_and_executed_negative_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.json"
            subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            data = json.loads(output.read_text())
            self.assertEqual(data["status"], "PASS")
            self.assertEqual(data["configuration"]["selector_domain_sizes"], [2, 3])
            self.assertEqual(
                data["configuration"]["endpoint_pair_scope"],
                "ordered non-identical endpoint pairs",
            )
            self.assertEqual(data["totals"]["counterexamples"], 0)
            self.assertGreater(data["totals"]["subset_replays"], 1000)
            self.assertTrue(data["negative_controls_passed"])

            controls = data["negative_controls"]
            hidden = controls[
                "hidden_visibility_breaks_structural_identification"
            ]
            self.assertTrue(hidden["empty_patch"]["actual_sufficient"])
            self.assertFalse(hidden["empty_patch"]["predicted_sufficient"])
            self.assertTrue(
                hidden["empty_patch"]["structural_equivalence_violated"]
            )
            self.assertTrue(
                hidden["restored_complete_evidence"]["all_subsets_agree"]
            )

            unstable = controls[
                "unstable_identity_breaks_coordinate_correspondence"
            ]
            self.assertTrue(
                unstable["unstable_positional_views"]["failure_observed"]
            )
            self.assertEqual(
                unstable["restored_stable_identity"]["changed_identities"],
                ["x", "y"],
            )
            self.assertFalse(
                unstable["restored_stable_identity"]["empty_patch_reaches_new"]
            )
            self.assertTrue(
                unstable["restored_stable_identity"]["full_patch_reaches_new"]
            )
            self.assertTrue(
                unstable["restored_stable_identity"]["positive_control_passed"]
            )

            value_only = controls["value_only_incomparable_minima"]
            self.assertEqual(
                value_only["incomparable_minimal_sufficient_sets"],
                [["a"], ["b"]],
            )
            overlap = controls["overlapping_write_breaks_upward_closure"]
            self.assertTrue(overlap["upward_closure_violation_observed"])
            self.assertTrue(
                overlap["restored_disjoint_endpoint_blocks"][
                    "upward_principal_filter_restored"
                ]
            )


if __name__ == "__main__":
    unittest.main()
