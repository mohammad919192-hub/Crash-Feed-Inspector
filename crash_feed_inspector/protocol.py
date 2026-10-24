"""Explicit, configurable parsing for candidate final-round events.

No target-site schema is assumed. A caller must provide event and field paths
that have been independently confirmed against authorized, sanitized samples.
Parsed results remain unverified until reconciled with trusted visible history.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Iterable


_PATH_PATTERN = re.compile(
    r"^(?:\[\d+\]|[^.\[\]]+)(?:\[\d+\])*(?:\.[^.\[\]]+(?:\[\d+\])*)*$"
)


def _validate_path(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("A non-empty JSON field path is required.")
    normalized = path.strip()
    if not _PATH_PATTERN.fullmatch(normalized):
        raise ValueError(f"Invalid field path: {path!r}")
    return normalized


def get_path(value: Any, path: str) -> Any:
    """Resolve a strict dotted JSON path with optional non-negative list indexes."""
    normalized = _validate_path(path)
    tokens: list[str | int] = []
    for segment in normalized.split("."):
        key_match = re.match(r"^[^\[]+", segment)
        if key_match:
            tokens.append(key_match.group(0))
            remainder = segment[key_match.end():]
        else:
            remainder = segment
        tokens.extend(int(index) for index in re.findall(r"\[(\d+)\]", remainder))

    current = value
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                raise ValueError(f"Field path {path!r} does not exist.")
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                raise ValueError(f"Field path {path!r} does not exist.")
            current = current[token]
    return current


def _as_multiplier(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError("Multiplier must be a numeric value.")
    try:
        text = str(value).strip()
        if text.lower().endswith("x"):
            text = text[:-1].strip()
        multiplier = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid multiplier value: {value!r}") from exc
    if not math.isfinite(multiplier) or multiplier < 1.0:
        raise ValueError(f"Multiplier must be finite and >= 1.0: {value!r}")
    return multiplier


def _as_utc_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Timestamp must be a non-empty ISO-8601 string.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone offset.")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_final_result(
    raw_message: str,
    *,
    event_type_path: str,
    final_event_types: Iterable[str],
    round_id_path: str,
    multiplier_path: str,
    timestamp_path: str | None = None,
    source: str = "websocket",
    schema_version: str = "unconfirmed",
) -> dict[str, Any] | None:
    """Parse one explicitly mapped final-event candidate, or return None.

    This function never marks data as verified. Event types and field paths
    must be grounded in a confirmed protocol mapping. A human must still
    reconcile outcomes with a trusted reference before modeling.
    """
    allowed_types = {str(item) for item in final_event_types if str(item)}
    if not allowed_types:
        raise ValueError("At least one confirmed final event type is required.")
    if not event_type_path or not round_id_path or not multiplier_path:
        raise ValueError("Event type, round ID, and multiplier paths are required.")
    for configured_path in (event_type_path, round_id_path, multiplier_path, timestamp_path):
        if configured_path is not None:
            _validate_path(configured_path)
    if not source.strip() or not schema_version.strip():
        raise ValueError("Source and schema_version must be non-empty.")

    try:
        payload = json.loads(raw_message)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, (dict, list)):
        return None
    try:
        event_type = str(get_path(payload, event_type_path))
    except ValueError:
        return None
    if event_type not in allowed_types:
        return None

    round_id_value = get_path(payload, round_id_path)
    if isinstance(round_id_value, bool) or round_id_value is None:
        raise ValueError("Round ID must be a non-empty string or number.")
    round_id = str(round_id_value).strip()
    if not round_id:
        raise ValueError("Round ID must be a non-empty string or number.")

    multiplier = _as_multiplier(get_path(payload, multiplier_path))
    timestamp_utc = None
    if timestamp_path:
        timestamp_utc = _as_utc_timestamp(get_path(payload, timestamp_path))

    return {
        "round_id": round_id,
        "timestamp_utc": timestamp_utc,
        "multiplier": multiplier,
        "source": source.strip(),
        "verified": False,
        "verification_status": "pending_manual_confirmation",
        "schema_version": schema_version.strip(),
        "event_type": event_type,
    }
