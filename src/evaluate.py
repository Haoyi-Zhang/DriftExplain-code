"""Run the claim-linked finite evidence suite.

The default outputs contain only deterministic semantic evidence.  Optional
wall-clock observations are written to separate files so rerunning the suite
does not silently replace the measurements used by the paper.
"""
from __future__ import annotations

import argparse
import copy
import csv
import gc
import json
import os
import random
import statistics
import time
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path
from typing import Any

from checker import check_certificate, replay_classification
from generate import load_public_fixtures, make_public_evolutions, make_random_case
from producer import (
    Counts,
    analyze_values,
    candidate_space,
    classify_candidate,
    classify_values,
    compute_delta,
    incremental_new_values,
    key,
    make_certificate,
    textual_baseline,
)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({name for row in rows for name in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tiny_model(
    states: tuple[str, str, str], catalog: str, missing_a: bool, name: str
) -> dict[str, Any]:
    rules = [
        {"id": "r-a", "family": "alpha", "requires": ["a"], "forbids": ["guard"]},
        {"id": "r-b", "family": "beta", "requires": ["b"], "forbids": ["guard"]},
    ]
    if catalog == "alpha_only":
        rules = [rules[0]]
    normalizer = {"a": ["x"], "b": ["y"], "guard": ["z"]}
    if missing_a:
        del normalizer["a"]
    return {
        "name": name,
        "targets": [
            {
                "anchor": "site",
                "raw": {"x": states[0], "y": states[1], "z": states[2]},
                "origins": {"x": "tiny:x", "y": "tiny:y", "z": "tiny:z"},
            }
        ],
        "normalizer": normalizer,
        "rules": rules,
    }


def run_exhaustive(results_dir: Path) -> dict[str, Any]:
    triads = list(product(("T", "F", "U"), repeat=3))
    catalog_pairs = [
        ("both", "both", "catalog-stable"),
        ("both", "alpha_only", "rule-removal"),
        ("alpha_only", "both", "rule-addition"),
    ]
    normalizer_pairs = [
        (False, False, "normalizer-stable"),
        (False, True, "normalizer-loss"),
    ]
    rows: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    replay_diagnostics: Counter[str] = Counter()
    certificate_diagnostics: Counter[str] = Counter()
    replay_total = 0
    replay_agreements = 0
    certificate_total = 0
    certificate_accepted = 0
    sampled_per_class: Counter[str] = Counter()
    maximum_delta = 0
    maximum_witness = 0
    for old_states in triads:
        for new_states in triads:
            for old_catalog, new_catalog, catalog_change in catalog_pairs:
                for old_missing, new_missing, normalizer_change in normalizer_pairs:
                    old = tiny_model(old_states, old_catalog, old_missing, "tiny-old")
                    new = tiny_model(new_states, new_catalog, new_missing, "tiny-new")
                    for family in ("alpha", "beta"):
                        produced_class, produced_old, produced_new = classify_candidate(
                            old, new, family, "site"
                        )
                        checked_class, checked_old, checked_new = replay_classification(
                            old, new, family, "site"
                        )
                        replay_total += 1
                        agrees = (
                            produced_class == checked_class
                            and produced_old == checked_old
                            and produced_new == checked_new
                        )
                        replay_agreements += int(agrees)
                        replay_diagnostics["agreement" if agrees else "disagreement"] += 1
                        class_counts[produced_class] += 1

                        # Exact witness minimality is expensive by design.  We
                        # retain a deterministic, class-stratified subset while
                        # replaying the classification semantics on the entire
                        # finite domain above.
                        if sampled_per_class[produced_class] < 64:
                            certificate = make_certificate(old, new, family, "site")
                            decision, diagnostic = check_certificate(old, new, certificate)
                            certificate_total += 1
                            certificate_accepted += int(decision)
                            certificate_diagnostics[diagnostic] += 1
                            sampled_per_class[produced_class] += 1
                            maximum_delta = max(maximum_delta, len(certificate["delta"]))
                            maximum_witness = max(maximum_witness, len(certificate["witness"]))
                    rows.append(
                        {
                            "old_states": "".join(old_states),
                            "new_states": "".join(new_states),
                            "catalog_change": catalog_change,
                            "normalizer_change": normalizer_change,
                        }
                    )
    write_csv(
        results_dir / "exhaustive_grid.csv",
        rows,
        ["old_states", "new_states", "catalog_change", "normalizer_change"],
    )
    return {
        "classification_replays": replay_total,
        "classification_agreements": replay_agreements,
        "classification_agreement_rate": replay_agreements / replay_total,
        "classification_counts": dict(sorted(class_counts.items())),
        "replay_diagnostics": dict(sorted(replay_diagnostics.items())),
        "minimality_certificates_checked": certificate_total,
        "minimality_certificates_accepted": certificate_accepted,
        "minimality_acceptance_rate": certificate_accepted / certificate_total,
        "minimality_sample_by_class": dict(sorted(sampled_per_class.items())),
        "certificate_diagnostics": dict(sorted(certificate_diagnostics.items())),
        "maximum_delta_elements": maximum_delta,
        "maximum_witness_elements": maximum_witness,
        "enumerated_model_pairs": len(rows),
    }


def _mutations(certificate: dict[str, Any]) -> list[tuple[str, Any]]:
    outcomes = ["preserved", "newly_justified", "invalidated", "unresolved", "absent"]
    mutations: list[tuple[str, Any]] = []

    # Exercise the outer parser boundary as well as field-level integrity.
    # The checker must reject an arbitrary JSON value rather than crash while
    # assuming a mapping.
    mutations.append(("certificate-shape", []))

    candidate = copy.deepcopy(certificate)
    candidate["schema"] = "other-schema"
    mutations.append(("schema", candidate))

    candidate = copy.deepcopy(certificate)
    current = candidate["classification"]
    candidate["classification"] = outcomes[(outcomes.index(current) + 1) % len(outcomes)]
    mutations.append(("classification", candidate))

    candidate = copy.deepcopy(certificate)
    candidate["candidate"]["family"] += "-changed"
    mutations.append(("family", candidate))

    candidate = copy.deepcopy(certificate)
    delta_size = len(candidate["delta"])
    candidate["change_bound"] = delta_size - 1 if delta_size else -1
    mutations.append(("change-bound", candidate))

    candidate = copy.deepcopy(certificate)
    candidate["old"]["value"] = "F" if candidate["old"]["value"] != "F" else "T"
    mutations.append(("old-evidence", candidate))

    candidate = copy.deepcopy(certificate)
    candidate["new"]["value"] = "F" if candidate["new"]["value"] != "F" else "T"
    mutations.append(("new-evidence", candidate))

    candidate = copy.deepcopy(certificate)
    candidate["delta"] = list(candidate["delta"]) + ["program|ghost|fact"]
    mutations.append(("delta-member", candidate))

    candidate = copy.deepcopy(certificate)
    candidate["witness"] = list(candidate["witness"]) + ["program|ghost|fact"]
    mutations.append(("witness-member", candidate))

    candidate = copy.deepcopy(certificate)
    if candidate["witness"]:
        candidate["witness"] = candidate["witness"] + [candidate["witness"][0]]
    else:
        candidate["witness"] = ["program|ghost|fact", "program|ghost|fact"]
    mutations.append(("witness-duplicate", candidate))

    candidate = copy.deepcopy(certificate)
    if candidate["old"].get("rules"):
        candidate["old"]["rules"] = candidate["old"]["rules"][:-1]
    else:
        candidate["old"]["rules"] = [{"rule": "ghost"}]
    mutations.append(("evidence-structure", candidate))
    return mutations


def run_public(results_dir: Path, data_dir: Path) -> tuple[dict[str, Any], list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]]:
    fixtures = load_public_fixtures(data_dir / "public_fixtures.json")
    cases = make_public_evolutions(fixtures)
    fixture_by_id = {fixture["id"]: fixture for fixture in fixtures}
    rows: list[dict[str, Any]] = []
    certificates: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    classifications: Counter[str] = Counter()
    baseline_correct = 0
    cert_dir = results_dir / "certificates"
    cert_dir.mkdir(parents=True, exist_ok=True)
    witness_sizes: list[int] = []
    delta_sizes: list[int] = []
    for case in cases:
        certificate = make_certificate(
            case["old"], case["new"], case["family"], case["anchor"]
        )
        accepted, diagnostic = check_certificate(case["old"], case["new"], certificate)
        if not accepted:
            raise AssertionError(f"public case rejected: {case['id']} ({diagnostic})")
        write_json(cert_dir / f"{case['id']}.json", certificate)
        certificates.append((case["old"], case["new"], certificate))
        actual = certificate["classification"]
        case_delta = compute_delta(case["old"], case["new"])
        baseline = textual_baseline(
            case["old"], case["new"], case["family"], case["anchor"], case_delta
        )
        baseline_correct += int(actual == baseline)
        classifications[actual] += 1
        witness_sizes.append(len(certificate["witness"]))
        delta_sizes.append(len(certificate["delta"]))
        fixture = fixture_by_id[case["fixture"]]
        rows.append(
            {
                "case": case["id"],
                "fixture": case["fixture"],
                "category": fixture["category"],
                "mutation": case["mutation"],
                "classification": actual,
                "checker": diagnostic,
                "delta_elements": len(certificate["delta"]),
                "witness_elements": len(certificate["witness"]),
                "textual_baseline": baseline,
                "baseline_correct": int(actual == baseline),
                "source_path": fixture["source_path"],
                "annotated_lines": fixture["annotated_lines"],
            }
        )
    write_csv(
        results_dir / "public_cases.csv",
        rows,
        [
            "case",
            "fixture",
            "category",
            "mutation",
            "classification",
            "checker",
            "delta_elements",
            "witness_elements",
            "textual_baseline",
            "baseline_correct",
            "source_path",
            "annotated_lines",
        ],
    )
    return (
        {
            "fixtures": len(fixtures),
            "evolutions": len(cases),
            "classification_counts": dict(sorted(classifications.items())),
            "checker_acceptance_rate": 1.0,
            "textual_baseline_accuracy": baseline_correct / len(cases),
            "mean_delta_elements": statistics.fmean(delta_sizes),
            "mean_witness_elements": statistics.fmean(witness_sizes),
            "mean_witness_reduction": 1.0
            - statistics.fmean(witness_sizes) / statistics.fmean(delta_sizes),
        },
        certificates,
    )


def run_scaling(
    results_dir: Path,
    measure_timing: bool = False,
    timing_repetitions: int = 7,
    timing_warmups: int = 1,
) -> tuple[
    dict[str, Any],
    list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
]:
    configurations = [
        (24, 6, 12, 1, 20),
        (24, 6, 12, 4, 20),
        (96, 8, 32, 1, 15),
        (96, 8, 32, 4, 15),
        (96, 8, 32, 8, 15),
        (256, 8, 64, 1, 8),
        (256, 8, 64, 4, 8),
        (256, 8, 64, 8, 8),
    ]
    rng = random.Random(271828)
    rows: list[dict[str, Any]] = []
    if timing_repetitions < 1:
        raise ValueError("timing repetitions must be positive")
    if timing_warmups < 0:
        raise ValueError("timing warmups must be nonnegative")
    timing_rows: list[dict[str, Any]] = []
    timing_case_rows: list[dict[str, Any]] = []
    sampled_certificates: list[
        tuple[dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = []
    full_family_obligations = 0
    incremental_family_obligations = 0
    full_rule_obligations = 0
    incremental_rule_obligations = 0
    semantic_disagreements = 0
    checked_certificates = 0
    baseline_total = 0
    baseline_correct = 0
    witness_sizes: list[int] = []
    delta_sizes: list[int] = []
    witness_by_class: dict[str, list[int]] = defaultdict(list)
    delta_by_class: dict[str, list[int]] = defaultdict(list)
    sampled_class_counts: Counter[str] = Counter()

    case_number = 0
    for target_count, family_count, rule_count, change_count, repetitions in configurations:
        for _ in range(repetitions):
            case_number += 1
            case = make_random_case(
                rng,
                f"generated-{case_number:03d}",
                target_count,
                family_count,
                rule_count,
                change_count,
            )
            spaces = candidate_space(case["old"], case["new"])

            # The old result is materialized before either new-version strategy,
            # as it would be in an evolving analyzer.  Timing, when requested,
            # excludes construction of this shared cache.
            cached_old = analyze_values(case["old"], spaces)

            full_counts = Counts()
            full_new = analyze_values(case["new"], spaces, full_counts)

            incremental_counts = Counts()
            incremental_new, affected = incremental_new_values(
                case["old"],
                case["new"],
                incremental_counts,
                cached_old=cached_old,
            )

            disagreements = sum(
                full_new[item] != incremental_new[item] for item in full_new
            )
            semantic_disagreements += disagreements
            full_family_obligations += full_counts.family_evaluations
            incremental_family_obligations += incremental_counts.family_evaluations
            full_rule_obligations += full_counts.rule_evaluations
            incremental_rule_obligations += incremental_counts.rule_evaluations

            actual_delta = compute_delta(case["old"], case["new"])
            classifications = {
                item: classify_values(cached_old[item], full_new[item])
                for item in cached_old
            }
            relevant = [
                (family, anchor)
                for family, anchor in sorted(affected)
                if classifications[key(family, anchor)] != "absent"
            ]
            for family, anchor in relevant:
                item = key(family, anchor)
                actual = classifications[item]
                predicted = textual_baseline(
                    case["old"],
                    case["new"],
                    family,
                    anchor,
                    actual_delta,
                    old_value=cached_old[item],
                )
                baseline_total += 1
                baseline_correct += int(actual == predicted)

            # Exact subset minimality has exponential cost in the number of
            # atomic changes and is not part of the scaling measurement.  One
            # deterministic non-absent candidate is checked for every case with
            # at most four atoms; all candidates still receive full/incremental
            # semantic comparison.
            certificate_candidates = relevant[:1] if len(actual_delta) <= 4 else []
            for family, anchor in certificate_candidates:
                certificate = make_certificate(
                    case["old"], case["new"], family, anchor, maximum_changes=4
                )
                accepted, diagnostic = check_certificate(
                    case["old"], case["new"], certificate, maximum_changes=4
                )
                if not accepted:
                    raise AssertionError(
                        f"generated certificate rejected: {case['id']} "
                        f"{family}|{anchor} {diagnostic}"
                    )
                checked_certificates += 1
                # Retain only compact 24-target cases for fault injection.  The
                # witness metrics still include every checked scaling size.
                if target_count <= 24:
                    sampled_certificates.append((case["old"], case["new"], certificate))
                certificate_class = certificate["classification"]
                sampled_class_counts[certificate_class] += 1
                witness_sizes.append(len(certificate["witness"]))
                delta_sizes.append(len(certificate["delta"]))
                witness_by_class[certificate_class].append(len(certificate["witness"]))
                delta_by_class[certificate_class].append(len(certificate["delta"]))

            if os.environ.get("DRIFT_PROGRESS"):
                print(
                    f"scaling-case={case_number} targets={target_count} "
                    f"changes={change_count}",
                    flush=True,
                )

            rows.append(
                {
                    "case": case["id"],
                    "targets": target_count,
                    "families": family_count,
                    "rules": rule_count,
                    "declared_changes": change_count,
                    "actual_delta_elements": len(actual_delta),
                    "candidate_count": len(spaces),
                    "affected_candidates": len(affected),
                    "affected_fraction": len(affected) / len(spaces),
                    "full_family_evaluations": full_counts.family_evaluations,
                    "incremental_family_evaluations": incremental_counts.family_evaluations,
                    "full_rule_evaluations": full_counts.rule_evaluations,
                    "incremental_rule_evaluations": incremental_counts.rule_evaluations,
                    "semantic_disagreements": disagreements,
                }
            )
            if measure_timing:
                # Warm both paths before observation.  Each measured pair is
                # preceded by a collection, runs with cyclic GC disabled, and
                # alternates which strategy goes first.  Instrumentation
                # counters are omitted from timing; both paths include
                # candidate-space construction and new-version validation,
                # while construction of the shared old cache is excluded.
                def run_full() -> dict[str, str]:
                    timed_spaces = candidate_space(case["old"], case["new"])
                    return analyze_values(case["new"], timed_spaces)

                def run_incremental() -> dict[str, str]:
                    values, _ = incremental_new_values(
                        case["old"], case["new"], cached_old=cached_old
                    )
                    return values

                # Generated models contain no reference cycles.  One
                # collection before the warmup/measurement block avoids
                # inheriting unrelated pending work without injecting a full
                # collection between every microbenchmark pair.
                gc.collect()
                for warmup in range(timing_warmups):
                    if (case_number + warmup) % 2:
                        warm_incremental = run_incremental()
                        warm_full = run_full()
                    else:
                        warm_full = run_full()
                        warm_incremental = run_incremental()
                    if warm_full != warm_incremental:
                        raise AssertionError("timing warmup changed semantics")
                    del warm_full, warm_incremental

                case_full_ns: list[int] = []
                case_incremental_ns: list[int] = []
                for repetition in range(timing_repetitions):
                    gc_was_enabled = gc.isenabled()
                    if gc_was_enabled:
                        gc.disable()
                    first_strategy = (
                        "incremental" if (case_number + repetition) % 2 else "full"
                    )
                    try:
                        if first_strategy == "full":
                            start = time.perf_counter_ns()
                            timed_full = run_full()
                            full_ns = time.perf_counter_ns() - start
                            start = time.perf_counter_ns()
                            timed_incremental = run_incremental()
                            incremental_ns = time.perf_counter_ns() - start
                        else:
                            start = time.perf_counter_ns()
                            timed_incremental = run_incremental()
                            incremental_ns = time.perf_counter_ns() - start
                            start = time.perf_counter_ns()
                            timed_full = run_full()
                            full_ns = time.perf_counter_ns() - start
                    finally:
                        if gc_was_enabled:
                            gc.enable()
                    if timed_full != timed_incremental or timed_full != full_new:
                        raise AssertionError("timed strategy changed semantics")
                    case_full_ns.append(full_ns)
                    case_incremental_ns.append(incremental_ns)
                    timing_rows.append(
                        {
                            "case": case["id"],
                            "targets": target_count,
                            "declared_changes": change_count,
                            "repetition": repetition + 1,
                            "first_strategy": first_strategy,
                            "full_time_us": full_ns / 1000,
                            "incremental_time_us": incremental_ns / 1000,
                            "runtime_ratio": incremental_ns / full_ns,
                        }
                    )
                    del timed_full, timed_incremental

                median_full_ns = statistics.median(case_full_ns)
                median_incremental_ns = statistics.median(case_incremental_ns)
                timing_case_rows.append(
                    {
                        "case": case["id"],
                        "targets": target_count,
                        "declared_changes": change_count,
                        "median_full_time_us": median_full_ns / 1000,
                        "median_incremental_time_us": median_incremental_ns / 1000,
                        "median_runtime_ratio": median_incremental_ns / median_full_ns,
                    }
                )

            # Detailed objects are intentionally per-case.  Release them before
            # constructing the next model so the sweep stays below the memory
            # cap even when Python retains nested-allocation arenas.
            del cached_old, full_new, incremental_new, classifications, case
            gc.collect()

    write_csv(
        results_dir / "scaling.csv",
        rows,
        [
            "case",
            "targets",
            "families",
            "rules",
            "declared_changes",
            "actual_delta_elements",
            "candidate_count",
            "affected_candidates",
            "affected_fraction",
            "full_family_evaluations",
            "incremental_family_evaluations",
            "full_rule_evaluations",
            "incremental_rule_evaluations",
            "semantic_disagreements",
        ],
    )

    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["targets"]), int(row["declared_changes"]))].append(row)
    aggregate_rows: list[dict[str, Any]] = []
    for (targets, changes), group in sorted(grouped.items()):
        aggregate_rows.append(
            {
                "targets": targets,
                "declared_changes": changes,
                "cases": len(group),
                "median_affected_fraction": statistics.median(
                    float(row["affected_fraction"]) for row in group
                ),
                "median_family_obligation_reduction": 1.0
                - statistics.median(
                    float(row["incremental_family_evaluations"])
                    / float(row["full_family_evaluations"])
                    for row in group
                ),
                "median_rule_obligation_reduction": 1.0
                - statistics.median(
                    float(row["incremental_rule_evaluations"])
                    / float(row["full_rule_evaluations"])
                    for row in group
                ),
            }
        )
    write_csv(
        results_dir / "scaling_aggregate.csv",
        aggregate_rows,
        [
            "targets",
            "declared_changes",
            "cases",
            "median_affected_fraction",
            "median_family_obligation_reduction",
            "median_rule_obligation_reduction",
        ],
    )

    if measure_timing:
        write_csv(
            results_dir / "timing_observations.csv",
            timing_rows,
            [
                "case",
                "targets",
                "declared_changes",
                "repetition",
                "first_strategy",
                "full_time_us",
                "incremental_time_us",
                "runtime_ratio",
            ],
        )
        write_csv(
            results_dir / "timing_case_medians.csv",
            timing_case_rows,
            [
                "case",
                "targets",
                "declared_changes",
                "median_full_time_us",
                "median_incremental_time_us",
                "median_runtime_ratio",
            ],
        )
        timing_groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        for row in timing_case_rows:
            timing_groups[(int(row["targets"]), int(row["declared_changes"]))].append(row)
        timing_aggregate: list[dict[str, Any]] = []
        for (targets, changes), group in sorted(timing_groups.items()):
            ratios = [float(row["median_runtime_ratio"]) for row in group]
            ratio_quartiles = statistics.quantiles(
                ratios, n=4, method="inclusive"
            )
            timing_aggregate.append(
                {
                    "targets": targets,
                    "declared_changes": changes,
                    "cases": len(group),
                    "median_full_time_us": statistics.median(
                        float(row["median_full_time_us"]) for row in group
                    ),
                    "median_incremental_time_us": statistics.median(
                        float(row["median_incremental_time_us"]) for row in group
                    ),
                    "median_runtime_ratio": statistics.median(
                        ratios
                    ),
                    "runtime_ratio_q1": ratio_quartiles[0],
                    "runtime_ratio_q3": ratio_quartiles[2],
                }
            )
        write_csv(
            results_dir / "timing_aggregate.csv",
            timing_aggregate,
            [
                "targets",
                "declared_changes",
                "cases",
                "median_full_time_us",
                "median_incremental_time_us",
                "median_runtime_ratio",
                "runtime_ratio_q1",
                "runtime_ratio_q3",
            ],
        )
        overall_ratios = [
            float(row["median_runtime_ratio"]) for row in timing_case_rows
        ]
        overall_quartiles = statistics.quantiles(
            overall_ratios, n=4, method="inclusive"
        )
        first_strategy_counts = Counter(
            str(row["first_strategy"]) for row in timing_rows
        )
        write_json(
            results_dir / "timing_summary.json",
            {
                "cases": len(timing_case_rows),
                "observed_pairs": len(timing_rows),
                "measurements_per_case_per_strategy": timing_repetitions,
                "warmup_pairs_per_case": timing_warmups,
                "alternating_first_strategy": True,
                "cyclic_gc_disabled_during_timed_pairs": True,
                "instrumentation_counters_excluded": True,
                "old_cache_construction_excluded": True,
                "candidate_space_construction_included": True,
                "new_version_validation_included": True,
                "median_runtime_ratio": statistics.median(
                    overall_ratios
                ),
                "runtime_ratio_q1": overall_quartiles[0],
                "runtime_ratio_q3": overall_quartiles[2],
                "first_strategy_counts": dict(sorted(first_strategy_counts.items())),
            },
        )

    return (
        {
            "cases": len(rows),
            "semantic_disagreements": semantic_disagreements,
            "full_family_obligations": full_family_obligations,
            "incremental_family_obligations": incremental_family_obligations,
            "family_obligation_reduction": 1.0
            - incremental_family_obligations / full_family_obligations,
            "full_rule_obligations": full_rule_obligations,
            "incremental_rule_obligations": incremental_rule_obligations,
            "rule_obligation_reduction": 1.0
            - incremental_rule_obligations / full_rule_obligations,
            "median_affected_fraction": statistics.median(
                float(row["affected_fraction"]) for row in rows
            ),
            "sampled_certificates_checked": checked_certificates,
            "textual_baseline_accuracy": (
                baseline_correct / baseline_total if baseline_total else None
            ),
            "textual_baseline_cases": baseline_total,
            "mean_sampled_delta_elements": (
                statistics.fmean(delta_sizes) if delta_sizes else 0.0
            ),
            "mean_sampled_witness_elements": (
                statistics.fmean(witness_sizes) if witness_sizes else 0.0
            ),
            "mean_sampled_witness_reduction": (
                1.0 - statistics.fmean(witness_sizes) / statistics.fmean(delta_sizes)
                if delta_sizes and statistics.fmean(delta_sizes)
                else 0.0
            ),
            "sampled_classification_counts": dict(sorted(sampled_class_counts.items())),
            "mean_nonpreserved_witness_reduction": (
                1.0
                - statistics.fmean(
                    [
                        size
                        for cls, values in witness_by_class.items()
                        if cls != "preserved"
                        for size in values
                    ]
                )
                / statistics.fmean(
                    [
                        size
                        for cls, values in delta_by_class.items()
                        if cls != "preserved"
                        for size in values
                    ]
                )
                if any(
                    cls != "preserved" and values
                    for cls, values in delta_by_class.items()
                )
                else 0.0
            ),
            "witness_metrics_by_class": {
                cls: {
                    "cases": len(witness_by_class[cls]),
                    "mean_delta_elements": statistics.fmean(delta_by_class[cls]),
                    "mean_witness_elements": statistics.fmean(witness_by_class[cls]),
                    "mean_reduction": 1.0
                    - statistics.fmean(witness_by_class[cls])
                    / statistics.fmean(delta_by_class[cls]),
                }
                for cls in sorted(witness_by_class)
            },
        },
        sampled_certificates,
    )


