"""Deterministic exact-evidence support study; standard library only.

No source contracts are executed. Small finite models are owned controls.
The producer selects structural support; the independent checker performs
single-deletion replays; complete subset enumeration is the small oracle.
"""
from __future__ import annotations
import argparse
import copy
import csv
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

import checker
import producer
from producer import (candidate_space, classify_candidate, compute_delta,
                      make_certificate, minimum_witness)
from evaluate import tiny_model


def base() -> dict[str, Any]:
    return {
        "targets": [{"anchor": "a", "raw": {"x": "F", "y": "T", "z": "U"},
                     "origins": {"x": "line:x", "y": "line:y", "z": "line:z"}}],
        "normalizer": {"p": ["x"], "q": ["y"], "u": ["z"]},
        "rules": [{"id": "r", "family": "f", "requires": ["p"], "forbids": ["q"]},
                  {"id": "s", "family": "g", "requires": ["u"]}],
    }


def directed_pairs() -> Iterator[tuple[str, dict, dict, str, str]]:
    """Twelve concrete policies in both directions: exactly 24 owned pairs."""
    pairs = []
    for index in range(12):
        old, new = base(), base()
        t = new["targets"][0]
        if index == 0:
            t["raw"]["x"] = "T"; t["raw"]["noise"] = "U"
        elif index == 1:
            t["raw"]["x"] = "U"; t["raw"]["y"] = "F"
        elif index == 2:
            del new["normalizer"]["p"]
            t["raw"]["x"] = "T"
        elif index == 3:
            new["normalizer"]["p"] = ["x", "y"]
            t["raw"]["y"] = "U"
        elif index == 4:
            old["normalizer"]["p"] = ["x", "y"]
            new["normalizer"]["p"] = ["y", "x"]
            t["origins"]["x"] = "line:relocated"
        elif index == 5:
            new["rules"].append({"id": "t", "family": "f", "requires": ["u", "q"]})
            t["raw"]["z"] = "T"
        elif index == 6:
            new["rules"][0]["family"] = "g"
            new["rules"][1]["family"] = "f"
        elif index == 7:
            new["targets"] = []
            new["rules"] = []
            del new["normalizer"]["p"]
        elif index == 8:
            # Ignored metadata and absent-versus-empty literals are observable
            # to the raw delta but not to the complete semantic evidence tree.
            old["rules"][0].pop("forbids")
            new["rules"][0]["forbids"] = []
            new["rules"][0]["note"] = "descriptive only"
        elif index == 9:
            t["origins"]["x"] = "line:renumbered"
            t["origins"]["noise"] = "unused"
        elif index == 10:
            new["normalizer"]["p"] = ["fresh"]
            t["raw"]["x"] = "T"; t["raw"]["fresh"] = "U"
        else:
            new["rules"][0]["requires"] = ["q", "u"]
            new["rules"][0]["forbids"] = []
            new["normalizer"]["q"] = ["z", "x"]
            t["raw"]["z"] = "F"; t["raw"]["x"] = "T"
        pairs.append((f"policy-{index:02d}", old, new, "f", "a"))
    for name, old, new, family, anchor in pairs:
        yield name + "-forward", old, new, family, anchor
        yield name + "-reverse", new, old, family, anchor


def combination_pairs() -> Iterator[tuple[str, dict, dict, str, str]]:
    """Forty deterministic multi-kind pairs; no outcome-based selection."""
    for index in range(40):
        old, new = base(), base()
        t = new["targets"][0]
        for j, name in enumerate(("x", "y", "z")):
            if index & (1 << j):
                t["raw"][name] = ("T", "F", "T")[j]
        if index % 2:
            new["normalizer"]["p"] = ["y", "x"]
        if index % 3:
            new["rules"][0]["requires"] = ["u", "p"]
        if index % 4:
            t["origins"]["z"] = "line:new-z"
        if index % 5:
            new["rules"][1]["family"] = "f"
        if index % 7:
            t["raw"]["unused"] = "T"
        yield f"combination-{index:02d}", old, new, "f", "a"


