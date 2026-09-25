const crypto = require("node:crypto");

const ALLOWED_HOST = /^(?:[a-z0-9-]+\.)*(?:artificial\.one|vercel\.app)$/i;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const TOOL_ID = /^[a-z0-9][a-z0-9-]{0,79}$/i;

function config() {
  const url = (process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL || "").replace(/\/$/, "");
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN || "";
  return url && token ? { url, token } : null;
}

async function redis(command) {
  const value = config();
  if (!value) throw new Error("Watchlist storage is not configured");
  const response = await fetch(`${value.url}/${command.map(encodeURIComponent).join("/")}`, { headers: { Authorization: `Bearer ${value.token}` } });
  if (!response.ok) throw new Error(`Watchlist storage returned ${response.status}`);
  const body = await response.json();
  return body.result;
}

function body(req) {
  if (req.body && typeof req.body === "object" && !Buffer.isBuffer(req.body)) return req.body;
  return JSON.parse(Buffer.isBuffer(req.body) ? req.body.toString("utf8") : req.body || "{}");
}

function baseUrl(req) {
  const host = String(req.headers["x-forwarded-host"] || req.headers.host || "artificial.one").split(",")[0].trim();
  return ALLOWED_HOST.test(host) ? `https://${host}` : "https://artificial.one";
}

async function sendConfirmation(email, token, req) {
  const key = process.env.RESEND_API_KEY || "";
  const sender = process.env.WATCHLIST_EMAIL_FROM || "Artificial.One Watchlist <updates@artificial.one>";
  if (!key) throw new Error("Watchlist email delivery is not configured");
  const link = `${baseUrl(req)}/api/watchlist-subscribe?token=${token}`;
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: sender,
      to: [email],
      subject: "Confirm your Artificial.One Elephant watchlist",
      text: `Confirm your AI tool change watchlist: ${link}\n\nThe elephant sends only confirmed changes for your selected tools. Ignore this message if you did not request it.`,
      html: `<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;padding:28px"><h1>Confirm your Elephant watchlist</h1><p>Receive an alert only when a selected AI tool has a change confirmed by the repeated-observation monitor.</p><p><a href="${link}" style="display:inline-block;background:#5b21b6;color:white;padding:13px 18px;border-radius:9px;text-decoration:none;font-weight:700">Confirm watchlist</a></p><p style="color:#667085;font-size:12px">Ignore this message if you did not request it.</p></div>`,
    }),
  });
  if (!response.ok) throw new Error(`Watchlist email delivery returned ${response.status}`);
}

async function confirm(req, res) {
  const token = String(req.query?.token || "");
  if (!/^[a-f0-9]{48}$/.test(token)) return res.status(400).json({ error: "invalid_confirmation" });
  if (String(req.query?.action || "") === "unsubscribe") {
    const lookup = `watch:unsubscribe:${crypto.createHash("sha256").update(token).digest("hex")}`;
    const activeKey = await redis(["GET", lookup]);
    if (activeKey) await redis(["DEL", activeKey]);
    await redis(["DEL", lookup]);
    return res.redirect(303, "/ai-tool-observatory.html?unsubscribed=1");
  }
  const key = `watch:pending:${crypto.createHash("sha256").update(token).digest("hex")}`;
  const raw = await redis(["GET", key]);
  if (!raw) return res.status(410).json({ error: "confirmation_expired" });
  const record = JSON.parse(raw);
  const active = `watch:active:${crypto.createHash("sha256").update(record.email).digest("hex")}`;
  const unsubscribeToken = crypto.randomBytes(24).toString("hex");
  const unsubscribeKey = `watch:unsubscribe:${crypto.createHash("sha256").update(unsubscribeToken).digest("hex")}`;
  await redis(["SET", active, JSON.stringify({ email: record.email, tool_ids: record.tool_ids, confirmed_at: new Date().toISOString(), last_event_id: "", unsubscribe_token: unsubscribeToken })]);
  await redis(["SET", unsubscribeKey, active]);
  await redis(["DEL", key]);
  res.setHeader("Cache-Control", "no-store");
  return res.redirect(303, "/watchlist-confirmed.html");
}

async function subscribe(req, res) {
  let value;
  try { value = body(req); } catch (_) { return res.status(400).json({ error: "invalid_json" }); }
  if (String(value.website || "")) return res.status(202).json({ accepted: true });
  const email = String(value.email || "").trim().toLowerCase();
  const ids = Array.from(new Set((Array.isArray(value.tool_ids) ? value.tool_ids : []).map(String).filter((id) => TOOL_ID.test(id)))).slice(0, 30);
  if (!EMAIL.test(email) || email.length > 180 || !ids.length || value.consent !== true) return res.status(400).json({ error: "Enter a valid email, watch at least one tool and confirm consent." });
  const ip = String(req.headers["x-forwarded-for"] || req.socket?.remoteAddress || "unknown").split(",")[0];
  const throttle = `watch:rate:${crypto.createHash("sha256").update(ip).digest("hex").slice(0, 24)}`;
  const count = Number(await redis(["INCR", throttle]));
  if (count === 1) await redis(["EXPIRE", throttle, "3600"]);
  if (count > 8) return res.status(429).json({ error: "Too many requests. Try again later." });
  const token = crypto.randomBytes(24).toString("hex");
  const pending = `watch:pending:${crypto.createHash("sha256").update(token).digest("hex")}`;
  await redis(["SET", pending, JSON.stringify({ email, tool_ids: ids, requested_at: new Date().toISOString() }), "EX", "86400"]);
  await sendConfirmation(email, token, req);
  res.setHeader("Cache-Control", "no-store");
  return res.status(202).json({ accepted: true });
}

module.exports = async function handler(req, res) {
  try {
    if (req.method === "GET") return await confirm(req, res);
    if (req.method === "POST") return await subscribe(req, res);
    res.setHeader("Allow", "GET, POST");
    return res.status(405).json({ error: "method_not_allowed" });
  } catch (error) {
    console.error("watchlist_error", error);
    return res.status(503).json({ error: "Watchlist confirmation is temporarily unavailable." });
  }
};