def run_faults(
    results_dir: Path,
    certificates: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    rejected = 0
    total = 0
    diagnostics: Counter[str] = Counter()
    for certificate_index, (old, new, certificate) in enumerate(certificates):
        for mutation_name, mutated in _mutations(certificate):
            accepted, diagnostic = check_certificate(old, new, mutated)
            total += 1
            rejected += int(not accepted)
            diagnostics[diagnostic] += 1
            rows.append(
                {
                    "certificate": certificate_index,
                    "mutation": mutation_name,
                    "accepted": int(accepted),
                    "diagnostic": diagnostic,
                }
            )
    write_csv(
        results_dir / "fault_injection.csv",
        rows,
        ["certificate", "mutation", "accepted", "diagnostic"],
    )
    return {
        "mutations": total,
        "rejected": rejected,
        "rejection_rate": rejected / total if total else None,
        "diagnostics": dict(sorted(diagnostics.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "result directory; relative paths are resolved beneath the artifact "
            "(default: reproduced-results)"
        ),
    )
    parser.add_argument(
        "--measure-timing",
        action="store_true",
        help="also write machine-dependent timing observations",
    )
    parser.add_argument(
        "--timing-repetitions",
        type=int,
        default=7,
        help="measured pairs per case when --measure-timing is enabled",
    )
    parser.add_argument(
        "--timing-warmups",
        type=int,
        default=1,
        help="unrecorded warmup pairs per case when --measure-timing is enabled",
    )
    args = parser.parse_args()
    artifact = args.artifact.resolve()
    data_dir = artifact / "data"
    if args.output is None:
        results_dir = artifact / "reproduced-results"
    elif args.output.is_absolute():
        results_dir = args.output
    else:
        results_dir = artifact / args.output
    results_dir = results_dir.resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    # Remove only known generated evidence from a prior run.
    for name in (
        "exhaustive_grid.csv",
        "public_cases.csv",
        "scaling.csv",
        "scaling_aggregate.csv",
        "timing_observations.csv",
        "timing_case_medians.csv",
        "timing_aggregate.csv",
        "timing_summary.json",
        "fault_injection.csv",
        "summary.json",
    ):
        path = results_dir / name
        if path.exists():
            path.unlink()
    cert_dir = results_dir / "certificates"
    if cert_dir.exists():
        for path in cert_dir.glob("*.json"):
            path.unlink()

    exhaustive = run_exhaustive(results_dir)
    public, public_certificates = run_public(results_dir, data_dir)
    scaling, generated_certificates = run_scaling(
        results_dir,
        measure_timing=args.measure_timing,
        timing_repetitions=args.timing_repetitions,
        timing_warmups=args.timing_warmups,
    )
    # Fault injection uses every public certificate and a deterministic prefix
    # from the generated sample to keep replay obligations bounded.
    faults = run_faults(
        results_dir,
        public_certificates + generated_certificates,
    )
    summary = {
        "exhaustive": exhaustive,
        "public_patterns": public,
        "generated_scaling": scaling,
        "fault_injection": faults,
    }
    write_json(results_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"results written to {results_dir}")


if __name__ == "__main__":
    main()