def tiny_pairs() -> Iterator[tuple[str, dict, dict, str, str]]:
    triads = itertools.product(("T", "F", "U"), repeat=3)
    triads = list(triads)
    cats = (("both", "both"), ("both", "alpha_only"), ("alpha_only", "both"))
    norms = ((False, False), (False, True))
    number = 0
    for left, right, cat, norm in itertools.product(triads, triads, cats, norms):
        old = tiny_model(left, cat[0], norm[0], "tiny-old")
        new = tiny_model(right, cat[1], norm[1], "tiny-new")
        for family in ("alpha", "beta"):
            yield f"tiny-{number:05d}", old, new, family, "site"
            number += 1


def test_pair(case: tuple, enumerate_all: bool = True,
              certificate: dict[str, Any] | None = None) -> dict[str, Any]:
    name, old, new, family, anchor = case
    ops = checker._changes(old, new)
    if len(ops) > 8 and enumerate_all:
        raise ValueError("small-oracle admission bound exceeded")
    cert = certificate if certificate is not None else make_certificate(
        old, new, family, anchor, maximum_changes=64)
    accepted, diagnostic = checker.check_certificate(old, new, cert, maximum_changes=64)
    if not accepted:
        raise AssertionError((name, diagnostic))
    support = set(cert["witness"])
    if len(support) != len(cert["witness"]):
        raise AssertionError("duplicate support")
    final = checker._family_result(new, family, anchor)
    if enumerate_all:
        oracle = checker.enumerated_witness(old, new, family, anchor, 64)
        if cert["witness"] != oracle:
            raise AssertionError((name, "oracle disagreement"))
    tested, sufficient = 0, 0
    if enumerate_all:
        for mask in range(1 << len(ops)):
            chosen = [op for j, op in enumerate(ops) if mask & (1 << j)]
            evidence = checker._family_result(checker._patch(old, chosen), family, anchor)
            expected = support <= {op["id"] for op in chosen}
            actual = evidence == final
            if actual != expected:
                raise AssertionError((name, "principal filter", mask))
            tested += 1
            sufficient += int(actual)
    return {"case": name, "classification": cert["classification"],
            "delta_elements": len(ops), "witness_elements": len(support),
            "structural_deletion_agreement": 1,
            "enumerated_minimum_agreement": 1 if enumerate_all else "not sampled",
            "subsets_examined": tested, "sufficient_subsets": sufficient,
            "principal_filter_disagreements": 0}


def negative_control() -> dict[str, Any]:
    old = {"targets": [{"anchor": "a", "raw": {"x": "F", "y": "F"}}],
           "normalizer": {"p": ["x", "y"]},
           "rules": [{"id": "r", "family": "f", "requires": ["p"]}]}
    new = copy.deepcopy(old)
    new["targets"][0]["raw"] = {"x": "T", "y": "T"}
    changes = checker._changes(old, new)
    full = checker._family_result(new, "f", "a")
    value_sets, exact_sets = [], []
    for mask in range(4):
        subset = [op for j, op in enumerate(changes) if mask & (1 << j)]
        result = checker._family_result(checker._patch(old, subset), "f", "a")
        names = [op["id"] for op in subset]
        if result["value"] == full["value"]:
            value_sets.append(names)
        if result == full:
            exact_sets.append(names)
    mandatory_value = set.intersection(*(set(s) for s in value_sets))
    assert not mandatory_value and [] not in value_sets
    assert exact_sets == [["program|a|x", "program|a|y"]]
    return {"kind": "owned finite negative control", "old": old, "new": new,
            "value_sufficient_subsets": value_sets, "exact_sufficient_subsets": exact_sets,
            "value_mandatory_intersection_is_insufficient": True,
            "source_security_meaning": "none"}


