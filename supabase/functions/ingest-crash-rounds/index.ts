import { createClient } from "npm:@supabase/supabase-js@2";

const MAX_BODY_BYTES = 1_000_000;
const MAX_ROWS = 500;
const MAX_MULTIPLIER = 99_999_999.9999;

function response(status: number, payload: Record<string, unknown>): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function jwtRole(token: string): string | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")));
    return typeof payload.role === "string" ? payload.role : null;
  } catch {
    return null;
  }
}

function nonEmptyString(value: unknown, maxLength: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.trim().length <= maxLength;
}

function parseTimestamp(value: unknown): string | null | undefined {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string" || !/(Z|[+-]\d{2}:\d{2})$/i.test(value)) return undefined;
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) return undefined;
  return new Date(milliseconds).toISOString();
}

async function readBodyBounded(req: Request, limit: number): Promise<string | null> {
  if (!req.body) return "";
  const reader = req.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > limit) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const joined = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(joined);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return response(405, { error: "method_not_allowed" });

  const authorization = req.headers.get("authorization") ?? "";
  const token = authorization.replace(/^Bearer\s+/i, "").trim();
  if (!token || jwtRole(token) !== "service_role") {
    return response(403, { error: "service_role_required" });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return response(500, { error: "server_configuration_missing" });
  }

  let bodyText: string | null;
  try {
    bodyText = await readBodyBounded(req, MAX_BODY_BYTES);
  } catch {
    return response(400, { error: "invalid_request_body" });
  }
  if (bodyText === null) return response(413, { error: "request_too_large" });

  let body: unknown;
  try {
    body = JSON.parse(bodyText);
  } catch {
    return response(400, { error: "invalid_json" });
  }
  if (!body || typeof body !== "object" || !Array.isArray((body as { rows?: unknown }).rows)) {
    return response(400, { error: "rows_array_required" });
  }

  const inputRows = (body as { rows: unknown[] }).rows;
  if (inputRows.length < 1 || inputRows.length > MAX_ROWS) {
    return response(400, { error: "batch_size_must_be_between_1_and_500" });
  }

  const uniqueRows = new Map<string, Record<string, unknown>>();
  for (const item of inputRows) {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      return response(400, { error: "each_row_must_be_an_object" });
    }
    const row = item as Record<string, unknown>;
    const source = typeof row.source === "string" ? row.source.trim() : "";
    const roundId = typeof row.round_id === "string" ? row.round_id.trim() : "";
    const schemaVersion = typeof row.schema_version === "string" ? row.schema_version.trim() : "unknown";
    const multiplier = row.multiplier;
    const occurredAt = parseTimestamp(row.timestamp_utc);

    if (!nonEmptyString(source, 128) || !nonEmptyString(roundId, 256) ||
        !nonEmptyString(schemaVersion || "unknown", 128)) {
      return response(400, { error: "source_round_id_or_schema_version_invalid" });
    }
    if (typeof multiplier !== "number" || !Number.isFinite(multiplier) ||
        multiplier < 1 || multiplier > MAX_MULTIPLIER ||
        Math.abs(multiplier * 10_000 - Math.round(multiplier * 10_000)) > 0.00001) {
      return response(400, { error: "multiplier_must_be_finite_ge_1_with_at_most_4_decimals" });
    }
    if (occurredAt === undefined) return response(400, { error: "timestamp_utc_must_be_iso8601_with_timezone" });
    if (row.verified !== false) {
      return response(400, { error: "only_unverified_candidates_can_be_ingested" });
    }

    const key = JSON.stringify([source, roundId]);
    const normalized = {
      source,
      round_id: roundId,
      occurred_at: occurredAt,
      multiplier,
      schema_version: schemaVersion || "unknown",
      verified: false,
      verification_status: "pending_manual_confirmation",
      verification_method: null,
      verified_at: null,
      source_event_sha256: null,
    };
    const previous = uniqueRows.get(key);
    if (previous && previous.multiplier !== multiplier) {
      return response(409, { error: "conflicting_duplicate_round_in_request", round_id: roundId });
    }
    uniqueRows.set(key, normalized);
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const normalizedRows = [...uniqueRows.values()];
  const existingByKey = new Map<string, number>();

  const sourceGroups = new Map<string, string[]>();
  for (const row of normalizedRows) {
    const source = String(row.source);
    const ids = sourceGroups.get(source) ?? [];
    ids.push(String(row.round_id));
    sourceGroups.set(source, ids);
  }

  for (const [source, ids] of sourceGroups) {
    const { data, error } = await supabase
      .from("crash_rounds")
      .select("source,round_id,multiplier")
      .eq("source", source)
      .in("round_id", ids);
    if (error) return response(500, { error: "database_read_failed" });
    for (const existing of data ?? []) {
      existingByKey.set(JSON.stringify([existing.source, existing.round_id]), Number(existing.multiplier));
    }
  }

  const conflicts: string[] = [];
  const rowsToInsert: Record<string, unknown>[] = [];
  let alreadyPresent = 0;
  for (const row of normalizedRows) {
    const key = JSON.stringify([row.source, row.round_id]);
    const existingMultiplier = existingByKey.get(key);
    if (existingMultiplier !== undefined) {
      if (Math.round(existingMultiplier * 10_000) !== Math.round(Number(row.multiplier) * 10_000)) {
        conflicts.push(String(row.round_id));
      } else {
        alreadyPresent += 1;
      }
      continue;
    }
    rowsToInsert.push(row);
  }

  if (conflicts.length) {
    return response(409, {
      error: "stored_round_multiplier_conflict",
      conflicting_round_ids: conflicts.slice(0, 100),
      conflict_count: conflicts.length,
      inserted: 0,
      already_present: 0,
    });
  }

  if (rowsToInsert.length) {
    const { error } = await supabase.from("crash_rounds").insert(rowsToInsert);
    if (error) {
      // A concurrent insert can win after the preflight read. Never overwrite it.
      if (error.code === "23505") return response(409, { error: "concurrent_round_conflict_retry" });
      return response(500, { error: "database_insert_failed" });
    }
  }

  return response(200, {
    received: inputRows.length,
    unique_rows: normalizedRows.length,
    inserted: rowsToInsert.length,
    already_present: alreadyPresent,
    verified: 0,
    note: "All ingested rows remain unverified until independently reconciled.",
  });
});
