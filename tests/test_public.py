import unittest
from collections import Counter
from pathlib import Path

from checker import check_certificate
from generate import load_public_fixtures, make_public_evolutions
from producer import make_certificate


class PublicPatternTests(unittest.TestCase):
    def test_public_pattern_matrix(self) -> None:
        artifact = Path(__file__).resolve().parents[1]
        fixtures = load_public_fixtures(artifact / "data" / "public_fixtures.json")
        cases = make_public_evolutions(fixtures)
        counts = Counter()
        self.assertEqual(len(fixtures), 9)
        self.assertEqual(len(cases), 36)
        for case in cases:
            cert = make_certificate(
                case["old"], case["new"], case["family"], case["anchor"]
            )
            accepted, diagnostic = check_certificate(case["old"], case["new"], cert)
            self.assertTrue(accepted, f"{case['id']}: {diagnostic}")
            counts[cert["classification"]] += 1
        self.assertEqual(
            counts,
            Counter({
                "preserved": 9,
                "newly_justified": 9,
                "invalidated": 9,
                "unresolved": 9,
            }),
        )


if __name__ == "__main__":
    unittest.main()
