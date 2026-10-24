import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from crash_feed_inspector.cli import main


class ResearchCliOrderingTests(unittest.TestCase):
    def run_research(self, csv_text):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as handle:
            handle.write(csv_text)
            path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["research-csv", str(path)])
        self.assertEqual(result, 0)
        return json.loads(output.getvalue())

    def test_missing_verified_timestamps_return_no_signal(self):
        report = self.run_research(
            "round_id,multiplier,verified,timestamp_utc\n"
            "r1,1.5,true,\n"
            "r2,2.0,true,\n"
        )
        self.assertEqual(report["research"]["status"], "no_signal_missing_timestamps")
        self.assertEqual(report["research"]["missing_timestamps"], 2)
        self.assertNotIn("threshold_results", report["research"])

    def test_out_of_order_verified_timestamps_return_no_signal(self):
        report = self.run_research(
            "round_id,multiplier,verified,timestamp_utc\n"
            "r2,2.0,true,2026-01-02T00:00:00Z\n"
            "r1,1.5,true,2026-01-01T00:00:00Z\n"
        )
        self.assertEqual(report["research"]["status"], "no_signal_chronology_invalid")
        self.assertEqual(report["research"]["chronology_violations"], 1)
        self.assertNotIn("threshold_results", report["research"])

    def run_analysis(self, csv_text):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as handle:
            handle.write(csv_text)
            path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["analyze-csv", str(path), "--min-train", "1"])
        self.assertEqual(result, 0)
        return json.loads(output.getvalue())

    def test_analyze_skips_walk_forward_when_verified_timestamps_are_missing(self):
        report = self.run_analysis(
            "round_id,multiplier,verified,timestamp_utc\n"
            "r1,1.5,true,\n"
            "r2,2.0,true,\n"
        )
        self.assertEqual(report["walk_forward_baseline"]["status"], "no_signal_missing_timestamps")
        self.assertNotIn("hit_rate", report["walk_forward_baseline"])

    def test_analyze_skips_walk_forward_when_verified_timestamps_are_out_of_order(self):
        report = self.run_analysis(
            "round_id,multiplier,verified,timestamp_utc\n"
            "r2,2.0,true,2026-01-02T00:00:00Z\n"
            "r1,1.5,true,2026-01-01T00:00:00Z\n"
        )
        self.assertEqual(report["walk_forward_baseline"]["status"], "no_signal_chronology_invalid")
        self.assertEqual(report["walk_forward_baseline"]["chronology_violations"], 1)


if __name__ == "__main__":
    unittest.main()
