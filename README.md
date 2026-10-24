# Crash Feed Inspector

Read-only diagnostics and statistical research for an authorized Crash-game WebSocket feed. The project distinguishes observed protocol data from verified outcomes and descriptive statistics from unsupported prediction claims.

## Current capabilities

- Bounded, read-only WebSocket capture with timeout and message-count limits.
- Best-effort redaction of common credential fields before local messages are written.
- Local JSONL inspection that reports observed event-like values, JSON paths, and multiplier-like candidates without assuming a site schema.
- Explicit configurable JSON event parsing; no target-site event schema is assumed.
- Candidate rows remain unverified until reconciled against trusted visible history.
- Strict CSV validation, duplicate-round rejection, timestamp normalization, and chronology diagnostics.
- Descriptive statistics, Wilson confidence intervals, recent-window stability checks, and a chronological walk-forward frequency baseline.
- Unit tests through GitHub Actions.
- Supabase schema exists in the connected project, but migration-history reconciliation is still required; the CLI does not write to Supabase.

## Explicit non-goals

- No bet placement, bankroll management, or automated wagering.
- No bypassing authentication, CAPTCHA, rate limits, or access controls.
- No claim that historical outcomes reliably predict the next round.
- No assertion that any endpoint, mirrored site, or undocumented event format is currently working.

## Setup

Requires Python 3.11+.

    python -m venv .venv
    # Windows: .venv\\Scripts\\activate
    # macOS/Linux:
    source .venv/bin/activate
    python -m pip install -r requirements.txt
    cp .env.example .env

Set CRASH_WS_URL in .env to a WebSocket endpoint you are authorized to access. It must begin with ws:// or wss://. Do not put credentials, cookies, or tokens in the URL or commit them to GitHub.

## Capture and inspect a bounded sample

    python -m crash_feed_inspector capture
    python -m crash_feed_inspector inspect-jsonl

Optional inspection arguments:

    python -m crash_feed_inspector inspect-jsonl data/messages.jsonl --max-messages 100

The report lists JSON field paths and types, event-like values, and candidate values for fields whose names resemble multiplier/coefficient fields. This is exploratory only: a numeric field may be an unrelated ID, timer, balance, or intermediate value. Confirm a completed-round event, then compare several captured values with the visible completed-round history before configuring parser paths. Do not mark rows verified because values merely look plausible.

Configuration:
- MAX_MESSAGES: maximum messages (default 100; hard cap 10,000)
- WS_TIMEOUT_SECONDS: receive timeout (default 15; hard cap 300 seconds)
- CRASH_EVENT_TYPE_PATH, CRASH_FINAL_EVENT_TYPES, CRASH_ROUND_ID_PATH, CRASH_MULTIPLIER_PATH: optional schema mapping, only after the event format is confirmed
- CRASH_TIMESTAMP_PATH: optional ISO-8601 timestamp field path
- CRASH_SCHEMA_VERSION: label for the manually documented mapping

A path is a dotted JSON path with optional array indexes, such as data.rounds[0].multiplier. If the mapping is not fully configured, capture stores sanitized messages without inferring multipliers.

Output files are local and ignored by Git:
- data/messages.jsonl: sanitized message samples with capture timestamps
- data/rounds.csv: normalized candidates with verified=false; prior rows are preserved, repeated round IDs are deduplicated, and conflicting multipliers are skipped with a warning

Redaction is best-effort, not a guarantee. Do not capture a source if it may expose credentials that cannot safely be retained. Review samples locally before sharing them and remove all session material.

## Validate, analyze, and research historical CSV

CSV must contain round_id and multiplier. Optional columns are timestamp_utc, source, verified, and schema_version. Timestamps must include a timezone. Round IDs must be unique within the file. If verified is omitted or blank, it defaults to false.

    python -m crash_feed_inspector validate-csv path/to/rounds.csv
    python -m crash_feed_inspector analyze-csv path/to/rounds.csv --threshold 2.0 --min-train 30
    python -m crash_feed_inspector research-csv path/to/rounds.csv
    python -m crash_feed_inspector research-csv path/to/rounds.csv --thresholds 1.5 2 3 5 --windows 30 100 300 --min-history 100 --max-window-rate-gap 0.15
    python -m crash_feed_inspector dashboard-csv path/to/rounds.csv --output data/dashboard.html --threshold 2.0

