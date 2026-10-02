"""Regression obligations for complete-evidence support, not source security."""
import ast
import copy
import unittest
from pathlib import Path
from unittest import mock

import checker
import producer
from support_study import directed_pairs, negative_control


def model():
    return {"targets": [{"anchor": "a", "raw": {"x": "F", "y": "F", "unused": "F"}}],
            "normalizer": {"p": ["x", "y"]},
            "rules": [{"id": "r", "family": "f", "requires": ["p"]}]}


class SupportTests(unittest.TestCase):
    def test_all_aliases_are_observed_even_when_one_decides_value(self):
        old, new = model(), model()
        new["targets"][0]["raw"].update(x="T", y="T")
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"),
                         ["program|a|x", "program|a|y"])

    def test_value_only_counterexample_has_two_alternative_minima(self):
        result = negative_control()
        self.assertEqual(result["value_sufficient_subsets"],
                         [["program|a|x"], ["program|a|y"],
                          ["program|a|x", "program|a|y"]])
        self.assertEqual(result["exact_sufficient_subsets"],
                         [["program|a|x", "program|a|y"]])

    def test_origin_only_support_with_unchanged_value(self):
        old, new = model(), model()
        new["targets"][0]["origins"] = {"x": "relocated"}
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"), ["program|a|x"])
        self.assertEqual(producer.classify_candidate(old, new, "f", "a")[0], "absent")

    def test_closed_world_origin_without_explicit_raw_is_observed(self):
        old, new = model(), model()
        old["targets"][0]["raw"].pop("x")
        new["targets"][0]["raw"].pop("x")
        new["targets"][0]["origins"] = {"x": "catalogued_absence"}
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"), ["program|a|x"])
        certificate = producer.make_certificate(old, new, "f", "a")
        self.assertEqual(checker.check_certificate(old, new, certificate), (True, "accepted"))
        self.assertEqual(certificate["new"]["rules"][0]["required"][0]["value"], "F")
        self.assertEqual(certificate["new"]["rules"][0]["required"][0]["observations"][0]["origin"],
                         "catalogued_absence")

    def test_added_target_and_old_only_family_rule_are_both_observable(self):
        old, new = model(), model()
        old["targets"] = []
        new["rules"] = []
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"),
                         ["rule|r", "target|a"])
        certificate = producer.make_certificate(old, new, "f", "a")
        self.assertEqual(certificate["old"]["reason"], "target_absent")
        self.assertEqual(certificate["new"]["reason"], "family_absent")
        self.assertEqual(checker.check_certificate(old, new, certificate), (True, "accepted"))

    def test_contradictory_literal_has_declared_three_valued_semantics(self):
        expected = {"F": "F", "T": "F", "U": "U"}
        for raw_value, family_value in expected.items():
            with self.subTest(raw_value=raw_value):
                old, new = model(), model()
                for endpoint in (old, new):
                    endpoint["targets"][0]["raw"]["x"] = raw_value
                    endpoint["rules"][0]["requires"] = ["p"]
                    endpoint["rules"][0]["forbids"] = ["p"]
                producer.validate_version(old)
                self.assertEqual(producer.evaluate_family(old, "f", "a")["value"], family_value)
                classification, _, replay = checker.replay_classification(old, new, "f", "a")
                self.assertEqual(replay["value"], family_value)
                self.assertIn(classification, {"preserved", "unresolved", "absent"})

    def test_ignored_rule_metadata_has_no_support(self):
        old, new = model(), model()
        new["rules"][0].update(forbids=[], note="ignored descriptive field")
        self.assertEqual(len(producer.compute_delta(old, new)), 1)
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"), [])

    def test_alias_order_is_evidence(self):
        old, new = model(), model()
        new["normalizer"]["p"] = ["y", "x"]
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"), ["normalizer|p"])

    def test_target_absence_precedes_rule_and_normalizer_lookup(self):
        old, new = model(), model()
        new.update(targets=[], rules=[], normalizer={})
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"), ["target|a"])
        cert = producer.make_certificate(old, new, "f", "a")
        self.assertEqual(checker.check_certificate(old, new, cert), (True, "accepted"))

    def test_added_target_is_atomic_and_not_split_into_program_changes(self):
        old, new = model(), model()
        old["targets"] = []
        new["rules"][0]["forbids"] = ["q"]
        self.assertEqual([d["kind"] for d in producer.compute_delta(old, new)],
                         ["rule", "target"])
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"),
                         ["rule|r", "target|a"])

    def test_family_move_changes_both_projections(self):
        old, new = model(), model()
        new["rules"][0]["family"] = "g"
        for family in ("f", "g"):
            self.assertEqual(producer.minimum_witness(old, new, family, "a"), ["rule|r"])
            certificate = producer.make_certificate(old, new, family, "a")
            self.assertEqual(checker.check_certificate(old, new, certificate),
                             (True, "accepted"))

    def test_only_final_aliases_require_observation_changes(self):
        old, new = model(), model()
        new["normalizer"]["p"] = ["y"]
        new["targets"][0]["raw"].update(x="T", y="T")
        self.assertEqual(producer.minimum_witness(old, new, "f", "a"),
                         ["normalizer|p", "program|a|y"])

    def test_full_patch_is_effectively_not_syntactically_equal(self):
        old, new = model(), model()
        old["targets"][0]["raw"]["x"] = "T"
        del new["targets"][0]["raw"]["x"]
        new["targets"][0]["description"] = "ignored target metadata"
        patch = producer.apply_operations(old, producer.compute_delta(old, new))
        self.assertNotEqual(patch, new)
        self.assertEqual(patch["targets"][0]["raw"]["x"], "F")
        self.assertEqual(producer.evaluate_family(patch, "f", "a"),
                         producer.evaluate_family(new, "f", "a"))

    def test_missing_essential_and_surplus_witness_are_rejected(self):
        old, new = model(), model()
        new["targets"][0]["raw"].update(x="T", unused="T")
        cert = producer.make_certificate(old, new, "f", "a")
        for witness in ([], ["program|a|unused", "program|a|x"]):
            bad = copy.deepcopy(cert)
            bad["witness"] = witness
            self.assertEqual(checker.check_certificate(old, new, bad),
                             (False, "witness_minimality"))

    def test_checker_has_no_producer_or_shared_analysis_import(self):
        source = Path(checker.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(item.name.split(".")[0] for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append((node.module or "").split(".")[0])
        self.assertLessEqual(set(imports), {"__future__", "copy", "itertools", "typing"})

    def test_larger_bound_is_explicit_not_self_authorized(self):
        old, new = model(), model()
        old["targets"][0]["raw"] = {f"x{i}": "F" for i in range(16)}
        new["targets"][0]["raw"] = {f"x{i}": "T" for i in range(16)}
        old["normalizer"]["p"] = list(old["targets"][0]["raw"])
        new["normalizer"]["p"] = list(old["targets"][0]["raw"])
        cert = producer.make_certificate(old, new, "f", "a", 64)
        self.assertEqual(checker.check_certificate(old, new, cert), (False, "witness_bound"))
        self.assertEqual(checker.check_certificate(old, new, cert, 64), (True, "accepted"))
        self.assertEqual(len(cert["witness"]), 16)

    def test_directed_shapes_agree_with_two_exhaustive_oracles(self):
        for name, old, new, family, anchor in directed_pairs():
            with self.subTest(case=name):
                direct = producer.minimum_witness(old, new, family, anchor)
                self.assertEqual(direct, producer.enumerated_witness(old, new, family, anchor))
                self.assertEqual(direct, checker.enumerated_witness(old, new, family, anchor, 12))

    def test_invalid_admission_bound_does_not_become_semantic_uncertainty(self):
        old, new = model(), model()
        cert = producer.make_certificate(old, new, "f", "a")
        for bound in (True, -1, "12"):
            self.assertEqual(checker.check_certificate(old, new, cert, bound),
                             (False, "checker_bound"))
        with mock.patch.object(checker, "_least_witness",
                               side_effect=AssertionError("deletion core replay")):
            self.assertEqual(checker.check_certificate(old, new, cert),
                             (False, "witness_consistency"))
