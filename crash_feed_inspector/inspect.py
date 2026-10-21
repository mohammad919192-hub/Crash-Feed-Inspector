"""Local, read-only inspection of sanitized JSONL capture samples."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_CANDIDATE_KEY = re.compile(r"(multiplier|coefficient|crash.?point|factor|payout.?factor|bust)", re.I)
_SECRET_KEY = re.compile(r"(authorization|cookie|token|jwt|bearer|credential|password|passwd|secret|api.?key|csrf|session.?id|signed.?url)", re.I)


def _walk(value: Any, prefix: str = "", depth: int = 0):
    """Yield (path, key, type, value) for leaves, with a conservative depth cap."""
    if depth > 8:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if _SECRET_KEY.search(key_text):
                yield path, key_text, "redacted", "[REDACTED]"
            elif isinstance(item, (dict, list)):
                yield from _walk(item, path, depth + 1)
            else:
                yield path, key_text, type(item).__name__, item
    elif isinstance(value, list):
        for index, item in enumerate(value[:20]):
            path = f"{prefix}[{index}]"
            if isinstance(item, (dict, list)):
                yield from _walk(item, path, depth + 1)
            else:
                yield path, str(index), type(item).__name__, item


def inspect_jsonl(path: Path, *, max_messages: int = 100) -> dict[str, Any]:
    """Summarize message structure and probable multiplier-like fields.

    The report is exploratory only: it never declares a field to be the
    authoritative completed-round multiplier and never verifies any outcome.
    """
    if max_messages < 1 or max_messages > 1000:
        raise ValueError("max_messages must be between 1 and 1000.")
    if not path.is_file():
        raise ValueError(f"Capture file does not exist: {path}")

    message_count = 0
    json_count = 0
    invalid_count = 0
    path_types: dict[str, Counter[str]] = defaultdict(Counter)
    candidate_samples: dict[str, list[Any]] = defaultdict(list)
    event_values: Counter[str] = Counter()

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if message_count >= max_messages:
                break
            if not line.strip():
                continue
            message_count += 1
            try:
                envelope = json.loads(line)
                raw = envelope.get("raw_sanitized") if isinstance(envelope, dict) else None
                payload = json.loads(raw) if isinstance(raw, str) else None
            except (json.JSONDecodeError, TypeError, AttributeError):
                invalid_count += 1
                continue
            if not isinstance(payload, (dict, list)):
                invalid_count += 1
                continue
            json_count += 1
            for field_path, key, value_type, value in _walk(payload):
                path_types[field_path][value_type] += 1
                if key.lower() in {"type", "event", "eventtype", "event_type", "action", "op"} and isinstance(value, (str, int, float)):
                    event_values[str(value)[:120]] += 1
                if _CANDIDATE_KEY.search(key) and value_type in {"int", "float", "str"}:
                    if len(candidate_samples[field_path]) < 5:
                        # Values are from already-sanitized local samples; avoid dumping arbitrary strings.
                        candidate_samples[field_path].append(value if isinstance(value, (int, float)) else str(value)[:80])

    return {
        "file": str(path),
        "messages_scanned": message_count,
        "json_messages": json_count,
        "invalid_or_non_json_messages": invalid_count,
        "event_type_value_counts": dict(event_values.most_common(20)),
        "observed_field_paths": {
            field_path: dict(types) for field_path, types in sorted(path_types.items())
        },
        "multiplier_like_field_candidates": {
            field_path: samples for field_path, samples in sorted(candidate_samples.items())
        },
        "warning": (
            "Exploratory schema summary only. Numeric fields may be unrelated; "
            "confirm a completed-round event and reconcile values with visible game history. "
            "No candidate is automatically verified."
        ),
    }
