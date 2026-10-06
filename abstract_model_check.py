#!/usr/bin/env python3
"""Independent bounded checker for the structural-support theorem.

This file imports no analyzer code. It exhaustively enumerates small fixed
stratified frames. A state has one always-read selector coordinate and one leaf
coordinate per selector value. Evidence is the selector followed by the
selected leaf. Delta atoms own pairwise-disjoint blocks of changed coordinates.
The checker verifies, for every subset of atoms, that exact final-evidence
equality holds iff all atoms intersecting the final read closure are selected.
Four deliberately out-of-contract constructions are executed as negative
controls, each with a restored-premise positive control.
"""
from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from typing import Callable, Iterable


def set_partitions(items: Iterable[int]):
    items = tuple(items)
    if not items:
        yield ()
        return
    first, *rest = items
    for part in set_partitions(rest):
        yield ((first,),) + part
        for index in range(len(part)):
            block = tuple(sorted((first,) + part[index]))
            yield part[:index] + (block,) + part[index + 1 :]


def canonical_partitions(items: Iterable[int]):
    seen: set[tuple[tuple[int, ...], ...]] = set()
    for partition in set_partitions(items):
        canonical = tuple(
            sorted(
                (tuple(sorted(block)) for block in partition),
                key=lambda block: (block[0], len(block), block),
            )
        )
        if canonical not in seen:
            seen.add(canonical)
            yield canonical


def evidence(state: tuple[int, ...]) -> tuple[int, int]:
    selector = state[0]
    return selector, state[1 + selector]


def patch(
    old: tuple[int, ...],
    new: tuple[int, ...],
    blocks: tuple[tuple[int, ...], ...],
    chosen: set[int],
) -> tuple[int, ...]:
    result = list(old)
    for atom, block in enumerate(blocks):
        if atom in chosen:
            for coordinate in block:
                result[coordinate] = new[coordinate]
    return tuple(result)


def powerset(size: int):
    for mask in range(1 << size):
        yield {index for index in range(size) if mask & (1 << index)}


def check_domain(domain_size: int) -> dict:
    coordinates = 1 + domain_size
    states = list(product(range(domain_size), repeat=coordinates))
    endpoint_pairs = partitions = subset_replays = 0
    failures: list[dict] = []
    for old in states:
        for new in states:
            changed = tuple(
                index for index, (left, right) in enumerate(zip(old, new)) if left != right
            )
            if not changed:
                continue
            endpoint_pairs += 1
            final_read = {0, 1 + new[0]}
            for blocks in canonical_partitions(changed):
                partitions += 1
                support = {
                    atom
                    for atom, block in enumerate(blocks)
                    if final_read.intersection(block)
                }
                target = evidence(new)
                for chosen in powerset(len(blocks)):
                    subset_replays += 1
                    actual = evidence(patch(old, new, blocks, chosen)) == target
                    predicted = support.issubset(chosen)
                    if actual != predicted:
                        failures.append(
                            {
                                "domain_size": domain_size,
                                "old": old,
                                "new": new,
                                "blocks": blocks,
                                "chosen": sorted(chosen),
                                "support": sorted(support),
                                "actual": actual,
                                "predicted": predicted,
                            }
                        )
                        return {
                            "domain_size": domain_size,
                            "nonidentical_endpoint_pairs": endpoint_pairs,
                            "atom_partitions": partitions,
                            "subset_replays": subset_replays,
                            "failures": failures,
                        }
    return {
        "domain_size": domain_size,
        "nonidentical_endpoint_pairs": endpoint_pairs,
        "atom_partitions": partitions,
        "subset_replays": subset_replays,
        "failures": failures,
    }


def minimal_sufficient_sets(
    atoms: tuple[str, ...], predicate: Callable[[set[str]], bool]
) -> list[list[str]]:
    sufficient: list[set[str]] = []
    for chosen_mask in range(1 << len(atoms)):
        chosen = {
            atom for index, atom in enumerate(atoms) if chosen_mask & (1 << index)
        }
        if predicate(chosen):
            sufficient.append(chosen)
    minimal = [
        chosen
        for chosen in sufficient
        if not any(other < chosen and predicate(other) for other in sufficient)
    ]
    return [sorted(chosen) for chosen in minimal]


