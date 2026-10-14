"""Explicit query regressions run in both normal and optimized Python."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
import candidate_query_check as experiment
import information_paths_check as paths_experiment


class QueryExecutionTests(unittest.TestCase):
    def test_identification_work_is_really_executed(self):
        report = experiment.boolean_regression(3)
        self.assertEqual(report['support_candidate_pairs'], 85)
        self.assertEqual(report['accepted_exact_supports'], 15)
        self.assertEqual(report['identification_queries_across_supports'], 34)

    def test_corrupted_identification_is_detected(self):
        with mock.patch.object(experiment, 'identify', return_value=frozenset()):
            with self.assertRaises(AssertionError):
                experiment.boolean_regression(1)

    def test_finite_measurement_retains_actual_checker_work(self):
        rows = experiment.finite_regression()
        self.assertEqual(len(rows), 12)
        sparse = next(row for row in rows if row['delta_atoms'] == 64 and row['support_atoms'] == 1)
        self.assertEqual(sparse['identification_checker_hybrid_replays'], 65)
        self.assertEqual(sparse['candidate_verifier_hybrid_replays'], 2)

    def test_disagreeing_receiver_cannot_produce_a_pass_report(self):
        one_case = list(paths_experiment.cases())[:1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'fresh-results'
            with mock.patch.object(paths_experiment, 'cases', return_value=one_case):
                with mock.patch.dict(paths_experiment.APIS,
                                     {'structure': lambda *args: (False, 'rejected')}):
                    with self.assertRaises(AssertionError):
                        paths_experiment.run(output)
            self.assertFalse((output / 'report.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
