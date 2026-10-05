import { execFileSync } from "node:child_process";

// Vercel builds ordinary human/PR commits immediately. High-frequency bot
// commits are collected on main and released together by scheduled-site-release.
const subject = execFileSync("git", ["log", "-1", "--pretty=%s"], { encoding: "utf8" }).trim();
const explicitRelease = subject.includes("[release]");
const botOnly = subject.includes("[skip ci]") || [
  "Refresh AppSumo availability",
  "Fulfil sponsored-content orders",
].some((prefix) => subject.startsWith(prefix));

if (explicitRelease || !botOnly) {
  console.log(`Build required: ${subject}`);
  process.exit(1);
}
console.log(`Build batched until the next scheduled release: ${subject}`);
process.exit(0);
