# Crash Feed Inspector

Read-only diagnostics and statistical research for an authorized Crash-game WebSocket feed. The project is designed to distinguish observed protocol data from verified round outcomes and statistical evidence from unsupported prediction claims.

## Current capabilities

- Bounded WebSocket capture with timeout and message-count limits.
- Best-effort redaction of common credential fields before local messages are written.
- Local JSONL inspection that summarizes observed event values, JSON paths, and multiplier-like field candidates without assuming a target-site schema.
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

### Inspect captured messages

After capture, summarize the observed structure locally:

```bash
python -m crash_feed_inspector inspect-jsonl
```

Optional arguments:

```bash
python -m crash_feed_inspector inspect-jsonl data/messages.jsonl --max-messages 100
```

The report lists JSON field paths and types, event-like values, and candidate values for fields whose names resemble multiplier/coefficient fields. This is exploratory evidence only: a numeric field may be an unrelated ID, timer, balance, or intermediate value. Confirm that the event represents a completed round, then compare several captured values with the game's visible completed-round history before configuring parser paths. Do not mark rows verified just because the values look like multipliers.

If the candidate list is empty, that does not prove multipliers are absent: they may be encoded in a binary or non-JSON payload, nested in an unrecognized format, or omitted from this particular feed. Inspect only authorized samples; do not share raw logs until you have reviewed them locally.

Redaction is best-effort, not a guarantee. Do not capture a source if it may expose credentials that cannot safely be retained. Review samples locally before sharing them and remove all session material.

## Validate and analyze historical CSV

CSV must contain round_id and multiplier. Optional columns are timestamp_utc, source, verified, and schema_version. Timestamps must include a timezone. Round IDs must be unique within the file. If verified is omitted or blank, it defaults to false.

```bash
python -m crash_feed_inspector validate-csv path/to/rounds.csv
python -m crash_feed_inspector analyze-csv path/to/rounds.csv --threshold 2.0 --min-train 30
python -m crash_feed_inspector dashboard-csv path/to/rounds.csv --output data/dashboard.html --threshold 2.0
```

Analysis and dashboard generation refuse to proceed if there are no rows explicitly marked verified=true. The HTML dashboard is a local static snapshot, not a live feed. Only mark rows verified after independently reconciling them against a trusted source. Never mark heuristic numeric candidates verified simply because they look plausible.

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
- docs/ARCHITECTURE.md — module boundaries and engineering decisions
- docs/DELIVERY_PLAN.md — acceptance matrix and ordered delivery plan
- docs/METRICS.md — KPI definitions and quality gates
- docs/ROADMAP.md — stages and evidence-based completion criteria

## Current verification limits

The live endpoint and its authoritative completed-round event have not been verified in this repository. Synthetic fixtures test generic parser behavior only; they do not establish the real feed schema or any predictive advantage.

## Android / Termux setup

Termux is supported on a best-effort basis. Use a current Termux installation and run the following from the Termux shell:

```bash
pkg update
pkg install git python nano -y
git clone https://github.com/mohammad919192-hub/Crash-Feed-Inspector.git
cd Crash-Feed-Inspector
python -m pip install -r requirements.txt
python -m crash_feed_inspector --help
cp .env.example .env
nano .env
```

If the repository is already cloned, enter its directory instead of running `git clone` again. If `pip` reports an externally-managed-environment error, do not force-install packages; create a virtual environment with `python -m venv .venv` and activate it with `source .venv/bin/activate`, then rerun the pip install command.

In `.env`, keep exactly one active `CRASH_WS_URL=` assignment and set it only to a WebSocket endpoint you are authorized to access. Do not paste cookies, session tokens, passwords, or authorization headers into this file or share them in logs. Leave all `CRASH_*_PATH` parser fields blank until the actual message format has been inspected and independently confirmed. The endpoint is not verified by this project; a successful WebSocket handshake alone does not prove that completed-round multipliers are present.

Run a capture only after setting an authorized endpoint:

```bash
python -m crash_feed_inspector capture
python -m crash_feed_inspector inspect-jsonl
```

A capture with no parser mapping stores sanitized message samples only; it does not identify or validate multipliers. Review local samples carefully before sharing them because redaction is best-effort. To update an existing checkout after a GitHub change, run `git pull --ff-only` from the repository directory.
