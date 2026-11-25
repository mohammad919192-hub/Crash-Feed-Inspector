"""Local-only HTTP receiver for browser-observed SignalR OnCrash events.

The userscript forwards only completed-round event payloads. It does not collect
cookies, authorization headers, bets, balances, or other WebSocket traffic.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from dotenv import load_dotenv

from .continuous_capture import _db, _export_csv, _sync_pending

MAX_BODY = 16_384


def _store_event(conn, body: dict) -> str:
    if body.get("event") != "OnCrash":
        raise ValueError("unsupported_event")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ValueError("event_data_missing")
    value = data.get("f")
    if isinstance(value, bool):
        raise ValueError("invalid_multiplier")
    multiplier = float(value)
    if not math.isfinite(multiplier) or multiplier < 1 or multiplier > 1e9:
        raise ValueError("multiplier_out_of_range")

    event_id = str(body.get("eventId") or "").strip()
    if not event_id or len(event_id) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", event_id):
        raise ValueError("invalid_event_id")

    # The reference payload exposes the round identifier as data.l. Prefer it
    # so separate deliveries of the same round deduplicate across page sessions.
    raw_round_id = data.get("l")
    if raw_round_id is None:
        round_id = event_id  # compatibility fallback for feeds without a round ID
    else:
        if isinstance(raw_round_id, bool):
            raise ValueError("invalid_round_id")
        round_id = str(raw_round_id).strip()
        if (
            not round_id
            or len(round_id) > 256
            or not re.fullmatch(r"[A-Za-z0-9._:-]+", round_id)
        ):
            raise ValueError("invalid_round_id")

    host = str(body.get("host") or "unknown").lower()
    host = re.sub(r"[^a-z0-9.-]", "", host)[:120] or "unknown"
    source = "browser_signalr:" + host
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    observed_ms = body.get("observedAtMs")
    try:
        observed_ms = int(observed_ms)
        if observed_ms <= 0:
            raise ValueError
        timestamp = datetime.fromtimestamp(observed_ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError, OSError):
        timestamp = now

    existing = conn.execute(
        "SELECT multiplier FROM crash_rounds WHERE source=? AND round_id=?",
        (source, round_id),
    ).fetchone()
    if existing:
        if round(float(existing[0]) * 10000) != round(multiplier * 10000):
            conn.execute(
                """INSERT INTO collector_conflicts
                (source,round_id,stored_multiplier,incoming_multiplier,observed_at_utc)
                VALUES(?,?,?,?,?)""",
                (source, round_id, existing[0], multiplier, now),
            )
            conn.commit()
            return "conflict"
        return "duplicate"

    conn.execute(
        """INSERT INTO crash_rounds
        (source,round_id,timestamp_utc,multiplier,verified,schema_version,synced,captured_at_utc)
        VALUES(?,?,?,?,0,'browser-signalr-oncrash-v1',0,?)""",
        (source, round_id, timestamp, multiplier, now),
    )
    conn.commit()
    return "saved"


def run_browser_bridge() -> None:
    load_dotenv()
    token = os.getenv("CRASH_BRIDGE_TOKEN", "").strip()
    if len(token) < 24:
        raise SystemExit("Set CRASH_BRIDGE_TOKEN in local .env (at least 24 characters).")
    host = os.getenv("CRASH_BRIDGE_HOST", "127.0.0.1").strip()
    if host not in ("127.0.0.1", "localhost"):
        raise SystemExit("For safety, CRASH_BRIDGE_HOST must be loopback (127.0.0.1 or localhost).")
    port = int(os.getenv("CRASH_BRIDGE_PORT", "8765"))
    if not 1024 <= port <= 65535:
        raise SystemExit("CRASH_BRIDGE_PORT must be between 1024 and 65535.")

    conn = _db()
    lock = threading.Lock()
    totals = {"saved": 0, "duplicate": 0, "conflict": 0, "rejected": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _reply(self, status: int, payload: dict):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if urlparse(self.path).path != "/health":
                self._reply(404, {"ok": False})
                return
            self._reply(200, {"ok": True, "service": "crash-feed-browser-bridge"})

        def do_POST(self):
            if urlparse(self.path).path != "/crash":
                self._reply(404, {"ok": False})
                return
            supplied = self.headers.get("Authorization", "")
            expected = "Bearer " + token
            if not hmac.compare_digest(supplied, expected):
                self._reply(401, {"ok": False, "error": "unauthorized"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > MAX_BODY:
                    raise ValueError("invalid_body_size")
                body = json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("json_object_required")
                with lock:
                    status = _store_event(conn, body)
                    totals[status] += 1
                    if status == "saved":
                        _export_csv(conn)
                        try:
                            _sync_pending(conn)
                        except Exception:
                            pass  # durable local SQLite outbox remains pending
                print(f"Browser SignalR: {status} {body.get('data', {}).get('f')}x | totals={totals}")
                self._reply(200, {"ok": True, "status": status})
            except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                totals["rejected"] += 1
                self._reply(400, {"ok": False, "error": str(exc)[:120]})

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Browser bridge listening on http://{host}:{port}")
    print("Install the userscript and open an authorized crash-game page in the same Android device.")
    print("Only OnCrash multiplier events are accepted; rows remain verified=false.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("Bridge stopped.")
    finally:
        server.server_close()
        with lock:
            _export_csv(conn)
            conn.close()
