import json
import unittest
from pathlib import Path


class ResultInvariantTests(unittest.TestCase):
    def test_frozen_result_invariants(self) -> None:
        artifact = Path(__file__).resolve().parents[1]
        summary = json.loads((artifact / "results" / "summary.json").read_text())
        exhaustive = summary["exhaustive"]
        self.assertEqual(exhaustive["classification_replays"], 8748)
        self.assertEqual(exhaustive["classification_agreements"], 8748)
        self.assertEqual(exhaustive["minimality_certificates_checked"], 301)
        self.assertEqual(exhaustive["minimality_certificates_accepted"], 301)

        public = summary["public_patterns"]
        self.assertEqual(public["fixtures"], 9)
        self.assertEqual(public["evolutions"], 36)
        self.assertEqual(public["checker_acceptance_rate"], 1.0)

        scaling = summary["generated_scaling"]
        self.assertEqual(scaling["semantic_disagreements"], 0)

        # The retained timing/scaling campaign exceeded its frozen obligation
        # ceiling.  Preserve its semantic-disagreement invariant, but do not turn
        # a favorable reduction metric into a completion gate.
        accounting = json.loads(
            (artifact / "results" / "resource_accounting.json").read_text()
        )
        self.assertEqual(
            accounting["status"], "EMPIRICAL_CAMPAIGN_TERMINATED_OVER_CAP"
        )
        self.assertGreater(
            accounting["timing_candidate_evaluations_lower_bound"],
            accounting["declared_campaign_obligation_cap"],
        )
        self.assertFalse(accounting["budget_reset"])
        self.assertFalse(accounting["positive_performance_claims_allowed"])
        verification = accounting["current_post_disposition_verification"]
        self.assertEqual(verification["unit_tests"]["methods"], 46)
        self.assertEqual(verification["unit_tests"]["status"], "PASS")
        self.assertEqual(
            verification["campaign_effect"],
            "none; the empirical campaign remains terminated over cap",
        )
        self.assertEqual(
            verification["generated_differential_check"]["disagreements"], 0
        )

        faults = summary["fault_injection"]
        self.assertEqual(faults["mutations"], 638)
        self.assertEqual(faults["rejected"], 638)
        self.assertEqual(faults["diagnostics"]["certificate_shape"], 58)


if __name__ == "__main__":
    unittest.main()
