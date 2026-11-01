# GameData365 automated ingestion

## What is deployed

The Supabase project `Crash` has an Edge Function named `sync-gamedata365`. It calls the provider's documented crash-history endpoint once for each configured game:

- `GET /v1/crash/history?game=aviator&limit=50`
- `GET /v1/crash/history?game=jetx&limit=50`

It normalizes `round_id`, `multiplier`, and timezone-aware `timestamp` into `public.crash_rounds`. Source labels are `gamedata365:aviator` and `gamedata365:jetx`. The unique key is `(source, round_id)`. Repeated identical rows are ignored; conflicting multipliers are quarantined in run diagnostics and never overwrite stored values.

Every provider row is inserted with `verified=false` and `verification_status='pending_manual_confirmation'`. No ingestion path marks a round verified. Raw provider payloads and API keys are not persisted. The operational table `public.crash_ingestion_runs` records sanitized run metadata, request counts, inserted/duplicate/conflicting rows, per-game coverage metadata, and error codes.

## Required one-time secrets

1. In Supabase Dashboard, open **Edge Functions → Secrets** for project `htfrixfcirgrhlmwtkjs`.
2. Add `GAMEDATA365_API_KEY` with the GameData365 key. Do not add it to GitHub, source code, or chat.
3. In Supabase Dashboard, open **Database → Vault** and create a secret named `crash_ingest_service_role_jwt` containing the project's Supabase **secret API key** (`sb_secret_...`), preferably the `default` secret key. It is used only by pg_cron to authenticate the scheduled Edge Function call. Never paste it into chat or commit it.
4. The function is deployed with `verify_jwt=false` because Supabase secret API keys are not JWTs. It validates the incoming `apikey` header against the server-injected `SUPABASE_SECRET_KEYS.default` value. Do not remove this in-function authentication check.

The function also relies on Supabase's built-in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` Edge Function environment variables. The GameData365 key is a separate secret.

## Start one immediate run

After both secrets exist, execute this SQL once in the Supabase SQL Editor:

```sql
select net.http_post(
  url := 'https://htfrixfcirgrhlmwtkjs.supabase.co/functions/v1/sync-gamedata365',
  headers := jsonb_build_object(
    'Content-Type', 'application/json',
    'apikey', (select decrypted_secret from vault.decrypted_secrets where name = 'crash_ingest_secret_key')
  ),
  body := '{"trigger_source":"manual"}'::jsonb,
  timeout_milliseconds := 30000
) as request_id;
```

pg_net is asynchronous. After the request completes, inspect the run table:

```sql
select id, started_at, finished_at, status, provider_requests,
       rows_received, rows_inserted, rows_duplicate, rows_conflict, details, error_code
from public.crash_ingestion_runs
order by started_at desc
limit 10;
```

## Enable the free-plan schedule

The free GameData365 key allows 200 requests per month and only the newest 50 history rounds per game. Each sync run uses two provider requests (one per game). The recommended schedule below runs every 8 hours: 3 runs/day × 30 days × 2 requests = 180 requests/month, leaving a small reserve for manual checks. Do not schedule more frequently on this plan.

After the immediate run succeeds, execute:

```sql
select cron.schedule(
  'crash-gamedata365-sync-8h',
  '0 */8 * * *',
  $$
  select net.http_post(
    url := 'https://htfrixfcirgrhlmwtkjs.supabase.co/functions/v1/sync-gamedata365',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'apikey', (select decrypted_secret from vault.decrypted_secrets where name = 'crash_ingest_secret_key')
    ),
    body := '{"trigger_source":"cron"}'::jsonb,
    timeout_milliseconds := 30000
  );
  $$
);
```

The schedule uses UTC. Inspect it with:

```sql
select jobid, jobname, schedule, active
from cron.job
where jobname = 'crash-gamedata365-sync-8h';
```

To remove it:

```sql
select cron.unschedule(jobid)\nfrom cron.job\nwhere jobname = 'crash-gamedata365-sync-8h';
```

## Important free-tier coverage limitation

This schedule is deliberately quota-safe, not a complete high-frequency archive. The provider exposes only the newest 50 history rounds per game on the free key. If a game produces more than 50 rounds between 8-hour runs, intermediate rounds will not be collected. Therefore the free tier can establish a recurring sample/history snapshot, but it cannot guarantee complete round-by-round coverage or a gap-free training dataset. The run metadata records the returned history window and whether a next cursor was present; it does not invent missing rounds.

A complete continuous archive would require a substantially higher request quota or a provider-supported streaming/webhook feed. The free plan's 200 monthly calls cannot support frequent polling of both games.

## Health and data checks

Latest run summary:

```sql
select started_at, status, provider_requests, rows_received,
       rows_inserted, rows_duplicate, rows_conflict, error_code
from public.crash_ingestion_runs
order by started_at desc
limit 10;
```

Round counts by game:

```sql
select source, count(*) as rounds,
       count(*) filter (where verified) as verified_rounds,
       min(occurred_at) as oldest_round,
       max(occurred_at) as newest_round
from public.crash_rounds
where source in ('gamedata365:aviator', 'gamedata365:jetx')
group by source
order by source;
```

All tables remain server-only with RLS enabled and no direct `anon` or `authenticated` table privileges. Never expose a Supabase service-role key or the GameData365 API key to browser code.
