#!/usr/bin/env python3
"""Build deterministic commercial-intent pages from approved partner data.

The generator deliberately uses only reviewed registry copy. Search Console
queries and revenue totals never enter these public pages.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from scripts.build_partner_offers import (
        GENERATED_MARKER,
        apply_revenue_strategy,
        esc,
        load_registry,
        public_offers,
        shell,
        validate_registry,
    )
except ModuleNotFoundError:  # Direct execution
    from build_partner_offers import (  # type: ignore
        GENERATED_MARKER,
        apply_revenue_strategy,
        esc,
        load_registry,
        public_offers,
        shell,
        validate_registry,
    )


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "partner_offers.json"
OUTPUT_DIR = ROOT / "search-intent"
SITEMAP_PATH = ROOT / "sitemap.xml"
SEARCH_STRATEGY_PATH = ROOT / "data" / "search_growth_strategy.json"
SITEMAP_START = "  <!-- search-revenue:start -->"
SITEMAP_END = "  <!-- search-revenue:end -->"
MAX_ALTERNATIVE_PAGES = 8
MAX_COMPARISON_PAGES = 8


def intent_cluster(category: str) -> str:
    normalized = category.casefold()
    groups = (
        ("growth", ("advert", "conversion", "email", "marketing", "research", "sales", "seo")),
        ("content", ("audio", "design", "presentation", "video", "voice", "web")),
        ("documents", ("document", "pdf", "signature")),
        ("operations", ("automation", "business", "course", "education", "erp", "learning", "practice", "productivity", "tracking", "training")),
        ("data", ("data", "database", "developer")),
    )
    for group, terms in groups:
        if any(term in normalized for term in terms):
            return group
    return normalized


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.casefold())).strip("-")


def cta(offer: dict[str, Any], placement: str) -> str:
    return (
        f'<a href="{esc(offer["tracking_url"])}" target="_blank" '
        'rel="nofollow sponsored noopener" data-affiliate-offer="" '
        f'data-offer-id="{esc(offer["id"])}" data-placement="{esc(placement)}" '
        'class="btn-primary inline-block rounded-xl px-6 py-3 font-bold text-white">'
        f'{esc(offer["cta_label"])} →</a>'
    )


def tool_card(offer: dict[str, Any], placement: str) -> str:
    return f'''<article class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <p class="text-xs font-bold uppercase tracking-widest text-indigo-600">{esc(offer['category'])}</p>
      <h2 class="mt-2 text-2xl font-black">{esc(offer['name'])}</h2>
      <p class="mt-3 text-slate-600">{esc(offer['summary'])}</p>
      <p class="mt-4 text-sm"><strong>Best for:</strong> {esc(offer['best_for'])}</p>
      <p class="mt-3 text-sm text-slate-500"><strong>Pricing note:</strong> {esc(offer['pricing_note'])}</p>
      <div class="mt-6 flex flex-wrap gap-3">
        <a class="rounded-xl border border-indigo-200 px-5 py-3 font-bold text-indigo-700" href="../partner-offers/{esc(offer['slug'])}.html">Read review</a>
        {cta(offer, placement)}
      </div>
    </article>'''


def render_alternatives(primary: dict[str, Any], alternatives: list[dict[str, Any]]) -> str:
    cards = "\n".join(tool_card(item, f"alternatives-{primary['id']}") for item in alternatives)
    content = f'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16">
      <p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Independent shortlist</p>
      <h1 class="mt-4 text-4xl font-black md:text-6xl">Best {esc(primary['name'])} alternatives</h1>
      <p class="mt-6 max-w-3xl text-lg text-slate-600">Compare {esc(primary['name'])} with other verified tools before choosing. The shortlist prioritizes similar use cases and current site-wide conversion signals; commercial relationships are disclosed.</p>
      <div class="mt-8 rounded-2xl border border-indigo-200 bg-indigo-50 p-6">
        <h2 class="text-2xl font-bold">Start with {esc(primary['name'])}</h2>
        <p class="mt-2 text-slate-600">{esc(primary['why_consider'])}</p>
        <div class="mt-5 flex flex-wrap gap-3"><a class="rounded-xl border border-indigo-200 bg-white px-6 py-3 font-bold text-indigo-700" href="../partner-offers/{esc(primary['slug'])}.html">Read our review</a>{cta(primary, 'alternatives-primary')}</div>
      </div>
    </div></section>
    <section class="mx-auto max-w-5xl px-5 py-10"><h2 class="text-3xl font-black">Compare the strongest alternatives</h2><div class="mt-7 grid gap-6 md:grid-cols-2">{cards}</div></section>'''
    items = [primary, *alternatives]
    return shell(
        title=f"Best {primary['name']} Alternatives: Compare Features & Fit | artificial.one",
        description=f"Compare {primary['name']} alternatives by use case, audience fit and current pricing notes. Includes transparent partner disclosures.",
        canonical_path=f"search-intent/{primary['slug']}-alternatives.html",
        content=content,
        prefix="../",
        structured_data={
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": f"Best {primary['name']} alternatives",
            "itemListElement": [
                {"@type": "ListItem", "position": index, "name": item["name"], "url": f"https://artificial.one/partner-offers/{item['slug']}.html"}
                for index, item in enumerate(items, 1)
            ],
        },
    )


def render_use_case(category: str, offers: list[dict[str, Any]]) -> str:
    category_slug = slugify(category)
    cards = "\n".join(tool_card(item, f"use-case-{category_slug}") for item in offers)
    examples = ", ".join(str(item["name"]) for item in offers[:4])
    content = f'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16">
      <p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Use-case guide</p>
      <h1 class="mt-4 text-4xl font-black md:text-6xl">Best {esc(category)} tools</h1>
      <p class="mt-6 max-w-3xl text-lg text-slate-600">A practical comparison of verified {esc(category)} products including {esc(examples)}. Choose by workflow fit first, then confirm today’s pricing and limits.</p>
    </div></section>
    <section class="mx-auto max-w-5xl px-5 py-10"><div class="grid gap-6 md:grid-cols-2">{cards}</div></section>'''
    return shell(
        title=f"Best {category} Tools: Reviews, Use Cases & Pricing | artificial.one",
        description=f"Compare the best verified {category} tools by use case, audience fit and current pricing notes.",
        canonical_path=f"search-intent/best-{category_slug}-tools.html",
        content=content,
        prefix="../",
        structured_data={
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": f"Best {category} tools",
            "itemListElement": [
                {"@type": "ListItem", "position": index, "name": item["name"], "url": f"https://artificial.one/partner-offers/{item['slug']}.html"}
                for index, item in enumerate(offers, 1)
            ],
        },
    )


def render_comparison(left: dict[str, Any], right: dict[str, Any]) -> str:
    content = f'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16 text-center">
      <p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Side-by-side comparison</p>
      <h1 class="mt-4 text-4xl font-black md:text-6xl">{esc(left['name'])} vs {esc(right['name'])}</h1>
      <p class="mx-auto mt-6 max-w-3xl text-lg text-slate-600">Compare intended users, practical use cases, limitations and current pricing notes. Verify the live vendor terms before buying.</p>
    </div></section>
    <section class="mx-auto max-w-5xl px-5 py-10"><div class="grid gap-6 md:grid-cols-2">{tool_card(left, 'comparison-left')}{tool_card(right, 'comparison-right')}</div>
      <div class="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-6"><h2 class="text-2xl font-bold">How to choose</h2><p class="mt-3 text-amber-950"><strong>{esc(left['name'])}:</strong> {esc(left['why_consider'])}</p><p class="mt-3 text-amber-950"><strong>{esc(right['name'])}:</strong> {esc(right['why_consider'])}</p></div>
    </section>'''
    return shell(
        title=f"{left['name']} vs {right['name']}: Features, Pricing & Fit | artificial.one",
        description=f"Compare {left['name']} vs {right['name']} by use cases, audience fit, limitations and current pricing notes.",
        canonical_path=f"search-intent/{left['slug']}-vs-{right['slug']}.html",
        content=content,
        prefix="../",
        structured_data={
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": f"{left['name']} vs {right['name']}",
            "itemListElement": [
                {"@type": "ListItem", "position": index, "name": item["name"], "url": f"https://artificial.one/partner-offers/{item['slug']}.html"}
                for index, item in enumerate((left, right), 1)
            ],
        },
    )


def demand_catalog(offers: list[dict[str, Any]]) -> dict[str, tuple[dict[str, Any], str, int]]:
    result: dict[str, tuple[dict[str, Any], str, int]] = {}
    for offer in offers:
        for index, use_case in enumerate(offer.get("use_cases", [])):
            result[f"{offer['id']}-use-case-{index + 1}"] = (offer, str(use_case), index + 1)
    return result


def selected_demand_ids() -> list[str]:
    try:
        value = json.loads(SEARCH_STRATEGY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = value.get("demand_pages", []) if isinstance(value, dict) else []
    return [str(item) for item in items] if isinstance(items, list) else []


def render_demand_use_case(offer: dict[str, Any], use_case: str, alternatives: list[dict[str, Any]]) -> str:
    page_slug = f"{offer['slug']}-for-{slugify(use_case)}"
    alternative_cards = "\n".join(tool_card(item, f"demand-{offer['id']}-alternative") for item in alternatives[:3])
    content = f'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16">
      <p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Workflow decision guide</p>
      <h1 class="mt-4 text-4xl font-black md:text-6xl">{esc(offer['name'])} for {esc(use_case)}</h1>
      <p class="mt-6 max-w-3xl text-lg text-slate-600">Assess whether {esc(offer['name'])} fits this specific workflow, what to verify before subscribing, and which alternatives deserve comparison.</p>
      <div class="mt-8 rounded-2xl border border-indigo-200 bg-indigo-50 p-6"><h2 class="text-2xl font-black">Why consider it</h2><p class="mt-3 text-slate-700">{esc(offer['why_consider'])}</p><h2 class="mt-6 text-xl font-black">What to verify</h2><p class="mt-2 text-slate-700">{esc(offer['watch_out'])}</p><div class="mt-6 flex flex-wrap gap-3"><a class="rounded-xl border border-indigo-200 bg-white px-5 py-3 font-bold text-indigo-700" href="../partner-offers/{esc(offer['slug'])}.html">Read the full review</a>{cta(offer, 'demand-use-case-primary')}</div></div>
      <p class="mt-4 text-xs text-slate-500">Commercial disclosure: we may earn a commission from the marked partner link, at no extra cost to you.</p>
    </div></section><section class="mx-auto max-w-5xl px-5 py-10"><h2 class="text-3xl font-black">Alternatives for the same decision</h2><div class="mt-6 grid gap-6 md:grid-cols-3">{alternative_cards}</div></section>'''
    return shell(
        title=f"{offer['name']} for {use_case}: Fit, Limits & Alternatives | artificial.one",
        description=f"Evaluate {offer['name']} for {use_case}. Review workflow fit, limitations, pricing notes and relevant alternatives.",
        canonical_path=f"search-intent/{page_slug}.html", content=content, prefix="../",
        structured_data={"@context": "https://schema.org", "@type": "Article", "headline": f"{offer['name']} for {use_case}", "about": {"@type": "SoftwareApplication", "name": offer["name"]}},
    )


def planned_pages(offers: list[dict[str, Any]]) -> dict[Path, str]:
    pages: dict[Path, str] = {}
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for offer in offers:
        by_category[str(offer["category"])].append(offer)

    for primary in offers[:MAX_ALTERNATIVE_PAGES]:
        primary_cluster = intent_cluster(str(primary["category"]))
        alternatives = [
            item for item in offers
            if item["id"] != primary["id"] and intent_cluster(str(item["category"])) == primary_cluster
        ]
        if alternatives:
            pages[OUTPUT_DIR / f"{primary['slug']}-alternatives.html"] = render_alternatives(primary, alternatives[:4])

    comparisons = 0
    for category, members in sorted(by_category.items()):
        if len(members) < 2:
            continue
        category_slug = slugify(category)
        pages[OUTPUT_DIR / f"best-{category_slug}-tools.html"] = render_use_case(category, members)
        if comparisons < MAX_COMPARISON_PAGES:
            left, right = members[:2]
            pages[OUTPUT_DIR / f"{left['slug']}-vs-{right['slug']}.html"] = render_comparison(left, right)
            comparisons += 1
    catalog = demand_catalog(offers)
    for concept_id in selected_demand_ids():
        concept = catalog.get(concept_id)
        if not concept:
            continue
        offer, use_case, _index = concept
        alternatives = [item for item in offers if item["id"] != offer["id"] and intent_cluster(str(item["category"])) == intent_cluster(str(offer["category"]))]
        path = OUTPUT_DIR / f"{offer['slug']}-for-{slugify(use_case)}.html"
        pages[path] = render_demand_use_case(offer, use_case, alternatives)
    return pages


def apply_search_priority(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer aggregate search-demand winners without exposing search metrics."""
    try:
        strategy = json.loads(SEARCH_STRATEGY_PATH.read_text(encoding="utf-8"))
        priority = strategy.get("content_priority", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return offers
    if not isinstance(priority, list):
        return offers
    positions = {str(offer_id): index for index, offer_id in enumerate(priority)}
    return sorted(offers, key=lambda item: (positions.get(str(item["id"]), len(positions)), offers.index(item)))


def update_sitemap(source: str, paths: list[Path], lastmod: str) -> str:
    rows = [SITEMAP_START]
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        rows.append(f"  <url><loc>https://artificial.one/{relative}</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>")
    rows.append(SITEMAP_END)
    block = "\n".join(rows)
    if SITEMAP_START in source and SITEMAP_END in source:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), block, source, flags=re.S)
    source = re.sub(r"\s*<url>\s*<loc>https://artificial\.one/search-intent/[^<]+</loc>.*?</url>", "", source, flags=re.S)
    if "</urlset>" not in source:
        raise ValueError("sitemap.xml has no closing urlset element")
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + block + "\n</urlset>\n"


