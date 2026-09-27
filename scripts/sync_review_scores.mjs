#!/usr/bin/env node
/** Keep review-directory scores and detailed review pages on one five-point scale. */

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIRECTORY = path.join(ROOT, "reviews.html");
const CHECK = process.argv.includes("--check");

function slugify(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function fivePointScore(value) {
  const raw = String(value || "");
  const numeric = Number.parseFloat(raw) || 0;
  const normalized = /\/10\b/.test(raw) || numeric > 5 ? numeric / 2 : numeric;
  return Math.round((normalized + Number.EPSILON) * 10) / 10;
}

function displayScore(value) {
  return fivePointScore(value).toFixed(1);
}

function readDirectoryTools() {
  const source = fs.readFileSync(DIRECTORY, "utf8");
  const start = source.indexOf("const tools = ");
  const end = source.indexOf("function getCategorySlug", start);
  if (start < 0 || end < 0) throw new Error("reviews.html tool catalogue could not be located");
  const expression = source.slice(start + "const tools = ".length, end).trim().replace(/;$/, "");
  return vm.runInNewContext(expression, Object.create(null), { timeout: 1000 });
}

function canonicalTools(tools) {
  const chosen = new Map();
  for (const tool of tools) {
    const slug = slugify(tool.name);
    const current = chosen.get(slug);
    if (!current || fivePointScore(tool.rating) > fivePointScore(current.rating)) chosen.set(slug, tool);
  }
  return chosen;
}

function syncedPage(source, score) {
  const scoreText = score.toFixed(1);
  const filled = Math.max(0, Math.min(5, Math.round(score)));
  const stars = "★".repeat(filled) + "☆".repeat(5 - filled);
  let result = source.replace(
    /<div class="rating"[^>]*>[\s\S]*?<\/div>/i,
    `<div class="rating" aria-label="${scoreText} out of 5">${stars}</div>`
  );
  result = result.replace(
    /(<div class="score"[^>]*>)\s*[\d.]+\s*\/\s*(?:5|10)\s*(<\/div>)/i,
    `$1${scoreText}/5$2`
  );
  result = result.replace(/(Our Rating:\s*)[\d.]+\s*\/\s*(?:5|10)/gi, `$1${scoreText}/5`);
  return result;
}

function syncedAvailability(source, missing) {
  const payload = JSON.stringify([...missing].sort());
  return source.replace(
    /\/\* review-availability:start \*\/[\s\S]*?\/\* review-availability:end \*\//,
    `/* review-availability:start */${payload}/* review-availability:end */`
  );
}

const tools = readDirectoryTools();
const canonical = canonicalTools(tools);
const changed = [];
const missing = [];
const unsupported = [];

for (const [slug, tool] of canonical) {
  const page = path.join(ROOT, "tools", `${slug}-review.html`);
  if (!fs.existsSync(page)) {
    missing.push(slug);
    continue;
  }
  const source = fs.readFileSync(page, "utf8");
  if (!/<div class="score"[^>]*>/i.test(source)) {
    unsupported.push(slug);
    continue;
  }
  const expected = syncedPage(source, fivePointScore(tool.rating));
  if (expected !== source) {
    changed.push(path.relative(ROOT, page).replaceAll("\\", "/"));
    if (!CHECK) fs.writeFileSync(page, expected, "utf8");
  }
}

const directorySource = fs.readFileSync(DIRECTORY, "utf8");
const expectedDirectory = syncedAvailability(directorySource, missing);
const directoryChanged = expectedDirectory !== directorySource;
if (directoryChanged && !CHECK) fs.writeFileSync(DIRECTORY, expectedDirectory, "utf8");

const summary = `${canonical.size} canonical reviews; ${changed.length} score page(s) ${CHECK ? "out of sync" : "updated"}; ${missing.length} unpublished card(s) hidden until a detail page exists; ${unsupported.length} detail page(s) without the supported score block.`;
console.log(summary);
if (CHECK && (changed.length || directoryChanged)) {
  console.error(changed.slice(0, 30).join("\n"));
  if (directoryChanged) console.error("reviews.html availability list is out of sync");
  process.exitCode = 1;
}

export { canonicalTools, displayScore, fivePointScore, slugify, syncedAvailability, syncedPage };
