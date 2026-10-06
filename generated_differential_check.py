#!/usr/bin/env python3
"""Deterministic generated differential and metamorphic checks.

The check does not fit parameters or estimate deployed accuracy.  It expands the
fixture surface with seeded finite endpoint pairs, compares the structural
producer with two exhaustive implementations on small deltas, and checks two
representation-preserving metamorphisms.  It uses only the Python standard
library and the delivered finite model.
"""
from __future__ import annotations

import argparse
import copy
from itertools import combinations
import json
from pathlib import Path
import random
from typing import Any, Iterable
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import checker
from generate import make_random_case
import producer

SEEDS = (3, 11, 29, 47, 71)
CASES_PER_SEED = 12
MAX_CHANGES = 6
EXHAUSTIVE_CANDIDATE_LIMIT = 48


def _subsets(items: list[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    for size in range(len(items) + 1):
        for positions in combinations(range(len(items)), size):
            yield [items[index] for index in positions]


def _rename(model: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(model)
    result["targets"] = [
        {
            **target,
            "anchor": f"A_{target['anchor']}",
            "raw": {f"X_{name}": value for name, value in target.get("raw", {}).items()},
            "origins": {
                f"X_{name}": origin for name, origin in target.get("origins", {}).items()
            },
        }
        for target in model["targets"]
    ]
    result["normalizer"] = {
        f"C_{canonical}": [f"X_{alias}" for alias in aliases]
        for canonical, aliases in model["normalizer"].items()
    }
    result["rules"] = [
        {
            **rule,
            "id": f"R_{rule['id']}",
            "family": f"F_{rule['family']}",
            "requires": [f"C_{name}" for name in rule.get("requires", [])],
            "forbids": [f"C_{name}" for name in rule.get("forbids", [])],
        }
        for rule in model["rules"]
    ]
    return result


def _rename_atom(atom: str) -> str:
    parts = atom.split("|")
    if parts[0] == "target":
        return f"target|A_{parts[1]}"
    if parts[0] == "program":
        return f"program|A_{parts[1]}|X_{parts[2]}"
    if parts[0] == "normalizer":
        return f"normalizer|C_{parts[1]}"
    if parts[0] == "rule":
        return f"rule|R_{parts[1]}"
    raise AssertionError(f"unexpected atom: {atom}")


def _reverse_containers(model: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(model)
    result["targets"] = list(reversed(result["targets"]))
    result["rules"] = list(reversed(result["rules"]))
    return result


def run_check() -> dict[str, Any]:
    candidate_pairs = 0
    exhaustive_candidates = 0
    subset_replays = 0
    certificate_checks = 0
    renaming_checks = 0
    ordering_checks = 0
    disagreements: list[dict[str, Any]] = []

    for seed in SEEDS:
        rng = random.Random(seed)
        for index in range(CASES_PER_SEED):
            target_count = 1 + (index % 2)
            family_count = 2 + (index % 2)
            rule_count = 5 + (index % 4)
            change_count = 1 + (index % MAX_CHANGES)
            case = make_random_case(
                rng,
                f"seed-{seed}-case-{index}",
                target_count=target_count,
                family_count=family_count,
                rule_count=rule_count,
                change_count=change_count,
            )
            old, new = case["old"], case["new"]
            spaces = producer.candidate_space(old, new)

            detailed_old = producer.analyze(old, spaces)
            detailed_new = producer.analyze(new, spaces)
            compact_old = producer.analyze_values(old, spaces)
            compact_new = producer.analyze_values(new, spaces)
            if {key: value["value"] for key, value in detailed_old.items()} != compact_old:
                disagreements.append({"case": case["id"], "kind": "old detailed/compact"})
            if {key: value["value"] for key, value in detailed_new.items()} != compact_new:
                disagreements.append({"case": case["id"], "kind": "new detailed/compact"})

            reversed_old = _reverse_containers(old)
            reversed_new = _reverse_containers(new)
            renamed_old = _rename(old)
            renamed_new = _rename(new)

            for family, anchor in spaces:
                candidate_pairs += 1
                direct = producer.minimum_witness(
                    old, new, family, anchor, maximum_changes=MAX_CHANGES
                )
                producer_oracle = producer.enumerated_witness(
                    old, new, family, anchor, maximum_changes=MAX_CHANGES
                )
                checker_oracle = checker.enumerated_witness(
                    old, new, family, anchor, maximum_changes=MAX_CHANGES
                )
                if not (direct == producer_oracle == checker_oracle):
                    disagreements.append(
                        {
                            "case": case["id"],
                            "candidate": [family, anchor],
                            "kind": "witness disagreement",
                            "direct": direct,
                            "producer_oracle": producer_oracle,
                            "checker_oracle": checker_oracle,
                        }
                    )

                certificate = producer.make_certificate(
                    old, new, family, anchor, maximum_changes=MAX_CHANGES
                )
                decision = checker.check_certificate(
                    old, new, certificate, maximum_changes=MAX_CHANGES
                )
                certificate_checks += 1
                if decision != (True, "accepted"):
                    disagreements.append(
                        {
                            "case": case["id"],
                            "candidate": [family, anchor],
                            "kind": "certificate rejection",
                            "decision": list(decision),
                        }
                    )

                old_evidence = detailed_old[producer.key(family, anchor)]
                new_evidence = detailed_new[producer.key(family, anchor)]
                expected_class = producer.classify_values(
                    old_evidence["value"], new_evidence["value"]
                )
                observed_class = producer.classify_candidate(
                    old, new, family, anchor
                )[0]
                if expected_class != observed_class:
                    disagreements.append(
                        {
                            "case": case["id"],
                            "candidate": [family, anchor],
                            "kind": "classification/evidence mismatch",
                        }
                    )

                order_witness = producer.minimum_witness(
                    reversed_old,
                    reversed_new,
                    family,
                    anchor,
                    maximum_changes=MAX_CHANGES,
                )
                ordering_checks += 1
                if order_witness != direct:
                    disagreements.append(
                        {
                            "case": case["id"],
                            "candidate": [family, anchor],
                            "kind": "container-order metamorphism",
                            "expected": direct,
                            "actual": order_witness,
                        }
                    )

                renamed_witness = producer.minimum_witness(
                    renamed_old,
                    renamed_new,
                    f"F_{family}",
                    f"A_{anchor}",
                    maximum_changes=MAX_CHANGES,
                )
                renaming_checks += 1
                if renamed_witness != sorted(_rename_atom(atom) for atom in direct):
                    disagreements.append(
                        {
                            "case": case["id"],
                            "candidate": [family, anchor],
                            "kind": "bijective-renaming metamorphism",
                            "expected": sorted(_rename_atom(atom) for atom in direct),
                            "actual": renamed_witness,
                        }
                    )

                if exhaustive_candidates < EXHAUSTIVE_CANDIDATE_LIMIT:
                    changes = producer.compute_delta(old, new)
                    final = producer.evaluate_family(new, family, anchor)
                    support = set(direct)
                    for subset in _subsets(changes):
                        subset_replays += 1
                        hybrid = producer.apply_operations(old, subset)
                        sufficient = producer.evaluate_family(hybrid, family, anchor) == final
                        predicted = support.issubset({entry["id"] for entry in subset})
                        if sufficient != predicted:
                            disagreements.append(
                                {
                                    "case": case["id"],
                                    "candidate": [family, anchor],
                                    "kind": "principal-filter subset disagreement",
                                    "subset": [entry["id"] for entry in subset],
                                }
                            )
                    exhaustive_candidates += 1

    return {
        "status": "PASS" if not disagreements else "FAIL",
        "scope": (
            "seeded finite differential and metamorphic checks; no fitted model, "
            "source parser, performance claim, or statistical generalization"
        ),
        "configuration": {
            "seeds": list(SEEDS),
            "cases_per_seed": CASES_PER_SEED,
            "maximum_changes": MAX_CHANGES,
            "exhaustive_candidate_limit": EXHAUSTIVE_CANDIDATE_LIMIT,
        },
        "totals": {
            "generated_endpoint_pairs": len(SEEDS) * CASES_PER_SEED,
            "candidate_pairs": candidate_pairs,
            "certificate_checks": certificate_checks,
            "exhaustive_candidates": exhaustive_candidates,
            "subset_replays": subset_replays,
            "container_order_checks": ordering_checks,
            "bijective_renaming_checks": renaming_checks,
            "disagreements": len(disagreements),
        },
        "disagreements": disagreements,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "generated_differential_check.json",
    )
    args = parser.parse_args()
    result = run_check()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
