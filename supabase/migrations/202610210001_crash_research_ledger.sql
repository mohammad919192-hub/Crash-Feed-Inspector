-- Review-only draft. Do not apply until the correct Supabase project is confirmed.
-- The canonical public.crash_rounds table is created by
-- 20261021000000_create_crash_rounds.sql. Do not redefine it here.
-- Stores research estimates, not raw WebSocket messages or credentials.
-- RLS is enabled and browser/anon/authenticated table access is explicitly revoked.

create table if not exists public.crash_predictions (
    id bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    source text not null check (length(btrim(source)) > 0),
    target_threshold numeric(12, 4) not null check (
        target_threshold >= 1
        and target_threshold < 'Infinity'::numeric
    ),
    estimated_probability numeric(8, 7) not null check (
        estimated_probability >= 0 and estimated_probability <= 1
    ),
    confidence_low numeric(8, 7) not null check (
        confidence_low >= 0 and confidence_low <= 1
    ),
    confidence_high numeric(8, 7) not null check (
        confidence_high >= 0 and confidence_high <= 1
    ),
    model_version text not null check (length(btrim(model_version)) > 0),
    data_count integer not null check (data_count >= 0),
    decision text not null check (
        decision in ('no_signal', 'research_only', 'candidate_signal')
    ),
    feature_summary jsonb not null default '{}'::jsonb,
    evaluated_round_id text,
    evaluated_multiplier numeric(12, 4),
    evaluated_at timestamptz,
    check (confidence_low <= confidence_high),
    check (
        evaluated_multiplier is null
        or (
            evaluated_multiplier >= 1
            and evaluated_multiplier < 'Infinity'::numeric
        )
    )
);

create index if not exists crash_predictions_created_at_idx
    on public.crash_predictions (created_at desc);
create index if not exists crash_predictions_model_threshold_idx
    on public.crash_predictions (model_version, target_threshold, created_at desc);

alter table public.crash_predictions enable row level security;
revoke all on table public.crash_predictions from anon, authenticated;

comment on table public.crash_predictions is
    'Append-only descriptive research ledger. Store estimates before the corresponding outcome arrives; no estimate implies a reliable next-round prediction.';
