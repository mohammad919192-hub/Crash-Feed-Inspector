import sqlite3
import unittest

from crash_feed_inspector.browser_bridge import _store_event


class BrowserBridgeTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript("""
            CREATE TABLE crash_rounds (
                source TEXT NOT NULL, round_id TEXT NOT NULL, timestamp_utc TEXT NOT NULL,
                multiplier REAL NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
                schema_version TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0,
                captured_at_utc TEXT NOT NULL, PRIMARY KEY(source, round_id)
            );
            CREATE TABLE collector_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
                round_id TEXT NOT NULL, stored_multiplier REAL NOT NULL,
                incoming_multiplier REAL NOT NULL, observed_at_utc TEXT NOT NULL
            );
        """)

    def tearDown(self):
        self.conn.close()

    def event(self, multiplier=2.31, event_id="evt-1"):
        return {
            "event": "OnCrash", "eventId": event_id, "observedAtMs": 1760000000000,
            "host": "example-game.test", "data": {"f": multiplier, "l": 77},
        }

    def test_stores_multiplier_as_unverified_candidate(self):
        self.assertEqual(_store_event(self.conn, self.event()), "saved")
        row = self.conn.execute(
            "SELECT multiplier, verified, schema_version FROM crash_rounds"
        ).fetchone()
        self.assertEqual(row, (2.31, 0, "browser-signalr-oncrash-v1"))

    def test_duplicate_event_is_idempotent(self):
        _store_event(self.conn, self.event())
        self.assertEqual(_store_event(self.conn, self.event()), "duplicate")

    def test_conflicting_duplicate_is_quarantined(self):
        _store_event(self.conn, self.event())
        self.assertEqual(_store_event(self.conn, self.event(3.2)), "conflict")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM collector_conflicts").fetchone()[0], 1)

    def test_rejects_non_final_or_invalid_multiplier(self):
        event = self.event()
        event["event"] = "OnStart"
        with self.assertRaises(ValueError):
            _store_event(self.conn, event)
        with self.assertRaises(ValueError):
            _store_event(self.conn, self.event(0.5))

    def test_rejects_invalid_event_id(self):
        with self.assertRaises(ValueError):
            _store_event(self.conn, self.event(event_id="../bad"))


if __name__ == "__main__":
    unittest.main()
