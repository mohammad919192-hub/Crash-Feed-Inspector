-- Reconciled schema for the connected Crash Feed Inspector Supabase project.
-- Safe to replay against the observed schema: CREATE TABLE/INDEX IF NOT EXISTS
-- avoids replacing existing data. No raw WebSocket payloads or credentials belong here.

create table if not exists public.crash_rounds (
    id bigint generated always as identity primary key,
    source text not null check (length(btrim(source)) > 0),
    round_id text not null check (length(btrim(round_id)) > 0),
    occurred_at timestamptz,
    multiplier numeric(12, 4) not null check (
        multiplier >= 1
        and multiplier < 'Infinity'::numeric
    ),
    schema_version text not null default 'unknown',
    verified boolean not null default false,
    verification_status text not null default 'pending_manual_confirmation'
        check (verification_status in (
            'pending_manual_confirmation',
            'verified',
            'rejected',
            'conflict'
        )),
    verification_method text,
    verified_at timestamptz,
    source_event_sha256 text
        check (source_event_sha256 is null or source_event_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    constraint crash_rounds_source_round_id_key unique (source, round_id),
    constraint crash_rounds_verification_metadata_check
        check (
            (verified = false and verification_status <> 'verified')
            or (
                verified = true
                and verification_status = 'verified'
                and verification_method is not null
                and length(btrim(verification_method)) > 0
                and verified_at is not null
            )
        )
);

create index if not exists crash_rounds_occurred_at_idx
    on public.crash_rounds (occurred_at desc);
create index if not exists crash_rounds_verified_occurred_at_idx
    on public.crash_rounds (verified, occurred_at desc);

alter table public.crash_rounds enable row level security;
revoke all on table public.crash_rounds from anon, authenticated;

comment on table public.crash_rounds is
    'Normalized crash-game outcomes; unverified until reconciled against a trusted visible history.';
