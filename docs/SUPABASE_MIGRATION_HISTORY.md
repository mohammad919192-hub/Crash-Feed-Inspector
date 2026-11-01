# Supabase migration history reconciliation

## Connected project

The connected Supabase project is `Crash` (`htfrixfcirgrhlmwtkjs`). Its remote migration ledger contained these versions:

- `20261015112619_commitment_radar_initial_schema`
- `20261015120014_commitment_radar_backend_hardening`
- `20261018094039_commitment_radar_audit_trigger_hardening`
- `20261018100502_commitment_radar_audit_cascade_guard`
- `20261021102333_clear_legacy_application_for_reuse`
- `20261021105220_crash_research_schema`
- `20261021111154_crash_integrity_guardrails`
- `20261021112101_crash_prediction_integrity`
- `20261024131139_crash_predictions_evaluated_multiplier_finite_guard`
- `20261024132027_create_crash_rounds`
- `20261024132036_crash_research_ledger`
- `20261101103009_gamedata365_ingestion_pipeline`
- `20261101103309_relocate_pg_net_extension`

The first five original migration SQL bodies were not present in this repository, and the live project no longer contains the legacy Commitment Radar tables. Their local files are therefore explicitly marked historical/inert for fresh installs: they preserve timestamp alignment without re-creating the retired application. This is a deliberate final-state baseline, **not** a claim that the original SQL bodies were recovered.

The Crash migrations reconstruct the current end-state schema for clean local resets. The three migrations recorded on 2026-10-24 were applied through the Supabase migration tool; the latter two are idempotent schema confirmations. All 13 remote migration versions now have matching local filenames.

## Live repair

On 2026-10-24, the live `public.crash_predictions` table was confirmed empty. A migration added and validated `crash_predictions_evaluated_multiplier_finite_check`, enforcing that a non-null evaluated multiplier is finite and at least 1. The weaker previous constraint was removed after the stronger constraint was validated. No rows were deleted or rewritten.

The live project keeps all application tables server-only with RLS enabled and no direct `anon`/`authenticated` grants. The non-relocatable `pg_net` extension was safely recreated in the non-exposed `extensions` schema after confirming its request queue and response store were empty. The `ingest-crash-rounds` and `sync-gamedata365` Edge Functions are deployed with JWT verification enabled and only accept a `service_role` JWT. The new `public.crash_ingestion_runs` table records sanitized polling diagnostics. The GameData365 key must be added to Edge Function Secrets and the cron caller's legacy service-role JWT must be stored in Vault before automated polling is enabled. Never put either key in a client, chat, or Git commit. See `docs/GAMEDATA365_INGESTION.md`.

## Required verification before future schema changes

1. Run `supabase migration list` after linking the CLI to project `htfrixfcirgrhlmwtkjs`.
2. Review `supabase db push --dry-run` and ensure only intended pending versions are shown.
3. Apply only reviewed migrations; do not use `db reset --linked` on this project.
4. After any schema change, verify the resulting columns, constraints, RLS state, grants, and migration ledger with read-only SQL queries.
5. Run `supabase db reset` locally (not linked) to prove the migration chain can create the intended final schema from scratch.

The local migration chain intentionally produces only the current Crash Feed Inspector schema; it does not recreate the retired Commitment Radar app.
