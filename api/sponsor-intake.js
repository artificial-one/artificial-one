const SITE = "https://artificial.one";
const PREVIEW_ORIGIN = /^https:\/\/[a-z0-9-]+\.vercel\.app$/i;

function text(value, max) {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

async function verifyPayment(sessionId, secret) {
  const response = await fetch(`https://api.stripe.com/v1/checkout/sessions/${encodeURIComponent(sessionId)}`, { headers: { Authorization: `Bearer ${secret}` } });
  if (!response.ok) return null;
  const session = await response.json();
  return session.payment_status === "paid" ? session : null;
}

async function storeBrief(sessionId, value) {
  const url = (process.env.UPSTASH_REDIS_REST_URL || "").replace(/\/$/, "");
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || "";
  if (!url || !token) throw new Error("storage unavailable");
  const response = await fetch(`${url}/pipeline`, {
    method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify([["SET", `sponsor:intake:${sessionId}`, JSON.stringify(value), "NX", "EX", 31536000]]),
  });
  if (!response.ok) throw new Error("storage rejected");
  const result = await response.json();
  return Boolean(result?.[0]?.result);
}

async function notify(value) {
  const key = process.env.RESEND_API_KEY || "";
  if (!key) throw new Error("notification unavailable");
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST", headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: process.env.SPONSOR_EMAIL_FROM || "Artificial.One Sponsorship <onboarding@resend.dev>", to: ["hello@artificial.one"], subject: `Paid sponsorship brief — ${value.company}`, text: `Package: ${value.package_id}\nCompany: ${value.company}\nContact: ${value.name} <${value.email}>\nProduct: ${value.product_url}\n\n${value.brief}` }),
  });
  if (!response.ok) throw new Error("notification rejected");
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  const origin = String(req.headers.origin || "").replace(/\/$/, "");
  if (origin && origin !== SITE && !PREVIEW_ORIGIN.test(origin)) return res.status(403).json({ error: "Origin not allowed" });
  const value = {
    session_id: text(req.body?.session_id, 200), name: text(req.body?.name, 80), company: text(req.body?.company, 100),
    email: text(req.body?.email, 180), product_url: text(req.body?.product_url, 500), brief: text(req.body?.brief, 3000),
  };
  if (!value.session_id.startsWith("cs_") || !/^\S+@\S+\.\S+$/.test(value.email) || !/^https:\/\//i.test(value.product_url) || !value.name || !value.company || !value.brief) return res.status(400).json({ error: "Complete every field using a valid email and HTTPS product URL." });
  const secret = process.env.STRIPE_SECRET_KEY || "";
  if (!secret) return res.status(503).json({ error: "Payment verification is unavailable." });
  try {
    const session = await verifyPayment(value.session_id, secret);
    if (!session) return res.status(403).json({ error: "A paid checkout session could not be verified." });
    value.package_id = text(session.metadata?.package_id, 80);
    value.received_at = new Date().toISOString();
    const stored = await storeBrief(value.session_id, value);
    if (!stored) return res.status(409).json({ error: "This paid sponsorship brief was already submitted." });
    await notify(value);
    return res.status(200).json({ ok: true });
  } catch (_) {
    return res.status(502).json({ error: "The brief could not be stored safely. Please retry." });
  }
};
