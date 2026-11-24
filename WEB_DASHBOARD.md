# Private web dashboard

The static dashboard is in `site/index.html`. It uses Supabase Auth and the project's publishable key only. Browser reads go through the `dashboard-read` Edge Function; the browser never receives the service-role key.

## Security and access

- The browser uses the public `sb_publishable_` key. This key is designed for client applications; it is not a substitute for authorization.
- `dashboard-read` requires a valid Supabase user JWT (`verify_jwt=true`) and independently validates it with Auth.
- Access is granted only when trusted `app_metadata.crash_dashboard` is the boolean `true`. Do not use `user_metadata`: users can edit it themselves.
- The Edge Function reads the three dashboard tables with its server-side service-role key and returns only the selected fields with bounded row limits. The key is never sent to the browser.
- Migration `20261124090000_web_dashboard_read_access.sql` also defines authenticated SELECT policies gated by the same trusted app_metadata claim. Anonymous table access is revoked.
- Keep public sign-up disabled. Create only approved operator accounts.

## One-time deployment steps

1. Confirm migration `20261124090000_web_dashboard_read_access.sql` is applied to the intended Crash Supabase project. The migration ledger and live schema must be checked after database connectivity is restored.
2. Create the operator's Auth user in Supabase Dashboard > Authentication > Users.
3. On that user, set **App Metadata** to include `{"crash_dashboard": true}`. Do not put this flag in User Metadata. Refresh the user's session after changing it.
4. Confirm the `dashboard-read` Edge Function is deployed with JWT verification enabled.
5. Add the GitHub Pages URL to Authentication > URL Configuration > Site URL and Redirect URLs:
   `https://mohammad919192-hub.github.io/Crash-Feed-Inspector/`
6. In GitHub repository Settings > Pages, choose **GitHub Actions** as the build and deployment source.
7. Pushes to `main` run web smoke tests and deploy the `site/` folder to GitHub Pages.

## Dashboard scope

- Overview: total, verified, pending and conflicting rounds; median and maximum multiplier; distribution histogram.
- Rounds: searchable and filterable history with CSV export.
- Research: read-only model evaluation ledger.
- Operations: GameData365 ingestion run history and status.
- Data refreshes every 60 seconds while the browser tab is visible.
- Limits per refresh: 5,000 rounds, 250 research rows, 100 ingestion runs.

No synthetic records are created. Empty or inaccessible tables are not presented as real data.
