-- Authenticated, read-only access for explicitly authorized Crash Feed Inspector operators.
-- The browser uses only a publishable key; service_role credentials stay server-side.
-- Access is granted only when trusted app_metadata contains crash_dashboard=true.

revoke all on table public.crash_rounds from anon;
revoke all on table public.crash_predictions from anon;
revoke all on table public.crash_ingestion_runs from anon;

grant select on table public.crash_rounds to authenticated;
grant select on table public.crash_predictions to authenticated;
grant select on table public.crash_ingestion_runs to authenticated;

alter table public.crash_rounds enable row level security;
alter table public.crash_predictions enable row level security;
alter table public.crash_ingestion_runs enable row level security;

drop policy if exists "authenticated_read_crash_rounds" on public.crash_rounds;
create policy "authenticated_read_crash_rounds"
  on public.crash_rounds for select to authenticated
  using ((select auth.jwt()) -> 'app_metadata' ->> 'crash_dashboard' = 'true');

drop policy if exists "authenticated_read_crash_predictions" on public.crash_predictions;
create policy "authenticated_read_crash_predictions"
  on public.crash_predictions for select to authenticated
  using ((select auth.jwt()) -> 'app_metadata' ->> 'crash_dashboard' = 'true');

drop policy if exists "authenticated_read_crash_ingestion_runs" on public.crash_ingestion_runs;
create policy "authenticated_read_crash_ingestion_runs"
  on public.crash_ingestion_runs for select to authenticated
  using ((select auth.jwt()) -> 'app_metadata' ->> 'crash_dashboard' = 'true');
