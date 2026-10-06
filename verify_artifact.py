#!/usr/bin/env python3
"""Run the complete finite-artifact verification in an isolated temporary copy.

Every deterministic checker writes to a fresh path outside the copied artifact.
The verifier requires each fresh file to exist, parses that file, and compares it
byte-for-byte and structurally with the frozen result shipped in the artifact.
No result is accepted merely because a copied frozen JSON file already exists.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

FORBIDDEN_RESULT_FIELDS = frozenset({"schema_version"})


def run(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    display_command: Iterable[str] | None = None,
    timeout_seconds: float = 120,
) -> dict[str, Any]:
    started = time.perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            command, cwd=cwd, env=env, text=True, encoding="utf-8",
            errors="replace", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False, timeout=timeout_seconds,
        )
        exit_status, output = completed.returncode, completed.stdout
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_status = 124
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output += f"\nVerification step exceeded {timeout_seconds:g} seconds.\n"
    shown = list(display_command) if display_command is not None else command
    if shown:
        shown = ["python", *shown[1:]]
    return {
        "command": " ".join(shown),
        "exit_status": exit_status,
        "output": output,
        "timed_out": timed_out,
        "wall_seconds": time.perf_counter() - started,
    }


def load_json(path: Path) -> tuple[Any | None, str | None]:
    if not path.is_file():
        return None, "missing file"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def forbidden_top_level_fields(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    return sorted(FORBIDDEN_RESULT_FIELDS.intersection(value))


def compare_generated_result(generated: Path, frozen: Path) -> dict[str, Any]:
    """Compare one newly generated JSON result with its frozen counterpart.

    The comparison is intentionally strict. A missing output, invalid JSON,
    forbidden top-level metadata, changed field, or formatting difference fails.
    """

    generated_value, generated_error = load_json(generated)
    frozen_value, frozen_error = load_json(frozen)
    generated_forbidden = forbidden_top_level_fields(generated_value)
    frozen_forbidden = forbidden_top_level_fields(frozen_value)
    semantic_equal = (
        generated_error is None
        and frozen_error is None
        and generated_value == frozen_value
    )
    byte_equal = False
    if generated_error is None and frozen_error is None:
        try:
            byte_equal = generated.read_bytes() == frozen.read_bytes()
        except OSError:
            byte_equal = False
    passed = (
        generated_error is None
        and frozen_error is None
        and not generated_forbidden
        and not frozen_forbidden
        and semantic_equal
        and byte_equal
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "generated_exists": generated.is_file(),
        "frozen_exists": frozen.is_file(),
        "generated_parse_error": generated_error,
        "frozen_parse_error": frozen_error,
        "forbidden_generated_fields": generated_forbidden,
        "forbidden_frozen_fields": frozen_forbidden,
        "semantic_equal": semantic_equal,
        "byte_equal": byte_equal,
    }


def regenerate_result(
    *,
    name: str,
    script: str,
    frozen_relative: str,
    extra_args: list[str],
    copy_root: Path,
    source_root: Path,
    generated_root: Path,
    env: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any], Any | None]:
    generated_path = generated_root / Path(frozen_relative).name
    if generated_path.exists():
        raise ValueError(f"fresh result path already exists: {generated_path}")
    command = [
        sys.executable,
        script,
        *extra_args,
        "--output",
        str(generated_path),
    ]
    display = [
        sys.executable,
        script,
        *extra_args,
        "--output",
        f"<isolated-output>/{generated_path.name}",
    ]
    execution = run(command, copy_root, env, display)
    comparison = compare_generated_result(
        generated_path, source_root / frozen_relative
    )
    generated_value, _ = load_json(generated_path)
    execution["fresh_output"] = comparison
    return execution, comparison, generated_value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--work-dir", type=Path,
                        help="new directory outside the artifact; retained with raw evidence")
    args = parser.parse_args()

    requested = args.root.resolve()
    source = requested / "artifact" if (requested / "artifact").is_dir() else requested
    output = args.output or (source / "results" / "one_command_verification.json")

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONUTF8"] = "1"

    if args.work_dir is not None:
        work = args.work_dir.resolve()
        if work == source or source in work.parents:
            parser.error("--work-dir must be outside the artifact")
        work.mkdir(parents=True, exist_ok=False)
    else:
        work = Path(tempfile.mkdtemp(prefix="artifact-verify-"))
    # Retain the isolated copy and regenerated results on success and failure.
    # Raw diagnostics must survive a failed gate; no tree is removed here.
    with nullcontext(work) as temporary:
        temporary_root = Path(temporary)
        copy_root = temporary_root / "artifact"
        generated_root = temporary_root / "regenerated"
        generated_root.mkdir(parents=True)
        shutil.copytree(source, copy_root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))

        raw_root = temporary_root / "raw"
        raw_root.mkdir()

        def retain(name: str, execution: dict[str, Any]) -> None:
            (raw_root / f"{name}.txt").write_text(execution["output"], encoding="utf-8")

        executions: dict[str, dict[str, Any]] = {}
        executions["unit_tests"] = run(
            [sys.executable, "run_tests.py"], copy_root, env
        )
        retain("unit_tests", executions["unit_tests"])

        deterministic_specs = [
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
            (
                "generated_differential",
                "generated_differential_check.py",
                "results/generated_differential_check.json",
                [],
            ),
        ]
        comparisons: dict[str, dict[str, Any]] = {}
        generated_values: dict[str, Any] = {}
        for name, script, relative, extra in deterministic_specs:
            execution, comparison, value = regenerate_result(
                name=name,
                script=script,
                frozen_relative=relative,
                extra_args=extra,
                copy_root=copy_root,
                source_root=source,
                generated_root=generated_root,
                env=env,
            )
            executions[name] = execution
            retain(name, execution)
            comparisons[relative] = comparison
            generated_values[name] = value

        audit_output = generated_root / "static_consistency.json"
        audit_execution = run(
            [
                sys.executable,
                "audit_static.py",
                "--root",
                ".",
                "--output",
                str(audit_output),
            ],
            copy_root,
            env,
            [
                sys.executable,
                "audit_static.py",
                "--root",
                ".",
                "--output",
                "<isolated-output>/static_consistency.json",
            ],
        )
        audit, audit_error = load_json(audit_output)
        audit_execution["fresh_output"] = {
            "status": "PASS"
            if audit_error is None and isinstance(audit, dict)
            else "FAIL",
            "generated_exists": audit_output.is_file(),
            "generated_parse_error": audit_error,
        }
        executions["static_audit"] = audit_execution
        retain("static_audit", audit_execution)
        audit = audit or {}
        generated = generated_values.get("generated_differential") or {}
        abstract = generated_values.get("abstract_model") or {}
        monotone = generated_values.get("monotone_core") or {}
        residue = sorted(
            str(path.relative_to(copy_root))
            for path in copy_root.rglob("*")
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}
        )

        unit_output = executions["unit_tests"].get("output", "")
        unit_match = re.search(r"Ran\s+(\d+)\s+tests?", unit_output)
        current_unit_tests = int(unit_match.group(1)) if unit_match else None

        status = (
            all(step["exit_status"] == 0 for step in executions.values())
            and all(item["status"] == "PASS" for item in comparisons.values())
            and audit.get("summary", {}).get("status") == "PASS"
            and generated.get("status") == "PASS"
            and abstract.get("status") == "PASS"
            and monotone.get("status") == "PASS"
            and current_unit_tests is not None
            and not residue
        )

        report = {
            "status": "PASS" if status else "FAIL",
            "scope": (
                "isolated-copy unit tests; fresh-output finite checks; strict "
                "frozen-result comparison; fresh static audit; residue verification"
            ),
            "executions": {
                name: {
                    "command": value["command"],
                    "exit_status": value["exit_status"],
                    "timed_out": value["timed_out"],
                    "wall_seconds": value["wall_seconds"],
                    "raw_output": f"raw/{name}.txt",
                }
                for name, value in executions.items()
            },
            "fresh_result_comparisons": comparisons,
            "current_unit_tests": current_unit_tests,
            "finite_check_totals_from_fresh_outputs": {
                "abstract_endpoint_pairs": abstract.get("totals", {}).get(
                    "endpoint_pairs"
                ),
                "abstract_atom_partitions": abstract.get("totals", {}).get(
                    "atom_partitions"
                ),
                "abstract_subset_replays": abstract.get("totals", {}).get(
                    "subset_replays"
                ),
                "monotone_predicates": monotone.get("totals", {}).get(
                    "all_predicates_examined"
                ),
                "monotone_theorem_checks": monotone.get("totals", {}).get(
                    "theorem_checks"
                ),
                "generated_endpoint_pairs": generated.get("totals", {}).get(
                    "generated_endpoint_pairs"
                ),
                "generated_subset_replays": generated.get("totals", {}).get(
                    "subset_replays"
                ),
            },
            "static_audit_from_fresh_output": audit.get("summary", {}),
            "bytecode_or_cache_residue": residue,
            "retained_work_directory": str(temporary_root),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
