-- Reconciled live repair: reject non-finite evaluated multipliers.
-- Safe to replay; the live table was empty when this constraint was installed.
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'crash_predictions_evaluated_multiplier_finite_check'
          and conrelid = 'public.crash_predictions'::regclass
    ) then
        alter table public.crash_predictions
            add constraint crash_predictions_evaluated_multiplier_finite_check
            check (
                evaluated_multiplier is null
                or (
                    evaluated_multiplier >= 1
                    and evaluated_multiplier < 'Infinity'::numeric
                )
            ) not valid;
    end if;
end
$$;

alter table public.crash_predictions
    validate constraint crash_predictions_evaluated_multiplier_finite_check;
