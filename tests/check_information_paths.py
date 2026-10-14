"""Owned benign regressions for invocation-local information and output safety."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import checker
import producer
import candidate_query_check
from check_prepared_support import cases, oracle


class InformationPathTests(unittest.TestCase):
    def test_identifier_reuses_admitted_delta_and_final_evidence(self):
        old, new = candidate_query_check.finite_pair(4, 1)
        cert = producer.make_certificate(old, new, "f", "a")
        with mock.patch.object(checker, "_changes", wraps=checker._changes) as changes:
            with mock.patch.object(checker, "_family_result", wraps=checker._family_result) as evidence:
                with mock.patch.object(checker, "_patch", wraps=checker._patch) as patch:
                    self.assertEqual(checker.check_certificate(old, new, cert), (True, "accepted"))
                    self.assertEqual(changes.call_count, 1)
                    self.assertEqual(evidence.call_count, patch.call_count + 2)

    def test_query_driver_refuses_occupied_output_before_computation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            sentinel = output / "summary.json"
            sentinel.write_text("owned-existing-result\n", encoding="utf-8")
            with mock.patch.object(candidate_query_check, "boolean_regression", return_value={}) as boolean:
                with mock.patch.object(candidate_query_check, "finite_regression", return_value=[{"x": 1}]):
                    with self.assertRaises(ValueError): candidate_query_check.run(output)
            boolean.assert_not_called()
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "owned-existing-result\n")

    def test_structure_visible_path_matches_literal_all_subset_oracle(self):
        for name, old, new, family, anchor in cases():
            cert, _ = oracle(old, new, family, anchor)
            for mask in range(1 << len(cert["delta"])):
                proposed = copy.deepcopy(cert)
                proposed["witness"] = [a for i, a in enumerate(cert["delta"]) if mask & (1 << i)]
                saved = copy.deepcopy((old, new, proposed))
                expected = (proposed["witness"] == cert["witness"])
                with self.subTest(case=name, mask=mask):
                    results = [api(old, new, proposed) for api in
                               (checker.check_certificate, checker.check_candidate_certificate,
                                checker.check_structural_certificate)]
                    self.assertEqual([r[0] for r in results], [expected] * 3)
                    self.assertEqual((old, new, proposed), saved)

    def test_structure_visible_path_uses_two_endpoints_and_no_hybrids(self):
        for d, k in ((0, 0), (4, 0), (4, 1), (4, 4), (64, 1)):
            old, new = candidate_query_check.finite_pair(d, k)
            cert = producer.make_certificate(old, new, "f", "a", 64)
            with mock.patch.object(checker, "_patch", side_effect=AssertionError("hybrid")):
                with mock.patch.object(checker, "_changes", wraps=checker._changes) as changes:
                    with mock.patch.object(checker, "_family_result", wraps=checker._family_result) as evidence:
                        self.assertEqual(checker.check_structural_certificate(old, new, cert, 64), (True, "accepted"))
                        self.assertEqual(changes.call_count, 1)
                        self.assertEqual(evidence.call_count, 2)

    def test_structure_visible_path_does_not_import_producer_or_query_helpers(self):
        old, new = candidate_query_check.finite_pair(4, 1)
        cert = producer.make_certificate(old, new, "f", "a")
        with mock.patch.object(producer, "_minimum_witness_prepared", side_effect=AssertionError("producer")):
            with mock.patch.object(checker, "_least_witness", side_effect=AssertionError("discovery")):
                with mock.patch.object(checker, "verify_candidate_witness", side_effect=AssertionError("query verifier")):
                    self.assertEqual(checker.check_structural_certificate(old, new, cert), (True, "accepted"))

    def test_structure_visible_admission_matches_replay_paths(self):
        old, new = candidate_query_check.finite_pair(4, 1)
        cert = producer.make_certificate(old, new, "f", "a")
        for field, value in (("schema", "other"), ("old", {}), ("new", {}),
                             ("delta", []), ("change_bound", True),
                             ("classification", "other"), ("witness", []),
                             ("witness", ["program|a|missing"])):
            changed = copy.deepcopy(cert); changed[field] = value
            self.assertEqual(checker.check_structural_certificate(old, new, changed),
                             checker.check_candidate_certificate(old, new, changed))

    def test_invocation_local_data_does_not_leak_between_endpoint_pairs(self):
        old, new = candidate_query_check.finite_pair(4, 1)
        first = producer.make_certificate(old, new, "f", "a")
        self.assertTrue(checker.check_certificate(old, new, first)[0])
        new["normalizer"]["p"] = ["x01"]
        second = producer.make_certificate(old, new, "f", "a")
        self.assertNotEqual(first["witness"], second["witness"])
        for api in (checker.check_certificate, checker.check_candidate_certificate,
                    checker.check_structural_certificate):
            self.assertTrue(api(old, new, second)[0])
            self.assertFalse(api(old, new, first)[0])


if __name__ == "__main__": unittest.main()
