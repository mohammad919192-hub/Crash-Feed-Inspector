# Architecture and Engineering Decisions

## System boundary

```text
Authorized 1xBet SignalR WebSocket
        |
        v
SignalR JSON v1 handshake + Account subscription
        |
        v
OnCrash event candidate (l / f / ts mapping)
        |
        v
Strict validation + local SQLite WAL outbox
        |                         |
        v                         v
Sanitized JSONL / CSV       Protected Supabase ingestion
                                  |
                                  v
                         public.crash_rounds
                                  |
                                  v
                         Authenticated private dashboard

GameData365 history sync is a separate supplementary ingestion path for Aviator
and JetX. It is not a replacement for the 1xBet Crash WebSocket collector.
All ingested provider rows remain unverified until independently reconciled.
```

## Module ownership

- `capture.py`: bounded WebSocket capture, timeout/message limits, sanitized local persistence.
- `continuous_capture.py`: continuous read-only SignalR listener, handshake, Account subscription, ping response, reconnect loop, OnCrash extraction, SQLite outbox, CSV export, and optional Supabase retry.
- `browser_bridge.py`: loopback-only HTTP receiver for browser-observed OnCrash events, bearer-token validation, SQLite persistence, CSV snapshot repair, and optional Supabase sync.
- `userscripts/crash-feed-inspector.user.js`: observes matching text WebSocket frames in the already-open authorized browser page and forwards only the final multiplier and round ID fields with bounded retries.
- `protocol.py`: explicit JSON-path parser for generic feeds; no guessed target-site schema.
- `security.py`: best-effort redaction of common secret-shaped fields.
- `dataset.py`: strict CSV contract, timestamp normalization, duplicate rejection, and quality report.
- `analytics.py`: descriptive statistics, rolling empirical rates, and walk-forward baseline.
- `research.py`: chronological threshold-frequency, uncertainty, and stability analysis.
- `supabase_sync.py`: authenticated client-side CLI helper for the protected ingestion Edge Function.
- Supabase Edge Functions: `ingest-crash-rounds` accepts only unverified candidates; `sync-gamedata365` imports documented Aviator/JetX history; `dashboard-read` gates private dashboard reads.
- `site/index.html`: static dashboard frontend; it never receives the Supabase service-role key.

## Browser bridge path

```text
Authorized game page
  -> existing browser WebSocket
  -> userscript filters SignalR OnCrash
  -> loopback HTTP + local bearer token
  -> browser_bridge.py
  -> SQLite WAL outbox
  -> CSV snapshot / protected Supabase ingestion
```

The browser adapter does not create a second game connection or extract session credentials. It depends on the target page using the expected `/sockets/crash` path and SignalR `OnCrash` payload. Delivery retries are bounded and in-memory; page closure or device loss can still create gaps. The receiver prefers `data.l` as the round ID and falls back to a delivery ID only when that field is absent.

## Persistence model

The 1xBet collector writes first to local SQLite in WAL mode. This is the durable outbox: transient Supabase failures do not discard collected rounds. The key is `(source, round_id)`; duplicate events are ignored, and a different multiplier for an existing key is recorded in `collector_conflicts` rather than overwriting history. The CSV export is a snapshot and always marks every row `verified=false`.

Supabase is a secondary synchronized store. The local collector marks a batch as synced only after the Edge Function acknowledges all rows as inserted or already present. The ingestion function validates source, round ID, multiplier precision/range, timestamp timezone, and the explicit `verified=false` flag. RLS and server-side function checks prevent browser clients from writing privileged records directly.

## Design decisions

1. **Read-only operation.** The collector listens only; it does not place bets or send game actions.
2. **Authorized access only.** The operator supplies an endpoint and session they are authorized to use. The project does not bypass login, CAPTCHA, rate limits, or access controls.
3. **No secret persistence in Git.** Full WebSocket URLs, cookies, account identifiers, and service-role keys belong only in the ignored local `.env`. Raw capture redaction is best-effort, not a guarantee.
4. **Parsing is not verification.** The `OnCrash/l/f/ts` mapping is derived from a third-party reference implementation, not an official provider schema. Every imported row remains unverified.
5. **Fail closed on malformed data.** Round IDs, timestamps, finite multipliers, supported precision, and database numeric bounds are checked before storage.
6. **Durable retry.** Local SQLite is retained if Supabase is unavailable. Acknowledgement mismatches do not mark queued rows as synced.
7. **No silent conflict resolution.** A conflicting multiplier for an existing round is recorded separately; the original value is never overwritten.
8. **No unsupported prediction claims.** Historical frequencies are descriptive. Any model must be compared against a predeclared baseline on chronological out-of-sample data, with uncertainty and a no-signal outcome.
9. **No betting actions or bankroll features.** The project remains a read-only research and monitoring tool.

## Known limitations

- The browser adapter's path/event reference is from a Melbet-focused third-party implementation; it is not an official or universal 1xBet protocol. The target 1xBet page has not yet been confirmed to emit the expected path and event.
- The direct 1xBet WebSocket endpoint and undocumented event mapping can change. Historical host/path values are not a guarantee of current availability.
- Earlier direct connection attempts returned HTTP 400; live endpoint compatibility still needs to be established using an authorized current session.
- Expired session credentials require operator refresh; automatic token harvesting is intentionally not implemented.
- WebSocket disconnections can cause gaps; this collector does not backfill missed rounds.
- Synthetic tests validate parsing, persistence, deduplication, conflict handling, and outbox behavior. They do not prove current live connectivity or source authenticity.
- GameData365 is a distinct supplementary historical source with its own quota and coverage limits.
- No captured row becomes verified automatically. Reconcile against trusted visible completed-round history before using data for research.
