import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crash_feed_inspector import capture as capture_module
from crash_feed_inspector.dataset import load_rounds_csv


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.closed = False

    def recv(self):
        return next(self.messages)

    def close(self):
        self.closed = True
        if getattr(self, "close_error", False):
            raise RuntimeError("simulated close failure")


class CaptureTests(unittest.TestCase):
    def run_capture(self, messages, environment, *, close_error=False, existing_csv=None, expect_error=False):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        base = Path(temp_dir.name)
        if existing_csv is not None:
            (base / "rounds.csv").write_text(existing_csv, encoding="utf-8")
        fake_socket = FakeWebSocket([*messages, None])
        fake_socket.close_error = close_error
        env = {
            "CRASH_WS_URL": "wss://example.invalid/feed",
            "MAX_MESSAGES": "10",
            "WS_TIMEOUT_SECONDS": "1",
            **environment,
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(capture_module, "load_dotenv"),
            patch.object(capture_module.websocket, "create_connection", return_value=fake_socket),
            patch.object(capture_module, "DATA_DIR", base),
            patch.object(capture_module, "RAW_PATH", base / "messages.jsonl"),
            patch.object(capture_module, "CSV_PATH", base / "rounds.csv"),
        ):
            if expect_error:
                with self.assertRaises(SystemExit):
                    capture_module.capture()
            else:
                capture_module.capture()
        return base, fake_socket

    def test_capture_without_mapping_does_not_infer_numbers_and_redacts_secrets(self):
        raw = json.dumps({"type": "round.completed", "id": "r1", "multiplier": 2.5, "token": "private-value"})
        base, fake_socket = self.run_capture([raw], {})
        self.assertTrue(fake_socket.closed)
        self.assertNotIn("private-value", (base / "messages.jsonl").read_text(encoding="utf-8"))
        with (base / "rounds.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows, [])

    def test_connection_error_does_not_leak_endpoint_credentials(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        secret_url = "wss://user:private-pass@example.invalid/feed?token=private-token"
        failure = RuntimeError(f"connection failed for {secret_url}")
        with (
            patch.dict(os.environ, {"CRASH_WS_URL": secret_url}, clear=True),
            patch.object(capture_module, "load_dotenv"),
            patch.object(capture_module, "DATA_DIR", Path(temp_dir.name)),
            patch.object(capture_module.websocket, "create_connection", side_effect=failure),
        ):
            with self.assertRaises(SystemExit) as raised:
                capture_module.capture()
        message = str(raised.exception)
        self.assertNotIn("private-pass", message)
        self.assertNotIn("private-token", message)
        self.assertIn("endpoint details suppressed", message)

    def test_close_error_does_not_discard_captured_csv(self):
        base, fake_socket = self.run_capture([], {}, close_error=True)
        self.assertTrue(fake_socket.closed)
        self.assertTrue((base / "rounds.csv").is_file())
        with (base / "rounds.csv").open(encoding="utf-8", newline="") as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])

    def test_capture_preserves_prior_rounds_and_adds_new_candidates(self):
        raw = json.dumps({
            "type": "round.completed",
            "data": {"round": {"id": "round-2", "multiplier": 3.0}},
        })
        config = {
            "CRASH_EVENT_TYPE_PATH": "type",
            "CRASH_FINAL_EVENT_TYPES": "round.completed",
            "CRASH_ROUND_ID_PATH": "data.round.id",
            "CRASH_MULTIPLIER_PATH": "data.round.multiplier",
            "CRASH_SCHEMA_VERSION": "synthetic-test-v1",
        }
        existing = (
            "round_id,timestamp_utc,multiplier,source,verified,schema_version\\n"
            "round-1,2026-01-01T00:00:00Z,2.0,fixture,false,fixture-v1\\n"
        )
        base, _ = self.run_capture([raw], config, existing_csv=existing)
        rows = load_rounds_csv(base / "rounds.csv")
        self.assertEqual([row["round_id"] for row in rows], ["round-1", "round-2"])

    def test_duplicate_round_across_captures_is_not_added_twice(self):
        raw = json.dumps({
            "type": "round.completed",
            "data": {"round": {"id": "round-1", "multiplier": 2.0}},
        })
        config = {
            "CRASH_EVENT_TYPE_PATH": "type",
            "CRASH_FINAL_EVENT_TYPES": "round.completed",
            "CRASH_ROUND_ID_PATH": "data.round.id",
            "CRASH_MULTIPLIER_PATH": "data.round.multiplier",
            "CRASH_SCHEMA_VERSION": "synthetic-test-v1",
        }
        existing = (
            "round_id,timestamp_utc,multiplier,source,verified,schema_version\\n"
            "round-1,2026-01-01T00:00:00Z,2.0,fixture,false,fixture-v1\\n"
        )
        base, _ = self.run_capture([raw], config, existing_csv=existing)
        rows = load_rounds_csv(base / "rounds.csv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["multiplier"], 2.0)

    def test_conflicting_candidate_does_not_overwrite_existing_history(self):
        raw = json.dumps({
            "type": "round.completed",
            "data": {"round": {"id": "round-1", "multiplier": 2.75}},
        })
        config = {
            "CRASH_EVENT_TYPE_PATH": "type",
            "CRASH_FINAL_EVENT_TYPES": "round.completed",
            "CRASH_ROUND_ID_PATH": "data.round.id",
            "CRASH_MULTIPLIER_PATH": "data.round.multiplier",
            "CRASH_SCHEMA_VERSION": "synthetic-test-v1",
        }
        existing = (
            "round_id,timestamp_utc,multiplier,source,verified,schema_version\\n"
            "round-1,2026-01-01T00:00:00Z,2.0,fixture,false,fixture-v1\\n"
        )
        base, _ = self.run_capture([raw], config, existing_csv=existing)
        rows = load_rounds_csv(base / "rounds.csv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["multiplier"], 2.0)

    def test_invalid_existing_csv_is_not_overwritten(self):
        invalid = "round_id,multiplier\\nround-1,not-a-number\\n"
        base, _ = self.run_capture([], {}, existing_csv=invalid, expect_error=True)
        self.assertEqual((base / "rounds.csv").read_text(encoding="utf-8"), invalid)

    def test_configured_mapping_emits_unverified_candidate(self):
        raw = json.dumps({
            "type": "round.completed",
            "data": {"round": {"id": "round-7", "multiplier": 2.75}},
        })
        config = {
            "CRASH_EVENT_TYPE_PATH": "type",
            "CRASH_FINAL_EVENT_TYPES": "round.completed",
            "CRASH_ROUND_ID_PATH": "data.round.id",
            "CRASH_MULTIPLIER_PATH": "data.round.multiplier",
            "CRASH_SCHEMA_VERSION": "synthetic-test-v1",
        }
        base, fake_socket = self.run_capture([raw], config)
        rows = load_rounds_csv(base / "rounds.csv")
        self.assertTrue(fake_socket.closed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["round_id"], "round-7")
        self.assertEqual(rows[0]["multiplier"], 2.75)
        self.assertFalse(rows[0]["verified"])


if __name__ == "__main__":
    unittest.main()
