#!/usr/bin/env python3
"""Owned Boolean and finite-record query regression; no source frontend or timing.

Both algorithms receive the same principal-filter promise and Boolean oracle.
Only verification receives a proposed answer. No historical campaign is run.
"""
from __future__ import annotations

import argparse
import copy
import csv
import itertools
import json
import sys
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import checker
import producer


def require(condition, detail=None):
    """Keep workload execution and result validation enabled under Python -O."""
    if not condition:
        raise AssertionError(detail)


def subsets(universe):
    for bits in itertools.product((False, True), repeat=len(universe)):
        yield frozenset(a for a, selected in zip(universe, bits) if selected)


def identify(universe, query):
    """The d-query oracle identification algorithm, without extra core replay."""
    whole = frozenset(universe)
    return frozenset(a for a in universe if not query(whole - {a}))


def boolean_regression(max_atoms=6):
    cases = accepted = identification_queries = verification_queries = 0
    for d in range(max_atoms + 1):
        universe = [f"a{i}" for i in range(d)]
        for hidden in subsets(universe):
            discovery_calls = []

            def discover_query(selected):
                discovery_calls.append(selected)
                return hidden <= selected

            require(identify(universe, discover_query) == hidden)
            require(len(discovery_calls) == d)
            identification_queries += len(discovery_calls)
            for candidate in subsets(universe):
                calls = []

                def query(selected):
                    calls.append(selected)
                    return hidden <= selected

                decision = checker.verify_candidate_witness(
                    universe, sorted(candidate), query)
                require(decision == (candidate == hidden), (d, hidden, candidate))
                bound = d if len(candidate) == d else len(candidate) + 1
                require(len(calls) <= bound)
                if decision:
                    require(len(calls) == bound)
                    accepted += 1
                cases += 1
                verification_queries += len(calls)
    # Upward closure alone does not make candidate minimality into leastness.
    disjunction = lambda selected: bool(selected & {"x", "y"})
    require(checker.verify_candidate_witness(["x", "y"], ["x"], disjunction))
    require(checker.verify_candidate_witness(["x", "y"], ["y"], disjunction))
    return {"maximum_atoms": max_atoms, "support_candidate_pairs": cases,
            "accepted_exact_supports": accepted,
            "identification_queries_across_supports": identification_queries,
            "verification_queries_across_support_candidate_pairs": verification_queries,
            "decision_disagreements": 0, "query_bound_violations": 0,
            "upward_only_control_has_two_accepted_inclusion_minima": True}


def finite_pair(d, k):
    raw = {f"x{i:02d}": "F" for i in range(d)}
    raw["steady"] = "F"
    old = {"targets": [{"anchor": "a", "raw": raw}],
           "normalizer": {"p": list(raw)[:k] if k else ["steady"]},
           "rules": [{"id": "r", "family": "f", "requires": ["p"]}]}
    new = copy.deepcopy(old)
    new["targets"][0]["raw"].update({f"x{i:02d}": "T" for i in range(d)})
    return old, new


def measured_check(api, old, new, certificate):
    # Count calls, not elapsed time or a formula substituted for measurements.
    with mock.patch.object(checker, "_patch", wraps=checker._patch) as patches:
        with mock.patch.object(checker, "_family_result",
                               wraps=checker._family_result) as evaluations:
            decision = api(old, new, certificate, 64)
            require(decision == (True, "accepted"), decision)
            return patches.call_count, evaluations.call_count


def finite_regression():
    rows = []
    for d in (16, 32, 64):
        for k in (0, 1, d // 2, d):
            old, new = finite_pair(d, k)
            snapshot = copy.deepcopy((old, new))
            certificate = producer.make_certificate(old, new, "f", "a", 64)
            require(len(certificate["delta"]) == d)
            require(len(certificate["witness"]) == k)
            discovery, discovery_evals = measured_check(
                checker.check_certificate, old, new, certificate)
            verification, verification_evals = measured_check(
                checker.check_candidate_certificate, old, new, certificate)
            require(discovery == d + 1)
            require(verification == (d if k == d else k + 1))
            require(discovery_evals == discovery + 2)  # same two admitted endpoints
            require(verification_evals == verification + 2)
            require((old, new) == snapshot)
            rows.append({"delta_atoms": d, "support_atoms": k,
                         "identification_checker_hybrid_replays": discovery,
                         "candidate_verifier_hybrid_replays": verification,
                         "identification_checker_evidence_evaluations": discovery_evals,
                         "candidate_verifier_evidence_evaluations": verification_evals,
                         "both_accept": True})
    return rows


def run(output):
    if output.exists():
        raise ValueError("output directory must not exist")
    boolean = boolean_regression()
    rows = finite_regression()
    output.mkdir(parents=True, exist_ok=False)
    with (output / "finite_query_counts.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = {"promise": "Q(S) iff hidden support is a subset of S for both algorithms",
              "metric": "Boolean oracle calls and instrumented hybrid/evidence calls; no timing",
              "boolean": boolean, "finite_record_cases": len(rows),
              "finite_query_counts": rows,
              "input_boundary": "owned finite records; no native/source frontend"}
    (output / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(run(options.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