def large_cases() -> list[dict[str, Any]]:
    rows = []
    for size in (16, 32, 64):
        for policy in ("all-observed", "half-observed", "origin-only", "target-absent"):
            observed = size if policy != "half-observed" else size // 2
            raw = {f"x{i:02d}": "F" for i in range(size)}
            aliases = list(raw)[:observed]
            old = {"targets": [{"anchor": "a", "raw": raw}],
                   "normalizer": {"p": aliases},
                   "rules": [{"id": "r", "family": "f", "requires": ["p"]}]}
            new = copy.deepcopy(old)
            if policy == "origin-only":
                new["targets"][0]["origins"] = {r: "line:changed" for r in raw}
            elif policy == "target-absent":
                # All norm changes are irrelevant once target absence is final.
                new["targets"] = []
                for i in range(size - 1):
                    new["normalizer"][f"unused{i:02d}"] = ["x00"]
            else:
                new["targets"][0]["raw"] = {r: "T" for r in raw}
            cert = make_certificate(old, new, "f", "a", 64)
            accepted, reason = checker.check_certificate(old, new, cert, 64)
            assert accepted, reason
            expected = 1 if policy == "target-absent" else observed
            assert len(cert["delta"]) == size and len(cert["witness"]) == expected
            # No exponential comparison is attempted on these instances.
            rows.append({"case": f"large-{size}-{policy}", "delta_elements": size,
                         "witness_elements": expected, "checker_hybrid_replays": size + 1,
                         "accepted": 1, "enumerated_baseline": "not run"})
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def run(output: Path, pilot: bool) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    # Count actual semantic calls, including oracle, deletion, and certificate
    # replays. This is a candidate/evidence obligation, not a rule counter.
    calls = Counter()
    original = checker._family_result
    original_producer = producer.evaluate_family
    def counted_producer(*args, **kwargs):
        calls["producer_candidate_evaluations"] += 1
        if sum(calls.values()) > 120000:
            raise RuntimeError("frozen candidate-obligation cap exceeded")
        return original_producer(*args, **kwargs)
    def counted(*args, **kwargs):
        calls["independent_candidate_evaluations"] += 1
        if sum(calls.values()) > 120000:
            raise RuntimeError("frozen candidate-obligation cap exceeded")
        return original(*args, **kwargs)
    checker._family_result = counted
    producer.evaluate_family = counted_producer
    try:
        directed = list(directed_pairs())
        if not pilot:
            directed += list(combination_pairs())
        rows = [test_pair(case) for case in directed]
        negative = negative_control()
        tiny_rows = []
        if not pilot:
            sampled = Counter()
            for case in tiny_pairs():
                _, old, new, family, anchor = case
                cert = make_certificate(old, new, family, anchor, 64)
                cls = cert["classification"]
                # All candidates compare structural and deletion methods.
                # Full subset and minimum oracles use the 301 class sample.
                full_oracle = sampled[cls] < 64
                tiny_rows.append(test_pair(case, enumerate_all=full_oracle, certificate=cert))
                if full_oracle:
                    sampled[cls] += 1
            large = large_cases()
            write_csv(output / "large_support.csv", large)
            write_csv(output / "tiny_support.csv", tiny_rows)
        else:
            large = []
        write_csv(output / "directed_support.csv", rows)
        (output / "value_only_counterexample.json").write_text(
            json.dumps(negative, indent=2, sort_keys=True) + "\n")
        summary = {"directed_pairs": len(rows), "tiny_candidates": len(tiny_rows),
                   "large_cases": len(large),
                   "all_subset_comparisons": sum(r["subsets_examined"] for r in rows + tiny_rows),
                   "structural_deletion_disagreements": 0,
                   "enumerated_minimum_disagreements": 0,
                   "principal_filter_disagreements": 0,
                   "value_only_negative_control_exposes_nonunique_support": True,
                   "independent_candidate_evaluations": calls["independent_candidate_evaluations"],
                   "producer_candidate_evaluations": calls["producer_candidate_evaluations"],
                   "total_candidate_evaluations": sum(calls.values()),
                   "tiny_complete_subset_cases": sum(bool(r["subsets_examined"]) for r in tiny_rows),
                   "enumerated_minimum_cases": sum(bool(r["subsets_examined"]) for r in rows + tiny_rows),
                   "maximum_small_delta": max(r["delta_elements"] for r in rows + tiny_rows),
                   "maximum_large_delta": max((r["delta_elements"] for r in large), default=0)}
        (output / "support_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return summary
    finally:
        checker._family_result = original
        producer.evaluate_family = original_producer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    options = parser.parse_args()
    print(json.dumps(run(options.output, options.pilot), indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
