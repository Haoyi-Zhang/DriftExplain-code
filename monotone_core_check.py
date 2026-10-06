#!/usr/bin/env python3
"""Exhaustive bounded validation of the deletion-core theorem.

Enumerates all Boolean predicates on subsets of up to four atoms, retains the
upward-closed predicates accepting the full set, and checks the set-theoretic
claims used by the independent deletion-replay checker. No analyzer code is
imported. A separately executed two-write state machine demonstrates why
upward closure is necessary and a monotone predicate restores the theorem.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def subsets(d):
    return range(1 << d)


def contains(s, t):
    return (s & t) == t


def upward(mask, d):
    for s in subsets(d):
        if (mask >> s) & 1:
            for t in subsets(d):
                if contains(t, s) and not ((mask >> t) & 1):
                    return False
    return True


def minimal_sets(sufficient):
    return [
        s
        for s in sufficient
        if not any(t != s and contains(s, t) for t in sufficient)
    ]


def deletion_core_from_predicate(predicate, d):
    full = (1 << d) - 1
    core = 0
    for atom in range(d):
        if not predicate(full & ~(1 << atom)):
            core |= 1 << atom
    return core


def intersection_of_sufficient(predicate, d):
    sufficient = [subset for subset in subsets(d) if predicate(subset)]
    if not sufficient:
        return None
    intersection = (1 << d) - 1
    for subset in sufficient:
        intersection &= subset
    return intersection


def label_subset(mask, atoms):
    selected = [atom for index, atom in enumerate(atoms) if mask & (1 << index)]
    return "{" + ",".join(selected) + "}" if selected else "{}"


def executed_negative_control():
    atoms = ("a", "b")
    d = len(atoms)

    def overwrite_state(mask):
        value = 0
        if mask & 1:  # a writes 1
            value = 1
        if mask & 2:  # b then writes 0
            value = 0
        return value

    def overwrite_predicate(mask):
        return overwrite_state(mask) == 0

    overwrite_values = {
        label_subset(mask, atoms): {
            "final_state": overwrite_state(mask),
            "sufficient": overwrite_predicate(mask),
        }
        for mask in subsets(d)
    }
    sufficient = [mask for mask in subsets(d) if overwrite_predicate(mask)]
    actual_intersection = intersection_of_sufficient(overwrite_predicate, d)
    recovered_core = deletion_core_from_predicate(overwrite_predicate, d)
    overwrite_upward = all(
        not overwrite_predicate(smaller)
        or not contains(larger, smaller)
        or overwrite_predicate(larger)
        for smaller in subsets(d)
        for larger in subsets(d)
    )
    failure_observed = (
        not overwrite_upward
        and actual_intersection == 0
        and recovered_core == 2
        and overwrite_predicate(recovered_core)
        and minimal_sets(sufficient) == [0]
    )

    # Restored premise: a monotone predicate requiring atom a. The deletion
    # core, intersection, unique least set, and principal filter then coincide.
    def requires_a(mask):
        return bool(mask & 1)

    restored_sufficient = [mask for mask in subsets(d) if requires_a(mask)]
    restored_intersection = intersection_of_sufficient(requires_a, d)
    restored_core = deletion_core_from_predicate(requires_a, d)
    restored_upward = all(
        not requires_a(smaller)
        or not contains(larger, smaller)
        or requires_a(larger)
        for smaller in subsets(d)
        for larger in subsets(d)
    )
    restored_principal = all(
        requires_a(mask) == contains(mask, restored_core) for mask in subsets(d)
    )
    restored_positive = (
        restored_upward
        and restored_intersection == 1
        and restored_core == 1
        and minimal_sets(restored_sufficient) == [1]
        and restored_principal
    )

    return {
        "passed": failure_observed and restored_positive,
        "executed_overwrite_state_machine": {
            "atom_order": ["a writes 1", "b writes 0"],
            "subset_results": overwrite_values,
            "upward_closed": overwrite_upward,
            "sufficient_set_intersection": label_subset(actual_intersection, atoms),
            "deletion_core": label_subset(recovered_core, atoms),
            "deletion_core_sufficient": overwrite_predicate(recovered_core),
            "minimal_sufficient_sets": [
                label_subset(mask, atoms) for mask in minimal_sets(sufficient)
            ],
            "theorem_failure_observed": failure_observed,
        },
        "restored_monotone_positive_control": {
            "predicate": "a is selected",
            "upward_closed": restored_upward,
            "sufficient_set_intersection": label_subset(
                restored_intersection, atoms
            ),
            "deletion_core": label_subset(restored_core, atoms),
            "minimal_sufficient_sets": [
                label_subset(mask, atoms)
                for mask in minimal_sets(restored_sufficient)
            ],
            "principal_filter": restored_principal,
            "positive_control_passed": restored_positive,
        },
    }


def run(max_atoms=4):
    totals = {
        "dimensions": 0,
        "all_predicates_examined": 0,
        "upward_predicates": 0,
        "theorem_checks": 0,
        "counterexamples": 0,
    }
    per_dimension = []
    examples = []
    for d in range(max_atoms + 1):
        full = (1 << d) - 1
        upward_count = 0
        examined = 0
        # Predicates are masks over the 2^d subsets.
        for predicate_mask in range(1 << (1 << d)):
            examined += 1
            totals["all_predicates_examined"] += 1
            if not ((predicate_mask >> full) & 1):
                continue
            if not upward(predicate_mask, d):
                continue
            upward_count += 1
            totals["upward_predicates"] += 1
            sufficient = [
                subset
                for subset in subsets(d)
                if (predicate_mask >> subset) & 1
            ]
            core = full
            for subset in sufficient:
                core &= subset
            deletion_core = 0
            for atom in range(d):
                if not ((predicate_mask >> (full & ~(1 << atom))) & 1):
                    deletion_core |= 1 << atom
            minima = minimal_sets(sufficient)
            principal = all(
                bool((predicate_mask >> subset) & 1) == contains(subset, core)
                for subset in subsets(d)
            )
            core_sufficient = bool((predicate_mask >> core) & 1)
            unique_least = core_sufficient and all(
                contains(subset, core) for subset in sufficient
            )
            no_least_implies_multiple = core_sufficient or len(minima) >= 2
            incomparable = core_sufficient or all(
                not contains(left, right) and not contains(right, left)
                for index, left in enumerate(minima)
                for right in minima[index + 1 :]
            )
            ok = (
                core == deletion_core
                and core_sufficient == unique_least == principal
                and no_least_implies_multiple
                and incomparable
            )
            totals["theorem_checks"] += 5
            if not ok:
                totals["counterexamples"] += 1
                examples.append(
                    {
                        "atoms": d,
                        "predicate_mask": predicate_mask,
                        "sufficient": sufficient,
                        "core": core,
                        "deletion_core": deletion_core,
                        "minimal": minima,
                        "principal": principal,
                    }
                )
                break
        per_dimension.append(
            {
                "atoms": d,
                "predicates_examined": examined,
                "upward_full_accepting": upward_count,
            }
        )
        totals["dimensions"] += 1
        if examples:
            break

    negative_control = executed_negative_control()
    return {
        "scope": (
            f"all Boolean predicates through {max_atoms} atoms; general theorem "
            "still relies on proof"
        ),
        "per_dimension": per_dimension,
        "totals": totals,
        "negative_control": negative_control,
        "status": (
            "PASS"
            if not examples and negative_control["passed"]
            else "FAIL"
        ),
        "counterexample_examples": examples,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-atoms", type=int, default=4)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent
        / "results"
        / "monotone_core_check.json",
    )
    args = parser.parse_args()
    output = run(args.max_atoms)
    text = json.dumps(output, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if output["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
