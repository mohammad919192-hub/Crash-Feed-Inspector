"""Bounded, read-only WebSocket message capture."""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

import websocket
from dotenv import load_dotenv

from .dataset import load_rounds_csv, quality_report
from .protocol import parse_final_result
from .security import sanitize_message

DATA_DIR = Path.cwd() / "data"
RAW_PATH = DATA_DIR / "messages.jsonl"
CSV_PATH = DATA_DIR / "rounds.csv"
ROUND_COLUMNS = ["round_id", "timestamp_utc", "multiplier", "source", "verified", "schema_version"]


def _parser_config() -> dict | None:
    event_path = os.getenv("CRASH_EVENT_TYPE_PATH", "").strip()
    final_types = [item.strip() for item in os.getenv("CRASH_FINAL_EVENT_TYPES", "").split(",") if item.strip()]
    round_path = os.getenv("CRASH_ROUND_ID_PATH", "").strip()
    multiplier_path = os.getenv("CRASH_MULTIPLIER_PATH", "").strip()
    timestamp_path = os.getenv("CRASH_TIMESTAMP_PATH", "").strip() or None
    configured = [bool(event_path), bool(final_types), bool(round_path), bool(multiplier_path)]
    if any(configured) and not all(configured):
        raise SystemExit(
            "Parser configuration is incomplete. Set CRASH_EVENT_TYPE_PATH, "
            "CRASH_FINAL_EVENT_TYPES, CRASH_ROUND_ID_PATH, and CRASH_MULTIPLIER_PATH together."
        )
    if not all(configured):
        return None
    return {
        "event_type_path": event_path,
        "final_event_types": final_types,
        "round_id_path": round_path,
        "multiplier_path": multiplier_path,
        "timestamp_path": timestamp_path,
        "source": "websocket",
        "schema_version": os.getenv("CRASH_SCHEMA_VERSION", "unconfirmed").strip() or "unconfirmed",
    }


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
    parser_config = _parser_config()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    count, parse_errors = 0, 0
    parsed_by_id: dict[str, dict] = {}
    conflicting_ids: set[str] = set()
    try:
        ws = websocket.create_connection(url, timeout=timeout, enable_multithread=True)
    except Exception as exc:
        raise SystemExit(
            f"WebSocket connection failed ({type(exc).__name__}); endpoint details suppressed."
        ) from None

    print("Connected. Capturing bounded sample; no bets or game actions are performed.")
    if parser_config is None:
        print("No confirmed parser mapping configured; capturing sanitized messages only.")
    try:
        while count < max_messages:
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                print("Receive timeout; stopping capture.")
                break
            except Exception as exc:
                print(f"Receive failed ({type(exc).__name__}); stopping capture.")
                break
            if raw is None:
                break
            count += 1
            raw_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            sanitized = sanitize_message(raw_text)
            record = {"captured_at_unix": time.time(), "message_index": count, "raw_sanitized": sanitized}
            with RAW_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

            if parser_config is not None:
                try:
                    result = parse_final_result(sanitized, **parser_config)
                except ValueError:
                    parse_errors += 1
                    result = None
                if result is not None:
                    round_id = result["round_id"]
                    if round_id in parsed_by_id and parsed_by_id[round_id]["multiplier"] != result["multiplier"]:
                        conflicting_ids.add(round_id)
                    else:
                        parsed_by_id[round_id] = result
            print(f"Captured message {count} ({len(raw_text)} characters; common secret fields redacted)")
    finally:
        try:
            ws.close()
        except Exception as exc:
            print(f"WebSocket close failed ({type(exc).__name__}); preserving captured output.")

    candidates = [row for round_id, row in parsed_by_id.items() if round_id not in conflicting_ids]

    # Merge with the prior CSV rather than discarding history on every capture run.
    # Invalid existing data must never be silently replaced.
    existing_rows = []
    if CSV_PATH.exists():
        try:
            with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as existing_handle:
                existing_reader = csv.DictReader(existing_handle)
                existing_headers = existing_reader.fieldnames or []
                raw_existing_rows = list(existing_reader)
            has_existing_data = any(
                any(value is not None and str(value).strip() for key, value in row.items() if key is not None)
                for row in raw_existing_rows
            )
            if not existing_headers or len(set(existing_headers)) != len(ROUND_COLUMNS) or set(existing_headers) != set(ROUND_COLUMNS):
                raise ValueError("Existing rounds CSV headers do not match the expected schema.")
            if has_existing_data:
                existing_rows = load_rounds_csv(CSV_PATH)
        except (OSError, ValueError) as exc:
            raise SystemExit(
                f"Existing rounds CSV is invalid; refusing to overwrite it ({type(exc).__name__})."
            ) from None

    existing_by_id = {row["round_id"]: row for row in existing_rows}
    new_rows = []
    historical_conflicts: set[str] = set()
    for row in candidates:
        round_id = row["round_id"]
        previous = existing_by_id.get(round_id)
        if previous is not None:
            if previous["multiplier"] != row["multiplier"]:
                historical_conflicts.add(round_id)
            continue
        existing_by_id[round_id] = row
        new_rows.append(row)

    merged_rows = [*existing_rows, *new_rows]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROUND_COLUMNS)
        writer.writeheader()
        for row in merged_rows:
            writer.writerow({key: row.get(key, "") for key in ROUND_COLUMNS})

    print(f"Saved {count} sanitized messages to {RAW_PATH}")
    print(
        f"Saved {len(merged_rows)} total round rows to {CSV_PATH} "
        f"({len(existing_rows)} retained, {len(new_rows)} new candidates)"
    )
    if conflicting_ids:
        print(f"Warning: excluded {len(conflicting_ids)} round IDs with conflicting multipliers in this capture.")
    if historical_conflicts:
        print(
            f"Warning: excluded {len(historical_conflicts)} candidates conflicting with existing CSV history; "
            "the existing rows were preserved."
        )
    if merged_rows:
        merged_quality = quality_report(merged_rows)
        if merged_quality["chronology_violations"]:
            print(
                f"Warning: merged history has {merged_quality['chronology_violations']} "
                "out-of-order timestamp transitions; research commands will refuse sequence-sensitive analysis."
            )
    if parse_errors:
        print(f"Warning: {parse_errors} messages had malformed configured result fields.")
    if parser_config is None:
        print("Configure parser paths only after confirming them against sanitized feed samples.")
    else:
        print("Every parsed row remains verified=false until reconciled with trusted visible game history.")
