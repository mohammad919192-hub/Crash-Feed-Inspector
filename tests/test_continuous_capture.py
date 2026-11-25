"""Regression tests for the adapted 1xBet SignalR collector.

These tests use synthetic protocol fixtures only. They do not claim that the
undocumented upstream endpoint is currently reachable or that its schema is
officially guaranteed.
"""
import csv
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from crash_feed_inspector import continuous_capture as collector


class SignalRFrameTests(unittest.TestCase):
    def test_frames_split_signalr_record_separator(self):
        frames = collector._frames(
            '{"type":6}\x1e{"type":1,"target":"OnCrash","arguments":[{"l":42,"f":2.5,"ts":1760000000000}]}\x1e'
        )
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0]["type"], 6)
        self.assertEqual(frames[1]["target"], "OnCrash")

    def test_frames_ignore_malformed_and_non_object_frames(self):
        frames = collector._frames('not-json\x1e[]\x1e{"type":6}\x1e')
        self.assertEqual(frames, [{"type": 6}])


class SignalRNormalizationTests(unittest.TestCase):
    def test_epoch_milliseconds_normalize_to_utc(self):
        value = collector._utc_from_epoch_ms(1760000000000)
        self.assertTrue(value.endswith("Z"))
        self.assertEqual(
            datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo,
            timezone.utc,
        )

    def test_timestamp_rejects_boolean_zero_fraction_and_non_finite(self):
        for value in (True, 0, 1.5, float("nan"), float("inf"), "not-a-time"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    collector._utc_from_epoch_ms(value)

    def test_multiplier_must_match_supabase_numeric_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(collector, "DATA_DIR", Path(directory)), patch.object(
                collector, "DB_PATH", Path(directory) / "collector.sqlite3"
            ):
                conn = collector._db()
                self.addCleanup(conn.close)
                base = {"l": "r-1", "f": 2.12345, "ts": 1760000000000}
                with self.assertRaises(ValueError):
                    collector._save_round(conn, base)
                with self.assertRaises(ValueError):
                    collector._save_round(conn, {**base, "l": None, "f": 2.5})
                for invalid in (True, 0.99, float("nan"), float("inf"), 100000000):
                    with self.subTest(multiplier=invalid):
                        with self.assertRaises((ValueError, TypeError, OverflowError)):
                            collector._save_round(conn, {**base, "f": invalid})

    def test_valid_oncrash_round_is_saved_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(collector, "DATA_DIR", Path(directory)), patch.object(
                collector, "DB_PATH", Path(directory) / "collector.sqlite3"
            ):
                conn = collector._db()
                self.addCleanup(conn.close)
                status = collector._save_round(
                    conn, {"l": "round-7", "f": 2.75, "ts": 1760000000000}
                )
                row = conn.execute(
                    "SELECT round_id,multiplier,verified,schema_version FROM crash_rounds"
                ).fetchone()
                self.assertEqual(status, "saved")
                self.assertEqual(row[0], "round-7")
                self.assertEqual(row[1], 2.75)
                self.assertEqual(row[2], 0)
                self.assertEqual(row[3], "signalr-oncrash-l-f-ts-v1")

    def test_duplicate_is_idempotent_and_conflict_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(collector, "DATA_DIR", Path(directory)), patch.object(
                collector, "DB_PATH", Path(directory) / "collector.sqlite3"
            ):
                conn = collector._db()
                self.addCleanup(conn.close)
                payload = {"l": "round-8", "f": 2.5, "ts": 1760000000000}
                self.assertEqual(collector._save_round(conn, payload), "saved")
                self.assertEqual(collector._save_round(conn, payload), "duplicate")
                self.assertEqual(
                    collector._save_round(conn, {**payload, "f": 3.0}), "conflict"
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM crash_rounds").fetchone()[0], 1
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM collector_conflicts").fetchone()[0], 1
                )

    def test_csv_export_always_marks_rows_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(collector, "DATA_DIR", root), patch.object(
                collector, "DB_PATH", root / "collector.sqlite3"
            ), patch.object(collector, "CSV_PATH", root / "rounds.csv"):
                conn = collector._db()
                self.addCleanup(conn.close)
                collector._save_round(
                    conn, {"l": "round-9", "f": 1.25, "ts": 1760000000000}
                )
                collector._export_csv(conn)
                with (root / "rounds.csv").open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["verified"], "false")


    def test_server_close_frame_is_treated_as_disconnect(self):
        class FakeSocket:
            def send(self, value):
                raise AssertionError("close frame must not be answered as a ping")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(collector, "DATA_DIR", root), patch.object(
                collector, "DB_PATH", root / "collector.sqlite3"
            ):
                conn = collector._db()
                self.addCleanup(conn.close)
                totals = {"messages": 0, "saved": 0, "duplicates": 0, "conflicts": 0, "sync_errors": 0}
                with self.assertRaises(ConnectionError):
                    collector._process_signalr_events([{"type": 7}], FakeSocket(), conn, totals)

    def test_coalesced_oncrash_event_is_processed_and_ping_is_answered(self):
        class FakeSocket:
            def __init__(self):
                self.sent = []

            def send(self, value):
                self.sent.append(value)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(collector, "DATA_DIR", root), patch.object(
                collector, "DB_PATH", root / "collector.sqlite3"
            ), patch.object(collector, "CSV_PATH", root / "rounds.csv"), patch.dict(
                "os.environ", {}, clear=True
            ):
                conn = collector._db()
                self.addCleanup(conn.close)
                socket = FakeSocket()
                totals = {"messages": 0, "saved": 0, "duplicates": 0, "conflicts": 0, "sync_errors": 0}
                events = [
                    {"type": 6},
                    {"type": 1, "target": "OnCrash", "arguments": [{"l": "coalesced-1", "f": 2.25, "ts": 1760000000000}]},
                ]
                collector._process_signalr_events(events, socket, conn, totals)
                self.assertEqual(len(socket.sent), 1)
                self.assertIn('"type": 6', socket.sent[0])
                self.assertEqual(totals["saved"], 1)
                self.assertEqual(
                    conn.execute("SELECT round_id FROM crash_rounds").fetchone()[0],
                    "coalesced-1",
                )

