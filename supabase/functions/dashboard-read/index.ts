import { createClient } from "npm:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Cache-Control": "no-store",
  "Content-Type": "application/json; charset=utf-8",
};

function reply(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), { status, headers: cors });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return reply(405, { error: "method_not_allowed" });

  const authorization = req.headers.get("authorization") ?? "";
  const token = authorization.replace(/^Bearer\\s+/i, "").trim();
  if (!token) return reply(401, { error: "authentication_required" });

  const url = Deno.env.get("SUPABASE_URL");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !anonKey || !serviceKey) {
    return reply(500, { error: "server_configuration_missing" });
  }

  const authClient = createClient(url, anonKey, {
    auth: { autoRefreshToken: false, persistSession: false },
    global: { headers: { Authorization: `Bearer ${token}` } },
  });
  const { data: authData, error: authError } = await authClient.auth.getUser(token);
  if (authError || !authData.user) return reply(401, { error: "invalid_session" });
  if (authData.user.app_metadata?.crash_dashboard !== true) {
    return reply(403, { error: "dashboard_access_not_granted" });
  }

  const admin = createClient(url, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const [rounds, predictions, runs] = await Promise.all([
    admin.from("crash_rounds")
      .select("source,round_id,occurred_at,multiplier,verified,verification_status,created_at,schema_version")
      .order("occurred_at", { ascending: false, nullsFirst: false }).limit(5000),
    admin.from("crash_predictions")
      .select("created_at,source,target_threshold,estimated_probability,confidence_low,confidence_high,model_version,data_count,decision,evaluated_round_id,evaluated_multiplier,evaluated_at")
      .order("created_at", { ascending: false }).limit(250),
    admin.from("crash_ingestion_runs")
      .select("started_at,finished_at,status,trigger_source,provider_requests,rows_received,rows_inserted,rows_duplicate,rows_conflict,error_code")
      .order("started_at", { ascending: false }).limit(100),
  ]);

  const failed = [rounds, predictions, runs].find((result) => result.error);
  if (failed?.error) {
    console.error("dashboard_read_query_failed", failed.error.code ?? "unknown");
    return reply(500, { error: "dashboard_data_unavailable" });
  }

  return reply(200, {
    rounds: rounds.data ?? [],
    predictions: predictions.data ?? [],
    runs: runs.data ?? [],
    generated_at: new Date().toISOString(),
  });
});
