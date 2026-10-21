# Metrics and Quality Gates

These definitions are a measurement contract, not current measured values. The repository contains no verified real-feed dataset yet, so targets remain unset until a baseline is observed.

| Metric | Definition | Interpretation guardrail | Current status |
|---|---|---|---|
| Connection success rate | Successful authorized connection attempts divided by all recorded connection attempts | Requires attempt-level operational logging; not available from a single capture transcript | Not measured |
| Messages captured | Number of received frames during a bounded capture | A larger count does not prove correct event parsing | Reported in CLI output |
| Candidate event rate | Schema-matched candidate events divided by decodable messages | Measures parser matching, not result accuracy | Available after explicit mapping |
| Parse error rate | Malformed configured result events divided by matched result-event attempts | Keep malformed fields separate from ignored non-final events | Partially counted during capture |
| Reconciliation accuracy | Candidate outcomes matching a trusted reference divided by candidates independently checked | Record sample selection and mismatches; never estimate this from parser output alone | Not measured |
| Round ID duplicate rate | Duplicate candidate round IDs divided by candidate rows | Distinguish repeated protocol notifications from conflicting multipliers | Conflicts are excluded in capture; dataset CSV duplicates are rejected |
| Timestamp coverage | Rows with timezone-aware timestamps divided by all imported rows | Missing timestamps weaken chronology and time-based evaluation | Reported by quality report |
| Chronology violation count | Count of observed timestamp decreases in CSV row order | Do not silently sort before evaluating sequence-sensitive data | Reported by quality report |
| Verified-data coverage | Explicitly verified rows divided by all candidate rows | A true flag is an assertion supported by documented reconciliation, not cryptographic proof | Reported by quality report |
| Brier score | Mean squared error of probability estimates for binary threshold outcomes | Compare against the baseline on identical walk-forward splits; lower is better | Implemented for historical-frequency baseline |
| Baseline improvement | Candidate model Brier score minus baseline Brier score on identical observations | Negative values favor the candidate; require uncertainty and untouched holdout before claims | Not implemented for candidate models |
| Calibration error | Difference between predicted probability and observed frequency across predeclared bins | Require enough observations per bin and report bin counts | Pending verified data and candidate model |

## Measurement rules

1. Do not set numeric targets until a verified baseline exists.
2. Keep operational health, parser coverage, outcome authenticity, and predictive quality as separate metric families.
3. Use explicit denominators and report sample sizes for every rate.
4. Keep data-quality failures visible; do not drop malformed records silently.
5. Compare predictive methods on identical chronological splits.
6. Treat no demonstrated improvement as a valid result, not a failed project.

## Immediate next measurement step

After an authorized feed sample is captured, document the message count, event-type distribution, candidate count, parse errors, conflicting round IDs, timestamp coverage, and manual reconciliation results. Do not calculate predictive performance until a sufficiently large verified history exists.
