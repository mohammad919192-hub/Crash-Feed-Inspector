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

The first five original migration SQL bodies were not present in this repository, and the live project no longer contains the legacy Commitment Radar tables. Their local files are therefore explicitly marked historical/inert for fresh installs: they preserve timestamp alignment without re-creating the retired application. This is a deliberate final-state baseline, **not** a claim that the original SQL bodies were recovered.

The three Crash migration files reconstruct the current end-state schema for clean local resets. Later migrations are idempotent and apply the current schema/guardrails.

## Live repair

On 2026-10-24, the live `public.crash_predictions` table was confirmed empty. A migration added and validated `crash_predictions_evaluated_multiplier_finite_check`, enforcing that a non-null evaluated multiplier is finite and at least 1. The weaker previous constraint was removed after the stronger constraint was validated. No rows were deleted or rewritten.

The live project still has no public client table grants or RLS policies. That is intentional until a server-side ingestion path with a least-privilege credential is implemented. Never put the service-role key in a client or commit it.

## Required verification before future schema changes

1. Run `supabase migration list` after linking the CLI to project `htfrixfcirgrhlmwtkjs`.
2. Review `supabase db push --dry-run` and ensure only intended pending versions are shown.
3. Apply only reviewed migrations; do not use `db reset --linked` on this project.
4. After any schema change, verify the resulting columns, constraints, RLS state, grants, and migration ledger with read-only SQL queries.
5. Run `supabase db reset` locally (not linked) to prove the migration chain can create the intended final schema from scratch.

The local migration chain intentionally produces only the current Crash Feed Inspector schema; it does not recreate the retired Commitment Radar app.
