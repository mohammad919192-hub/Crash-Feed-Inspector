"""Poll the documented GameData365 live Crash endpoint for every entitled game.

The endpoint returns the newest completed round per subscribed game in one request.
Polling frequency is quota-sensitive; this module never fabricates missing rounds.
"""
from __future__ import annotations

import json
import math
import os
import random
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from .continuous_capture import _db, _export_csv, _sync_pending

API_URL = "https://api.gamedata365.com/v1/crash/live"
MAX_MULTIPLIER = 99_999_999.9999


class FatalProviderError(RuntimeError):
    """Authentication or entitlement errors that will not recover by retrying."""


class ProviderQuotaExceeded(RuntimeError):
    """The provider quota is exhausted; stop polling until the quota resets."""


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp_missing")
    text = value.strip()
    # The provider documents timestamps as UTC; some examples omit the Z suffix.
    if not (text.endswith("Z") or "+" in text[10:] or "-" in text[10:]):
        text += "Z"
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp_timezone_missing")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_live(api_key: str, *, timeout: int = 15,
               opener: Callable[..., Any] | None = None) -> dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        raise ValueError("GAMEDATA365_API_KEY is empty.")
    if not 1 <= timeout <= 60:
        raise ValueError("timeout must be between 1 and 60 seconds.")
    request = Request(API_URL, headers={
        "X-API-Key": key,
        "Accept": "application/json",
        "User-Agent": "Crash-Feed-Inspector/1.0",
    })
    send = opener or urlopen
    try:
        with send(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
        if exc.code == 429:
            raise ProviderQuotaExceeded(f"provider_quota_exceeded: retry_after={retry_after or 'unspecified'}") from None
        if exc.code in (401, 403):
            raise FatalProviderError(f"provider_auth_or_entitlement_error_http_{exc.code}") from None
        if exc.code == 503:
            raise RuntimeError("provider_feed_stale_http_503") from None
        raise RuntimeError(f"provider_http_{exc.code}") from None
    except URLError:
        raise RuntimeError("provider_network_error") from None
    except TimeoutError:
        raise RuntimeError("provider_timeout") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("provider_invalid_json") from None

    if not isinstance(payload, dict) or payload.get("status") != "ok":
        code = payload.get("error") if isinstance(payload, dict) else None
        raise RuntimeError(f"provider_unexpected_response:{code or 'invalid_shape'}")
    games = payload.get("games")
    if not isinstance(games, list):
        raise RuntimeError("provider_games_array_missing")
    return payload


def normalize_live_games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    games = payload.get("games")
    if not isinstance(games, list):
        raise ValueError("games must be an array")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for game in games:
        if not isinstance(game, dict):
            continue
        game_id = game.get("game_id")
        latest = game.get("latest")
        if not isinstance(game_id, str) or not game_id.strip() or not isinstance(latest, dict):
            continue
        round_id = latest.get("round_id")
        multiplier_value = latest.get("multiplier")
        if not isinstance(round_id, (str, int)) or isinstance(round_id, bool):
            continue
        round_id = str(round_id).strip()
        if not round_id or len(round_id) > 256:
            continue
        if isinstance(multiplier_value, bool):
            continue
        try:
            multiplier = float(multiplier_value)
            occurred_at = _timestamp(latest.get("timestamp"))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(multiplier) or not 1 <= multiplier <= MAX_MULTIPLIER:
            continue
        key = (game_id.strip(), round_id)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({
            "source": f"gamedata365:{game_id.strip()}",
            "round_id": round_id,
            "timestamp_utc": occurred_at,
            "multiplier": multiplier,
            "schema_version": "gamedata365-crash-live-v1",
            "verified": False,
            "stale": bool(game.get("stale", False)),
            "game_name": str(game.get("game_name") or game_id),
            "provider": str(game.get("provider") or "unknown"),
        })
    return normalized


def store_live_rounds(conn: sqlite3.Connection, rounds: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"inserted": 0, "duplicates": 0, "conflicts": 0, "invalid": 0}
    for row in rounds:
        existing = conn.execute(
            "SELECT multiplier FROM crash_rounds WHERE source=? AND round_id=?",
            (row["source"], row["round_id"]),
        ).fetchone()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if existing:
            if round(float(existing[0]) * 10000) != round(float(row["multiplier"]) * 10000):
                conn.execute(
                    """INSERT INTO collector_conflicts
                    (source,round_id,stored_multiplier,incoming_multiplier,observed_at_utc)
                    VALUES(?,?,?,?,?)""",
                    (row["source"], row["round_id"], existing[0], row["multiplier"], now),
                )
                counts["conflicts"] += 1
            else:
                counts["duplicates"] += 1
            continue
        conn.execute(
            """INSERT INTO crash_rounds
            (source,round_id,timestamp_utc,multiplier,verified,schema_version,synced,captured_at_utc)
            VALUES(?,?,?, ?,0,?,0,?)""",
            (row["source"], row["round_id"], row["timestamp_utc"],
             row["multiplier"], row["schema_version"], now),
        )
        counts["inserted"] += 1
    conn.commit()
    return counts


def run_gamedata365_live() -> None:
    load_dotenv()
    api_key = os.getenv("GAMEDATA365_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "GAMEDATA365_API_KEY is required in local .env. Create/copy your official key "
            "from https://gamedata365.com/api-access; never paste it into chat or commit it."
        )
    try:
        interval = int(os.getenv("GAMEDATA365_POLL_SECONDS", "14400"))
        timeout = int(os.getenv("GAMEDATA365_TIMEOUT_SECONDS", "15"))
    except ValueError:
        raise SystemExit("GAMEDATA365_POLL_SECONDS and GAMEDATA365_TIMEOUT_SECONDS must be integers.")
    if interval < 5 or interval > 86400:
        raise SystemExit("GAMEDATA365_POLL_SECONDS must be between 5 and 86400.")
    if not 1 <= timeout <= 60:
        raise SystemExit("GAMEDATA365_TIMEOUT_SECONDS must be between 1 and 60.")
    monthly_calls = round(30 * 86400 / interval)
    print(f"GameData365 live polling: every {interval}s; approx. {monthly_calls:,} API calls per 30 days.")
    print("One request returns the latest completed round for every crash game in your API plan.")
    print("Polling only captures the latest snapshot; rounds between polls can be missed.")
    conn = _db()
    attempt = 0
    try:
        while True:
            started = time.monotonic()
            try:
                payload = fetch_live(api_key, timeout=timeout)
                rounds = normalize_live_games(payload)
                result = store_live_rounds(conn, rounds)
                attempt = 0
                if result["inserted"]:
                    _export_csv(conn)
                print(
                    f"games={len(rounds)} new={result['inserted']} duplicate={result['duplicates']} "
                    f"conflict={result['conflicts']} server_time={payload.get('server_time', 'unknown')}"
                )
                try:
                    synced = _sync_pending(conn)
                    if synced:
                        print(f"Supabase acknowledged {synced} queued rounds.")
                except Exception as exc:
                    print(f"Supabase sync deferred ({type(exc).__name__}); SQLite outbox retained.")
                delay = max(0.0, interval - (time.monotonic() - started))
            except KeyboardInterrupt:
                print("Stop requested; local database remains committed.")
                break
            except (FatalProviderError, ProviderQuotaExceeded) as exc:
                print(f"Collector stopped: {exc}. Correct the key/plan or wait for quota reset.")
                break
            except Exception as exc:
                attempt += 1
                delay = min(900, max(interval, 5) * (2 ** min(attempt - 1, 5))) + random.uniform(0, 3)
                print(f"Live poll failed ({type(exc).__name__}: {exc}); retry in {delay:.1f}s.")
            time.sleep(delay)
    finally:
        try:
            _export_csv(conn)
        finally:
            conn.close()
