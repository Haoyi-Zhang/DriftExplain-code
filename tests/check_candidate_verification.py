"""Explicit candidate-verification regressions, separate from retained base receipts."""
import copy
import itertools
import unittest
from unittest import mock

import checker
import producer
from candidate_query_check import boolean_regression, finite_pair, finite_regression
from check_prepared_support import cases, oracle


class CandidateVerificationTests(unittest.TestCase):
    def test_candidate_verifier_on_48_independently_scanned_endpoint_pairs(self):
        for name, old, new, family, anchor in cases():
            with self.subTest(case=name):
                cert, sufficient = oracle(old, new, family, anchor)
                self.assertEqual(checker.check_candidate_certificate(old, new, cert),
                                 (True, "accepted"))
                for bits in itertools.product((False, True), repeat=len(cert["delta"])):
                    proposed = copy.deepcopy(cert)
                    proposed["witness"] = [a for a, chosen in zip(cert["delta"], bits) if chosen]
                    expected = proposed["witness"] == cert["witness"]
                    self.assertEqual(checker.check_candidate_certificate(old, new, proposed)[0], expected)

    def test_all_principal_filter_support_candidate_pairs(self):
        result = boolean_regression()
        self.assertEqual(result["support_candidate_pairs"], 5461)
        self.assertEqual(result["accepted_exact_supports"], 127)
        self.assertEqual(result["decision_disagreements"], 0)
        self.assertEqual(result["query_bound_violations"], 0)

    def test_instrumented_finite_counts_under_same_promises(self):
        rows = finite_regression()
        self.assertEqual(len(rows), 12)
        sparse = next(r for r in rows if r["delta_atoms"] == 64 and r["support_atoms"] == 1)
        self.assertEqual(sparse["identification_checker_hybrid_replays"], 65)
        self.assertEqual(sparse["candidate_verifier_hybrid_replays"], 2)

    def test_candidate_path_uses_no_discovery_or_producer_selector(self):
        old, new = finite_pair(4, 1)
        cert = producer.make_certificate(old, new, "f", "a")
        with mock.patch.object(checker, "_least_witness", side_effect=AssertionError("discovery")):
            with mock.patch.object(producer, "_minimum_witness_prepared",
                                   side_effect=AssertionError("producer projection")):
                self.assertEqual(checker.check_candidate_certificate(old, new, cert),
                                 (True, "accepted"))

    def test_every_subset_certificate_and_inputs_unchanged(self):
        # Exhaustive benign small finite records, including empty/full supports.
        for d in range(5):
            for k in range(d + 1):
                old, new = finite_pair(d, k)
                cert = producer.make_certificate(old, new, "f", "a")
                for bits in itertools.product((False, True), repeat=d):
                    bad = copy.deepcopy(cert)
                    bad["witness"] = [a for a, chosen in zip(cert["delta"], bits) if chosen]
                    saved = copy.deepcopy((old, new, bad))
                    decision = checker.check_candidate_certificate(old, new, bad)
                    self.assertEqual(decision[0], bad["witness"] == cert["witness"])
                    self.assertEqual(decision, checker.check_certificate(old, new, bad))
                    self.assertEqual((old, new, bad), saved)

    def test_admission_and_required_fields_match_identification_checker(self):
        old, new = finite_pair(4, 1)
        cert = producer.make_certificate(old, new, "f", "a")
        for field, replacement in (("schema", "bad"), ("candidate", None),
                                   ("candidate", {"family": "ghost", "anchor": "a"}),
                                   ("change_bound", True), ("change_bound", 0),
                                   ("old", {}), ("new", {}), ("classification", "bad"),
                                   ("delta", []), ("witness", "bad"),
                                   ("witness", [cert["witness"][0]] * 2),
                                   ("witness", ["program|a|ghost"]), ("witness", [])):
            bad = copy.deepcopy(cert)
            bad[field] = replacement
            self.assertEqual(checker.check_candidate_certificate(old, new, bad),
                             checker.check_certificate(old, new, bad))
        for bound in (True, -1, "12", 0):
            self.assertEqual(checker.check_candidate_certificate(old, new, cert, bound),
                             checker.check_certificate(old, new, cert, bound))
        self.assertEqual(checker.check_candidate_certificate({}, new, cert),
                         (False, "malformed_input"))
        self.assertEqual(checker.check_candidate_certificate(old, new, None),
                         (False, "certificate_shape"))

    def test_noncanonical_candidates_rejected_before_query(self):
        for universe, candidate in ((["b", "a"], []), (["a", "a"], []),
                                     (["a"], ["a", "a"]), (["a"], ["b"]),
                                     (["a"], "a"), (["a"], [1])):
            query = mock.Mock()
            with self.assertRaises(ValueError):
                checker.verify_candidate_witness(universe, candidate, query)
            query.assert_not_called()

    def test_monotonicity_only_gives_inclusion_minimality_not_leastness(self):
        query = lambda selected: bool(selected & {"x", "y"})
        self.assertTrue(checker.verify_candidate_witness(["x", "y"], ["x"], query))
        self.assertTrue(checker.verify_candidate_witness(["x", "y"], ["y"], query))
        self.assertFalse(query(frozenset()))

    def test_boundary_query_transcripts_and_consistency_failure(self):
        calls = []
        def empty_support(selected):
            calls.append(selected)
            return True
        self.assertTrue(checker.verify_candidate_witness([], [], empty_support))
        self.assertEqual(calls, [])
        self.assertTrue(checker.verify_candidate_witness(["a"], [], empty_support))
        self.assertEqual(calls, [frozenset()])
        calls.clear()
        def full_support(selected):
            calls.append(selected)
            return selected == frozenset({"a", "b"})
        self.assertTrue(checker.verify_candidate_witness(["a", "b"], ["a", "b"], full_support))
        self.assertEqual(calls, [frozenset({"b"}), frozenset({"a"})])
        old, new = finite_pair(4, 1)
        cert = producer.make_certificate(old, new, "f", "a")
        with mock.patch.object(checker, "_patch", side_effect=ValueError("inconsistent patch")):
            self.assertEqual(checker.check_candidate_certificate(old, new, cert),
                             (False, "witness_consistency"))


if __name__ == "__main__":
    unittest.main()
