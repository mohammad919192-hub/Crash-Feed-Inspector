# Roadmap

## Stage 1 — Foundation
- [x] Bounded read-only WebSocket capture starter
- [x] Fix numeric regex and JSON Lines newline handling
- [x] Descriptive statistics and walk-forward baseline functions
- [x] Unit tests and CI workflow
- [ ] Run CI and resolve failures

## Stage 2 — Establish data truth
- [ ] Capture a small sample from an authorized endpoint
- [ ] Add sanitized protocol fixtures with no credentials
- [ ] Identify message types and authoritative final-result event
- [ ] Compare parsed outcomes with visible game history
- [ ] Replace heuristic extraction with schema-aware parsing

## Stage 3 — Historical dataset
- [ ] Add strict CSV import
- [ ] Normalize round ID, timestamp, multiplier, source, verification state
- [ ] Detect duplicates, gaps, invalid values, and ordering issues
- [ ] Produce a data-quality report

## Stage 4 — Research evaluation
- [ ] Compare baseline, rolling windows, and candidate models
- [ ] Use walk-forward evaluation and an untouched holdout
- [ ] Report calibration, Brier score, uncertainty, and sample sizes
- [ ] Record predictions before outcomes arrive
- [ ] Report no-signal when no robust advantage exists

## Stage 5 — User interface
- [ ] Connection and feed-health dashboard
- [ ] Historical chart and threshold-frequency table
- [ ] Data-quality and parser diagnostics
- [ ] Model-evaluation view with uncertainty
- [ ] No bet placement or bankroll automation

A successful connection does not prove correct parsing; good backtest results do not guarantee future performance.
