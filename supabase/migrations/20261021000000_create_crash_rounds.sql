-- Proposed persistence schema for Crash Feed Inspector.
-- This migration is committed for review only; it has NOT been applied to a live project.
-- Do not store raw WebSocket payloads or credentials in this table.

create table if not exists public.crash_rounds (
    id uuid primary key default gen_random_uuid(),
    source text not null check (length(btrim(source)) > 0),
    schema_version text not null check (length(btrim(schema_version)) > 0),
    round_id text not null check (length(btrim(round_id)) > 0),
    timestamp_utc timestamptz,
    multiplier numeric not null check (
        multiplier >= 1
        and multiplier < 'Infinity'::numeric
    ),
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
    created_at timestamptz not null default now(),
    constraint crash_rounds_source_schema_round_unique
        unique (source, schema_version, round_id),
    constraint crash_rounds_verification_metadata_check
        check (
            (verified = false and verification_status <> 'verified')
            or
            (
                verified = true
                and verification_status = 'verified'
                and verification_method is not null
                and length(btrim(verification_method)) > 0
                and verified_at is not null
            )
        )
);

create index if not exists crash_rounds_timestamp_idx
    on public.crash_rounds (timestamp_utc desc)
    where timestamp_utc is not null;

alter table public.crash_rounds enable row level security;

-- No browser/client access is granted by this migration. A trusted server-side
-- ingestion path must be designed separately; never expose service-role secrets.
revoke all on table public.crash_rounds from anon, authenticated;
