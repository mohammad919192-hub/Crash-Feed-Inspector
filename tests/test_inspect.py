import json
import tempfile
import unittest
from pathlib import Path

from crash_feed_inspector.inspect import inspect_jsonl


class InspectJsonlTests(unittest.TestCase):
    def test_reports_candidate_paths_without_claiming_verification(self):
        payload = {
            "type": "round.completed",
            "data": {"round": {"id": "r-1", "multiplier": 2.45}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "messages.jsonl"
            path.write_text(json.dumps({"raw_sanitized": json.dumps(payload)}) + "\n", encoding="utf-8")
            result = inspect_jsonl(path)
        self.assertEqual(result["json_messages"], 1)
        self.assertEqual(result["event_type_value_counts"]["round.completed"], 1)
        self.assertEqual(result["multiplier_like_field_candidates"]["data.round.multiplier"], [2.45])
        self.assertIn("automatically verified", result["warning"].lower())

    def test_rejects_missing_file(self):
        with self.assertRaises(ValueError):
            inspect_jsonl(Path("not-a-real-capture-file.jsonl"))


if __name__ == "__main__":
    unittest.main()
