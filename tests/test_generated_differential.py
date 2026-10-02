"""Generated finite stress checks against fixture and representation bias."""
import unittest

from generated_differential_check import run_check


class GeneratedDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_check()

    def test_generated_differential_has_no_disagreement(self):
        self.assertEqual(self.result["status"], "PASS", self.result["disagreements"][:3])
        self.assertEqual(self.result["totals"]["disagreements"], 0)

    def test_generated_surface_is_nontrivial(self):
        totals = self.result["totals"]
        self.assertGreaterEqual(totals["generated_endpoint_pairs"], 60)
        self.assertGreaterEqual(totals["candidate_pairs"], 200)
        self.assertGreaterEqual(totals["subset_replays"], 1000)

    def test_bijective_renaming_metamorphism(self):
        totals = self.result["totals"]
        self.assertEqual(totals["bijective_renaming_checks"], totals["candidate_pairs"])

    def test_container_order_metamorphism(self):
        totals = self.result["totals"]
        self.assertEqual(totals["container_order_checks"], totals["candidate_pairs"])


if __name__ == "__main__":
    unittest.main()
