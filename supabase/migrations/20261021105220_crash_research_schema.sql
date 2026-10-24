-- Reproducible baseline for the current Crash Feed Inspector schema.
-- Raw WebSocket payloads, credentials, and secrets must never be stored here.
create table if not exists public.crash_rounds (
    id bigint generated always as identity primary key,
    source text not null,
    round_id text not null,
    occurred_at timestamptz,
    multiplier numeric(12, 4) not null,
    schema_version text not null default 'unknown',
    verified boolean not null default false,
    verification_status text not null default 'pending_manual_confirmation',
    verification_method text,
    verified_at timestamptz,
    source_event_sha256 text,
    created_at timestamptz not null default now(),
    constraint crash_rounds_source_round_id_key unique (source, round_id),
    constraint crash_rounds_source_check check (length(btrim(source)) > 0),
    constraint crash_rounds_round_id_check check (length(btrim(round_id)) > 0),
    constraint crash_rounds_verification_status_check
        check (verification_status in ('pending_manual_confirmation', 'verified', 'rejected', 'conflict'))
);

create index if not exists crash_rounds_occurred_at_idx
    on public.crash_rounds (occurred_at desc);
create index if not exists crash_rounds_verified_occurred_at_idx
    on public.crash_rounds (verified, occurred_at desc);

alter table public.crash_rounds enable row level security;
revoke all on table public.crash_rounds from anon, authenticated;

comment on table public.crash_rounds is
    'Normalized crash-game outcomes; unverified until reconciled against a trusted visible history.';