def build(check: bool = False) -> int:
    registry = load_registry(REGISTRY_PATH)
    offers = apply_search_priority(apply_revenue_strategy(public_offers(validate_registry(registry), date.today())))
    expected = planned_pages(offers)
    sitemap_source = SITEMAP_PATH.read_text(encoding="utf-8")
    sitemap_expected = update_sitemap(sitemap_source, list(expected), str(registry["updated_at"]))
    stale = [path for path, value in expected.items() if not path.exists() or path.read_text(encoding="utf-8") != value]
    existing = {path for path in OUTPUT_DIR.glob("*.html")} if OUTPUT_DIR.exists() else set()
    removable = {path for path in existing - set(expected) if GENERATED_MARKER in path.read_text(encoding="utf-8", errors="ignore")}
    if check:
        if stale or removable or sitemap_source != sitemap_expected:
            print("Search revenue pages are stale.", file=sys.stderr)
            return 1
        print(f"Search revenue build is current ({len(expected)} pages).")
        return 0
    OUTPUT_DIR.mkdir(exist_ok=True)
    for path, value in expected.items():
        path.write_text(value, encoding="utf-8")
    for path in removable:
        path.unlink()
    SITEMAP_PATH.write_text(sitemap_expected, encoding="utf-8")
    print(f"Built {len(expected)} deterministic commercial-intent pages.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return build(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
