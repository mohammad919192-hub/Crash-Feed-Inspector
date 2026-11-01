-- GameData365 polling pipeline and operational audit.
-- Optional extensions are enabled only where the hosting platform provides them.
do $$
begin
  if exists (select 1 from pg_available_extensions where name = 'pg_cron') then
    execute 'create extension if not exists pg_cron with schema pg_catalog';
  end if;
  if exists (select 1 from pg_available_extensions where name = 'pg_net') then
    execute 'create extension if not exists pg_net';
  end if;
end
$$;

create table if not exists public.crash_ingestion_runs (
  id bigint generated always as identity primary key,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running'
    check (status in ('running', 'succeeded', 'partial', 'failed', 'skipped')),
  trigger_source text not null default 'manual'
    check (trigger_source in ('manual', 'cron')),
  provider_requests integer not null default 0
    check (provider_requests between 0 and 10),
  rows_received integer not null default 0 check (rows_received >= 0),
  rows_inserted integer not null default 0 check (rows_inserted >= 0),
  rows_duplicate integer not null default 0 check (rows_duplicate >= 0),
  rows_conflict integer not null default 0 check (rows_conflict >= 0),
  details jsonb not null default '{}'::jsonb,
  error_code text,
  created_at timestamptz not null default now(),
  constraint crash_ingestion_runs_finish_after_start
    check (finished_at is null or finished_at >= started_at)
);

create index if not exists crash_ingestion_runs_started_at_idx
  on public.crash_ingestion_runs (started_at desc);
create index if not exists crash_ingestion_runs_status_started_at_idx
  on public.crash_ingestion_runs (status, started_at desc);

alter table public.crash_ingestion_runs enable row level security;
revoke all on table public.crash_ingestion_runs from anon, authenticated;

comment on table public.crash_ingestion_runs is
  'Operational audit of GameData365 polling runs. Contains only sanitized metadata, never API keys or raw provider payloads.';
