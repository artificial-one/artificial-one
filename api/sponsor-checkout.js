const inventory = require("../data/sponsorship_inventory.json");

const SITE = "https://artificial.one";
const PREVIEW_ORIGIN = /^https:\/\/[a-z0-9-]+\.vercel\.app$/i;

function originAllowed(req) {
  const origin = String(req.headers.origin || "").replace(/\/$/, "");
  return !origin || origin === SITE || PREVIEW_ORIGIN.test(origin);
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  if (!originAllowed(req)) return res.status(403).json({ error: "Origin not allowed" });
  if (!inventory.checkout_enabled) return res.status(503).json({ error: "Online sponsorship booking is not active yet." });
  const secret = process.env.STRIPE_SECRET_KEY || "";
  if (!secret) return res.status(503).json({ error: "Secure checkout is temporarily unavailable." });
  const packageId = typeof req.body?.package_id === "string" ? req.body.package_id : "";
  const item = inventory.packages.find((entry) => entry.id === packageId);
  if (!item) return res.status(400).json({ error: "Unknown sponsorship package" });
  const params = new URLSearchParams({
    mode: "payment",
    success_url: `${SITE}/sponsor-success.html?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${SITE}/sponsor.html`,
    "line_items[0][quantity]": "1",
    "line_items[0][price_data][currency]": inventory.currency,
    "line_items[0][price_data][unit_amount]": String(item.price_cents),
    "line_items[0][price_data][product_data][name]": `artificial.one — ${item.name}`,
    "metadata[package_id]": item.id,
  });
  try {
    const response = await fetch("https://api.stripe.com/v1/checkout/sessions", {
      method: "POST",
      headers: { Authorization: `Bearer ${secret}`, "Content-Type": "application/x-www-form-urlencoded" },
      body: params,
    });
    const body = await response.json();
    if (!response.ok || !body.url) return res.status(502).json({ error: "Stripe could not create checkout." });
    return res.status(200).json({ url: body.url });
  } catch (_) {
    return res.status(502).json({ error: "Secure checkout is temporarily unavailable." });
  }
};
