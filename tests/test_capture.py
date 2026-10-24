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


class CaptureTests(unittest.TestCase):
    def run_capture(self, messages, environment):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        base = Path(temp_dir.name)
        fake_socket = FakeWebSocket([*messages, None])
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
