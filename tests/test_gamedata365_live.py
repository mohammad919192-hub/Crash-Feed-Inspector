import sqlite3
import unittest

from crash_feed_inspector.gamedata365_live import (
    fetch_live, normalize_live_games, store_live_rounds,
)


class FakeResponse:
    status = 200
    def __init__(self, body):
        self.body = body
    def read(self):
        return self.body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class GameData365LiveTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "status": "ok",
            "server_time": "2026-11-25T10:00:00Z",
            "games": [
                {"game_id": "aviator", "game_name": "Aviator", "provider": "spribe",
                 "stale": False, "latest": {"round_id": "a-1", "multiplier": 2.35,
                 "timestamp": "2026-11-25T09:59:50Z"}},
                {"game_id": "jetx", "game_name": "JetX", "provider": "smartsoft",
                 "stale": False, "latest": {"round_id": "j-1", "multiplier": 1.14,
                 "timestamp": "2026-11-25 09:59:48"}},
            ],
        }

    def test_fetch_uses_documented_endpoint_and_header(self):
        seen = {}
        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["key"] = request.get_header("X-api-key")
            seen["timeout"] = timeout
            return FakeResponse(b'{"status":"ok","games":[]}')
        result = fetch_live("test-secret", opener=opener)
        self.assertEqual(seen["url"], "https://api.gamedata365.com/v1/crash/live")
        self.assertEqual(seen["key"], "test-secret")
        self.assertEqual(result["games"], [])

    def test_normalizes_multiple_games_and_utc_timestamps(self):
        rows = normalize_live_games(self.payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["source"], "gamedata365:aviator")
        self.assertEqual(rows[0]["multiplier"], 2.35)
        self.assertEqual(rows[1]["timestamp_utc"], "2026-11-25T09:59:48Z")
        self.assertFalse(rows[0]["verified"])

    def test_invalid_or_incomplete_rows_are_skipped(self):
        payload = {"games": [
            {"game_id": "bad", "latest": {"round_id": "x", "multiplier": float("nan"), "timestamp": "2026-01-01T00:00:00Z"}},
            {"game_id": "missing", "latest": {"round_id": "x", "multiplier": 2}},
            {"game_id": "ok", "latest": {"round_id": "r", "multiplier": 1.5, "timestamp": "2026-01-01T00:00:00Z"}},
        ]}
        self.assertEqual(len(normalize_live_games(payload)), 1)

    def test_sqlite_deduplicates_and_quarantines_conflicts(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
        CREATE TABLE crash_rounds (
          source TEXT, round_id TEXT, timestamp_utc TEXT, multiplier REAL,
          verified INTEGER, schema_version TEXT, synced INTEGER, captured_at_utc TEXT,
          PRIMARY KEY(source, round_id));
        CREATE TABLE collector_conflicts (
          id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, round_id TEXT,
          stored_multiplier REAL, incoming_multiplier REAL, observed_at_utc TEXT);
        """)
        rows = normalize_live_games(self.payload)
        first = store_live_rounds(conn, rows)
        self.assertEqual(first["inserted"], 2)
        second = store_live_rounds(conn, rows)
        self.assertEqual(second["duplicates"], 2)
        conflict = dict(rows[0], multiplier=9.99)
        third = store_live_rounds(conn, [conflict])
        self.assertEqual(third["conflicts"], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crash_rounds").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM collector_conflicts").fetchone()[0], 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
