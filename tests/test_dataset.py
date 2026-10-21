import tempfile
import unittest
from pathlib import Path

from crash_feed_inspector.dataset import load_rounds_csv, quality_report, verified_multipliers


class DatasetTests(unittest.TestCase):
    def write_csv(self, content):
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, suffix=".csv")
        temp.write(content)
        temp.close()
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        return temp.name

    def test_load_defaults_to_unverified_and_normalizes_timezone(self):
        path = self.write_csv(
            "round_id,multiplier,timestamp_utc,source,verified\n"
            "r1,1.5,2026-01-01T03:00:00+03:00,test,false\n"
            "r2,2.0,,test,true\n"
        )
        rows = load_rounds_csv(path)
        self.assertEqual(rows[0]["timestamp_utc"], "2026-01-01T00:00:00Z")
        self.assertFalse(rows[0]["verified"])
        self.assertEqual(verified_multipliers(rows), [2.0])

    def test_duplicate_ids_rejected(self):
        path = self.write_csv("round_id,multiplier\nr1,1.2\nr1,1.5\n")
        with self.assertRaisesRegex(ValueError, "duplicate round_id"):
            load_rounds_csv(path)

    def test_invalid_multiplier_rejected(self):
        path = self.write_csv("round_id,multiplier\nr1,nan\n")
        with self.assertRaisesRegex(ValueError, "finite and >= 1.0"):
            load_rounds_csv(path)

    def test_missing_required_column_rejected(self):
        path = self.write_csv("id,value\nr1,2.0\n")
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            load_rounds_csv(path)

    def test_quality_report_flags_out_of_order_timestamps(self):
        rows = [
            {"timestamp_utc": "2026-01-02T00:00:00Z", "verified": True},
            {"timestamp_utc": "2026-01-01T00:00:00Z", "verified": False},
            {"timestamp_utc": None, "verified": False},
        ]
        report = quality_report(rows)
        self.assertEqual(report["row_count"], 3)
        self.assertEqual(report["chronology_violations"], 1)
        self.assertEqual(report["missing_timestamps"], 1)
        self.assertEqual(report["verified_rows"], 1)

    def test_empty_dataset_rejected(self):
        with self.assertRaises(ValueError):
            quality_report([])

    def test_duplicate_headers_rejected(self):
        path = self.write_csv("round_id,round_id,multiplier\nr1,r2,2.0\n")
        with self.assertRaisesRegex(ValueError, "duplicate column names"):
            load_rounds_csv(path)

    def test_extra_values_rejected(self):
        path = self.write_csv("round_id,multiplier\nr1,2.0,unexpected\n")
        with self.assertRaisesRegex(ValueError, "more values than the header"):
            load_rounds_csv(path)


if __name__ == "__main__":
    unittest.main()
