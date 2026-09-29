#!/usr/bin/env python3
"""Build category discovery pages for every active monetized product."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from html import escape
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

try:
    from scripts.affiliate_catalog import CLUSTERS, monetized_tools
    from scripts.build_partner_offers import shell
except ModuleNotFoundError:
    from affiliate_catalog import CLUSTERS, monetized_tools  # type: ignore
    from build_partner_offers import shell  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
OUTPUT_PATH = ROOT / "data" / "affiliate_growth_loop.json"
HUB_PATH = ROOT / "affiliate-categories.html"
CATEGORY_DIR = ROOT / "affiliate-categories"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def ordered_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranking = [str(item) for item in load_json(STRATEGY_PATH).get("ranking", [])]
    positions = {identifier: index for index, identifier in enumerate(ranking)}
    return sorted(tools, key=lambda item: (
        positions.get(str(item["offer_id"]), len(positions)),
        str(item.get("name") or "").casefold(),
    ))


def logo_url(tool: dict[str, Any]) -> str:
    host = urlparse(str(tool["affiliate_url"])).netloc.removeprefix("www.")
    return f"https://www.google.com/s2/favicons?domain={quote(host)}&sz=128"


def card(tool: dict[str, Any], placement: str) -> str:
    name = escape(str(tool.get("name") or "Software"))
    category = escape(str(tool.get("category") or tool["cluster_label"]))
    summary = escape(str(tool.get("summary") or tool.get("best_for") or "Review the current product fit, limits and offer."))
    best_for = escape(str(tool.get("best_for") or "Buyers comparing software for a defined workflow."))
    return f'''<article class="growth-card" data-search="{escape((name + ' ' + category + ' ' + summary).casefold())}">
      <a class="growth-card-main" href="{escape(str(tool['affiliate_url']), quote=True)}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-affiliate-network="{escape(str(tool.get('monetization', {}).get('network') or 'affiliate'))}" data-offer-id="{escape(str(tool['offer_id']))}" data-placement="{escape(placement)}" aria-label="Open the current {name} offer">
        <div class="growth-card-head"><img src="{escape(logo_url(tool), quote=True)}" alt="" width="44" height="44" loading="lazy"><span>{category}</span></div>
        <h2>{name}</h2><p>{summary}</p><p class="growth-fit"><strong>Best for:</strong> {best_for}</p><span class="growth-cta">Check current offer →</span>
      </a>
      <a class="growth-guide" href="../{escape(str(tool['profile_path']))}">Read the independent guide →</a>
    </article>'''


def styles() -> str:
    return '''<style>
    .growth-hero{padding:58px 0 28px;background:linear-gradient(135deg,#f7f3ff,#effcf4)}.growth-hero h1{max-width:850px;font-size:clamp(2.6rem,7vw,5.6rem);letter-spacing:-.06em;line-height:.94;margin:.18em 0}.growth-hero p{max-width:780px;color:#536071;font-size:1.08rem;line-height:1.65}.growth-shell{padding:34px 0 70px}.growth-search{width:100%;max-width:720px;border:2px solid #d8ccf6;border-radius:16px;padding:15px 18px;font:inherit;background:white}.growth-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:24px}.growth-card{border:1px solid #e4ddf1;border-radius:22px;background:#fff;box-shadow:0 12px 35px rgba(50,35,85,.08);overflow:hidden;display:flex;flex-direction:column;transition:.2s}.growth-card:hover{transform:translateY(-4px);box-shadow:0 18px 46px rgba(50,35,85,.14)}.growth-card-main{display:block;flex:1;padding:22px;color:#151321;text-decoration:none}.growth-card-head{display:flex;align-items:center;gap:11px;color:#7653b8;font-size:.76rem;font-weight:900;text-transform:uppercase;letter-spacing:.08em}.growth-card-head img{border-radius:12px;background:#f6f3fb}.growth-card h2{font-size:1.35rem;margin:18px 0 8px}.growth-card p{color:#5d6677;line-height:1.55}.growth-card .growth-fit{font-size:.9rem}.growth-cta{display:inline-block;margin-top:10px;color:#4c2ca0;font-weight:900}.growth-guide{padding:14px 22px;border-top:1px solid #eee8f6;color:#5b3db1;text-decoration:none;font-weight:800;font-size:.88rem}.cluster-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:25px}.cluster-link{display:block;padding:22px;border-radius:20px;background:white;border:1px solid #e1daf0;color:#201a2f;text-decoration:none;box-shadow:0 9px 26px rgba(50,35,85,.07)}.cluster-link strong{display:block;font-size:1.15rem}.cluster-link span{color:#6b6478;font-size:.9rem}.growth-disclosure{margin-top:28px;color:#6c6479;font-size:.86rem}@media(max-width:900px){.growth-grid,.cluster-list{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.growth-grid,.cluster-list{grid-template-columns:1fr}.growth-hero{padding-top:38px}}
    </style>'''


def render_hub(groups: dict[str, list[dict[str, Any]]]) -> str:
    blocks = []
    labels = {slug: label for slug, label, _ in CLUSTERS}
    for slug, tools in groups.items():
        blocks.append(f'<a class="cluster-link" href="affiliate-categories/{slug}.html"><strong>{escape(labels[slug])}</strong><span>{len(tools)} current partner option{"s" if len(tools) != 1 else ""} →</span></a>')
    content = f'''{styles()}<section class="growth-hero"><div class="container"><p class="eyebrow">Shop by outcome</p><h1>Find software for the job you need to finish.</h1><p>Browse every current partner option by practical category. Each product leads to an independent guide and a clearly marked current offer.</p><div class="cluster-list">{''.join(blocks)}</div><div class="panel" style="margin-top:28px"><h2>Choose by workflow, not by hype</h2><p>Start with the outcome you need: create content, produce video, improve visibility, automate work, analyze data or run a business process. Open a category to search its current options. Every card shows the product’s stated fit and links to the current partner destination; the separate guide adds buying questions, limitations and practical context. Newly approved products enter the appropriate category automatically after their exact referral link and internal guide are confirmed. Performance signals can change the order, but payment never guarantees inclusion or a positive verdict.</p></div><p class="growth-disclosure">Affiliate disclosure: artificial.one may earn a commission from marked offer links at no extra cost to you. Commercial relationships never guarantee placement.</p></div></section>'''
    return shell(title="AI Software by Category | artificial.one", description="Browse current AI and business software partner offers by practical category, with independent guides and clearly marked current offers.", canonical_path="affiliate-categories.html", content=content)


def render_category(slug: str, label: str, tools: list[dict[str, Any]]) -> str:
    cards = "".join(card(tool, f"category-{slug}") for tool in tools)
    payload = json.dumps([str(tool["offer_id"]) for tool in tools]).replace("<", "\\u003c")
    content = f'''{styles()}<section class="growth-hero"><div class="container"><p class="eyebrow">{escape(label)}</p><h1>Compare {escape(label).lower()} software.</h1><p>{len(tools)} current partner option{"s" if len(tools) != 1 else ""}, ordered by the site’s privacy-safe performance system while preserving room for newly approved products.</p><input class="growth-search" type="search" placeholder="Search this category…" aria-label="Search {escape(label)}" data-growth-search></div></section><section class="growth-shell"><div class="container"><div class="growth-grid" data-growth-grid>{cards}</div><p class="growth-disclosure">Open a card to visit the current partner destination, or use “Read the independent guide” for fit, limitations and decision support.</p></div></section><script type="application/json" id="growth-offer-ids">{payload}</script><script>document.addEventListener('DOMContentLoaded',()=>{{const input=document.querySelector('[data-growth-search]');if(!input)return;input.addEventListener('input',()=>{{const q=input.value.trim().toLowerCase();document.querySelectorAll('[data-growth-grid] .growth-card').forEach(card=>card.hidden=q&&!card.dataset.search.includes(q));}});}});</script>'''
    return shell(title=f"Best {label} Software & Current Offers | artificial.one", description=f"Compare {len(tools)} current {label.lower()} software options, independent guides and clearly marked partner offers.", canonical_path=f"affiliate-categories/{slug}.html", content=content, prefix="../")


def desired_outputs() -> tuple[dict[Path, str], dict[str, Any]]:
    tools = ordered_tools(monetized_tools())
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tool in tools:
        groups[str(tool["cluster_slug"])].append(tool)
    labels = {slug: label for slug, label, _ in CLUSTERS}
    outputs = {HUB_PATH: render_hub(groups)}
    for slug, members in groups.items():
        outputs[CATEGORY_DIR / f"{slug}.html"] = render_category(slug, labels[slug], members)
    data = {
        "version": 1,
        "updated_at": date.today().isoformat(),
        "products": len(tools),
        "clusters": [
            {"slug": slug, "name": labels[slug], "count": len(members), "offer_ids": [str(item["offer_id"]) for item in members]}
            for slug, members in groups.items()
        ],
        "policy": "All active products with an exact HTTPS affiliate destination and an internal guide are included; ordering is privacy-safe and performance-informed.",
    }
    outputs[OUTPUT_PATH] = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return outputs, data


def build(check: bool = False) -> int:
    outputs, data = desired_outputs()
    stale = [path for path, desired in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != desired]
    if check:
        if stale:
            raise SystemExit("Affiliate growth pages are stale: " + ", ".join(str(path.relative_to(ROOT)) for path in stale[:8]))
        return 0
    for path, desired in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != desired:
            path.write_text(desired, encoding="utf-8")
    print(f"Affiliate growth loop: {data['products']} products across {len(data['clusters'])} buyer categories; {len(stale)} files refreshed.")
    return len(stale)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    build(args.check)
