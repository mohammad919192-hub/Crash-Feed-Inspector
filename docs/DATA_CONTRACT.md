# Data Contract and Verification Gates

## 1. Raw feed messages

The capture tool writes sanitized JSON Lines records to local data/messages.jsonl. The captured payload is labeled raw_sanitized because common credential-shaped fields may have been replaced. This is not an exact wire archive. Redaction is best-effort and does not guarantee removal of every proprietary credential format.

Do not commit captured feed samples. Do not share cookies, bearer tokens, authorization headers, session identifiers, account data, or signed URLs. Raw payloads are not part of the proposed Supabase storage model.

## 2. Event parsing

No real target-site schema is hardcoded. The parser requires explicit configuration for:
- event_type_path: JSON path containing the event discriminator
- final_event_types: exact allowlist of completed-result event names
- round_id_path: stable round identifier
- multiplier_path: authoritative final multiplier field
- timestamp_path: optional ISO-8601 timestamp field with timezone
- schema_version: human-maintained label for the confirmed mapping

Paths support dotted object keys and numeric array indexes, for example data.rounds[0].multiplier. Examples in .env.example are synthetic only.

An event is ignored when its JSON cannot be decoded, its event type is not allowlisted, or the event-type path is missing. A matching event with invalid required fields is treated as a parse error. Conflicting multipliers for the same round ID are excluded from the generated candidate CSV.

## 3. Normalized CSV

Required columns:
- round_id: non-empty, unique within one imported file
- multiplier: finite numeric value greater than or equal to 1.0

Optional columns:
- timestamp_utc: ISO-8601 with an explicit timezone; normalized to UTC
- source: feed or import label
- verified: explicit boolean; blank or missing means false
- schema_version: manually maintained parser mapping version

Unknown columns are rejected so schema drift cannot silently alter downstream calculations. Duplicate IDs, malformed numbers, non-finite values, and timestamps without timezone are rejected. The importer fails closed instead of silently discarding malformed rows.

## 4. Verification is a separate operation

Parser output is always verified=false. A result may be marked verified only after it has been independently reconciled against a trusted visible completed-round history and the reconciliation procedure is documented. A plausible number, a successful WebSocket connection, or a matching field path is not sufficient evidence.

The offline analysis command only consumes rows explicitly marked verified=true. That flag is a user assertion, not cryptographic proof of authenticity.

## 5. Statistical research

- Preserve original round order for walk-forward evaluation.
- Use only information available before each target round.
- Report sample size and missing timestamp coverage.
- Compare candidate methods to a predeclared historical-frequency baseline on the same time splits.
- Preserve a final holdout that is not used for model selection.
- Treat short-window movement as noisy unless validated out of sample.
- If the evidence does not show a stable improvement over baseline, report no demonstrated predictive edge.

## 6. Supabase boundary

The connected Supabase project is named `Crash`. Its `public.crash_rounds` and `public.crash_predictions` tables currently contain zero rows; RLS is enabled and `anon`/`authenticated` have no direct SELECT or INSERT privileges. No Edge Function or application ingestion path was found. The remote database records eight migrations, but the repository migration history is incomplete and had a `timestamp_utc`/`occurred_at` schema mismatch. Reconcile migration history before applying further migrations; do not expose service-role credentials to a client.
