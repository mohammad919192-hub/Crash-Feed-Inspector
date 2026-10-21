# Crash Feed Inspector

Read-only diagnostics and statistical research for an authorized Crash-game WebSocket feed. The project is designed to distinguish observed protocol data from verified round outcomes and statistical evidence from unsupported prediction claims.

## Current capabilities

- Bounded WebSocket capture with timeout and message-count limits.
- Best-effort redaction of common credential fields before local messages are written.
- Explicit, configurable JSON event parsing; no target-site event schema is assumed.
- Candidate rows remain unverified until reconciled against a trusted visible result history.
- Strict CSV validation, duplicate-round rejection, timestamp normalization, and chronology diagnostics.
- Descriptive statistics and a chronological walk-forward historical-frequency baseline.
- Unit tests through GitHub Actions.

## Explicit non-goals

- No bet placement, bankroll management, or automated wagering.
- No bypassing authentication, CAPTCHA, rate limits, or access controls.
- No claim that historical outcomes reliably predict the next round.
- No assertion that any endpoint, mirrored site, or undocumented event format is currently working.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set CRASH_WS_URL in .env to a WebSocket endpoint you are authorized to access. It must begin with ws:// or wss://. Do not put credentials, cookies, or tokens in the URL or commit them to GitHub.

## Capture a bounded sample

```bash
python -m crash_feed_inspector capture
```

Configuration:
- MAX_MESSAGES: maximum messages (default 100; hard cap 10,000)
- WS_TIMEOUT_SECONDS: receive timeout (default 15; hard cap 300 seconds)
- CRASH_EVENT_TYPE_PATH, CRASH_FINAL_EVENT_TYPES, CRASH_ROUND_ID_PATH, CRASH_MULTIPLIER_PATH: optional schema mapping, only after the event format is confirmed
- CRASH_TIMESTAMP_PATH: optional ISO-8601 timestamp field path
- CRASH_SCHEMA_VERSION: label for the manually documented mapping

A path is a dotted JSON path with optional array indexes, such as data.rounds[0].multiplier. The examples in .env.example are illustrative only, not a verified schema for any particular website. If the mapping is not fully configured, capture stores sanitized messages without inferring multipliers.

Output files are local and ignored by Git:
- data/messages.jsonl: sanitized message samples with capture timestamps
- data/rounds.csv: schema-matched candidates in normalized CSV shape; verified is always false

Redaction is best-effort, not a guarantee. Do not capture a source if it may expose credentials that cannot safely be retained. Review samples locally before sharing them and remove all session material.

## Validate and analyze historical CSV

CSV must contain round_id and multiplier. Optional columns are timestamp_utc, source, verified, and schema_version. Timestamps must include a timezone. Round IDs must be unique within the file. If verified is omitted or blank, it defaults to false.

```bash
python -m crash_feed_inspector validate-csv path/to/rounds.csv
python -m crash_feed_inspector analyze-csv path/to/rounds.csv --threshold 2.0 --min-train 30
```

Analysis refuses to proceed if there are no rows explicitly marked verified=true. Only mark rows verified after independently reconciling them against a trusted source. Never mark heuristic numeric candidates verified simply because they look plausible.

## Python analytics example

```python
from crash_feed_inspector.analytics import describe, rolling_hit_rates, walk_forward_baseline

# Example values only; replace with verified historical outcomes.
multipliers = [1.12, 1.85, 2.4, 1.03, 5.1]
print(describe(multipliers))
print(rolling_hit_rates(multipliers, threshold=2.0, window=3))
```

Historical hit rates are descriptive, not guarantees or proof of a next-round edge. If outcomes are independent, recent results do not make a target multiplier due. Any candidate model must be compared with a simple baseline on chronological out-of-sample data and should report uncertainty and a no-signal outcome when no stable edge is demonstrated.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q crash_feed_inspector tests
```

## Project documents

- docs/PROJECT_SPEC.md — scope and research requirements
- docs/DATA_CONTRACT.md — parsing, normalization, and verification rules
- docs/ROADMAP.md — stages and evidence-based completion criteria

## Current verification limits

The live endpoint and its authoritative completed-round event have not been verified in this repository. Synthetic fixtures test generic parser behavior only; they do not establish the real feed schema or any predictive advantage.
