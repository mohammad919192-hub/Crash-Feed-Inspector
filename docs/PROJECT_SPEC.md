# Crash Feed Inspector — Project Specification

## Mission
Build a read-only research tool that captures authorized Crash-game feed messages, verifies the event schema, maintains clean historical results, computes descriptive statistics, and evaluates probability estimates on unseen future rounds.

This is not an automated betting bot. It must not place wagers, bypass authentication, evade access controls, or claim guaranteed prediction.

## Primary uncertainty
The first challenge is proving that the available feed can be accessed legitimately and identifying the authoritative final-result field. Until that is done, numeric strings extracted from protocol messages are unverified candidates, not confirmed multipliers.

## Data pipeline
1. Ingest bounded read-only WebSocket messages or user-provided historical CSV.
2. Store raw messages as append-only JSON Lines with capture time and message index. Never store cookies, tokens, or credentials.
3. Identify event types, round IDs, timestamps, and the authoritative completed-round result.
4. Normalize only verified outcomes into round_id, timestamp_utc, multiplier, source, verified, schema_version.
5. Validate finite multipliers >= 1.0; detect duplicates, missing IDs, out-of-order timestamps, gaps, and schema drift.
6. Report sample size, quantiles, empirical threshold frequencies, and rolling-window changes.
7. Evaluate estimates chronologically using walk-forward splits and compare against a simple historical-rate baseline.
8. Report calibration, Brier score, uncertainty, coverage, and limitations.

## Prediction scenarios
- Historical-frequency baseline: estimate the observed share of outcomes at or above a predeclared threshold. This is descriptive and does not mean the next round is due.
- Rolling windows: compare recent rates with long-run rates while exposing window size and sample count. Short windows can overreact to randomness.
- Probabilistic models: only consider after enough verified outcomes exist; use features available before the prediction time and calibrate outputs.
- Walk-forward evaluation: each estimate must use only earlier rounds; preserve an untouched final holdout when selecting models.
- No-signal outcome: if a model does not robustly outperform the baseline out of sample, explicitly report that no predictive edge was demonstrated.

## Independence and uncertainty
If outcomes are generated independently by a fair/random mechanism, recent results do not make a specific next multiplier due. Streaks and clusters can occur by chance. A predictive edge is not established by historical fit alone; it must be stable and survive out-of-sample evaluation.

## Security and compliance
Use only authorized data. Do not bypass login, CAPTCHA, rate limits, or access controls. Keep session material out of source control and logs. Do not automate bets. Apply bounded capture limits.

## Completion criteria
1. Unit tests pass in CI.
2. Parser is covered by sanitized protocol fixtures.
3. Endpoint and final-result semantics are documented with evidence.
4. Imported results are checked for duplicates, invalid values, and chronology.
5. Reports include sample size and uncertainty.
6. Evaluation is chronological, reproducible, and benchmarked.
7. README distinguishes verified outcomes from heuristic candidates.
