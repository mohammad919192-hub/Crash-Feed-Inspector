# Crash Feed Inspector

Read-only diagnostic tool for inspecting a configured Crash-game WebSocket feed.

## Status

The WebSocket endpoint and message schema have not yet been verified against the target site. Do not treat extracted values as confirmed round results or predictions.

## Safety

- No automated betting.
- No authentication bypass.
- Configure only a WebSocket endpoint you are authorized to access.
- Validate parsed multiplier candidates against the visible game history before relying on them.

## Starter package

The Python starter uses `CRASH_WS_URL` from a local `.env` file and is intended to log incoming messages for analysis. Never commit session cookies, access tokens, or credentials.