def value_only_control() -> dict:
    atoms = ("a", "b")

    def value_only(chosen: set[str]) -> bool:
        return "a" in chosen or "b" in chosen

    minima = minimal_sufficient_sets(atoms, value_only)

    def complete_evidence(chosen: set[str]) -> bool:
        return chosen == set(atoms)

    restored_minima = minimal_sufficient_sets(atoms, complete_evidence)
    passed = minima == [["a"], ["b"]] and restored_minima == [["a", "b"]]
    return {
        "passed": passed,
        "executed_predicate_values": {
            "empty": value_only(set()),
            "a": value_only({"a"}),
            "b": value_only({"b"}),
            "a_b": value_only({"a", "b"}),
        },
        "incomparable_minimal_sufficient_sets": minima,
        "restored_complete_evidence": {
            "minimal_sufficient_sets": restored_minima,
            "unique_least_restored": restored_minima == [["a", "b"]],
        },
    }


def overlapping_write_control() -> dict:
    def sequential_value(chosen: set[str]) -> int:
        value = 0
        if "a" in chosen:
            value = 1
        if "b" in chosen:
            value = 0
        return value

    def sufficient(chosen: set[str]) -> bool:
        return sequential_value(chosen) == 0

    evaluations = {
        "empty": sufficient(set()),
        "a": sufficient({"a"}),
        "b": sufficient({"b"}),
        "a_b": sufficient({"a", "b"}),
    }
    upward_violation = evaluations["empty"] and not evaluations["a"]

    # Restored premise: two disjoint coordinates, each atom writes its own
    # endpoint coordinate directly. Exact final evidence is then upward closed.
    def disjoint_patch(chosen: set[str]) -> tuple[int, int]:
        return (1 if "a" in chosen else 0, 1 if "b" in chosen else 0)

    restored = {
        "empty": disjoint_patch(set()) == (1, 1),
        "a": disjoint_patch({"a"}) == (1, 1),
        "b": disjoint_patch({"b"}) == (1, 1),
        "a_b": disjoint_patch({"a", "b"}) == (1, 1),
    }
    restored_upward = (
        not restored["empty"]
        and not restored["a"]
        and not restored["b"]
        and restored["a_b"]
    )
    return {
        "passed": upward_violation and restored_upward,
        "sequential_write_evaluations": evaluations,
        "upward_closure_violation_observed": upward_violation,
        "restored_disjoint_endpoint_blocks": {
            "evaluations": restored,
            "upward_principal_filter_restored": restored_upward,
        },
    }


