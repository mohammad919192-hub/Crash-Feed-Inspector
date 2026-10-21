"""Strict CSV loading and quality checks for historical round results."""
from __future__ import annotations

import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REQUIRED_COLUMNS = {"round_id", "multiplier"}
OPTIONAL_COLUMNS = {"timestamp_utc", "source", "verified", "schema_version"}


def _parse_verified(value: str | None, row_number: int) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"", "false", "0", "no"}:
        return False
    if normalized in {"true", "1", "yes"}:
        return True
    raise ValueError(f"Row {row_number}: verified must be true/false, 1/0, yes/no, or blank.")


def _parse_timestamp(value: str | None, row_number: int) -> str | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: timestamp_utc is not valid ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Row {row_number}: timestamp_utc must include a timezone offset.")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_rounds_csv(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a CSV; fail closed rather than silently dropping rows.

    Required columns: round_id,multiplier. Optional columns:
    timestamp_utc,source,verified,schema_version. Missing verification defaults
    to False, and round IDs must be unique within the file.
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError("CSV missing required columns: " + ", ".join(sorted(missing)))
        unknown = headers - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
        if unknown:
            raise ValueError("CSV has unsupported columns: " + ", ".join(sorted(unknown)))

        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            if not row or all(value is None or not value.strip() for value in row.values()):
                continue
            round_id = (row.get("round_id") or "").strip()
            if not round_id:
                raise ValueError(f"Row {row_number}: round_id cannot be empty.")
            if round_id in seen_ids:
                raise ValueError(f"Row {row_number}: duplicate round_id {round_id!r}.")
            seen_ids.add(round_id)

            raw_multiplier = (row.get("multiplier") or "").strip()
            try:
                multiplier = float(raw_multiplier)
            except ValueError as exc:
                raise ValueError(f"Row {row_number}: multiplier must be numeric.") from exc
            if not math.isfinite(multiplier) or multiplier < 1.0:
                raise ValueError(f"Row {row_number}: multiplier must be finite and >= 1.0.")

            rows.append({
                "round_id": round_id,
                "timestamp_utc": _parse_timestamp(row.get("timestamp_utc"), row_number),
                "multiplier": multiplier,
                "source": (row.get("source") or "csv_import").strip() or "csv_import",
                "verified": _parse_verified(row.get("verified"), row_number),
                "schema_version": (row.get("schema_version") or "unknown").strip() or "unknown",
            })
    if not rows:
        raise ValueError("CSV contains no data rows.")
    return rows


def quality_report(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize dataset completeness and chronology without hiding limitations."""
    data = list(rows)
    if not data:
        raise ValueError("At least one row is required for a quality report.")
    chronology_violations = 0
    previous = None
    for row in data:
        timestamp = row.get("timestamp_utc")
        if not timestamp:
            continue
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("All non-empty timestamps must include a timezone.")
        parsed = parsed.astimezone(timezone.utc)
        if previous is not None and parsed < previous:
            chronology_violations += 1
        previous = parsed
    return {
        "row_count": len(data),
        "verified_rows": sum(bool(row.get("verified")) for row in data),
        "unverified_rows": sum(not bool(row.get("verified")) for row in data),
        "missing_timestamps": sum(not row.get("timestamp_utc") for row in data),
        "chronology_violations": chronology_violations,
        "timestamp_coverage": sum(bool(row.get("timestamp_utc")) for row in data) / len(data),
        "interpretation": "Quality checks do not establish that source outcomes are authentic.",
    }


def verified_multipliers(rows: Iterable[dict[str, Any]]) -> list[float]:
    """Return only explicitly verified rows, preserving CSV chronology."""
    return [float(row["multiplier"]) for row in rows if row.get("verified") is True]