Research uses only rows explicitly marked verified=true. It reports historical threshold frequencies, Wilson 95% intervals, and stability comparisons across recent windows. Insufficient or unstable history yields a no-signal status. A stable historical rate is not a forecast of the next round and does not establish a profitable edge. Input must be ordered oldest-to-newest. Trying many thresholds/windows and reporting only the best creates multiple-testing bias; predefine comparisons and preserve a final untouched holdout.

Analysis and dashboard generation refuse to proceed if there are no rows explicitly marked verified=true. The HTML dashboard is a local static snapshot, not a live feed. Only mark rows verified after independently reconciling them against a trusted source.

## Python analytics example

    from crash_feed_inspector.analytics import describe, rolling_hit_rates, walk_forward_baseline
    multipliers = [1.12, 1.85, 2.4, 1.03, 5.1]  # synthetic example only
    print(describe(multipliers))
    print(rolling_hit_rates(multipliers, threshold=2.0, window=3))

Historical hit rates are descriptive, not guarantees or proof of a next-round edge. If outcomes are independent, recent results do not make a target multiplier due. A candidate model must be compared with a simple baseline on chronological out-of-sample data and should report uncertainty and a no-signal outcome when no stable edge is demonstrated.

## Tests

    python -m unittest discover -s tests -v
    python -m compileall -q crash_feed_inspector tests

## Data retention and Supabase status

See docs/RESEARCH_PIPELINE.md for the multi-filter workflow, provenance, validation, model-evaluation rules, and data-retention design. GitHub should store source code, tests, schema documentation, migrations, and methodology—not a new commit for every live round. A database is better suited to durable per-round records and a prediction ledger.

The connected Supabase project `Crash` contains empty `public.crash_rounds` and `public.crash_predictions` tables; both have RLS enabled and no direct table access for `anon` or `authenticated`. The eight remote migration versions now have matching local filenames. Five retired Commitment Radar versions are inert historical markers (their original SQL bodies were not present in this repository); three Crash migrations reconstruct the current final schema. The live finite-value guard for `evaluated_multiplier` has been applied and verified. No Edge Functions or ingestion service currently writes data to these tables, so capture remains local-only. See `docs/SUPABASE_MIGRATION_HISTORY.md`. Never expose a service-role key in a browser app.

## Project documents

- docs/PROJECT_SPEC.md — scope and research requirements
- docs/DATA_CONTRACT.md — parsing, normalization, and verification rules
- docs/ARCHITECTURE.md — module boundaries and engineering decisions
- docs/DELIVERY_PLAN.md — acceptance matrix and ordered delivery plan
- docs/METRICS.md — KPI definitions and quality gates
- docs/ROADMAP.md — stages and evidence-based completion criteria
- docs/RESEARCH_PIPELINE.md — multi-filter research, storage, retention, and signal gates

## Current verification limits

The live endpoint and its authoritative completed-round event have not been verified in this repository. Synthetic fixtures test generic parser behavior only; they do not establish the real feed schema or any predictive advantage. A successful WebSocket handshake does not prove completed-round multipliers are present.

## Android / Termux setup

    pkg update
    pkg install git python nano -y
    git clone https://github.com/mohammad919192-hub/Crash-Feed-Inspector.git
    cd Crash-Feed-Inspector
    python -m pip install -r requirements.txt
    python -m crash_feed_inspector --help
    cp .env.example .env
    nano .env

If the repository is already cloned, enter its directory instead of running git clone again. If pip reports an externally-managed-environment error, create a virtual environment with python -m venv .venv and activate it with source .venv/bin/activate; do not force-install packages.

In .env, keep exactly one active CRASH_WS_URL= assignment and set it only to a WebSocket endpoint you are authorized to access. Do not paste cookies, session tokens, passwords, or authorization headers into this file or share them in logs. Leave all CRASH_*_PATH parser fields blank until the actual message format has been inspected and independently confirmed. To update an existing checkout after a GitHub change, run git pull --ff-only from the repository directory.
