"""Continuous SignalR crash-round collector with a durable SQLite outbox.

This collector only listens to an endpoint and account the operator is authorized
to access. It does not place bets, send game actions, or attempt to bypass access
controls. Parsed rounds remain unverified until independently reconciled.
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websocket
from dotenv import load_dotenv

from .security import sanitize_message
from .supabase_sync import sync_rows

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "collector.sqlite3"
RAW_PATH = DATA_DIR / "continuous_messages.jsonl"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required in local .env; never paste credentials into chat or commit them.")
    return value


def _db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crash_rounds (
            source TEXT NOT NULL,
            round_id TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            multiplier REAL NOT NULL CHECK(multiplier >= 1),
            verified INTEGER NOT NULL DEFAULT 0 CHECK(verified = 0),
            schema_version TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0 CHECK(synced IN (0,1)),
            captured_at_utc TEXT NOT NULL,
            PRIMARY KEY(source, round_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collector_conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            round_id TEXT NOT NULL,
            stored_multiplier REAL NOT NULL,
            incoming_multiplier REAL NOT NULL,
            observed_at_utc TEXT NOT NULL
        )
    """)
    return conn


def _utc_from_epoch_ms(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("timestamp is not numeric")
    milliseconds = int(value)
    if milliseconds <= 0:
        raise ValueError("timestamp must be positive epoch milliseconds")
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _frames(raw: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for frame in raw.split("\x1e"):
        frame = frame.strip()
        if not frame:
            continue
        try:
            value = json.loads(frame)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            parsed.append(value)
    return parsed


def _save_round(conn: sqlite3.Connection, payload: dict[str, Any]) -> str:
    round_id = str(payload.get("l", "")).strip()
    multiplier_value = payload.get("f")
    if not round_id or len(round_id) > 256:
        raise ValueError("missing or invalid round id")
    if isinstance(multiplier_value, bool):
        raise ValueError("invalid multiplier")
    multiplier = float(multiplier_value)
    if not (1 <= multiplier < float("inf")):
        raise ValueError("multiplier must be finite and >= 1")
    timestamp = _utc_from_epoch_ms(payload.get("ts"))
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    source = "xbet_signalr"
    existing = conn.execute(
        "SELECT multiplier FROM crash_rounds WHERE source=? AND round_id=?",
        (source, round_id),
    ).fetchone()
    if existing:
        if round(float(existing[0]) * 10000) != round(multiplier * 10000):
            conn.execute(
                "INSERT INTO collector_conflicts(source,round_id,stored_multiplier,incoming_multiplier,observed_at_utc) VALUES(?,?,?,?,?)",
                (source, round_id, existing[0], multiplier, now),
            )
            conn.commit()
            return "conflict"
        return "duplicate"
    conn.execute(
        """INSERT INTO crash_rounds
        (source,round_id,timestamp_utc,multiplier,verified,schema_version,synced,captured_at_utc)
        VALUES(?,?,?,?,0,'signalr-oncrash-l-f-ts-v1',0,?)""",
        (source, round_id, timestamp, multiplier, now),
    )
    conn.commit()
    return "saved"


def _sync_pending(conn: sqlite3.Connection) -> int:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return 0
    rows = conn.execute(
        """SELECT source,round_id,timestamp_utc,multiplier,schema_version
        FROM crash_rounds WHERE synced=0 ORDER BY timestamp_utc LIMIT 100"""
    ).fetchall()
    if not rows:
        return 0
    payload = [{
        "source": row[0],
        "round_id": row[1],
        "timestamp_utc": row[2],
        "multiplier": float(row[3]),
        "verified": False,
        "schema_version": row[4],
    } for row in rows]
    result = sync_rows(payload, url, key, timeout=20, batch_size=100)
    if result["inserted"] + result["already_present"] != len(payload):
        raise RuntimeError("Supabase response did not account for every queued round")
    conn.executemany(
        "UPDATE crash_rounds SET synced=1 WHERE source=? AND round_id=?",
        [(row[0], row[1]) for row in rows],
    )
    conn.commit()
    return len(rows)


def _append_raw(raw: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "raw_sanitized": sanitize_message(raw),
    }
    with RAW_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()


def run_continuous() -> None:
    load_dotenv()
    url = _required("CRASH_WS_URL")
    if not url.startswith("wss://"):
        raise SystemExit("CRASH_WS_URL must use wss://.")
    account_id = _required("CRASH_ACCOUNT_ID")
    headers = [
        "Origin: " + os.getenv("CRASH_WS_ORIGIN", "https://ma-1xbet.com").strip(),
        "User-Agent: " + os.getenv(
            "CRASH_WS_USER_AGENT",
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
        ).strip(),
    ]
    cookie = os.getenv("CRASH_WS_COOKIE", "").strip()
    if cookie:
        headers.append("Cookie: " + cookie)

    conn = _db()
    attempt = 0
    totals = {"messages": 0, "saved": 0, "duplicates": 0, "conflicts": 0, "sync_errors": 0}
    print(f"Continuous listener started. Local durable database: {DB_PATH}")
    print("Only OnCrash candidates are stored; verified remains false.")
    try:
        while True:
            ws = None
            try:
                ws = websocket.create_connection(
                    url, timeout=30, header=headers, enable_multithread=True,
                    origin=os.getenv("CRASH_WS_ORIGIN", "https://ma-1xbet.com").strip(),
                )
                ws.settimeout(30)
                ws.send(json.dumps({"protocol": "json", "version": 1}) + "\x1e")
                handshake_ok = False
                handshake_deadline = time.monotonic() + 10
                while time.monotonic() < handshake_deadline:
                    response = ws.recv()
                    if isinstance(response, bytes):
                        response = response.decode("utf-8", errors="replace")
                    if any(frame.strip() == "{}" for frame in str(response).split("\x1e")):
                        handshake_ok = True
                        break
                if not handshake_ok:
                    raise RuntimeError("SignalR handshake acknowledgement not received")

                ws.send(json.dumps({
                    "arguments": [{"activity": 30, "account": account_id}],
                    "invocationId": "0",
                    "target": "Account",
                    "type": 1,
                }) + "\x1e")
                print("SignalR handshake complete; Account subscription sent.")
                attempt = 0

                while True:
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        print("No feed message for 30 seconds; connection remains open.")
                        continue
                    if raw is None:
                        raise ConnectionError("WebSocket closed by remote")
                    raw_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                    _append_raw(raw_text)
                    for event in _frames(raw_text):
                        totals["messages"] += 1
                        if event.get("type") == 6:
                            ws.send(json.dumps({"type": 6}) + "\x1e")
                        if event.get("type") != 1 or event.get("target") != "OnCrash":
                            continue
                        arguments = event.get("arguments")
                        if not isinstance(arguments, list) or not arguments or not isinstance(arguments[0], dict):
                            continue
                        try:
                            status = _save_round(conn, arguments[0])
                        except (ValueError, TypeError, OverflowError, OSError) as exc:
                            print(f"Rejected malformed OnCrash event ({type(exc).__name__}).")
                            continue
                        totals[status if status in totals else "saved"] += 1
                        print(
                            f"Round {arguments[0].get('l')} | {arguments[0].get('f')}x | "
                            f"status={status} | saved={totals['saved']} conflicts={totals['conflicts']}"
                        )
                        try:
                            synced = _sync_pending(conn)
                            if synced:
                                print(f"Supabase sync: {synced} candidate rows acknowledged.")
                        except Exception as exc:
                            totals["sync_errors"] += 1
                            print(f"Supabase sync deferred ({type(exc).__name__}); local outbox retained.")
            except KeyboardInterrupt:
                print("Stop requested; local data is committed.")
                break
            except Exception as exc:
                attempt += 1
                delay = min(300, 5 * (2 ** min(attempt - 1, 6))) + random.uniform(0, 2)
                print(f"Connection cycle failed ({type(exc).__name__}); reconnecting in {delay:.1f}s.")
                time.sleep(delay)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
    finally:
        try:
            pending = _sync_pending(conn)
            if pending:
                print(f"Final Supabase sync: {pending} rows.")
        except Exception as exc:
            print(f"Pending rows remain safely stored locally ({type(exc).__name__}).")
        counts = conn.execute(
            "SELECT COUNT(*), SUM(synced), COUNT(DISTINCT round_id) FROM crash_rounds"
        ).fetchone()
        print(f"Local totals: rounds={counts[0]}, synced={counts[1] or 0}; session={totals}")
        conn.close()
