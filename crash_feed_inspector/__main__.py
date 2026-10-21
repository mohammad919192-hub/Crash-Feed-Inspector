"""Capture a bounded sample of WebSocket messages for offline inspection."""
from __future__ import annotations

import csv
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
import websocket

ROOT = Path.cwd()
DATA_DIR = ROOT / "data"
RAW_PATH = DATA_DIR / "messages.jsonl"
CSV_PATH = DATA_DIR / "rounds.csv"
MULTIPLIER_RE = re.compile(r"(?<![\\w.])(\\d+(?:[.,]\\d+)?)\\s*x?", re.IGNORECASE)


def main() -> None:
    load_dotenv()
    url = os.getenv("CRASH_WS_URL", "").strip()
    if not url:
        raise SystemExit("CRASH_WS_URL is empty. Copy .env.example to .env and configure an authorized endpoint.")
    max_messages = max(1, int(os.getenv("MAX_MESSAGES", "100")))
    timeout = max(1, int(os.getenv("WS_TIMEOUT_SECONDS", "15")))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    candidates: list[dict[str, object]] = []
    try:
        ws = websocket.create_connection(url, timeout=timeout, enable_multithread=True)
    except Exception as exc:
        raise SystemExit(f"WebSocket connection failed: {type(exc).__name__}: {exc}") from exc
    print("Connected. Capturing messages; no bets or game actions are performed.")
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
            record = {"captured_at_unix": time.time(), "message_index": count, "raw": raw}
            with RAW_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\\n")
            # Heuristic only: candidates are not verified round outcomes.
            for match in MULTIPLIER_RE.finditer(raw):
                token = match.group(1).replace(",", ".")
                try:
                    value = float(token)
                except ValueError:
                    continue
                if 1.0 <= value <= 100000.0:
                    candidates.append({
                        "message_index": count,
                        "candidate_multiplier": value,
                        "matched_text": match.group(0),
                        "verified": False,
                    })
            print(f"Captured message {count} ({len(raw)} characters)")
    finally:
        ws.close()
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["message_index", "candidate_multiplier", "matched_text", "verified"])
        writer.writeheader()
        writer.writerows(candidates)
    print(f"Saved {count} raw messages to {RAW_PATH}")
    print(f"Saved {len(candidates)} unverified numeric candidates to {CSV_PATH}")
    print("Review raw messages and compare candidates with the game's displayed history before interpreting them.")


if __name__ == "__main__":
    main()
