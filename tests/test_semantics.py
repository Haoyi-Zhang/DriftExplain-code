import copy
import unittest

from checker import check_certificate
from producer import (
    analyze,
    analyze_values,
    apply_operations,
    candidate_space,
    classify_candidate,
    compute_delta,
    evaluate_family,
    incremental_new_analysis,
    incremental_new_values,
    key,
    make_certificate,
    minimum_witness,
    validate_version,
)


def base_model(guard: str = "F") -> dict:
    return {
        "name": "unit",
        "targets": [{
            "anchor": "a",
            "raw": {"sink_raw": "T", "guard_raw": guard, "noise": "F"},
            "origins": {"sink_raw": "unit", "guard_raw": "unit", "noise": "unit"},
        }],
        "normalizer": {"sink": ["sink_raw"], "guard": ["guard_raw"]},
        "rules": [{
            "id": "r",
            "family": "f",
            "requires": ["sink"],
            "forbids": ["guard"],
        }],
    }


class SemanticTests(unittest.TestCase):
    def test_detailed_and_compact_paths_agree(self) -> None:
        model = base_model()
        spaces = candidate_space(model, model)
        detailed = analyze(model, spaces)
        compact = analyze_values(model, spaces)
        self.assertEqual(
            {item: evidence["value"] for item, evidence in detailed.items()}, compact
        )

    def test_four_change_classes(self) -> None:
        old = base_model("F")
        new = copy.deepcopy(old)
        self.assertEqual(classify_candidate(old, new, "f", "a")[0], "preserved")

        invalidated = base_model("T")
        self.assertEqual(
            classify_candidate(old, invalidated, "f", "a")[0], "invalidated"
        )

        newly = base_model("F")
        self.assertEqual(
            classify_candidate(base_model("T"), newly, "f", "a")[0],
            "newly_justified",
        )

        unresolved = copy.deepcopy(old)
        del unresolved["normalizer"]["sink"]
        self.assertEqual(
            classify_candidate(old, unresolved, "f", "a")[0], "unresolved"
        )

    def test_incremental_equals_full(self) -> None:
        old = base_model("F")
        old["targets"].append({
            "anchor": "b",
            "raw": {"sink_raw": "F", "guard_raw": "F", "noise": "F"},
            "origins": {"sink_raw": "unit", "guard_raw": "unit", "noise": "unit"},
        })
        new = copy.deepcopy(old)
        new["targets"][0]["raw"]["guard_raw"] = "T"
        spaces = candidate_space(old, new)
        cached = analyze_values(old, spaces)
        incremental, _ = incremental_new_values(old, new, cached_old=cached)
        self.assertEqual(incremental, analyze_values(new, spaces))

    def test_incorrect_cache_value_is_not_authenticated(self) -> None:
        old = base_model("F")
        old["targets"].append({
            "anchor": "b",
            "raw": {"sink_raw": "F", "guard_raw": "F", "noise": "F"},
            "origins": {"sink_raw": "unit", "guard_raw": "unit", "noise": "unit"},
        })
        new = copy.deepcopy(old)
        new["targets"][0]["raw"]["guard_raw"] = "T"
        spaces = candidate_space(old, new)
        cache = analyze_values(old, spaces)
        cache[key("f", "b")] = "T"  # deliberately false cached value
        incremental, affected = incremental_new_values(old, new, cached_old=cache)
        self.assertNotIn(("f", "b"), affected)
        self.assertNotEqual(incremental, analyze_values(new, spaces))

    def test_incremental_validates_old_endpoint_with_supplied_cache(self) -> None:
        old = base_model("F")
        new = copy.deepcopy(old)
        spaces = candidate_space(old, new)
        cached_analysis = analyze(old, spaces)
        cached_values = analyze_values(old, spaces)
        malformed_old = copy.deepcopy(old)
        malformed_old["targets"] = "not-a-list"

        with self.assertRaises(ValueError):
            incremental_new_analysis(
                malformed_old, new, cached_old=cached_analysis
            )
        with self.assertRaises(ValueError):
            incremental_new_values(
                malformed_old, new, cached_old=cached_values
            )

    def test_minimum_witness_is_cardinality_first_and_lexical(self) -> None:
        old = base_model("F")
        new = copy.deepcopy(old)
        new["targets"][0]["raw"]["guard_raw"] = "T"
        new["targets"][0]["raw"]["noise"] = "T"
        witness = minimum_witness(old, new, "f", "a")
        self.assertEqual(witness, ["program|a|guard_raw"])

    def test_checker_accepts_and_rejects(self) -> None:
        old = base_model("F")
        new = copy.deepcopy(old)
        new["targets"][0]["raw"]["guard_raw"] = "T"
        certificate = make_certificate(old, new, "f", "a")
        self.assertEqual(certificate["change_bound"], 12)
        accepted, diagnostic = check_certificate(old, new, certificate)
        self.assertTrue(accepted, diagnostic)

        mutated = copy.deepcopy(certificate)
        mutated["classification"] = "preserved"
        accepted, diagnostic = check_certificate(old, new, mutated)
        self.assertFalse(accepted)
        self.assertEqual(diagnostic, "classification")

        over_bound = copy.deepcopy(certificate)
        over_bound["change_bound"] = 0
        accepted, diagnostic = check_certificate(old, new, over_bound)
        self.assertFalse(accepted)
        self.assertEqual(diagnostic, "witness_bound")

        ghost_class, ghost_old, ghost_new = classify_candidate(
            old, new, "ghost-family", "a"
        )
        ghost = copy.deepcopy(certificate)
        ghost["candidate"] = {"family": "ghost-family", "anchor": "a"}
        ghost["classification"] = ghost_class
        ghost["old"] = ghost_old
        ghost["new"] = ghost_new
        ghost["witness"] = []
        accepted, diagnostic = check_certificate(old, new, ghost)
        self.assertFalse(accepted)
        self.assertEqual(diagnostic, "candidate_space")
        with self.assertRaises(ValueError):
            make_certificate(old, new, "ghost-family", "a")

        malformed = copy.deepcopy(old)
        malformed["targets"] = "not-a-list"
        accepted, diagnostic = check_certificate(malformed, new, certificate)
        self.assertFalse(accepted)
        self.assertEqual(diagnostic, "malformed_input")

        accepted, diagnostic = check_certificate(old, new, [])
        self.assertFalse(accepted)
        self.assertEqual(diagnostic, "certificate_shape")

    def test_identifier_grammar_prevents_serialized_key_collisions(self) -> None:
        malformed = base_model()
        malformed["targets"][0]["anchor"] = "a|b"
        with self.assertRaises(ValueError):
            validate_version(malformed)

        malformed = base_model()
        malformed["normalizer"]["sink"] = ["sink_raw", "sink_raw"]
        with self.assertRaises(ValueError):
            validate_version(malformed)

    def test_witness_reproduces_the_final_evidence_path(self) -> None:
        old = {
            "targets": [{
                "anchor": "t",
                "raw": {"a_raw": "F", "b_raw": "F", "x_raw": "F"},
                "origins": {
                    "a_raw": "old-a",
                    "b_raw": "old-b",
                    "x_raw": "old-x",
                },
            }],
            "normalizer": {"a": ["a_raw"], "b": ["b_raw"]},
            "rules": [
                {"id": "r1", "family": "f", "requires": ["a"], "forbids": []},
                {"id": "r2", "family": "f", "requires": ["b"], "forbids": []},
            ],
        }
        new = copy.deepcopy(old)
        new["targets"][0]["raw"]["a_raw"] = "T"
        new["targets"][0]["origins"]["a_raw"] = "changed-a"
        new["targets"][0]["raw"]["b_raw"] = "T"
        new["targets"][0]["origins"]["b_raw"] = "changed-b"
        new["normalizer"]["a"] = ["x_raw"]

        operations = compute_delta(old, new)
        misleading = next(
            operation for operation in operations
            if operation["id"] == "program|t|a_raw"
        )
        misleading_result = evaluate_family(
            apply_operations(old, [misleading]), "f", "t"
        )
        final_result = evaluate_family(new, "f", "t")
        self.assertEqual(misleading_result["value"], final_result["value"])
        self.assertNotEqual(misleading_result, final_result)

        self.assertEqual(
            minimum_witness(old, new, "f", "t"),
            ["normalizer|a", "program|t|b_raw"],
        )
        certificate = make_certificate(old, new, "f", "t")
        accepted, diagnostic = check_certificate(old, new, certificate)
        self.assertTrue(accepted, diagnostic)


if __name__ == "__main__":
    unittest.main()
