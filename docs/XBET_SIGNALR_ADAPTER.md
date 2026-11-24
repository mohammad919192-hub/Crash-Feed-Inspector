# 1xBet SignalR adapter

## Upstream project and attribution

The protocol reference selected for this adapter is [Zakaria-laktati/crash-1xbet-monitoring](https://github.com/Zakaria-laktati/crash-1xbet-monitoring), distributed under the MIT License. Its original implementation combines a SignalR WebSocket scraper with PostgreSQL, Docker Compose, a Streamlit dashboard, and token-management utilities.

Crash Feed Inspector adapts the read-only SignalR collection path and its observed event mapping. It does **not** copy the upstream PostgreSQL/Docker/Streamlit stack: this repository already uses a local SQLite durable outbox, the protected Supabase ingestion function, and its existing private dashboard. The upstream project is credited as a protocol reference; this adapter is maintained independently.

## Observed protocol flow

The reference implementation describes this sequence:

1. Connect to an operator-supplied WebSocket URL.
2. Send the SignalR JSON protocol v1 handshake followed by the record separator `\x1e`:
   `{"protocol":"json","version":1}\x1e`.
3. Wait for the SignalR handshake acknowledgement.
4. Send the `Account` subscription invocation with the configured account identifier.
5. Listen for SignalR invocation messages whose target is `OnCrash`.
6. Read the first event argument:
   - `l`: round identifier
   - `f`: final multiplier candidate
   - `ts`: Unix timestamp in milliseconds
7. Reply to SignalR ping messages (type `6`) with a type `6` frame.
8. Reconnect after transport failures with bounded exponential backoff.

These field names and semantics come from a third-party reference implementation, not an official 1xBet protocol specification. A successful handshake or a numeric `f` field does not prove that the event is a completed round. Keep all collected rows unverified until multiple rounds have been reconciled against the site's visible completed-round history.

## Integration in this repository

The adapter is implemented in `crash_feed_inspector/continuous_capture.py` and exposed as:

```bash
python -m crash_feed_inspector collect
```

Data flow:

```text
Authorized 1xBet WebSocket
  -> SignalR handshake + Account subscription
  -> OnCrash event candidate
  -> strict field / timestamp / multiplier validation
  -> SQLite WAL database (durable local outbox)
  -> CSV snapshot (verified=false)
  -> protected ingest-crash-rounds Edge Function
  -> public.crash_rounds (verified=false)
  -> private dashboard
```

The collector stores:
- `crash_rounds`: one row per `(source, round_id)`, with timestamp, multiplier, schema version, sync state, and `verified=0`.
- `collector_conflicts`: conflicting multipliers for a previously seen round; the original row is never overwritten.
- `continuous_messages.jsonl`: best-effort redacted message samples for local diagnostics.
- `continuous_rounds.csv`: accumulated candidates, always exported with `verified=false`.

The local outbox is authoritative for retry safety. A row is marked synced only after the Edge Function acknowledges every row in the submitted batch. If Supabase is unavailable, local rows remain queued and the collector continues.

## Local configuration

Use a local, ignored `.env` file. Never commit it or paste its contents into chat, logs, screenshots, or issues.

Required:
- `CRASH_WS_URL`: complete `wss://` URL copied from a WebSocket session you are authorized to access. It may contain short-lived query credentials; treat the entire value as a password.
- `CRASH_ACCOUNT_ID`: account identifier required by the SignalR `Account` subscription.

Optional:
- `CRASH_WS_ORIGIN`: expected site origin (default: `https://ma-1xbet.com`).
- `CRASH_WS_COOKIE`: cookie header only if the authorized session requires it. Treat it as a password.
- `CRASH_WS_USER_AGENT`: source-compatible user agent.
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`: local CLI credentials for the protected ingestion function. The service-role key must never be put in frontend code.

Start the collector with:

```bash
python -m pip install -r requirements.txt
python -m crash_feed_inspector collect
```

Stop with Ctrl+C. SQLite commits are retained and the collector attempts a final outbox sync.

## Validation and limitations

- The collector is read-only. It does not place bets or send game actions.
- It does not bypass login, CAPTCHA, access controls, or rate limits. Use only an account/session and endpoint you are authorized to access, and comply with the provider's terms.
- The endpoint copied from the reference README (`wss://ma-1xbet.com/games-frame/sockets/crash`) is historical documentation, not a guarantee that the host, token, headers, or protocol remain current. Earlier direct connection attempts in this project returned HTTP 400. Do not treat the old URL as a working endpoint.
- Access tokens may expire. The operator must refresh an authorized session and update the local `.env`; automatic token extraction/refresh is intentionally not implemented.
- A disconnect can cause missed rounds. The collector does not backfill gaps from the WebSocket.
- The event mapping `OnCrash/l/f/ts` is versioned as `signalr-oncrash-l-f-ts-v1`; changing the mapping requires reviewing sanitized samples, updating the schema version, and adding fixtures.
- Multipliers are constrained to finite values of at least 1, at most four decimal places, and the current database's supported numeric range.
- Synthetic tests verify parser, storage, deduplication, conflict, and outbox behavior. They do not prove live endpoint compatibility or the authenticity of any captured result.
- Never mark rows verified merely because they arrived through this adapter. Verification requires independent reconciliation against trusted completed-round history.

## License

The upstream reference project declares the MIT License. This adapter's code in Crash Feed Inspector is part of this repository and does not include the upstream project's dashboard, database layer, or container orchestration.
