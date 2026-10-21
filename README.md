# Crash Feed Inspector

Read-only diagnostics and statistical research for a configured Crash-game WebSocket feed.

## What it does now

- Captures a bounded number of raw WebSocket messages into JSON Lines.
- Extracts numeric strings as **unverified candidates only**.
- Computes descriptive statistics for explicitly validated historical multipliers.
- Evaluates a simple historical-frequency baseline with chronological walk-forward testing.
- Runs unit tests in GitHub Actions.

## What it does not do

- It does not place bets or interact with the game to make wagers.
- It does not bypass authentication, CAPTCHA, rate limits, or access controls.
- It does not currently know the target site's authoritative event schema.
- It does not claim that historical outcomes can reliably predict the next round.

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

Edit .env and set CRASH_WS_URL to a WebSocket endpoint you are authorized to access. The endpoint must begin with ws:// or wss://. Do not put credentials, cookies, or tokens in the URL or commit them to GitHub.

Start a bounded capture:

```bash
python -m crash_feed_inspector
```

Optional settings in .env:
- MAX_MESSAGES: maximum messages to capture (default 100; hard cap 10,000)
- WS_TIMEOUT_SECONDS: socket timeout (default 15 seconds)

Output files are created locally in data/ and ignored by Git:
- messages.jsonl: raw message strings and capture timestamps
- rounds.csv: heuristic numeric candidates marked verified=false

**Important:** the current extraction is intentionally heuristic. Protocol messages can contain IDs, timestamps, counters, and unrelated numbers. Never use rounds.csv as a verified outcome dataset until the event schema is understood and each result has been validated against visible game history.

## Statistical functions

The analytics module accepts only finite numeric multipliers >= 1.0.

```python
from crash_feed_inspector.analytics import describe, rolling_hit_rates, walk_forward_baseline

multipliers = [1.12, 1.85, 2.4, 1.03, 5.1]  # example values only; replace with verified data
print(describe(multipliers))
print(rolling_hit_rates(multipliers, threshold=2.0, window=3))
# Walk-forward needs more rows than min_train; this is an evaluation, not betting advice.
```

The historical hit rate is not a guarantee or proof of a next-round edge. If outcomes are independent, recent results do not make a target multiplier due. See docs/PROJECT_SPEC.md for the research design and docs/ROADMAP.md for the completion plan.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Next critical step

Capture a small authorized sample, sanitize it, identify the actual event types and authoritative final-result field, then create schema-aware parsing and fixtures. Do not train a model on guessed numeric substrings.
