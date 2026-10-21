"""Bounded, read-only WebSocket message capture."""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

import websocket
from dotenv import load_dotenv

from .security import sanitize_message

DATA_DIR = Path.cwd() / "data"
RAW_PATH = DATA_DIR / "messages.jsonl"
CSV_PATH = DATA_DIR / "rounds.csv"


def capture() -> None:
    load_dotenv()
    url = os.getenv("CRASH_WS_URL", "").strip()
    if not url:
        raise SystemExit("CRASH_WS_URL is empty. Copy .env.example to .env and configure an authorized endpoint.")
    if not url.startswith(("wss://", "ws://")):
        raise SystemExit("CRASH_WS_URL must start with ws:// or wss://.")
    try:
        max_messages = max(1, min(10000, int(os.getenv("MAX_MESSAGES", "100"))))
        timeout = max(1, min(300, int(os.getenv("WS_TIMEOUT_SECONDS", "15"))))
    except ValueError as exc:
        raise SystemExit("MAX_MESSAGES and WS_TIMEOUT_SECONDS must be integers.") from exc

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    try:
        ws = websocket.create_connection(url, timeout=timeout, enable_multithread=True)
    except Exception as exc:
        raise SystemExit(f"WebSocket connection failed: {type(exc).__name__}: {exc}") from exc

    print("Connected. Capturing bounded sample; no bets or game actions are performed.")
    try:
        while count < max_messages:
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                print("Receive timeout; stopping capture.")
                break
            if raw is None:
                break
            count += 1
            sanitized = sanitize_message(str(raw))
            record = {"captured_at_unix": time.time(), "message_index": count, "raw_sanitized": sanitized}
            with RAW_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"Captured message {count} ({len(str(raw))} characters; common secret fields redacted)")
    finally:
        ws.close()

    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["message_index", "candidate_multiplier", "matched_text", "verified"],
        )
        writer.writeheader()
    print(f"Saved {count} sanitized messages to {RAW_PATH}")
    print(f"Created empty candidate template at {CSV_PATH}; no arbitrary numbers were inferred as outcomes.")
    print("Configure the schema-aware parser only after the feed format is confirmed.")
