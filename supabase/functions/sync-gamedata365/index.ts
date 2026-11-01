import { createClient } from "npm:@supabase/supabase-js@2";

const API_BASE = "https://api.gamedata365.com";
const GAMES = ["aviator", "jetx"] as const;
const HISTORY_LIMIT = 50;
const MAX_MULTIPLIER = 99_999_999.9999;
const REQUEST_TIMEOUT_MS = 15_000;

type GameId = typeof GAMES[number];
type NormalizedRound = {
  source: string;
  round_id: string;
  occurred_at: string;
  multiplier: number;
  schema_version: string;
  verified: false;
  verification_status: "pending_manual_confirmation";
  verification_method: null;
  verified_at: null;
  source_event_sha256: null;
};

function json(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
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

function parseUtcTimestamp(value: unknown): string | null {
  if (typeof value !== "string" || !/(Z|[+-]\d{2}:?\d{2})$/i.test(value.trim())) return null;
  const milliseconds = Date.parse(value);
  return Number.isFinite(milliseconds) ? new Date(milliseconds).toISOString() : null;
}

function normalizeRound(gameId: GameId, value: unknown): NormalizedRound | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const row = value as Record<string, unknown>;
  const roundId = typeof row.round_id === "string" ? row.round_id.trim() : "";
  const multiplier = row.multiplier;
  const occurredAt = parseUtcTimestamp(row.timestamp);

  if (!roundId || roundId.length > 256) return null;
  if (typeof multiplier !== "number" || !Number.isFinite(multiplier) ||
      multiplier < 1 || multiplier > MAX_MULTIPLIER ||
      Math.abs(multiplier * 10_000 - Math.round(multiplier * 10_000)) > 0.00001) return null;
  if (!occurredAt) return null;

  return {
    source: `gamedata365:${gameId}`,
    round_id: roundId,
    occurred_at: occurredAt,
    multiplier,
    schema_version: "gamedata365-crash-history-v1",
    verified: false,
    verification_status: "pending_manual_confirmation",
    verification_method: null,
    verified_at: null,
    source_event_sha256: null,
  };
}

