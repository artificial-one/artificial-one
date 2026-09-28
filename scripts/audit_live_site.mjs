#!/usr/bin/env node

const origin = (process.argv[2] || "https://www.artificial.one").replace(/\/$/, "");
const concurrency = Math.max(1, Number(process.env.AUDIT_CONCURRENCY || 16));

function decodeXml(value) {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&apos;", "'");
}

async function fetchText(url, options = {}) {
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(url, { redirect: "follow", signal: AbortSignal.timeout(20000), ...options });
      return {
        url,
        finalUrl: response.url,
        status: response.status,
        contentType: response.headers.get("content-type") || "",
        text: options.method === "HEAD" ? "" : await response.text(),
      };
    } catch (error) {
      lastError = error;
      if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, attempt * 350));
    }
  }
  throw lastError;
}

async function mapConcurrent(values, worker, limit = concurrency) {
  const output = new Array(values.length);
  let cursor = 0;
  async function run() {
    while (cursor < values.length) {
      const index = cursor++;
      try {
        output[index] = await worker(values[index], index);
      } catch (error) {
        output[index] = { url: values[index], status: 0, error: String(error) };
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, values.length) }, run));
  return output;
}

function pageContract(page) {
  const title = (page.text.match(/<title[^>]*>([^<]*)/i) || [])[1]?.trim() || "";
  const description = (page.text.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']*)/i) || [])[1]?.trim() || "";
  const h1Count = (page.text.match(/<h1\b/gi) || []).length;
  const hasViewport = /<meta[^>]+name=["']viewport["']/i.test(page.text);
  const hasPresentation = /<style\b|<link[^>]+rel=["']stylesheet["']/i.test(page.text);
  const hasMain = /<main\b/i.test(page.text);
  return { title, description, h1Count, hasViewport, hasPresentation, hasMain };
}

function internalTargets(page) {
  const found = [];
  const markup = page.text
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "");
  for (const match of markup.matchAll(/(?:href|src)=["']([^"'#]+)["']/gi)) {
    const raw = match[1].trim();
    if (!raw || /^(?:mailto:|tel:|javascript:|data:)/i.test(raw)) continue;
    try {
      const target = new URL(raw, page.finalUrl || page.url);
      if (target.origin === origin) {
        target.hash = "";
        found.push(target.href);
      }
    } catch {
      found.push(raw);
    }
  }
  return found;
}

async function main() {
  const sitemap = await fetchText(`${origin}/sitemap.xml?audit=${Date.now()}`);
  if (sitemap.status !== 200) throw new Error(`sitemap.xml returned HTTP ${sitemap.status}`);
  const pageUrls = [...sitemap.text.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => {
    const published = new URL(decodeXml(match[1]));
    return new URL(`${published.pathname}${published.search}`, `${origin}/`).href;
  });
  const pages = await mapConcurrent(pageUrls, (url) => fetchText(url));
  const pageIssues = [];
  const targetSet = new Set();

  for (const page of pages) {
    if (page.status !== 200 || !page.contentType?.includes("text/html")) {
      pageIssues.push({ url: page.url, issue: "page-unavailable", status: page.status, contentType: page.contentType, error: page.error });
      continue;
    }
    const contract = pageContract(page);
    if (!contract.title) pageIssues.push({ url: page.url, issue: "missing-title" });
    if (!contract.description) pageIssues.push({ url: page.url, issue: "missing-description" });
    if (!contract.hasViewport) pageIssues.push({ url: page.url, issue: "missing-viewport" });
    if (!contract.hasPresentation) pageIssues.push({ url: page.url, issue: "missing-styles" });
    if (!contract.hasMain) pageIssues.push({ url: page.url, issue: "missing-main-landmark" });
    if (contract.h1Count !== 1) pageIssues.push({ url: page.url, issue: "h1-count", count: contract.h1Count });
    internalTargets(page).forEach((target) => targetSet.add(target));
  }

  const targets = [...targetSet];
  const checkedTargets = await mapConcurrent(targets, async (url) => {
    const head = await fetchText(url, { method: "HEAD" });
    if (head.status === 405 || head.status === 501) return fetchText(url);
    return head;
  });
  const brokenTargets = checkedTargets
    .filter((result) => !result.status || result.status >= 400)
    .map(({ url, status, error }) => ({ url, status, error }));

  const issueCounts = pageIssues.reduce((counts, item) => {
    counts[item.issue] = (counts[item.issue] || 0) + 1;
    return counts;
  }, {});
  const report = {
    origin,
    sitemapPages: pageUrls.length,
    pagesChecked: pages.length,
    internalTargetsChecked: checkedTargets.length,
    pageIssueCount: pageIssues.length,
    issueCounts,
    pageIssues: pageIssues.slice(0, 40),
    availabilityIssues: pageIssues.filter((item) => item.issue === "page-unavailable").slice(0, 40),
    structuralIssues: pageIssues.filter((item) => !["page-unavailable", "missing-main-landmark"].includes(item.issue)).slice(0, 40),
    brokenTargetCount: brokenTargets.length,
    brokenTargets: brokenTargets.slice(0, 40),
  };
  console.log(JSON.stringify(report, null, 2));
  process.exitCode = pageIssues.some((item) => item.issue === "page-unavailable") || brokenTargets.length ? 1 : 0;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
