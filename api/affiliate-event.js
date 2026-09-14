const crypto = require("node:crypto");

const ALLOWED_ORIGIN = /^(https:\/\/)?([a-z0-9-]+\.)*artificial\.one$/i;
const PREVIEW_ORIGIN = /^https:\/\/[a-z0-9-]+\.vercel\.app$/i;
const SAFE_ID = /^[a-z0-9][a-z0-9-]{0,63}$/i;
const SAFE_PLACEMENT = /^[a-z0-9][a-z0-9_-]{0,79}$/i;
const SAFE_PATH = /^\/[a-z0-9/_\-.]{0,300}$/i;

function clean(value, pattern, fallback) {
  const text = typeof value === "string" ? value.trim() : "";
  return pattern.test(text) ? text : fallback;
}

function parseBody(req) {
  if (req.body && typeof req.body === "object" && !Buffer.isBuffer(req.body)) {
    return req.body;
  }
  const raw = Buffer.isBuffer(req.body) ? req.body.toString("utf8") : req.body;
  return raw ? JSON.parse(raw) : {};
}

function redisConfig() {
  const url = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
  return url && token ? { url: url.replace(/\/$/, ""), token } : null;
}

async function persistAggregate(event) {
  const redis = redisConfig();
  if (!redis) return false;

  const day = new Date().toISOString().slice(0, 10);
  const hash = crypto
    .createHash("sha256")
    .update(`${day}:${event.session_id}`)
    .digest("hex")
    .slice(0, 24);
  const key = `affiliate:clicks:${day}`;
  const commands = [
    ["HINCRBY", key, "total", 1],
    ["HINCRBY", key, `offer:${event.offer_id}`, 1],
    ["HINCRBY", key, `placement:${event.placement}`, 1],
    ["HINCRBY", key, `page:${event.page_path}`, 1],
    ["PFADD", `${key}:sessions`, hash],
    ["EXPIRE", key, 63072000],
    ["EXPIRE", `${key}:sessions`, 63072000],
  ];
  const response = await fetch(`${redis.url}/pipeline`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${redis.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(commands),
  });
  if (!response.ok) throw new Error(`Redis returned ${response.status}`);
  return true;
}

async function forwardToGa4(event) {
  const measurementId = process.env.GA4_MEASUREMENT_ID;
  const apiSecret = process.env.GA4_API_SECRET;
  if (!measurementId || !apiSecret) return false;

  const endpoint = new URL("https://region1.google-analytics.com/mp/collect");
  endpoint.searchParams.set("measurement_id", measurementId);
  endpoint.searchParams.set("api_secret", apiSecret);
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: event.session_id,
      consent: { ad_user_data: "DENIED", ad_personalization: "DENIED" },
      events: [{
        name: "affiliate_click",
        params: {
          offer_id: event.offer_id,
          placement: event.placement,
          page_path: event.page_path,
          engagement_time_msec: 1,
        },
      }],
    }),
  });
  if (!response.ok) throw new Error(`GA4 returned ${response.status}`);
  return true;
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "method_not_allowed" });
  }

  const origin = String(req.headers.origin || "");
  if (origin && !ALLOWED_ORIGIN.test(origin) && !PREVIEW_ORIGIN.test(origin)) {
    return res.status(403).json({ error: "origin_not_allowed" });
  }

  let body;
  try {
    body = parseBody(req);
  } catch (_) {
    return res.status(400).json({ error: "invalid_json" });
  }

  const event = {
    offer_id: clean(body.offer_id, SAFE_ID, "unknown"),
    placement: clean(body.placement, SAFE_PLACEMENT, "unknown"),
    page_path: clean(body.page_path, SAFE_PATH, "/"),
    session_id: clean(body.session_id, /^[a-z0-9-]{1,80}$/i, "anonymous"),
  };

  const results = await Promise.allSettled([
    persistAggregate(event),
    forwardToGa4(event),
  ]);
  const persisted = results.some(
    (result) => result.status === "fulfilled" && result.value === true
  );
  if (!persisted) {
    console.log("affiliate_click", {
      offer_id: event.offer_id,
      placement: event.placement,
      page_path: event.page_path,
    });
  }
  results.forEach((result) => {
    if (result.status === "rejected") console.error("affiliate_sink_error", result.reason);
  });

  res.setHeader("Cache-Control", "no-store");
  return res.status(202).json({ accepted: true });
};
