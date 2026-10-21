import unittest
from crash_feed_inspector.analytics import describe, rolling_hit_rates, validate_multipliers, walk_forward_baseline

class AnalyticsTests(unittest.TestCase):
    def test_describe(self):
        result = describe([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(result["sample_size"], 4)
        self.assertEqual(result["median"], 2.5)
        self.assertEqual(result["historical_hit_rates"]["2.0"], 0.75)
    def test_invalid_values(self):
        with self.assertRaises(ValueError): validate_multipliers([1.2, float("nan")])
        with self.assertRaises(ValueError): validate_multipliers([0.9])
    def test_rolling(self):
        result = rolling_hit_rates([1.0, 2.0, 3.0], 2.0, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["historical_rate"], 0.5)
        self.assertEqual(result[1]["historical_rate"], 1.0)
    def test_walk_forward(self):
        result = walk_forward_baseline([1.0, 2.0] * 20, 2.0, min_train=10)
        self.assertEqual(result["evaluated_rounds"], 30)
        self.assertGreaterEqual(result["brier_score"], 0.0)
        self.assertLessEqual(result["brier_score"], 1.0)

if __name__ == "__main__": unittest.main()
