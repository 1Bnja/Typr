import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "metrics-tests-only-secret-not-for-production")

from app.services.metrics import (
    calculate_ppm,
    calculate_precision,
    calculate_score,
    count_correct_chars,
)


class MetricsTests(unittest.TestCase):
    def test_matches_the_frontend_formulas(self):
        self.assertEqual(calculate_ppm(250, 60000), 50)
        self.assertEqual(calculate_ppm(1, 0), 0)
        self.assertEqual(calculate_precision(0, 0), 100)
        self.assertEqual(calculate_precision(11, 1), 90.9)
        self.assertEqual(calculate_score(50, 90), 45)

    def test_rounds_half_up_like_js(self):
        # round() de Python daría 0 (banker's rounding); Math.round de JS da 1.
        self.assertEqual(calculate_score(1, 50), 1)
        self.assertEqual(calculate_precision(8, 1), 87.5)

    def test_counts_only_matching_positions(self):
        self.assertEqual(count_correct_chars("hola", "hola"), 4)
        self.assertEqual(count_correct_chars("hxla", "hola"), 3)
        self.assertEqual(count_correct_chars("hola mundo", "hola"), 4)
        self.assertEqual(count_correct_chars("ho", "hola"), 2)


if __name__ == "__main__":
    unittest.main()
