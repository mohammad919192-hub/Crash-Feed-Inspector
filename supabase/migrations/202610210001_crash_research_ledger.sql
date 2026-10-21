-- Review-only draft. Do not apply until the correct Supabase project is confirmed.
-- Stores normalized round outcomes and predictions, not raw WebSocket messages or credentials.
-- RLS is enabled with no client policies by default: browser/anon/authenticated clients get no table access.
-- A trusted server-side ingestion service using a service-role credential is required; never expose that key in a client app.

create table if not exists public.crash_rounds (
    id bigint generated always as identity primary key,
    source text not null,
    round_id text not null,
    occurred_at timestamptz,
    multiplier numeric(12, 4) not null check (multiplier >= 1 and multiplier < 'Infinity'::numeric),
    schema_version text not null default 'unknown',
    verified boolean not null default false,
    verification_method text,
    source_event_sha256 text,
    created_at timestamptz not null default now(),
    unique (source, round_id),
    check (length(trim(source)) > 0),
    check (length(trim(round_id)) > 0)
);

create index if not exists crash_rounds_occurred_at_idx
    on public.crash_rounds (occurred_at desc);
create index if not exists crash_rounds_verified_occurred_at_idx
    on public.crash_rounds (verified, occurred_at desc);

create table if not exists public.crash_predictions (
    id bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    source text not null,
    target_threshold numeric(12, 4) not null check (target_threshold >= 1),
    estimated_probability numeric(8, 7) not null check (estimated_probability >= 0 and estimated_probability <= 1),
    confidence_low numeric(8, 7) not null check (confidence_low >= 0 and confidence_low <= 1),
    confidence_high numeric(8, 7) not null check (confidence_high >= 0 and confidence_high <= 1),
    model_version text not null,
    data_count integer not null check (data_count >= 0),
    decision text not null check (decision in ('no_signal', 'research_only', 'candidate_signal')),
    feature_summary jsonb not null default '{}'::jsonb,
    evaluated_round_id text,
    evaluated_multiplier numeric(12, 4),
    evaluated_at timestamptz,
    check (confidence_low <= confidence_high),
    check (evaluated_multiplier is null or evaluated_multiplier >= 1)
);

create index if not exists crash_predictions_created_at_idx
    on public.crash_predictions (created_at desc);
create index if not exists crash_predictions_model_threshold_idx
    on public.crash_predictions (model_version, target_threshold, created_at desc);

alter table public.crash_rounds enable row level security;
alter table public.crash_predictions enable row level security;

comment on table public.crash_rounds is
    'Normalized round outcomes. verified=false until reconciled against trusted visible history.';
comment on table public.crash_predictions is
    'Append-only research prediction ledger. Every estimate should be stored before the corresponding outcome arrives.';