async function fetchHistory(apiKey: string, gameId: GameId) {
  const url = new URL("/v1/crash/history", API_BASE);
  url.searchParams.set("game", gameId);
  url.searchParams.set("limit", String(HISTORY_LIMIT));

  const response = await fetch(url, {
    method: "GET",
    headers: { "X-API-Key": apiKey, "Accept": "application/json" },
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });

  if (!response.ok) {
    // Do not persist the response body: provider errors may contain account-specific links.
    throw new Error(`provider_http_${response.status}`);
  }

  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("provider_invalid_json_shape");
  }
  const data = payload as Record<string, unknown>;
  if (data.status !== "ok" || data.game_id !== gameId || !Array.isArray(data.rounds)) {
    throw new Error("provider_unexpected_history_schema");
  }

  return {
    rawCount: data.rounds.length,
    historySpins: typeof data.history_spins === "number" ? data.history_spins : null,
    hasMore: typeof data.next_cursor === "string" && data.next_cursor.length > 0,
    rounds: data.rounds,
  };
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json(405, { error: "method_not_allowed" });

  const token = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!token || jwtRole(token) !== "service_role") {
    return json(403, { error: "service_role_required" });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const gameDataKey = Deno.env.get("GAMEDATA365_API_KEY");
  if (!supabaseUrl || !serviceRoleKey || !gameDataKey) {
    return json(500, {
      error: "server_configuration_missing",
      required_secret: !gameDataKey ? "GAMEDATA365_API_KEY" : "supabase_environment",
    });
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  // Avoid accidental overlapping runs; stale locks self-expire after 30 minutes.
  const { data: activeRuns, error: activeError } = await supabase
    .from("crash_ingestion_runs")
    .select("id")
    .eq("status", "running")
    .gte("started_at", new Date(Date.now() - 30 * 60 * 1000).toISOString())
    .limit(1);
  if (activeError) return json(500, { error: "ingestion_lock_check_failed" });
  if (activeRuns?.length) return json(409, { error: "ingestion_already_running" });

  let triggerSource: "cron" | "manual" = "manual";
  try {
    const body = await req.json().catch(() => ({}));
    if (body && typeof body === "object" && !Array.isArray(body) &&
        (body as Record<string, unknown>).trigger_source === "cron") {
      triggerSource = "cron";
    }
  } catch {
    return json(400, { error: "invalid_request_body" });
  }

  const { data: run, error: runInsertError } = await supabase
    .from("crash_ingestion_runs")
    .insert({ status: "running", trigger_source: triggerSource })
    .select("id")
    .single();
  if (runInsertError || !run) return json(500, { error: "ingestion_run_create_failed" });

  const started = Date.now();
  let providerRequests = 0;
  let rowsReceived = 0;
  let rowsInserted = 0;
  let rowsDuplicate = 0;
  let rowsConflict = 0;
  let hasFailure = false;
  const gameResults: Record<string, unknown>[] = [];

  try {
    for (const gameId of GAMES) {
      providerRequests += 1;
      let history;
      try {
        history = await fetchHistory(gameDataKey, gameId);
      } catch (error) {
        hasFailure = true;
        gameResults.push({
          game_id: gameId,
          status: "failed",
          error_code: error instanceof Error ? error.message : "provider_request_failed",
        });
        continue;
      }

      rowsReceived += history.rawCount;
      const normalized: NormalizedRound[] = [];
      let invalidRows = 0;
      const inPage = new Map<string, NormalizedRound>();

      for (const item of history.rounds) {
        const row = normalizeRound(gameId, item);
        if (!row) {
          invalidRows += 1;
          continue;
        }
        const previous = inPage.get(row.round_id);
        if (previous && previous.multiplier !== row.multiplier) {
          rowsConflict += 1;
          invalidRows += 1;
          inPage.delete(row.round_id);
          continue;
        }
        inPage.set(row.round_id, row);
      }

      if (invalidRows > 0) hasFailure = true;
      normalized.push(...inPage.values());

      const ids = normalized.map((row) => row.round_id);
      const existingById = new Map<string, number>();
      if (ids.length) {
        const { data: existing, error: readError } = await supabase
          .from("crash_rounds")
          .select("round_id,multiplier")
          .eq("source", `gamedata365:${gameId}`)
          .in("round_id", ids);

        if (readError) {
          hasFailure = true;
          gameResults.push({
            game_id: gameId,
            status: "database_read_failed",
            fetched: history.rawCount,
            valid: normalized.length,
          });
          continue;
        }
        for (const item of existing ?? []) {
          existingById.set(item.round_id, Number(item.multiplier));
        }
      }

      const insertRows: NormalizedRound[] = [];
      let gameDuplicates = 0;
      let gameConflicts = 0;
      for (const row of normalized) {
        const previous = existingById.get(row.round_id);
        if (previous !== undefined) {
          if (Math.round(previous * 10_000) !== Math.round(row.multiplier * 10_000)) {
            gameConflicts += 1;
          } else {
            gameDuplicates += 1;
          }
        } else {
          insertRows.push(row);
        }
      }

      rowsConflict += gameConflicts;
      rowsDuplicate += gameDuplicates;
      if (gameConflicts > 0) hasFailure = true;

      let gameInserted = 0;
      if (insertRows.length) {
        const { data: inserted, error: insertError } = await supabase
          .from("crash_rounds")
          .upsert(insertRows, { onConflict: "source,round_id", ignoreDuplicates: true })
          .select("round_id");

        if (insertError) {
          hasFailure = true;
          gameResults.push({
            game_id: gameId,
            status: "database_insert_failed",
            fetched: history.rawCount,
            valid: normalized.length,
            duplicates: gameDuplicates,
            conflicts: gameConflicts,
          });
          continue;
        }
        gameInserted = inserted?.length ?? 0;
        // Any rows ignored due to a concurrent insert are counted as duplicates.
        gameDuplicates += Math.max(0, insertRows.length - gameInserted);
        rowsDuplicate += Math.max(0, insertRows.length - gameInserted);
      }

      rowsInserted += gameInserted;
      gameResults.push({
        game_id: gameId,
        status: invalidRows || gameConflicts ? "partial" : "ok",
        fetched: history.rawCount,
        valid: normalized.length,
        inserted: gameInserted,
        duplicates: gameDuplicates,
        conflicts: gameConflicts,
        invalid: invalidRows,
        history_spins: history.historySpins,
        has_more: history.hasMore,
        oldest_round_at: normalized.length
          ? normalized.reduce((a, b) => a.occurred_at < b.occurred_at ? a : b).occurred_at
          : null,
        newest_round_at: normalized.length
          ? normalized.reduce((a, b) => a.occurred_at > b.occurred_at ? a : b).occurred_at
          : null,
      });
    }

    const status = hasFailure ? (rowsInserted || rowsReceived ? "partial" : "failed") : "succeeded";
    const finishedAt = new Date().toISOString();
    const details = {
      provider: "GameData365",
      games: gameResults,
      duration_ms: Date.now() - started,
      history_limit_per_game: HISTORY_LIMIT,
      note: "Provider history is bounded by the account plan; rows are stored as unverified candidates.",
    };

    const { error: updateError } = await supabase
      .from("crash_ingestion_runs")
      .update({
        finished_at: finishedAt,
        status,
        provider_requests: providerRequests,
        rows_received: rowsReceived,
        rows_inserted: rowsInserted,
        rows_duplicate: rowsDuplicate,
        rows_conflict: rowsConflict,
        details,
      })
      .eq("id", run.id);

    if (updateError) return json(500, { error: "ingestion_run_finalize_failed", run_id: run.id });

    return json(status === "failed" ? 502 : 200, {
      run_id: run.id,
      status,
      provider_requests: providerRequests,
      rows_received: rowsReceived,
      rows_inserted: rowsInserted,
      rows_duplicate: rowsDuplicate,
      rows_conflict: rowsConflict,
      games: gameResults,
      duration_ms: Date.now() - started,
      verified: 0,
    });
  } catch {
    await supabase
      .from("crash_ingestion_runs")
      .update({
        finished_at: new Date().toISOString(),
        status: "failed",
        provider_requests: providerRequests,
        rows_received: rowsReceived,
        rows_inserted: rowsInserted,
        rows_duplicate: rowsDuplicate,
        rows_conflict: rowsConflict,
        error_code: "unexpected_ingestion_error",
        details: { provider: "GameData365", games: gameResults },
      })
      .eq("id", run.id);
    return json(500, { error: "unexpected_ingestion_error", run_id: run.id });
  }
});
