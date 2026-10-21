# Architecture and Engineering Decisions

## System boundary

```text
Authorized WebSocket endpoint
        |
        v
Bounded capture (timeout + message cap)
        |
        +--> best-effort secret redaction --> local sanitized JSONL
        |
        v
Explicit schema mapping (no guessed event names or fields)
        |
        v
Candidate final-result rows (verified=false)
        |
        v
CSV contract validation + data-quality report
        |
        v
Manual reconciliation with trusted visible history
        |
        v
Verified historical dataset
        |
        v
Descriptive analysis + chronological walk-forward baseline
```

## Module ownership

- capture.py: network boundary, bounded reads, sanitized local persistence, candidate CSV export.
- security.py: best-effort redaction of common secret-shaped fields.
- protocol.py: explicit JSON-path resolution and event allowlist; never sets verified=true.
- dataset.py: strict CSV contract, timestamp normalization, duplicate rejection, quality report.
- analytics.py: descriptive statistics, rolling empirical rates, and walk-forward baseline.
- cli.py: command routing and JSON output.
- report.py: self-contained local HTML report from explicitly verified CSV rows only.
- Supabase migration: proposed server-only persistence schema; not deployed.

## Design decisions

1. No guessed multiplier extraction. Raw protocol messages often include timestamps, IDs, counters, and unrelated numeric values. The parser must be configured from an observed and reviewed schema.
2. Parsing is not verification. Parsed values remain candidates until reconciled against a trusted reference.
3. Fail closed on malformed data. Invalid numeric values, duplicate round IDs, unsupported CSV columns, and ambiguous timezone values are rejected rather than silently corrected.
4. Keep credentials out of logs. Common sensitive fields are redacted before writing. Redaction is best-effort, so sensitive sources must not be captured if safe retention cannot be established.
5. No direct database writes yet. The existing active Supabase project has not been confirmed as belonging to this repository. The migration is review-only until the correct destination and ingestion trust boundary are established.
6. Research must be chronological. Model features and probabilities for a round may use only earlier outcomes. Historical fit alone is not evidence of a reliable edge.
7. No betting actions. The project is read-only and analytical.

## Known gaps

- Live endpoint reachability and permissions are unverified.
- The authoritative final event and multiplier field are unknown.
- No sanitized fixture from the actual protocol has been reviewed.
- No real dataset exists in the repository.
- CI status must be checked after the current commits.
- The HTML report is a local snapshot, not a live dashboard or live Supabase ingestion service.
