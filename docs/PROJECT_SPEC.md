# Crash Feed Inspector — Project Specification

## Mission
Build a read-only research tool that captures authorized Crash-game feed messages, establishes the event schema, maintains a clean historical dataset, computes descriptive statistics, and evaluates probability estimates on unseen future rounds.

This is not an automated betting bot. It must not place wagers, bypass authentication, evade access controls, or claim guaranteed prediction.

## Primary uncertainty
The available endpoint and authoritative final-result field are not yet verified. Numeric values found in protocol messages are not outcomes unless a reviewed event mapping and independent reconciliation support that interpretation.

## Data pipeline
1. Capture a bounded sample from an authorized WebSocket endpoint or import a user-provided historical CSV.
2. Write locally sanitized JSON Lines with capture time and message index. Redaction is best-effort; do not capture sources that may expose credentials that cannot safely be retained.
3. Identify event types, stable round IDs, timestamps, and the authoritative completed-round result from real sanitized samples.
4. Parse only through an explicit event allowlist and configured field paths. All parsed rows remain verified=false until manually reconciled with trusted visible history.
5. Normalize candidate rows to round_id, timestamp_utc, multiplier, source, verified, and schema_version.
6. Reject invalid/non-finite multipliers, duplicate IDs, malformed timestamps, duplicate CSV headers, unknown columns, and malformed row shapes. Report missing timestamps and chronology violations.
7. Report sample size, nearest-rank quantiles, empirical threshold frequencies, rolling-window changes, and data-quality limits.
8. Evaluate historical-frequency estimates chronologically using walk-forward splits. Candidate models must use the same splits and preserve an untouched final holdout.
9. Report calibration, Brier score, uncertainty, sample size, and limitations when enough verified observations exist.
10. Report no-signal if evidence does not show a stable out-of-sample improvement over the baseline.

## Prediction scenarios
- Historical-frequency baseline: estimate the observed share of outcomes at or above a predeclared threshold. This is descriptive and does not mean the next round is due.
- Rolling windows: compare recent rates with long-run rates while exposing window size and sample count. Short windows can overreact to randomness.
- Probabilistic models: consider only after enough verified outcomes exist; use features available before the prediction time and calibrate outputs.
- Walk-forward evaluation: each estimate must use only earlier observations; preserve an untouched final holdout when selecting models.
- No-signal outcome: if a model does not robustly outperform the baseline out of sample, explicitly report that no predictive edge was demonstrated.

## Independence and uncertainty
If outcomes are generated independently by a fair/random mechanism, recent results do not make a specific next multiplier due. Streaks and clusters can occur by chance. A predictive edge is not established by historical fit alone; it must be stable and survive out-of-sample evaluation.

## Security and compliance
Use only authorized data. Do not bypass login, CAPTCHA, rate limits, or access controls. Do not commit captured feed samples, credentials, cookies, tokens, or signed URLs. The proposed Supabase schema stores normalized round data only, not raw messages. No wagering automation is in scope.

## Implementation status

Implemented in the repository:
- bounded read-only capture and best-effort redaction;
- configurable JSON path parser with exact final-event allowlist;
- normalized CSV loading, strict validation, and quality report;
- verified-only CLI analysis;
- descriptive statistics and chronological walk-forward baseline;
- unit tests and CI on Python 3.11 and 3.12;
- local static HTML report for verified historical data;
- review-only Supabase migration with RLS enabled and client access revoked.

Not yet established:
- live endpoint reachability and authorization;
- actual final-event type and multiplier path;
- any real protocol fixture or trusted historical dataset;
- a stable predictive advantage;
- a live Supabase destination or ingestion service;
- a live or deployed dashboard (only an offline static report is implemented).

## Completion criteria
- [x] Unit tests and compilation pass in CI for supported Python versions (observed on commit with capture tests; recheck after later commits).
- [x] Generic parser behavior is covered by synthetic tests.
- [ ] Real endpoint and final-result semantics are documented with evidence.
- [x] CSV input is checked for duplicates, invalid values, timezone ambiguity, and malformed shape.
- [x] Statistical summaries expose sample size and interpretation limits.
- [x] Walk-forward baseline uses only earlier observations.
- [x] README distinguishes parsed candidates from verified outcomes.
- [ ] Real-feed fixtures and reconciliation tests are added after a sanitized sample is reviewed.
- [ ] Candidate models are benchmarked against the baseline on an untouched holdout.
- [ ] The intended Supabase project is confirmed before applying migrations.
