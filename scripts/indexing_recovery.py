#!/usr/bin/env python3
"""Build crawl discovery assets, audit commercial pages, and notify IndexNow."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from scripts.build_partner_offers import esc, shell
except ModuleNotFoundError:
    from build_partner_offers import esc, shell  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
SITEMAP_PATH = ROOT / "sitemap.xml"
REPORT_PATH = ROOT / "data" / "indexing_recovery.json"
SEARCH_STRATEGY_PATH = ROOT / "data" / "search_growth_strategy.json"
HUB_PATH = ROOT / "buyers-guides.html"
SITE = "https://artificial.one"
INDEXNOW_KEY = "a10e20260915d74b93c2f18e7a45c901"
SITEMAP_START = "  <!-- indexing-recovery:start -->"
SITEMAP_END = "  <!-- indexing-recovery:end -->"
HREF_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)', re.I)
CANONICAL_RE = re.compile(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']([^"\']+)', re.I)


def priority_pages() -> list[Path]:
    paths = [ROOT / "ai-tool-finder.html", ROOT / "ai-stack-builder.html", ROOT / "decision-tools.html", ROOT / "offer-updates.html", ROOT / "partner-offers.html", ROOT / "appsumo-ai-tools.html", ROOT / "sponsor.html"]
    for folder in ("partner-offers", "search-intent", "calculators"):
        paths.extend(sorted((ROOT / folder).glob("*.html")))
    return [path for path in paths if path.exists()]


def page_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S) or re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", match.group(1) if match else path.stem)
    return re.sub(r"\s+", " ", value).strip()


def crawl_priority_paths(paths: list[Path]) -> list[Path]:
    strategy = load_public_json(SEARCH_STRATEGY_PATH)
    by_relative = {"/" + path.relative_to(ROOT).as_posix(): path for path in paths}
    result: list[Path] = []
    for value in strategy.get("crawl_priority", []):
        candidate = by_relative.get(str(value))
        if candidate and candidate not in result:
            result.append(candidate)
    return result


def render_hub(paths: list[Path], crawl_priority: list[Path] | None = None) -> str:
    priority = list(crawl_priority or [])
    priority_position = {path: index for index, path in enumerate(priority)}
    groups: dict[str, list[Path]] = {"Decision tools": [], "Partner reviews": [], "Comparisons and buying guides": []}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("partner-offers/"):
            groups["Partner reviews"].append(path)
        elif relative.startswith("search-intent/"):
            groups["Comparisons and buying guides"].append(path)
        else:
            groups["Decision tools"].append(path)
    sections: list[str] = []
    for label, members in groups.items():
        members.sort(key=lambda item: (priority_position.get(item, len(priority_position)), page_title(item).casefold()))
        links = "".join(f'<li><a class="font-semibold text-indigo-700 hover:underline" href="{esc(item.relative_to(ROOT).as_posix())}">{esc(page_title(item))}</a></li>' for item in members)
        sections.append(f'<section class="rounded-2xl border border-slate-200 bg-white p-6"><h2 class="text-2xl font-black">{esc(label)}</h2><ul class="mt-4 space-y-3">{links}</ul></section>')
    priority_cards = "".join(
        f'<a class="rounded-xl border border-indigo-200 bg-white p-4 font-semibold text-indigo-800 shadow-sm hover:border-indigo-400" href="{esc(item.relative_to(ROOT).as_posix())}">{esc(page_title(item))} →</a>'
        for item in priority[:40]
    )
    priority_section = (
        f'''<section class="mx-auto max-w-6xl px-5 pt-10"><div class="rounded-2xl border border-indigo-200 bg-indigo-50 p-6"><p class="text-xs font-bold uppercase tracking-widest text-indigo-600">Priority guides</p><h2 class="mt-2 text-2xl font-black">Useful pages being surfaced now</h2><div class="mt-5 grid gap-3 md:grid-cols-2">{priority_cards}</div></div></section>'''
        if priority_cards
        else ""
    )
    content = f'''<section class="bg-white"><div class="mx-auto max-w-6xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Buyer resource library</p><h1 class="mt-4 text-4xl font-black md:text-6xl">AI software decision guides</h1><p class="mt-5 max-w-3xl text-lg text-slate-600">Browse free calculators, structured comparisons and reviewed partner offers by the decision you need to make.</p></div></section>{priority_section}<section class="mx-auto grid max-w-6xl gap-6 px-5 py-10 lg:grid-cols-3">{''.join(sections)}</section>'''
    return shell(title="AI Software Buying Guides and Calculators | artificial.one", description="Browse artificial.one AI software calculators, comparisons and partner decision guides.", canonical_path="buyers-guides.html", content=content, structured_data={"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI software decision guides"})


def _local_path(source: Path, href: str) -> str | None:
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    base = SITE + "/" + source.relative_to(ROOT).as_posix()
    parsed = urlparse(urljoin(base, href))
    if parsed.netloc.casefold().removeprefix("www.") != "artificial.one":
        return None
    path = parsed.path.lstrip("/") or "index.html"
    return path if path.endswith(".html") else None


def audit(paths: list[Path], virtual: dict[Path, str] | None = None, sitemap_text: str | None = None) -> dict[str, Any]:
    virtual = virtual or {}
    incoming: Counter[str] = Counter()
    all_pages = sorted({path for path in ROOT.rglob("*.html") if ".git" not in path.parts} | set(virtual))
    for source in all_pages:
        text = virtual.get(source) or source.read_text(encoding="utf-8", errors="ignore")
        for href in HREF_RE.findall(text):
            target = _local_path(source, href)
            if target:
                incoming[target] += 1
    sitemap = sitemap_text if sitemap_text is not None else SITEMAP_PATH.read_text(encoding="utf-8", errors="ignore")
    issues: list[dict[str, str]] = []
    depths: Counter[str] = Counter()
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        text = virtual.get(path) or path.read_text(encoding="utf-8", errors="ignore")
        expected = f"{SITE}/{relative}"
        canonical = CANONICAL_RE.search(text)
        if not canonical or canonical.group(1).rstrip("/") != expected.rstrip("/"):
            issues.append({"path": relative, "issue": "canonical"})
        if re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex', text, re.I):
            issues.append({"path": relative, "issue": "noindex"})
        if expected not in sitemap and path != HUB_PATH:
            issues.append({"path": relative, "issue": "sitemap"})
        count = incoming[relative]
        depths["0" if count == 0 else "1" if count < 3 else "3+"] += 1
        if count == 0 and path != HUB_PATH:
            issues.append({"path": relative, "issue": "no_internal_link"})
    return {
        "version": 1,
        "updated_at": content_lastmod(),
        "method": "static-commercial-indexability-audit",
        "priority_pages": len(paths),
        "issues": issues,
        "incoming_link_distribution": dict(depths),
        "indexnow": {"key_location": f"{SITE}/{INDEXNOW_KEY}.txt", "submission_enabled": True},
        "note": "This report covers static crawl signals. Google indexing verdicts remain private in the Search Console monitor.",
    }


def content_lastmod() -> str:
    values: list[str] = []
    for relative in ("data/partner_offers.json", "data/search_growth_strategy.json"):
        try:
            value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            candidate = str(value.get("updated_at") or "")
            date.fromisoformat(candidate)
            values.append(candidate)
        except (OSError, ValueError, json.JSONDecodeError, AttributeError):
            continue
    return max(values) if values else date.today().isoformat()


def update_sitemap(source: str) -> str:
    rows = [SITEMAP_START]
    rows.append(f"  <url><loc>{SITE}/buyers-guides.html</loc><lastmod>{content_lastmod()}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>")
    if (ROOT / "offer-updates.html").exists():
        alerts = load_public_json(ROOT / "data" / "offer_change_alerts.json")
        rows.append(f"  <url><loc>{SITE}/offer-updates.html</loc><lastmod>{alerts.get('updated_at') or content_lastmod()}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>")
    rows.append(SITEMAP_END)
    row = "\n".join(rows)
    if SITEMAP_START in source and SITEMAP_END in source:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), row, source, flags=re.S)
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + row + "\n</urlset>\n"


def load_public_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def changed_urls() -> list[str]:
    commands = (("git", "diff", "--name-only", "HEAD"), ("git", "diff", "--name-only", "HEAD^", "HEAD"))
    paths: set[str] = set()
    for command in commands:
        try:
            output = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True).stdout
        except OSError:
            continue
        for value in output.splitlines():
            relative = value.strip().replace("\\", "/")
            if relative.endswith((".html", ".xml")) and not relative.startswith((".git/", "newsletter/")):
                paths.add(relative)
    return [f"{SITE}/{path}" for path in sorted(paths)][:10000]


def submit_indexnow(urls: list[str], state_path: Path) -> str:
    if (os.environ.get("INDEXNOW_SUBMIT_ENABLED") or "").casefold() != "true":
        return "IndexNow submission disabled"
    state = load_public_json(state_path)
    pending = sorted(set(str(item) for item in state.get("pending_urls", []) if str(item).startswith(SITE + "/")) | set(urls))[:10000]
    if not pending:
        return "IndexNow has no changed URLs"
    body = json.dumps({"host": "artificial.one", "key": INDEXNOW_KEY, "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt", "urlList": pending}).encode()
    request = Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({"version": 1, "pending_urls": [], "submitted_on": date.today().isoformat()}, indent=2) + "\n", encoding="utf-8")
            return f"IndexNow accepted {len(pending)} changed URLs (HTTP {response.status})"
    except Exception as exc:
        # Search-engine notification is best-effort and must never block a site build.
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"version": 1, "pending_urls": pending}, indent=2) + "\n", encoding="utf-8")
        return f"IndexNow notification deferred ({type(exc).__name__})"


def write_if_changed(path: Path, text: str) -> bool:
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    if previous == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def build(check: bool = False, submit: bool = False, state_path: Path = ROOT / ".indexnow" / "private-state.json") -> int:
    pages = priority_pages()
    priority = crawl_priority_paths(pages)
    hub = render_hub(pages, priority)
    virtual = {HUB_PATH: hub}
    pages_with_hub = [*pages, HUB_PATH]
    sitemap = SITEMAP_PATH.read_text(encoding="utf-8")
    expected_sitemap = update_sitemap(sitemap)
    report = json.dumps(audit(pages_with_hub, virtual, expected_sitemap), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    stale = (not HUB_PATH.exists() or HUB_PATH.read_text(encoding="utf-8") != hub or not REPORT_PATH.exists() or REPORT_PATH.read_text(encoding="utf-8") != report or sitemap != expected_sitemap)
    if check:
        if stale:
            print("Indexing recovery assets are stale.", file=sys.stderr)
            return 1
        print(f"Indexing recovery assets are current ({len(pages_with_hub)} priority pages).")
        return 0
    write_if_changed(HUB_PATH, hub)
    write_if_changed(REPORT_PATH, report)
    write_if_changed(SITEMAP_PATH, expected_sitemap)
    status = submit_indexnow(changed_urls(), state_path) if submit else "IndexNow not requested"
    print(f"Audited {len(pages_with_hub)} priority pages; {status}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--state", type=Path, default=ROOT / ".indexnow" / "private-state.json")
    args = parser.parse_args()
    return build(check=args.check, submit=args.submit, state_path=args.state)


if __name__ == "__main__":
    raise SystemExit(main())
