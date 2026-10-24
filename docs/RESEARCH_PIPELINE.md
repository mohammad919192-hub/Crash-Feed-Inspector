# Research Pipeline and Data Retention

## Objective

Maintain a provenance-aware history of observed rounds and time-stamped research estimates. The system must distinguish captured messages, parsed candidates, independently verified outcomes, and model estimates.

## Multi-filter workflow

1. **Transport health:** record whether the authorized socket connects, messages arrive, and timeouts/disconnections occur. A connected socket is not proof that round outcomes are present.
2. **Message/schema filter:** summarize JSON paths and event-like fields; only configure parser paths after reviewing real sanitized samples.
3. **Round-completion filter:** accept only a documented final-result event. Ignore countdowns, live counters, animation updates, and interim values.
4. **Integrity filter:** require a stable round ID, finite multiplier >= 1, valid timestamps where available, duplicate detection, and conflict quarantine.
5. **Independent verification:** compare captured outcomes with a trusted visible completed-round history. Until reconciled, a candidate stays unverified and must not enter model training.
6. **Dataset quality:** report missing timestamps, source/schema versions, duplicates, chronology violations, missing data, and conflicting records.
7. **Baseline estimates:** compute empirical threshold frequencies and confidence intervals from verified outcomes only.
8. **Stability filter:** compare recent windows with the full historical frequency; large shifts result in no_signal_unstable_history. If none of the configured windows fits the available history, return no_signal_stability_unavailable.
9. **Out-of-sample evaluation:** predictions must be timestamped before the result, use only earlier data, and be evaluated on chronological holdouts. Compare against simple frequency baselines using proper scoring rules and calibration.
10. **Decision gate:** report no_signal when data are insufficient, unstable, unverified, unordered, missing required timestamps, or fail predeclared evaluation criteria. A passing filter means only that a historical estimate passed those diagnostics; it does not establish an exploitable edge.

## Current local research command

Only rows explicitly marked verified=true are considered:

    python -m crash_feed_inspector research-csv data/rounds.csv
    python -m crash_feed_inspector research-csv data/rounds.csv --thresholds 1.5 2 3 5 --windows 30 100 300 --min-history 100 --max-window-rate-gap 0.15

For this command, every verified row must have a timezone-aware timestamp, and the verified rows must appear oldest-to-newest in the CSV. If timestamps are missing or verified rows are out of order, the command emits a no_signal status and does not calculate threshold frequencies. This ordering check is necessary because a list of multiplier values alone cannot prove chronology.

Defaults are transparent and configurable; they are not optimized trading parameters. Trying many thresholds/windows and then reporting the best creates multiple-testing bias. Pre-register thresholds and preserve a final untouched holdout.

## Where each kind of data belongs

- **GitHub:** source code, schema documentation, migrations, tests, release notes, model methodology, and small synthetic fixtures. Do not create one Git commit per live round; that is inefficient, noisy, and can accidentally publish private or sensitive data.
- **Supabase/Postgres:** proposed durable store for normalized round records and a prediction ledger, once the owner explicitly confirms the intended project. Keep it server-side and use least privilege. Never expose a service-role key in a browser app.
- **Local Termux:** temporary sanitized capture files and local analysis outputs. They are not a durable backup unless separately backed up.
- **Raw WebSocket frames:** do not upload by default. They can contain tokens, session IDs, account metadata, or proprietary information. Keep only necessary sanitized fields and an event hash when legally and technically appropriate.
- **Model memory/state:** store versioned, inspectable features and training-window metadata in the database, not undocumented internal model memory. Each estimate should record data count, model version, time, threshold, probability, uncertainty interval, and later outcome if available.

## Supabase migration status

The connected Supabase project `Crash` already has empty `public.crash_rounds` and `public.crash_predictions` tables. RLS is enabled and direct `anon`/`authenticated` SELECT/INSERT privileges are absent; the security advisor reports `rls_enabled_no_policy` as INFO, which is consistent with a server-only access model but means browser clients cannot use these tables. The live database records eight migrations while the repository previously tracked only two draft files, and the old `crash_rounds` draft used `timestamp_utc` while the live table uses `occurred_at`. The revised migration files are aligned to the observed table contract, but the remote-only migration history still needs reconciliation. Do not run `supabase db push` until the migration list and history are reviewed. No ingestion service or Edge Function currently writes data to these tables.

## Forecast validity

Crash outcomes may be independent by design. Historical clustering, streaks, or patterns can arise by chance, particularly when many thresholds and windows are examined. The system must not claim a probability for the next round merely because a historical rate exists. A real predictive claim requires preregistered, leakage-free out-of-sample results that beat a baseline by a meaningful margin with uncertainty accounted for. If this evidence is absent, the correct result is no_signal.
