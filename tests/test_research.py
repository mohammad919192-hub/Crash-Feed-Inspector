import unittest

from crash_feed_inspector.research import research_report, wilson_interval


class ResearchReportTests(unittest.TestCase):
    def test_wilson_interval_contains_observed_rate(self):
        low, high = wilson_interval(50, 100)
        self.assertLessEqual(low, 0.5)
        self.assertGreaterEqual(high, 0.5)
        self.assertGreater(low, 0.3)
        self.assertLess(high, 0.7)

    def test_insufficient_history_returns_no_signal(self):
        report = research_report([1.2, 2.4, 1.1], thresholds=(2.0,), windows=(2,), min_history=10)
        result = report["threshold_results"]["2.0"]
        self.assertEqual(result["status"], "no_signal_insufficient_history")
        self.assertFalse(result["filters"]["minimum_history_passed"])

    def test_recent_instability_returns_no_signal(self):
        data = [1.1] * 80 + [3.0] * 20
        report = research_report(
            data,
            thresholds=(2.0,),
            windows=(20, 100),
            min_history=50,
            max_window_rate_gap=0.15,
        )
        result = report["threshold_results"]["2.0"]
        self.assertEqual(result["status"], "no_signal_unstable_history")
        self.assertFalse(result["filters"]["window_stability_passed"])

    def test_stable_history_is_not_called_a_prediction(self):
        data = [1.1, 2.2] * 100
        report = research_report(
            data,
            thresholds=(2.0,),
            windows=(30, 100, 200),
            min_history=100,
            max_window_rate_gap=0.15,
        )
        result = report["threshold_results"]["2.0"]
        self.assertEqual(result["status"], "historical_rate_only_no_next_round_claim")
        self.assertIn("not a reliable prediction", report["interpretation"])

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            research_report([1.1, 2.0], windows=(0,))


if __name__ == "__main__":
    unittest.main()
