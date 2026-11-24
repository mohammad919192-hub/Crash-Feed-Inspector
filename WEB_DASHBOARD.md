# Private web dashboard

The static dashboard is in `site/index.html`. It uses Supabase Auth and the project's publishable key only. The UI is read-only and does not expose provider tokens, database passwords, or the service-role key.

## Security and access

- The browser uses the public `sb_publishable_` key. This key is designed for client applications; it is not a substitute for authorization.
- The browser never uses `service_role`.
- Sign-in is email/password through Supabase Auth. Keep public sign-up disabled and create approved operators under Authentication > Users.
- Migration `20261124090000_web_dashboard_read_access.sql` grants SELECT only to the `authenticated` role on `crash_rounds`, `crash_predictions`, and `crash_ingestion_runs`. Anonymous access is revoked.
- These policies are project-wide for authenticated users. Only create accounts for trusted operators. If multi-tenant access is introduced, add ownership columns and per-user RLS predicates first.

## One-time deployment steps

1. Apply the dashboard migration to the intended Crash Supabase project.
2. Create the operator's Auth user in Supabase Dashboard > Authentication > Users. Do not enable public sign-up.
3. Add the GitHub Pages URL to Authentication > URL Configuration > Site URL and Redirect URLs:
   `https://mohammad919192-hub.github.io/Crash-Feed-Inspector/`
4. In GitHub repository Settings > Pages, choose GitHub Actions as the build and deployment source.
5. Merge the dashboard branch into `main`. The workflow runs smoke tests and deploys the `site/` folder to GitHub Pages.

## Dashboard scope

- Overview: total, verified, pending and conflicting rounds; median and maximum multiplier; distribution histogram.
- Rounds: searchable and filterable history with CSV export.
- Research: read-only model evaluation ledger.
- Operations: GameData365 ingestion run history and status.
- Data refreshes every 60 seconds while the browser tab is visible.
- Limits per refresh: 5,000 rounds, 250 research rows, 100 ingestion runs.

No synthetic records are created. Empty or inaccessible tables are not presented as real data.
