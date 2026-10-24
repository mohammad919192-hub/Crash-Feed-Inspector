-- Add integrity guards to the normalized round ledger.
do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.crash_rounds'::regclass
          and conname = 'crash_rounds_multiplier_check'
    ) then
        alter table public.crash_rounds
            add constraint crash_rounds_multiplier_check
            check (multiplier >= 1 and multiplier < 'Infinity'::numeric) not valid;
    end if;

    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.crash_rounds'::regclass
          and conname = 'crash_rounds_source_event_sha256_format_check'
    ) then
        alter table public.crash_rounds
            add constraint crash_rounds_source_event_sha256_format_check
            check (source_event_sha256 is null or source_event_sha256 ~ '^[0-9a-f]{64}$') not valid;
    end if;

    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.crash_rounds'::regclass
          and conname = 'crash_rounds_check'
    ) then
        alter table public.crash_rounds
            add constraint crash_rounds_check
            check (
                (verified = false and verification_status <> 'verified')
                or (
                    verified = true
                    and verification_status = 'verified'
                    and verification_method is not null
                    and length(btrim(verification_method)) > 0
                    and verified_at is not null
                )
            ) not valid;
    end if;
end
$$;

alter table public.crash_rounds validate constraint crash_rounds_multiplier_check;
alter table public.crash_rounds validate constraint crash_rounds_source_event_sha256_format_check;
alter table public.crash_rounds validate constraint crash_rounds_check;

alter table public.crash_rounds enable row level security;
revoke all on table public.crash_rounds from anon, authenticated;
