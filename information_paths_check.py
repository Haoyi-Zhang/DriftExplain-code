"""Actual bounded same-input path comparison on owned finite records.

This executes neither a native contract nor an external analyzer. Structure
access, not a new minimal-set algorithm, permits the zero-hybrid baseline.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tests")]
sys.dont_write_bytecode = True
import checker
from candidate_query_check import finite_pair, boolean_regression, require
from check_prepared_support import cases, oracle


APIS = {"identify": checker.check_certificate,
        "candidate": checker.check_candidate_certificate,
        "structure": checker.check_structural_certificate}


def measured(api, old, new, cert, bound=64):
    with mock.patch.object(checker, "_changes", wraps=checker._changes) as delta:
        with mock.patch.object(checker, "_patch", wraps=checker._patch) as hybrids:
            with mock.patch.object(checker, "_family_result", wraps=checker._family_result) as evidence:
                decision = api(old, new, cert, bound)
                return {"decision": list(decision), "delta_reconstructions": delta.call_count,
                        "hybrid_replays": hybrids.call_count, "evidence_evaluations": evidence.call_count}


def run(output):
    if output.exists(): raise ValueError("output directory must not exist")
    started = datetime.now(timezone.utc).isoformat()
    records = []
    proposed_count = 0
    for name, old, new, family, anchor in cases():
        cert, sufficient = oracle(old, new, family, anchor)
        results = {name: measured(api, old, new, cert) for name, api in APIS.items()}
        require(all(r["decision"] == [True, "accepted"] for r in results.values()))
        require(all(r["delta_reconstructions"] == 1 for r in results.values()))
        require(results["structure"]["hybrid_replays"] == 0)
        require(results["structure"]["evidence_evaluations"] == 2)
        proposals = []
        for mask in range(1 << len(cert["delta"])):
            proposed = copy.deepcopy(cert)
            proposed["witness"] = [atom for i, atom in enumerate(cert["delta"]) if mask & (1 << i)]
            outcomes = {name: list(api(old, new, proposed, 64)) for name, api in APIS.items()}
            expected = proposed["witness"] == cert["witness"]
            require(all(result[0] == expected for result in outcomes.values()))
            proposals.append({"witness": proposed["witness"], "literal_exact_support": expected,
                              "outcomes": outcomes})
        proposed_count += len(proposals)
        records.append({"id": name, "old": old, "new": new, "certificate": cert,
                        "literal_sufficient_subsets": sufficient, "measurements": results,
                        "proposals": proposals})
    # Same predeclared d/k combinations as the retained comparison, no tuning.
    from producer import make_certificate
    large = []
    for d in (16, 32, 64):
        for k in (0, 1, d // 2, d):
            old, new = finite_pair(d, k)
            cert = make_certificate(old, new, "f", "a", 64)
            results = {name: measured(api, old, new, cert) for name, api in APIS.items()}
            require(all(r["decision"] == [True, "accepted"] for r in results.values()))
            require(results["identify"]["hybrid_replays"] == d + 1)
            require(results["candidate"]["hybrid_replays"] == (d if k == d else k + 1))
            for name in ("identify", "candidate"):
                require(results[name]["evidence_evaluations"] == results[name]["hybrid_replays"] + 2)
            require(results["structure"]["hybrid_replays"] == 0)
            require(results["structure"]["evidence_evaluations"] == 2)
            large.append({"d": d, "k": k, "old": old, "new": new,
                          "certificate": cert, "measurements": results})
    bindings = []
    for path in [ROOT / "src/checker.py", ROOT / "src/producer.py",
                 ROOT / "candidate_query_check.py", ROOT / "information_paths_check.py",
                 ROOT / "tests/check_prepared_support.py", ROOT / "tests/check_information_paths.py"]:
        data = path.read_bytes()
        bindings.append({"path": path.relative_to(ROOT).as_posix(),
                         "sha256": hashlib.sha256(data).hexdigest()})
    report = {"status": "PASS", "scope": "Owned finite records, not source contracts; no timing or native execution",
              "small_pairs": len(records), "proposed_certificates": proposed_count,
              "decision_disagreements": 0, "large_pairs": len(large),
              "boolean": boolean_regression(), "small_records": records, "large_records": large,
              "structure_scope": "Same endpoints, candidate, full delta and reconstructed evidence; structure visible. Oracle lower bounds are not applicable to this path.",
              "native_execution": False, "source_frontend_execution": False,
              "environment": {"python": sys.version, "platform": platform.platform(),
                              "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
                              "command": "python -B information_paths_check.py --output NEW_DIRECTORY",
                              "source_bindings": bindings}}
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("status", "small_pairs", "proposed_certificates", "large_pairs", "decision_disagreements", "native_execution")}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args().output.resolve())
