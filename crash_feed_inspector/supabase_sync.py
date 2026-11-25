"""Send normalized, unverified candidate rows to the project's authenticated Edge Function."""
from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_MULTIPLIER = 99_999_999.9999


def sync_rows(
    rows: Iterable[dict[str, Any]],
    supabase_url: str,
    service_role_key: str,
    *,
    timeout: int = 20,
    batch_size: int = 500,
    opener: Callable[..., Any] | None = None,
) -> dict[str, int]:
    """Send only unverified candidates; the server never marks them verified."""
    base_url = (supabase_url or "").strip().rstrip("/")
    key = (service_role_key or "").strip()
    if not base_url.startswith("https://"):
        raise ValueError("SUPABASE_URL must be a valid https:// project URL.")
    if not key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY is empty; set it only in your local ignored .env.")
    if not 1 <= timeout <= 120:
        raise ValueError("timeout must be between 1 and 120 seconds.")
    if not 1 <= batch_size <= 500:
        raise ValueError("batch_size must be between 1 and 500.")
    materialized = list(rows)
    if not materialized:
        raise ValueError("No candidate rows to sync.")
    if any(not isinstance(row, dict) or row.get("verified") is not False for row in materialized):
        raise ValueError("sync-supabase accepts only object rows explicitly marked verified=false.")

    for index, row in enumerate(materialized, start=1):
        source = row.get("source")
        round_id = row.get("round_id")
        schema_version = row.get("schema_version")
        multiplier = row.get("multiplier")
        if not isinstance(source, str) or not source.strip() or len(source.strip()) > 128:
            raise ValueError(f"Candidate row {index}: source must be a non-empty string of at most 128 characters.")
        if not isinstance(round_id, str) or not round_id.strip() or len(round_id.strip()) > 256:
            raise ValueError(f"Candidate row {index}: round_id must be a non-empty string of at most 256 characters.")
        if not isinstance(schema_version, str) or not schema_version.strip() or len(schema_version.strip()) > 128:
            raise ValueError(f"Candidate row {index}: schema_version must be a non-empty string of at most 128 characters.")
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)):
            raise ValueError(f"Candidate row {index}: multiplier must be numeric.")
        numeric_multiplier = float(multiplier)
        if not math.isfinite(numeric_multiplier) or not 1 <= numeric_multiplier <= MAX_MULTIPLIER:
            raise ValueError(f"Candidate row {index}: multiplier is outside the supported finite range.")
        if abs(numeric_multiplier * 10_000 - round(numeric_multiplier * 10_000)) > 0.00001:
            raise ValueError(f"Candidate row {index}: multiplier may have at most four decimal places.")
        timestamp = row.get("timestamp_utc")
        if timestamp not in (None, ""):
            if not isinstance(timestamp, str):
                raise ValueError(f"Candidate row {index}: timestamp_utc must be ISO-8601 text or null.")
            try:
                parsed_timestamp = datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"Candidate row {index}: timestamp_utc is invalid ISO-8601.") from exc
            if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
                raise ValueError(f"Candidate row {index}: timestamp_utc must include a timezone.")

    send = opener or urlopen
    endpoint = f"{base_url}/functions/v1/ingest-crash-rounds"
    totals = {"received": 0, "unique_rows": 0, "inserted": 0, "already_present": 0, "verified": 0}
    for offset in range(0, len(materialized), batch_size):
        batch = materialized[offset:offset + batch_size]
        request = Request(
            endpoint,
            data=json.dumps({"rows": batch}, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}", "apikey": key},
            method="POST",
        )
        try:
            with send(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                response_text = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise ValueError(
                f"Supabase ingestion rejected batch with HTTP {exc.code}; check the key, deployed function, and round conflicts."
            ) from None
        except URLError:
            raise ValueError("Supabase ingestion request failed; check connectivity and SUPABASE_URL.") from None
        except TimeoutError:
            raise ValueError("Supabase ingestion request timed out.") from None
        if not 200 <= status < 300:
            raise ValueError(f"Supabase ingestion returned HTTP {status}.")
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            raise ValueError("Supabase ingestion returned invalid JSON.") from None
        if not isinstance(result, dict) or "inserted" not in result or "already_present" not in result:
            raise ValueError("Supabase ingestion returned an unexpected response.")
        for counter in totals:
            value = result.get(counter, 0)
            if not isinstance(value, int) or value < 0:
                raise ValueError("Supabase ingestion returned invalid counters.")
            totals[counter] += value
    return totals