class SignalRSupabaseOutboxTests(unittest.TestCase):
    def test_pending_rows_are_marked_synced_only_after_full_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(collector, "DATA_DIR", root), patch.object(
                collector, "DB_PATH", root / "collector.sqlite3"
            ), patch.dict(
                "os.environ",
                {
                    "SUPABASE_URL": "https://example.supabase.co",
                    "SUPABASE_SERVICE_ROLE_KEY": "test-only-key",
                },
            ):
                conn = collector._db()
                self.addCleanup(conn.close)
                collector._save_round(
                    conn, {"l": "round-10", "f": 4.0, "ts": 1760000000000}
                )
                with patch.object(
                    collector,
                    "sync_rows",
                    return_value={"inserted": 0, "already_present": 0, "verified": 0},
                ):
                    with self.assertRaises(RuntimeError):
                        collector._sync_pending(conn)
                self.assertEqual(
                    conn.execute("SELECT synced FROM crash_rounds").fetchone()[0], 0
                )
                with patch.object(
                    collector,
                    "sync_rows",
                    return_value={"inserted": 1, "already_present": 0, "verified": 0},
                ):
                    self.assertEqual(collector._sync_pending(conn), 1)
                self.assertEqual(
                    conn.execute("SELECT synced FROM crash_rounds").fetchone()[0], 1
                )

    def test_outbox_is_left_untouched_without_supabase_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(collector, "DATA_DIR", root), patch.object(
                collector, "DB_PATH", root / "collector.sqlite3"
            ), patch.dict("os.environ", {}, clear=True):
                conn = collector._db()
                self.addCleanup(conn.close)
                collector._save_round(
                    conn, {"l": "round-11", "f": 1.8, "ts": 1760000000000}
                )
                self.assertEqual(collector._sync_pending(conn), 0)
                self.assertEqual(
                    conn.execute("SELECT synced FROM crash_rounds").fetchone()[0], 0
                )


if __name__ == "__main__":
    unittest.main()
