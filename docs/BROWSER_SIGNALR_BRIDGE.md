# Browser SignalR bridge (no provider API key)

This option captures completed crash multipliers from a game page that you open and are authorized to access. It uses the browser's existing WebSocket session; it does **not** request or export cookies, bearer tokens, account IDs, balances, or betting messages.

## What the open-source reference establishes

The reference implementation [dinethlive/crash-game-RAG](https://github.com/dinethlive/crash-game-RAG) documents a SignalR WebSocket path containing `sockets/crash`, the SignalR record separator `\\x1e`, and a completed-round event named `OnCrash` whose first argument contains the multiplier in `f`. It is an implementation reference for one Melbet game page, not a universal provider contract. Its AI prediction logic is not used here.

## 1. Start the local receiver in Termux

From the repository root:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the generated random value into your ignored local `.env` file:

```ini
CRASH_BRIDGE_TOKEN=PASTE_YOUR_RANDOM_VALUE_HERE
CRASH_BRIDGE_HOST=127.0.0.1
CRASH_BRIDGE_PORT=8765
```

Start the receiver:

```bash
python -m crash_feed_inspector bridge-server
```

It binds only to loopback. Keep Termux running while collecting.

## 2. Install the browser userscript

1. Install a userscript manager that supports `GM_xmlhttpRequest` (for example, Tampermonkey or Violentmonkey) in a compatible Android browser.
2. Open `userscripts/crash-feed-inspector.user.js` from this repository and create a new userscript with its contents.
3. Replace `REPLACE_WITH_LOCAL_CRASH_BRIDGE_TOKEN` with the exact same random value used in `.env`.
4. Save and enable the script.
5. Open the crash game page in the same Android device. The page must be one you can access normally; do not share session material.

The script only observes WebSocket URLs containing `/sockets/crash` and forwards SignalR `OnCrash` events. It does not create a game connection or bypass login.

## 3. Confirm capture

Open this URL on the same device to confirm the local receiver is running:

`http://127.0.0.1:8765/health`

When a round ends, Termux should print a line similar to:

`Browser SignalR: saved 2.31x | totals=...`

The captured file is:

`data/continuous_rounds.csv`

The SQLite database is:

`data/collector.sqlite3`

## Important data-quality limits

- The reference's `OnCrash` / `f` mapping is documented by a third-party project and is not an official schema for every crash game. Confirm several captured values against the visible completed-round history.
- The receiver uses a locally generated event ID because the reference does not establish a stable round ID in the event. Replays may therefore not deduplicate across separate page sessions.
- The timestamp is the browser observation time, not a provider-signed event timestamp.
- All rows remain `verified=false`. The bridge does not establish source authenticity or predictive advantage.
- The reference project is specifically configured for a Melbet game URL; other brands may use different WebSocket paths, event names, or payload fields. If the page does not emit `/sockets/crash` + `OnCrash`, this adapter will collect nothing.
- The userscript runs on HTTPS pages but only forwards the single final multiplier field and minimal metadata. Never edit it to forward cookies, authorization headers, or full socket traffic.
