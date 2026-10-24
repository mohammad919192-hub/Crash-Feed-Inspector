-- Research ledger. Estimates are descriptive records, not guarantees of future outcomes.
create table if not exists public.crash_predictions (
    id bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    source text not null check (length(btrim(source)) > 0),
    target_threshold numeric(12, 4) not null
        check (target_threshold >= 1 and target_threshold < 'Infinity'::numeric),
    estimated_probability numeric(8, 7) not null
        check (estimated_probability >= 0 and estimated_probability <= 1),
    confidence_low numeric(8, 7) not null
        check (confidence_low >= 0 and confidence_low <= 1),
    confidence_high numeric(8, 7) not null
        check (confidence_high >= 0 and confidence_high <= 1),
    model_version text not null check (length(btrim(model_version)) > 0),
    data_count integer not null check (data_count >= 0),
    decision text not null check (decision in ('no_signal', 'research_only', 'candidate_signal')),
    feature_summary jsonb not null default '{}'::jsonb,
    evaluated_round_id text,
    evaluated_multiplier numeric(12, 4),
    evaluated_at timestamptz,
    constraint crash_predictions_confidence_order_check check (confidence_low <= confidence_high),
    constraint crash_predictions_probability_interval_check
        check (confidence_low <= estimated_probability and estimated_probability <= confidence_high),
    constraint crash_predictions_evaluation_fields_check
        check (
            (evaluated_round_id is null and evaluated_multiplier is null and evaluated_at is null)
            or (
                evaluated_round_id is not null and length(btrim(evaluated_round_id)) > 0
                and evaluated_multiplier is not null and evaluated_at is not null
            )
        ),
    constraint crash_predictions_evaluated_multiplier_check
        check (evaluated_multiplier is null or evaluated_multiplier >= 1),
    constraint crash_predictions_evaluated_multiplier_finite_check
        check (
            evaluated_multiplier is null
            or (evaluated_multiplier >= 1 and evaluated_multiplier < 'Infinity'::numeric)
        )
);

create index if not exists crash_predictions_created_at_idx
    on public.crash_predictions (created_at desc);
create index if not exists crash_predictions_model_threshold_idx
    on public.crash_predictions (model_version, target_threshold, created_at desc);

alter table public.crash_predictions enable row level security;
revoke all on table public.crash_predictions from anon, authenticated;

comment on table public.crash_predictions is
    'Append-only research ledger; estimates should be stored before their corresponding outcomes arrive.';
