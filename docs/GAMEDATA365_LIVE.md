# GameData365 ingestion: live Crash snapshots and historical backfill

## Live collector (recommended starting point)

The documented endpoint is:

```http
GET https://api.gamedata365.com/v1/crash/live
X-API-Key: YOUR_KEY
```

One response contains the newest completed round for every crash game enabled in the API plan. Each item includes `game_id`, `game_name`, `provider`, `stale`, and `latest.round_id/multiplier/timestamp`. The provider's current catalogue documents 31 crash games across 10 studios. The API plan determines which games are actually returned; the collector does not assume every catalogue game is entitled.

### Termux / local setup

1. Create an API key from https://gamedata365.com/api-access. Do not paste it into chat or commit it.
2. Add these values to the ignored local `.env` file:

```dotenv
GAMEDATA365_API_KEY=your_private_key
GAMEDATA365_POLL_SECONDS=14400
GAMEDATA365_TIMEOUT_SECONDS=15
SUPABASE_URL=https://htfrixfcirgrhlmwtkjs.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_private_supabase_service_role_jwt
```

3. Update the repository and install requirements:

```bash
git pull --ff-only
python -m pip install -r requirements.txt
```

4. Start collection:

```bash
python -m crash_feed_inspector collect-gamedata365
```

The collector writes to `data/collector.sqlite3`, exports `data/continuous_rounds.csv`, and retries the existing authenticated Supabase ingestion function. Local SQLite writes are committed before network synchronization. Identical rounds are deduplicated by `(source, round_id)`; conflicting multipliers are written to `collector_conflicts` and never overwrite the original value. All imported records remain `verified=false`.

### Quota and completeness

Every successful API call counts as one request. The live endpoint returns the newest round per game, not every round since the previous request. A round that starts and finishes between polls can be missed. The program prints the approximate monthly request count:

`30 × 86,400 / polling_interval_seconds`

For example, a 300-second interval uses approximately 8,640 calls per 30 days; a 5-second interval uses approximately 518,400. A 14,400-second interval uses approximately 180 calls per 30 days. Choose an interval that fits the account's actual quota. The documented free key is limited to 200 requests/month, so it cannot provide continuous capture. Do not run a high-frequency poll on a low-quota key.

The API may return `stale=true`; this means the game has not produced a recent round. A stale value is still a historical last result, not a fresh live event. Provider HTTP 401/403, 429, and 503 conditions are reported distinctly. The collector uses exponential backoff after errors and does not invent missing rounds.

## Historical backfill / existing Edge Function

The existing `sync-gamedata365` Supabase Edge Function is a separate history importer for Aviator and JetX. It currently fetches a bounded history page and records `next_cursor` metadata; it does not yet perform full cursor pagination. Its existing schedule is quota-sensitive and should not be mistaken for a continuous stream.

The provider documents `GET /v1/crash/history?game=<game_id>&limit=<n>&cursor=<next_cursor>`; pages can be followed until `next_cursor=null`, subject to the account's history window. A complete historical backfill with per-game cursor persistence is a separate implementation task.

## What is and is not verified

A successful HTTP response proves that the API returned a record, not that every round was captured. Compare samples against the provider's own visible history and inspect run gaps. Imported rows remain unverified until an independent reconciliation process is completed. The collector does not place bets, bypass access controls, or predict future outcomes.
