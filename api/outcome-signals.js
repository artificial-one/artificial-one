const crypto = require("node:crypto");

const ALLOWED_ORIGIN = /^(https:\/\/)?([a-z0-9-]+\.)*artificial\.one$/i;
const PREVIEW_ORIGIN = /^https:\/\/[a-z0-9-]+\.vercel\.app$/i;
const SAFE_ID = /^[a-z0-9][a-z0-9-]{0,79}$/i;
const SAFE_DECISION = /^[a-f0-9]{16,64}$/i;
const SAFE_ANONYMOUS = /^[a-f0-9]{32,64}$/i;
const SIGNALS = new Set(["helpful_yes", "helpful_no", "chosen", "worked_yes", "worked_partly", "worked_no"]);

function config() {
  const url = (process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL || "").replace(/\/$/, "");
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN || "";
  return url && token ? { url, token } : null;
}

async function command(parts) {
  const value = config();
  if (!value) throw new Error("Outcome storage is not configured");
  const response = await fetch(`${value.url}/${parts.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${value.token}` },
  });
  if (!response.ok) throw new Error(`Outcome storage returned ${response.status}`);
  return (await response.json()).result;
}

function parseBody(req) {
  if (req.body && typeof req.body === "object" && !Buffer.isBuffer(req.body)) return req.body;
  return JSON.parse(Buffer.isBuffer(req.body) ? req.body.toString("utf8") : req.body || "{}");
}

function empty(toolId) {
  return { tool_id: toolId, responses: 0, helpful: 0, chosen: 0, worked: 0, partly: 0 };
}

function summarize(toolId, raw) {
  const rows = Array.isArray(raw) ? raw : [];
  const values = {};
  for (let index = 0; index < rows.length; index += 2) values[String(rows[index])] = Number(rows[index + 1] || 0);
  const responses = values.responses || 0;
  if (responses < 3) return empty(toolId);
  return {
    tool_id: toolId,
    responses,
    helpful: values.helpful_yes || 0,
    chosen: values.chosen || 0,
    worked: values.worked_yes || 0,
    partly: values.worked_partly || 0,
  };
}

async function readSignals(req, res) {
  const requested = String(req.query?.tool_ids || "").split(",").filter((id) => SAFE_ID.test(id)).slice(0, 3);
  const ids = Array.from(new Set(requested));
  const signals = await Promise.all(ids.map(async (id) => summarize(id, await command(["HGETALL", `outcome:aggregate:${id}`]))));
  res.setHeader("Cache-Control", "public, max-age=300, stale-while-revalidate=3600");
  return res.status(200).json({ signals, privacy: "Only anonymous aggregates with at least three responses are shown." });
}

async function writeSignal(req, res) {
  const origin = String(req.headers.origin || "");
  if (origin && !ALLOWED_ORIGIN.test(origin) && !PREVIEW_ORIGIN.test(origin)) return res.status(403).json({ error: "origin_not_allowed" });
  let body;
  try { body = parseBody(req); } catch (_) { return res.status(400).json({ error: "invalid_json" }); }
  const signal = String(body.signal || "");
  const toolId = String(body.tool_id || "");
  const decisionId = String(body.decision_id || "");
  const anonymousId = String(body.anonymous_id || "");
  if (!SIGNALS.has(signal) || !SAFE_ID.test(toolId) || !SAFE_DECISION.test(decisionId) || !SAFE_ANONYMOUS.test(anonymousId)) return res.status(400).json({ error: "invalid_signal" });

  const group = signal.startsWith("helpful_") ? "helpful" : signal.startsWith("worked_") ? "worked" : "chosen";
  const fingerprint = crypto.createHash("sha256").update(`${anonymousId}:${toolId}:${group}`).digest("hex");
  const accepted = await command(["SET", `outcome:dedupe:${fingerprint}`, "1", "NX", "EX", "31536000"]);
  if (accepted === "OK") {
    await command(["HINCRBY", `outcome:aggregate:${toolId}`, signal, "1"]);
    const respondent = crypto.createHash("sha256").update(`${anonymousId}:${toolId}`).digest("hex");
    const isNew = await command(["SET", `outcome:respondent:${respondent}`, "1", "NX", "EX", "31536000"]);
    if (isNew === "OK") await command(["HINCRBY", `outcome:aggregate:${toolId}`, "responses", "1"]);
  }
  res.setHeader("Cache-Control", "no-store");
  return res.status(202).json({ accepted: accepted === "OK" });
}

module.exports = async function handler(req, res) {
  try {
    if (req.method === "GET") return await readSignals(req, res);
    if (req.method === "POST") return await writeSignal(req, res);
    res.setHeader("Allow", "GET, POST");
    return res.status(405).json({ error: "method_not_allowed" });
  } catch (error) {
    console.error("outcome_signal_error", error);
    return res.status(503).json({ error: "Outcome signals are temporarily unavailable." });
  }
};
