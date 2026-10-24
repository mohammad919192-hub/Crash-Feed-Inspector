import io
import json
import unittest
from urllib.error import HTTPError

from crash_feed_inspector.supabase_sync import sync_rows


ROWS = [{
    "round_id": "r1", "timestamp_utc": "2026-01-01T00:00:00Z", "multiplier": 2.0,
    "source": "fixture", "verified": False, "schema_version": "fixture-v1",
}]


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class SupabaseSyncTests(unittest.TestCase):
    def test_sends_candidates_with_server_key_and_returns_counters(self):
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return FakeResponse({"received": 1, "unique_rows": 1, "inserted": 1, "already_present": 0, "verified": 0})

        result = sync_rows(ROWS, "https://example.supabase.co", "server-secret", opener=opener)
        self.assertEqual(result["inserted"], 1)
        request, timeout = requests[0]
        self.assertEqual(request.full_url, "https://example.supabase.co/functions/v1/ingest-crash-rounds")
        self.assertEqual(request.get_header("Authorization"), "Bearer server-secret")
        self.assertEqual(request.get_header("Apikey"), "server-secret")
        self.assertEqual(timeout, 20)
        self.assertFalse(json.loads(request.data)["rows"][0]["verified"])

    def test_refuses_verified_rows(self):
        with self.assertRaisesRegex(ValueError, "verified=false"):
            sync_rows([{**ROWS[0], "verified": True}], "https://example.supabase.co", "server-secret")

    def test_requires_https_and_key(self):
        with self.assertRaisesRegex(ValueError, "https"):
            sync_rows(ROWS, "http://example.supabase.co", "server-secret")
        with self.assertRaisesRegex(ValueError, "SERVICE_ROLE_KEY"):
            sync_rows(ROWS, "https://example.supabase.co", "")

    def test_http_error_does_not_leak_response_body(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 409, "conflict", {}, io.BytesIO(b"secret database details"))
        with self.assertRaisesRegex(ValueError, "HTTP 409") as caught:
            sync_rows(ROWS, "https://example.supabase.co", "server-secret", opener=opener)
        self.assertNotIn("secret database details", str(caught.exception))

    def test_chunks_rows_to_configured_batch_size(self):
        requests = []
        def opener(request, timeout):
            batch = json.loads(request.data)["rows"]
            requests.append(batch)
            return FakeResponse({"received": len(batch), "unique_rows": len(batch), "inserted": len(batch), "already_present": 0, "verified": 0})
        rows = [{**ROWS[0], "round_id": f"r{i}"} for i in range(3)]
        result = sync_rows(rows, "https://example.supabase.co", "server-secret", batch_size=2, opener=opener)
        self.assertEqual([len(batch) for batch in requests], [2, 1])
        self.assertEqual(result["inserted"], 3)


if __name__ == "__main__":
    unittest.main()
