# Delivery Plan and Acceptance Matrix

## Observable outcome

A read-only research tool that can capture a bounded authorized feed sample, parse only explicitly mapped final-result events, preserve unverified status until reconciliation, validate historical CSV data, and evaluate simple historical baselines without implying a guaranteed prediction.

## Source snapshot

- Repository: https://github.com/mohammad919192-hub/Crash-Feed-Inspector
- Default branch: main
- Implementation is committed directly to the repository.
- Current source paths are recorded in the module map in docs/ARCHITECTURE.md.
- The real endpoint and authoritative event schema remain unknown.
- The Supabase migration is proposed and review-only; it has not been applied.

## Traceability and acceptance

| Requirement | Component | Implementation | Acceptance evidence |
|---|---|---|---|
| P-01 Bounded, read-only capture | C-01 | crash_feed_inspector/capture.py | tests/test_capture.py; bounded message and timeout settings |
| P-02 Never infer a result from arbitrary numbers | C-02 | crash_feed_inspector/protocol.py | tests/test_protocol.py; configured mapping required |
| P-03 Do not persist common credential-shaped fields as-is | C-03 | crash_feed_inspector/security.py | tests/test_security.py; redaction is explicitly best-effort |
| P-04 Reject invalid or ambiguous CSV data | C-04 | crash_feed_inspector/dataset.py | tests/test_dataset.py; duplicate IDs, invalid values, malformed headers and ambiguous timestamps rejected |
| P-05 Analyze verified outcomes only | C-05 | crash_feed_inspector/cli.py and analytics.py | tests/test_analytics.py and CLI guard |
| P-06 Keep statistical evaluation chronological | C-06 | crash_feed_inspector/analytics.py | walk-forward baseline uses earlier rows only; Brier score reported |
| P-07 Restrict database access by default | C-07 | supabase/migrations/20261021000000_create_crash_rounds.sql | migration review only; live DB verification intentionally pending |
| P-08 Reproducible CI | C-08 | .github/workflows/tests.yml | Python 3.11 and 3.12 compile and unit-test jobs |
| P-09 Source-backed historical visualization | C-09 | crash_feed_inspector/report.py | tests/test_report.py; verified rows only; standalone local HTML |

## Ordered delivery sequence

1. Run the CI matrix after the latest commit; fix any failing test and rerun.
2. Confirm the WebSocket endpoint is authorized and reachable using a small bounded capture.
3. Inspect sanitized messages locally. Do not send credentials, cookies, signed URLs, or account identifiers.
4. Identify the event discriminator, stable round ID, authoritative completed multiplier field, and optional timestamp.
5. Configure the parser mapping and compare a sample of candidate rows with visible completed-round history.
6. Add sanitized fixtures from the actual protocol only after that review.
7. Import a real historical dataset, run the quality report, and document provenance.
8. Compare the historical-frequency baseline to candidate models with walk-forward splits and an untouched final holdout.
9. Choose the intended Supabase project before applying the migration or implementing any ingestion writes.
10. Use the local HTML snapshot for verified historical summaries; build a live dashboard only after data quality and the event schema are established.

## Release gates

- No live feed claims until endpoint reachability is observed.
- No verified-result claims until candidate outcomes are reconciled with a trusted reference.
- No model-performance claims without an adequate sample, chronological evaluation, and comparison against a baseline.
- No Supabase writes until the destination project and least-privilege server-side ingestion path are approved.
- No wagering automation is included.

## Reporting contract

For each implementation pass, report changed paths, commit references, CI run URL and conclusion, commands or checks actually executed, remaining unknowns, and actions not performed. Never infer a passing CI result from the existence of a workflow file.
