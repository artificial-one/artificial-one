const fs = require("node:fs");
const path = require("node:path");

const SAFE = /^[a-z0-9][a-z0-9 _&+.,/-]{0,79}$/i;

function load(name) {
  return JSON.parse(fs.readFileSync(path.join(process.cwd(), "data", name), "utf8"));
}

function integer(value, fallback, maximum) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) ? Math.max(0, Math.min(maximum, parsed)) : fallback;
}

function text(value) {
  const normalized = String(value || "").trim();
  return SAFE.test(normalized) ? normalized : "";
}

function compact(tool) {
  return {
    id: tool.id,
    name: tool.name,
    category: tool.category,
    summary: tool.summary,
    best_for: tool.best_for,
    features: tool.features || [],
    platforms: tool.platforms || [],
    pricing: tool.pricing || {},
    verification: tool.verification || {},
    links: {
      profile: tool.links?.profile || "",
      source: tool.links?.source || "",
    },
  };
}

module.exports = async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "method_not_allowed" });
  }
  const limit = integer(req.query?.limit, 20, 100);
  const offset = integer(req.query?.offset, 0, 100000);
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400");
  if (String(req.query?.changes || "") === "true") {
    const history = load("tool_change_history.json");
    const events = Array.isArray(history.events) ? history.events : [];
    return res.status(200).json({ version: 1, updated_at: history.updated_at, total: events.length, offset, limit, items: events.slice(offset, offset + limit) });
  }
  const catalog = load("tool_intelligence.json");
  const query = text(req.query?.q).toLowerCase();
  const category = text(req.query?.category).toLowerCase();
  const free = String(req.query?.free || "").toLowerCase() === "true";
  const tools = (catalog.tools || []).filter((tool) => {
    const haystack = String(tool.search_text || [tool.name, tool.category, tool.summary, tool.best_for].join(" ")).toLowerCase();
    if (query && !query.split(/\s+/).every((part) => haystack.includes(part))) return false;
    if (category && !String(tool.category || "").toLowerCase().includes(category)) return false;
    if (free && !tool.pricing?.has_free_plan) return false;
    return true;
  });
  return res.status(200).json({
    version: 1,
    updated_at: catalog.updated_at,
    methodology: catalog.methodology,
    total: tools.length,
    offset,
    limit,
    items: tools.slice(offset, offset + limit).map(compact),
  });
};
