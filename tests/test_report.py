import tempfile
import unittest
from pathlib import Path

from crash_feed_inspector.report import generate_dashboard


class ReportTests(unittest.TestCase):
    def test_dashboard_uses_verified_rows_and_omits_round_ids(self):
        rows = [
            {"round_id": "private-round-1", "multiplier": 1.5, "verified": True,
             "timestamp_utc": "2026-01-01T00:00:00Z", "source": "test", "schema_version": "v1"},
            {"round_id": "private-round-2", "multiplier": 9999.0, "verified": False,
             "timestamp_utc": None, "source": "test", "schema_version": "v1"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = generate_dashboard(rows, Path(directory) / "dashboard.html", threshold=2.0)
            html = output.read_text(encoding="utf-8")
        self.assertIn("Verified rounds", html)
        self.assertIn("1.500x", html)
        self.assertNotIn("9999", html)
        self.assertNotIn("private-round", html)
        self.assertIn("Historical frequencies", html)

    def test_dashboard_refuses_unverified_only_data(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No rows are explicitly verified"):
                generate_dashboard(
                    [{"round_id": "r1", "multiplier": 2.0, "verified": False}],
                    Path(directory) / "dashboard.html",
                )


if __name__ == "__main__":
    unittest.main()
