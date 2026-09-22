#!/usr/bin/env python3
"""Conservatively remove unsupported legacy catalogue pages from the search index.

The pages remain available to visitors.  Only records that are explicitly marked
as legacy, have no mapped source, have no active monetization, and have at most
one internal inbound link are selected.  A generated marker makes the change
reversible when a record is later reviewed or starts receiving deliberate links.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from html import unescape
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin, urlparse


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://artificial.one"
CATALOG_PATH = Path("data/tool_intelligence.json")
REPORT_PATH = Path("data/legacy_index_consolidation.json")
SEARCH_STRATEGY_PATH = Path("data/search_growth_strategy.json")
SITEMAP_PATH = Path("sitemap.xml")
MARKER_START = "<!-- legacy-index-consolidation:start -->"
MARKER_END = "<!-- legacy-index-consolidation:end -->"
MARKER = f'{MARKER_START}<meta name="robots" content="noindex,follow">{MARKER_END}'
HREF_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)', re.I)
CANONICAL_RE = re.compile(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']([^"\']+)', re.I)
URL_ROW_RE = re.compile(r"\s*<url>.*?</url>", re.S)
LOC_RE = re.compile(r"<loc>\s*([^<]+)\s*</loc>", re.I)


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def internal_target(root: Path, source: Path, href: str) -> str | None:
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    base = f"{SITE}/{source.relative_to(root).as_posix()}"
    parsed = urlparse(urljoin(base, href))
    if parsed.netloc.casefold().removeprefix("www.") != "artificial.one":
        return None
    value = parsed.path.lstrip("/") or "index.html"
    return value if value.endswith(".html") else None


def inbound_counts(root: Path) -> Counter[str]:
    result: Counter[str] = Counter()
    for page in root.rglob("*.html"):
        if any(part in {".git", "node_modules"} for part in page.parts):
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        for href in HREF_RE.findall(text):
            target = internal_target(root, page, href)
            if target:
                result[target] += 1
    return result


def canonical_for(root: Path, relative: str, text: str) -> str:
    match = CANONICAL_RE.search(text)
    if match and match.group(1).startswith(SITE + "/"):
        return match.group(1).split("#", 1)[0]
    return f"{SITE}/{relative}"


def add_marker(text: str) -> str:
    if MARKER_START in text or re.search(
        r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex', text, re.I
    ):
        return text
    if "</head>" not in text.casefold():
        raise ValueError("HTML page has no closing head element")
    return re.sub(r"</head>", f"  {MARKER}\n</head>", text, count=1, flags=re.I)


def remove_marker(text: str) -> str:
    return re.sub(
        rf"\s*{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\s*",
        "\n",
        text,
        flags=re.S,
    )


def filter_sitemap(source: str, excluded_urls: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        loc = LOC_RE.search(match.group(0))
        return "" if loc and unescape(loc.group(1).strip()).rstrip("/") in excluded_urls else match.group(0)

    return URL_ROW_RE.sub(replace, source)


def restore_sitemap(source: str, restored_urls: set[str]) -> str:
    existing = {unescape(item).strip().rstrip("/") for item in LOC_RE.findall(source)}
    rows = [
        f"  <url><loc>{url}</loc><lastmod>{date.today().isoformat()}</lastmod><changefreq>monthly</changefreq><priority>0.3</priority></url>"
        for url in sorted(restored_urls)
        if url.rstrip("/") not in existing
    ]
    if not rows:
        return source
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + "\n".join(rows) + "\n</urlset>\n"


def plan(root: Path) -> tuple[list[dict[str, Any]], set[str]]:
    catalog = load_json(root / CATALOG_PATH, {})
    records = catalog.get("tools", []) if isinstance(catalog, dict) else []
    incoming = inbound_counts(root)
    search_strategy = load_json(root / SEARCH_STRATEGY_PATH, {})
    observed_pages = {
        str(item).lstrip("/")
        for item in search_strategy.get("observed_pages", [])
        if isinstance(item, str)
    } if isinstance(search_strategy, dict) else set()
    decisions: list[dict[str, Any]] = []
    selected: set[str] = set()

    for record in records:
        if not isinstance(record, dict):
            continue
        relative = str(record.get("links", {}).get("profile") or "").lstrip("/")
        page = root / relative
        if not relative or not relative.startswith("tools/") or not page.is_file():
            continue
        status = str(record.get("verification", {}).get("status") or "")
        source = str(record.get("links", {}).get("source") or "").strip()
        monetized = bool(record.get("monetization", {}).get("active"))
        links = int(incoming.get(relative, 0))
        observed = relative in observed_pages
        eligible = status == "legacy-catalog" and not source and not monetized and links <= 1 and not observed
        action = "noindex" if eligible else "keep"
        reasons = []
        if eligible:
            reasons = ["legacy catalogue record", "no mapped evidence source", "no active monetization", f"{links} internal inbound links"]
            selected.add(relative)
        decisions.append(
            {
                "path": relative,
                "name": str(record.get("name") or page.stem),
                "action": action,
                "status": status,
                "inbound_links": links,
                "recent_google_impressions": observed,
                "reasons": reasons,
            }
        )

    return sorted(decisions, key=lambda item: item["path"]), selected


def desired_outputs(root: Path) -> tuple[dict[Path, str], dict[str, Any]]:
    decisions, selected = plan(root)
    previous = load_json(root / REPORT_PATH, {})
    previous_selected = {
        str(item.get("path") or "")
        for item in previous.get("decisions", [])
        if isinstance(item, dict) and item.get("action") == "noindex"
    }
    outputs: dict[Path, str] = {}

    for relative in sorted(selected | previous_selected):
        page = root / relative
        if not page.is_file():
            continue
        current = page.read_text(encoding="utf-8", errors="ignore")
        desired = add_marker(current) if relative in selected else remove_marker(current)
        outputs[page] = desired

    sitemap_path = root / SITEMAP_PATH
    sitemap = sitemap_path.read_text(encoding="utf-8", errors="ignore")
    excluded_urls = {
        canonical_for(root, relative, outputs.get(root / relative) or (root / relative).read_text(encoding="utf-8", errors="ignore")).rstrip("/")
        for relative in selected
    }
    restored_urls = {
        canonical_for(root, relative, outputs.get(root / relative) or (root / relative).read_text(encoding="utf-8", errors="ignore")).rstrip("/")
        for relative in previous_selected - selected
        if (root / relative).is_file()
    }
    outputs[sitemap_path] = restore_sitemap(filter_sitemap(sitemap, excluded_urls), restored_urls)

    report = {
        "version": 1,
        "updated_at": date.today().isoformat(),
        "method": "reversible-conservative-legacy-index-consolidation",
        "policy": {
            "scope": "Existing tools/*.html records only",
            "noindex_requires": [
                "verification status is legacy-catalog",
                "no mapped evidence source",
                "no active monetization",
                "at most one internal inbound link",
                "no Google impressions in the current Search Console window",
            ],
            "effect": "The page stays live with noindex,follow and is removed from the sitemap.",
            "recovery": "The generated noindex is removed and the canonical is restored to the sitemap when the page no longer matches the policy.",
        },
        "summary": {
            "evaluated": len(decisions),
            "kept": len(decisions) - len(selected),
            "noindex": len(selected),
            "restored": len(previous_selected - selected),
        },
        # Keep the public audit compact: only URLs affected by the policy need
        # individual disclosure. Aggregate counts cover the protected records.
        "decisions": [item for item in decisions if item["action"] == "noindex"],
    }
    outputs[root / REPORT_PATH] = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    return outputs, report


def run(root: Path = ROOT, check: bool = False) -> dict[str, Any]:
    outputs, report = desired_outputs(root)
    stale = [path for path, desired in outputs.items() if not path.exists() or path.read_text(encoding="utf-8", errors="ignore") != desired]
    if check:
        if stale:
            names = ", ".join(path.relative_to(root).as_posix() for path in stale[:12])
            raise SystemExit(f"Legacy index consolidation is stale: {names}")
        return report
    for path, desired in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desired, encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = run(check=args.check)
    summary = result["summary"]
    print(
        f"Legacy index consolidation evaluated {summary['evaluated']} pages: "
        f"kept {summary['kept']}, noindexed {summary['noindex']}, restored {summary['restored']}."
    )
