"""Send normalized, unverified candidate rows to the project's authenticated Edge Function."""
from __future__ import annotations

import json
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
    if any(row.get("verified") is not False for row in materialized):
        raise ValueError("sync-supabase accepts only rows explicitly marked verified=false.")

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
