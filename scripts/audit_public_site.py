#!/usr/bin/env python3
"""Read-only public-site audit used before every commercial release."""

from __future__ import annotations

from collections import Counter, defaultdict
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

try:
    from scripts.affiliate_catalog import COMMERCIAL_CORE_IDS, is_ai_relevant, monetized_tools
except ModuleNotFoundError:
    from affiliate_catalog import COMMERCIAL_CORE_IDS, is_ai_relevant, monetized_tools  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://www.artificial.one/"
HREF = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)', re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
DESC = re.compile(r'<meta\b(?=[^>]*\bname=["\']description["\'])[^>]*\bcontent=(?:"([^"]*)"|\'([^\']*)\')', re.I)
CANONICAL = re.compile(r'<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>', re.I)
IMG = re.compile(r"<img\b[^>]*>", re.I)


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def public_pages(root: Path = ROOT) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.html")
        if not ({".git", "Claude"} & set(path.parts)) and not path.name.startswith("google")
    )


def target_path(source: Path, href: str) -> str | None:
    if href.startswith(("#", "mailto:", "tel:", "javascript:", "/api/")):
        return None
    resolved = urlparse(urljoin(SITE + source.relative_to(ROOT).as_posix(), href))
    if resolved.netloc.casefold().removeprefix("www.") != "artificial.one":
        return None
    path = resolved.path.lstrip("/") or "index.html"
    if path.endswith("/"):
        path += "index.html"
    return path if "." in Path(path).name else None


def audit(root: Path = ROOT) -> dict[str, object]:
    pages = public_pages(root)
    known = {path.relative_to(root).as_posix() for path in pages}
    titles: dict[str, list[str]] = defaultdict(list)
    missing_canonical: list[str] = []
    weak_descriptions: list[str] = []
    broken: set[tuple[str, str]] = set()
    image_issues: list[str] = []
    incoming: Counter[str] = Counter()
    for path in pages:
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8", errors="ignore")
        match = TITLE.search(source)
        if match:
            titles[clean(match.group(1)).casefold()].append(relative)
        if not CANONICAL.search(source):
            missing_canonical.append(relative)
        description = DESC.search(source)
        value = (description.group(1) or description.group(2)) if description else ""
        if len(clean(value)) < 55 or "Categories ▾" in value:
            weak_descriptions.append(relative)
        visible_markup = re.sub(r"<(script|style|template)\b.*?</\1>", "", source, flags=re.I | re.S)
        visible_markup = re.sub(r'<a\b[^>]*class=["\'][^"\']*\bbrand\b[^"\']*["\'][^>]*>.*?</a>', "", visible_markup, flags=re.I | re.S)
        for href in HREF.findall(visible_markup):
            target = target_path(path, href)
            if not target:
                continue
            incoming[target] += 1
            if target not in known and not (root / target).exists():
                broken.add((relative, target))
        image_critical = relative in {"index.html", "ai-tool-finder.html", "ai-software-shortlist.html"} or relative.startswith("partner-offers/")
        if image_critical:
            for tag in IMG.findall(visible_markup):
                if "width=" not in tag or "height=" not in tag or "alt=" not in tag:
                    image_issues.append(relative)
                    break

    registry = json.loads((root / "data" / "partner_offers.json").read_text(encoding="utf-8"))
    published = [item for item in registry.get("offers", []) if item.get("status") == "published"]
    core = [item for item in published if item.get("id") in COMMERCIAL_CORE_IDS]
    core_links = {
        str(item["id"]): incoming[f"partner-offers/{item['slug']}.html"] for item in core
    }
    priority = (root / "sitemap-priority.xml").read_text(encoding="utf-8")
    return {
        "html_pages": len(pages),
        "published_partner_offers": len(published),
        "monetized_catalog_products": len(monetized_tools(root / "data" / "tool_intelligence.json")),
        "ai_relevant_partner_offers": sum(is_ai_relevant(item) for item in published),
        "commercial_core_pages": len(core),
        "priority_urls": priority.count("<loc>"),
        "broken_internal_links": [{"source": source, "target": target} for source, target in sorted(broken)],
        "duplicate_titles": [paths for paths in titles.values() if len(paths) > 1],
        "missing_canonicals": missing_canonical,
        "weak_descriptions": weak_descriptions,
        "core_pages_below_three_incoming_links": {
            identifier: count for identifier, count in core_links.items() if count < 3
        },
        "pages_with_incomplete_image_dimensions_or_alt": sorted(set(image_issues)),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
