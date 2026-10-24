# Roadmap

## Stage 1 — Foundation and offline safety
- [x] Bounded read-only WebSocket capture
- [x] Sanitize common credential-shaped fields before local logging
- [x] Explicit schema-mapped event parser that never self-certifies outcomes
- [x] Strict CSV loading, duplicate-ID rejection, timezone normalization, and quality report
- [x] CLI commands for capture, CSV validation, and verified-only analysis
- [x] Descriptive statistics and chronological walk-forward baseline
- [x] Unit tests and GitHub Actions workflow
- [ ] Confirm the latest GitHub Actions run is green

## Stage 2 — Establish data truth
- [ ] Capture a small sample from an authorized endpoint
- [ ] Review and sanitize the sample before sharing
- [ ] Identify actual event types and authoritative completed-round field
- [ ] Compare parsed outcomes with visible game history
- [ ] Add sanitized fixtures derived from the real protocol, with secrets removed
- [ ] Record source, schema version, and validation procedure

## Stage 3 — Historical dataset
- [x] Define normalized CSV contract: round ID, timestamp, multiplier, source, verification state, schema version
- [x] Reject duplicate IDs and invalid or non-finite multipliers
- [x] Report missing timestamps and out-of-order timestamps
- [ ] Add real-feed reconciliation and conflict-resolution workflow
- [ ] Establish retention and provenance rules for historical datasets

## Stage 4 — Research evaluation
- [x] Historical-frequency baseline with chronological walk-forward evaluation
- [x] Brier score and majority-direction accuracy for the baseline
- [ ] Compare candidate models against the baseline on identical time splits
- [ ] Preserve an untouched final holdout
- [ ] Report calibration, uncertainty, sample sizes, and multiple-testing risk
- [ ] Record predictions before outcomes arrive
- [ ] Report no-signal when no robust advantage exists

## Stage 5 — Persistence and operator interface
- [x] Generate a self-contained local HTML snapshot from verified CSV data
- [x] Inspect the connected Supabase `Crash` project, table definitions, grants, RLS, migration history, and advisors
- [ ] Reconcile remote-only migration history, then verify the schema migration against the live table contract
- [ ] Build a live feed-health and parser-diagnostics interface
- [x] Add historical distribution and data-quality views in the local HTML report
- [ ] Add model-evaluation views after a real verified dataset exists
- [ ] Deploy only after endpoint mapping, tests, and access policy are reviewed

The live endpoint and result schema remain unverified. Supabase table/RLS state was inspected, but migration history is incomplete in the repository and no ingestion service is present. A successful socket connection does not prove correct parsing; a backtest does not guarantee future performance. No betting or bankroll automation is in scope.