def hidden_selector_control() -> dict:
    old = (0, 7, 9)
    new = (1, 7, 9)
    blocks = ((0,),)
    # Complete keyed leaf records, but the selector controlling visibility is
    # not recorded. Derive support from the actual final hidden read closure:
    # the selector atom is exterior even though it changes the selected key.
    hidden_final_read = {1 + new[0]}
    support = {
        atom for atom, block in enumerate(blocks)
        if hidden_final_read.intersection(block)
    }

    def hidden_evidence(state: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
        key = 1 + state[0]
        return ((key, state[key]),)

    empty = set()
    full = {0}
    hidden_empty_actual = hidden_evidence(patch(old, new, blocks, empty)) == hidden_evidence(new)
    hidden_empty_predicted = support.issubset(empty)
    hidden_violation = hidden_empty_actual != hidden_empty_predicted

    restored_final_read = {0, 1 + new[0]}
    restored_support = {
        atom for atom, block in enumerate(blocks)
        if restored_final_read.intersection(block)
    }
    restored_agreements = []
    for chosen in powerset(len(blocks)):
        actual = evidence(patch(old, new, blocks, chosen)) == evidence(new)
        predicted = restored_support.issubset(chosen)
        restored_agreements.append(actual == predicted)

    return {
        "passed": hidden_violation and all(restored_agreements),
        "old_state": list(old),
        "new_state": list(new),
        "selector_atom_block": [0],
        "hidden_final_read": sorted(hidden_final_read),
        "support": sorted(support),
        "empty_patch": {
            "hidden_old_evidence": [list(record) for record in hidden_evidence(old)],
            "hidden_new_evidence": [list(record) for record in hidden_evidence(new)],
            "actual_sufficient": hidden_empty_actual,
            "predicted_sufficient": hidden_empty_predicted,
            "structural_equivalence_violated": hidden_violation,
        },
        "restored_complete_evidence": {
            "final_read": sorted(restored_final_read),
            "support": sorted(restored_support),
            "old_evidence": list(evidence(old)),
            "new_evidence": list(evidence(new)),
            "empty_patch_sufficient": evidence(old) == evidence(new),
            "support_patch_sufficient": evidence(
                patch(old, new, blocks, full)
            )
            == evidence(new),
            "all_subsets_agree": all(restored_agreements),
        },
    }


def unstable_identity_control() -> dict:
    old = {"x": 1, "y": 2}
    new = {"x": 2, "y": 1}
    old_order = ("x", "y")
    unstable_correspondence = {"x": "y", "y": "x"}
    stable_correspondence = {"x": "x", "y": "y"}

    def correspondence_view(
        endpoint: dict[str, int], correspondence: dict[str, str]
    ) -> tuple[int, ...]:
        return tuple(endpoint[correspondence[identity]] for identity in old_order)

    def changed_under(correspondence: dict[str, str]) -> list[str]:
        return [
            identity
            for identity in old_order
            if old[identity] != new[correspondence[identity]]
        ]

    def keyed_evidence(endpoint: dict[str, int]) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(endpoint.items()))

    def stable_patch(chosen: set[str]) -> dict[str, int]:
        result = dict(old)
        for identity in chosen:
            result[identity] = new[identity]
        return result

    unstable_old_view = tuple(old[identity] for identity in old_order)
    unstable_new_view = correspondence_view(new, unstable_correspondence)
    unstable_changes = changed_under(unstable_correspondence)
    stable_changes = changed_under(stable_correspondence)
    failure_observed = (
        unstable_old_view == unstable_new_view
        and not unstable_changes
        and keyed_evidence(old) != keyed_evidence(new)
    )
    restored = (
        stable_changes == ["x", "y"]
        and keyed_evidence(stable_patch(set())) != keyed_evidence(new)
        and keyed_evidence(stable_patch(set(stable_changes))) == keyed_evidence(new)
    )
    return {
        "passed": failure_observed and restored,
        "old_keyed_state": [[key, value] for key, value in sorted(old.items())],
        "new_keyed_state": [[key, value] for key, value in sorted(new.items())],
        "unstable_correspondence": unstable_correspondence,
        "unstable_positional_views": {
            "old": list(unstable_old_view),
            "new": list(unstable_new_view),
            "masked_changes": unstable_changes,
            "keyed_endpoints_differ": keyed_evidence(old) != keyed_evidence(new),
            "failure_observed": failure_observed,
        },
        "restored_stable_identity": {
            "correspondence": stable_correspondence,
            "changed_identities": stable_changes,
            "empty_patch_reaches_new": keyed_evidence(stable_patch(set()))
            == keyed_evidence(new),
            "full_patch_reaches_new": keyed_evidence(
                stable_patch(set(stable_changes))
            )
            == keyed_evidence(new),
            "positive_control_passed": restored,
        },
    }


def negative_controls() -> dict[str, dict]:
    return {
        "value_only_incomparable_minima": value_only_control(),
        "overlapping_write_breaks_upward_closure": overlapping_write_control(),
        "hidden_visibility_breaks_structural_identification": hidden_selector_control(),
        "unstable_identity_breaks_coordinate_correspondence": unstable_identity_control(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent
        / "results"
        / "abstract_model_check.json",
    )
    args = parser.parse_args()

    selector_domains = [2, 3]
    runs = [check_domain(size) for size in selector_domains]
    controls = negative_controls()
    controls_passed = all(control["passed"] for control in controls.values())
    output = {
        "checker_independence": (
            "standard library only; imports no project analyzer, producer, "
            "checker, or test module"
        ),
        "scope": (
            "bounded exhaustive validation of one-selector stratified frames; "
            "not a substitute for the paper proof"
        ),
        "configuration": {
            "selector_domain_sizes": selector_domains,
            "endpoint_pair_scope": "ordered non-identical endpoint pairs",
        },
        "domains": runs,
        "totals": {
            "endpoint_pairs": sum(
                run["nonidentical_endpoint_pairs"] for run in runs
            ),
            "atom_partitions": sum(run["atom_partitions"] for run in runs),
            "subset_replays": sum(run["subset_replays"] for run in runs),
            "counterexamples": sum(len(run["failures"]) for run in runs),
        },
        "negative_controls": controls,
        "negative_controls_passed": controls_passed,
        "status": (
            "PASS"
            if all(not run["failures"] for run in runs) and controls_passed
            else "FAIL"
        ),
    }
    text = json.dumps(output, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if output["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
