import json
import unittest

from crash_feed_inspector.protocol import get_path, parse_final_result

SAMPLE = {
    "type": "round.completed",
    "data": {
        "round": {"id": "demo-001", "multiplier": "2.35x"},
        "ended_at": "2026-01-02T03:04:05+03:00",
    },
}


class ProtocolTests(unittest.TestCase):
    def test_nested_path_and_array_index(self):
        self.assertEqual(get_path({"data": {"items": [{"value": 4}]}}, "data.items[0].value"), 4)

    def test_non_final_event_is_ignored(self):
        raw = json.dumps({"type": "round.started", "data": {"round": {"id": "a", "multiplier": 2}}})
        self.assertIsNone(parse_final_result(
            raw, event_type_path="type", final_event_types=["round.completed"],
            round_id_path="data.round.id", multiplier_path="data.round.multiplier",
        ))

    def test_explicit_final_event_is_candidate_not_verified(self):
        result = parse_final_result(
            json.dumps(SAMPLE), event_type_path="type", final_event_types=["round.completed"],
            round_id_path="data.round.id", multiplier_path="data.round.multiplier",
            timestamp_path="data.ended_at", source="synthetic_fixture", schema_version="fixture-v1",
        )
        self.assertEqual(result["round_id"], "demo-001")
        self.assertEqual(result["multiplier"], 2.35)
        self.assertEqual(result["timestamp_utc"], "2026-01-02T00:04:05Z")
        self.assertFalse(result["verified"])
        self.assertEqual(result["verification_status"], "pending_manual_confirmation")

    def test_invalid_multiplier_fails_closed(self):
        raw = json.dumps({"type": "done", "id": "r1", "multiplier": float("nan")})
        with self.assertRaises(ValueError):
            parse_final_result(
                raw, event_type_path="type", final_event_types=["done"],
                round_id_path="id", multiplier_path="multiplier",
            )

    def test_timezone_required(self):
        raw = json.dumps({"type": "done", "id": "r1", "multiplier": 1.5, "time": "2026-01-02T03:04:05"})
        with self.assertRaises(ValueError):
            parse_final_result(
                raw, event_type_path="type", final_event_types=["done"],
                round_id_path="id", multiplier_path="multiplier", timestamp_path="time",
            )

    def test_invalid_configuration_rejected(self):
        with self.assertRaises(ValueError):
            parse_final_result("{}", event_type_path="type", final_event_types=[],
                               round_id_path="id", multiplier_path="multiplier")


if __name__ == "__main__":
    unittest.main()
