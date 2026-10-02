from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "verify_artifact.py"
SPEC = importlib.util.spec_from_file_location("verify_artifact_module", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_toy_generator(path: Path, value, *, create_output: bool = True) -> None:
    body = """#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
"""
    if create_output:
        body += (
            "args.output.parent.mkdir(parents=True, exist_ok=True)\n"
            f"value = {value!r}\n"
            "args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + '\\n')\n"
        )
    body += "raise SystemExit(0)\n"
    path.write_text(body)


class VerificationChainTests(unittest.TestCase):
    def environment(self):
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONHASHSEED"] = "0"
        return environment

    def test_current_abstract_and_monotone_generators_write_fresh_matching_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            generated_root = Path(directory)
            specifications = [
                (
                    "abstract_model",
                    "abstract_model_check.py",
                    "results/abstract_model_check.json",
                    [],
                ),
                (
                    "monotone_core",
                    "monotone_core_check.py",
                    "results/monotone_core_check.json",
                    ["--max-atoms", "4"],
                ),
            ]
            for name, script, relative, extra in specifications:
                with self.subTest(name=name):
                    execution, comparison, value = VERIFY.regenerate_result(
                        name=name,
                        script=script,
                        frozen_relative=relative,
                        extra_args=extra,
                        copy_root=ROOT,
                        source_root=ROOT,
                        generated_root=generated_root,
                        env=self.environment(),
                    )
                    self.assertEqual(execution["exit_status"], 0)
                    self.assertEqual(comparison["status"], "PASS")
                    self.assertIsInstance(value, dict)
                    self.assertEqual(value["status"], "PASS")

    def test_missing_fresh_output_is_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_root = root / "copy"
            source_root = root / "source"
            generated_root = root / "generated"
            copy_root.mkdir()
            source_root.mkdir()
            generated_root.mkdir()
            write_toy_generator(copy_root / "toy.py", {"status": "PASS"}, create_output=False)
            write_json(source_root / "results" / "toy.json", {"status": "PASS"})
            execution, comparison, value = VERIFY.regenerate_result(
                name="missing",
                script="toy.py",
                frozen_relative="results/toy.json",
                extra_args=[],
                copy_root=copy_root,
                source_root=source_root,
                generated_root=generated_root,
                env=self.environment(),
            )
            self.assertEqual(execution["exit_status"], 0)
            self.assertIsNone(value)
            self.assertEqual(comparison["status"], "FAIL")
            self.assertFalse(comparison["generated_exists"])
            self.assertEqual(comparison["generated_parse_error"], "missing file")

    def test_changed_frozen_field_is_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_root = root / "copy"
            source_root = root / "source"
            generated_root = root / "generated"
            copy_root.mkdir()
            source_root.mkdir()
            generated_root.mkdir()
            write_toy_generator(
                copy_root / "toy.py",
                {"status": "PASS", "totals": {"cases": 7}},
            )
            write_json(
                source_root / "results" / "toy.json",
                {"status": "PASS", "totals": {"cases": 8}},
            )
            execution, comparison, _ = VERIFY.regenerate_result(
                name="changed-frozen",
                script="toy.py",
                frozen_relative="results/toy.json",
                extra_args=[],
                copy_root=copy_root,
                source_root=source_root,
                generated_root=generated_root,
                env=self.environment(),
            )
            self.assertEqual(execution["exit_status"], 0)
            self.assertEqual(comparison["status"], "FAIL")
            self.assertFalse(comparison["semantic_equal"])
            self.assertFalse(comparison["byte_equal"])

    def test_forbidden_format_conflict_is_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_root = root / "copy"
            source_root = root / "source"
            generated_root = root / "generated"
            copy_root.mkdir()
            source_root.mkdir()
            generated_root.mkdir()
            write_toy_generator(
                copy_root / "toy.py",
                {
                    "schema_version": 1,
                    "status": "PASS",
                    "totals": {"cases": 7},
                },
            )
            write_json(
                source_root / "results" / "toy.json",
                {"status": "PASS", "totals": {"cases": 7}},
            )
            execution, comparison, _ = VERIFY.regenerate_result(
                name="format-conflict",
                script="toy.py",
                frozen_relative="results/toy.json",
                extra_args=[],
                copy_root=copy_root,
                source_root=source_root,
                generated_root=generated_root,
                env=self.environment(),
            )
            self.assertEqual(execution["exit_status"], 0)
            self.assertEqual(comparison["status"], "FAIL")
            self.assertEqual(
                comparison["forbidden_generated_fields"], ["schema_version"]
            )


if __name__ == "__main__":
    unittest.main()
