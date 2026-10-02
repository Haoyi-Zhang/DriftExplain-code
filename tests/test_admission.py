"""Admission, diagnostic, and cache-contract regression tests."""
from __future__ import annotations

import copy
import unittest

import checker
import producer


def model(guard: str = "F") -> dict:
    return {
        "targets": [
            {
                "anchor": "a",
                "raw": {"sink_raw": "T", "guard_raw": guard, "noise": "F"},
                "origins": {
                    "sink_raw": "unit",
                    "guard_raw": "unit",
                    "noise": "unit",
                },
            }
        ],
        "normalizer": {"sink": ["sink_raw"], "guard": ["guard_raw"]},
        "rules": [
            {
                "id": "r",
                "family": "f",
                "requires": ["sink"],
                "forbids": ["guard"],
            }
        ],
    }


class AdmissionTests(unittest.TestCase):
    def test_validate_version_rejects_malformed_structures(self) -> None:
        cases = []

        missing = model()
        del missing["targets"]
        cases.append(missing)

        wrong_container = model()
        wrong_container["rules"] = "not-a-list"
        cases.append(wrong_container)

        duplicate_anchor = model()
        duplicate_anchor["targets"].append(copy.deepcopy(duplicate_anchor["targets"][0]))
        cases.append(duplicate_anchor)

        bad_state = model()
        bad_state["targets"][0]["raw"]["sink_raw"] = "maybe"
        cases.append(bad_state)

        duplicate_alias = model()
        duplicate_alias["normalizer"]["sink"] = ["sink_raw", "sink_raw"]
        cases.append(duplicate_alias)

        duplicate_rule = model()
        duplicate_rule["rules"].append(copy.deepcopy(duplicate_rule["rules"][0]))
        cases.append(duplicate_rule)

        duplicate_literal = model()
        duplicate_literal["rules"][0]["requires"] = ["sink", "sink"]
        cases.append(duplicate_literal)

        invalid_identifier = model()
        invalid_identifier["rules"][0]["id"] = "bad|id"
        cases.append(invalid_identifier)

        for index, malformed in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaises((TypeError, ValueError)):
                    producer.validate_version(malformed)

    def test_extended_malformed_forms_are_rejected_by_both_implementations(self) -> None:
        malformed_models = []

        target_not_mapping = model()
        target_not_mapping["targets"] = ["not-a-mapping"]
        malformed_models.append(target_not_mapping)

        raw_not_mapping = model()
        raw_not_mapping["targets"][0]["raw"] = []
        malformed_models.append(raw_not_mapping)

        origins_not_mapping = model()
        origins_not_mapping["targets"][0]["origins"] = []
        malformed_models.append(origins_not_mapping)

        origin_not_string = model()
        origin_not_string["targets"][0]["origins"]["sink_raw"] = 7
        malformed_models.append(origin_not_string)

        normalizer_not_mapping = model()
        normalizer_not_mapping["normalizer"] = []
        malformed_models.append(normalizer_not_mapping)

        empty_aliases = model()
        empty_aliases["normalizer"]["sink"] = []
        malformed_models.append(empty_aliases)

        rule_not_mapping = model()
        rule_not_mapping["rules"] = ["not-a-mapping"]
        malformed_models.append(rule_not_mapping)

        bad_family = model()
        bad_family["rules"][0]["family"] = ""
        malformed_models.append(bad_family)

        bad_forbids = model()
        bad_forbids["rules"][0]["forbids"] = "guard"
        malformed_models.append(bad_forbids)

        for index, malformed in enumerate(malformed_models):
            with self.subTest(index=index):
                with self.assertRaises((TypeError, ValueError)):
                    producer.validate_version(malformed)
                self.assertEqual(
                    checker.check_certificate(malformed, model(), {}),
                    (False, "malformed_input"),
                )

    def test_checker_diagnostic_matrix(self) -> None:
        old = model("F")
        new = model("T")
        new["targets"][0]["raw"]["noise"] = "T"
        certificate = producer.make_certificate(old, new, "f", "a")

        mutations = []

        bad = copy.deepcopy(certificate)
        bad["schema"] = "other"
        mutations.append((bad, "schema"))

        bad = copy.deepcopy(certificate)
        bad["candidate"] = None
        mutations.append((bad, "candidate"))

        bad = copy.deepcopy(certificate)
        bad["candidate"] = {"family": "ghost", "anchor": "a"}
        mutations.append((bad, "candidate_space"))

        bad = copy.deepcopy(certificate)
        bad["change_bound"] = True
        mutations.append((bad, "witness_bound"))

        bad = copy.deepcopy(certificate)
        bad["old"] = {}
        mutations.append((bad, "old_evidence"))

        bad = copy.deepcopy(certificate)
        bad["new"] = {}
        mutations.append((bad, "new_evidence"))

        bad = copy.deepcopy(certificate)
        bad["classification"] = "preserved"
        mutations.append((bad, "classification"))

        bad = copy.deepcopy(certificate)
        bad["delta"] = list(reversed(bad["delta"]))
        mutations.append((bad, "delta"))

        bad = copy.deepcopy(certificate)
        bad["witness"] = "not-a-list"
        mutations.append((bad, "witness_shape"))

        bad = copy.deepcopy(certificate)
        bad["witness"] = [certificate["witness"][0], certificate["witness"][0]]
        mutations.append((bad, "witness_order"))

        bad = copy.deepcopy(certificate)
        bad["witness"] = ["program|a|ghost"]
        mutations.append((bad, "witness_member"))

        bad = copy.deepcopy(certificate)
        bad["witness"] = []
        mutations.append((bad, "witness_minimality"))

        for mutated, expected in mutations:
            with self.subTest(expected=expected):
                self.assertEqual(checker.check_certificate(old, new, mutated), (False, expected))

    def test_producer_rejects_invalid_candidate_and_bounds(self) -> None:
        old = model("F")
        new = model("T")
        new["targets"][0]["raw"]["noise"] = "T"

        with self.assertRaises(TypeError):
            producer.minimum_witness(old, new, "f", "a", True)
        with self.assertRaises(ValueError):
            producer.minimum_witness(old, new, "f", "a", -1)
        with self.assertRaises(ValueError):
            producer.minimum_witness(old, new, "ghost", "a")
        with self.assertRaises(ValueError):
            producer.minimum_witness(old, new, "f", "a", 1)

    def test_incremental_cache_requires_exact_union_space(self) -> None:
        old = model("F")
        new = model("T")
        with self.assertRaises(ValueError):
            producer.incremental_new_analysis(old, new, cached_old={})
        with self.assertRaises(ValueError):
            producer.incremental_new_values(old, new, cached_old={})


if __name__ == "__main__":
    unittest.main()
