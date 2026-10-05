#!/usr/bin/env python3
"""Build the public AI software price, plan and evidence tracker."""

from __future__ import annotations

import argparse
import csv
from datetime import date
import io
import json
from pathlib import Path
from typing import Any

try:
    from scripts.affiliate_catalog import COMMERCIAL_CORE_IDS, is_ai_relevant
    from scripts.build_partner_offers import (
        DEFAULT_REGISTRY, ROOT, esc, load_registry, public_offer_data,
        public_offers, shell, validate_registry,
    )
except ModuleNotFoundError:
    from affiliate_catalog import COMMERCIAL_CORE_IDS, is_ai_relevant  # type: ignore
    from build_partner_offers import (  # type: ignore
        DEFAULT_REGISTRY, ROOT, esc, load_registry, public_offer_data,
        public_offers, shell, validate_registry,
    )


OUTPUT_PATH = ROOT / "ai-software-price-tracker.html"
JSON_PATH = ROOT / "data" / "ai-software-price-tracker.json"
CSV_PATH = ROOT / "data" / "ai-software-price-tracker.csv"
CHANGE_PATH = ROOT / "data" / "tool_change_history.json"
ALERT_PATH = ROOT / "data" / "offer_change_alerts.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def tracker_records(registry_path: Path = DEFAULT_REGISTRY) -> list[dict[str, Any]]:
    offers = public_offers(validate_registry(load_registry(registry_path)), date.today())
    positions = {identifier: index for index, identifier in enumerate(COMMERCIAL_CORE_IDS)}
    alerts = load_json(ALERT_PATH).get("alerts", [])
    history = load_json(CHANGE_PATH).get("events", [])
    latest: dict[str, dict[str, Any]] = {}
    for item in [*alerts, *history]:
        identifier = str(item.get("offer_id") or item.get("tool_id") or "")
        if identifier in positions and identifier not in latest:
            latest[identifier] = item
    records: list[dict[str, Any]] = []
    for offer in offers:
        identifier = str(offer["id"])
        if identifier not in positions or not is_ai_relevant(offer):
            continue
        public = public_offer_data(offer)
        change = latest.get(identifier, {})
        records.append({
            "id": identifier,
            "name": offer["name"],
            "category": offer["category"],
            "recorded_price": public["price"],
            "pricing_note": offer["pricing_note"],
            "trial": public["trial"],
            "terms_checked": offer["terms_verified_at"],
            "evidence_sources": len(offer.get("evidence", [])),
            "latest_confirmed_change": change.get("detected_on") or "No recent confirmed change",
            "change_type": change.get("kind") or ("offer or plan" if change else ""),
            "fit": offer["best_for"],
            "limitation": offer["watch_out"],
            "guide_url": f"partner-offers/{offer['slug']}.html",
            "official_url": public["officialUrl"],
        })
    return sorted(records, key=lambda item: positions[item["id"]])


def render_json(records: list[dict[str, Any]]) -> str:
    return json.dumps({
        "version": 1,
        "updated_at": max((str(item["terms_checked"]) for item in records), default=date.today().isoformat()),
        "method": "reviewed-commercial-core-price-plan-tracker",
        "products": records,
        "note": "Recorded labels are evidence snapshots, not a guarantee of today's vendor price. Open the source before buying.",
    }, indent=2, ensure_ascii=False) + "\n"


def render_csv(records: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    fields = ["name", "category", "recorded_price", "pricing_note", "trial", "terms_checked", "evidence_sources", "latest_confirmed_change", "guide_url", "official_url"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def render_page(records: list[dict[str, Any]]) -> str:
    cards = "".join(
        f'''<article class="tracker-card" data-tracker-card data-search="{esc(' '.join((item['name'], item['category'], item['fit'])).casefold())}">
          <div class="tracker-card-head"><div><p class="eyebrow">{esc(item['category'])}</p><h2>{esc(item['name'])}</h2></div><span class="verified-pill">Checked {esc(item['terms_checked'])}</span></div>
          <div class="tracker-price"><strong>{esc(item['recorded_price'])}</strong><span>{esc(item['trial'])}</span></div>
          <p>{esc(item['pricing_note'])}</p>
          <dl><div><dt>Evidence</dt><dd>{item['evidence_sources']} primary source{'s' if item['evidence_sources'] != 1 else ''}</dd></div><div><dt>Latest detected change</dt><dd>{esc(item['latest_confirmed_change'])}</dd></div></dl>
          <p class="fit"><strong>Best fit:</strong> {esc(item['fit'])}</p><p class="limit"><strong>Verify before buying:</strong> {esc(item['limitation'])}</p>
          <div class="tracker-actions"><a class="btn btn-acid" href="{esc(item['guide_url'])}">Open evidence dossier →</a><a class="link-subtle" href="{esc(item['official_url'])}" target="_blank" rel="noopener">Check vendor source ↗</a></div>
        </article>'''
        for item in records
    )
    content = f'''<section class="page-hero"><div class="container"><p class="eyebrow">Updated from reviewed vendor evidence</p><h1>AI software price &amp; plan tracker</h1><p class="lead">Compare the recorded buying facts for {len(records)} commercially relevant AI products. See when each record was checked, what changed, and what still needs verification before you pay.</p><div class="tracker-tools"><input type="search" placeholder="Search product, category or job…" data-tracker-search><a class="btn btn-secondary" href="data/ai-software-price-tracker.csv" download>Download CSV</a></div><p class="disclosure">Prices and plans change. Recorded labels are evidence snapshots, not a promise of today’s vendor price.</p></div></section>
    <section class="container section-tight"><div class="tracker-grid" data-tracker-grid>{cards}</div><p class="empty" data-tracker-empty hidden>No matching product. Try a broader task or category.</p></section>
    <style>.tracker-tools{{display:flex;gap:12px;align-items:center;margin-top:24px}}.tracker-tools input{{flex:1;min-width:0;padding:15px 18px;border:1px solid #d8d5e5;border-radius:14px;font:inherit}}.tracker-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}}.tracker-card{{padding:26px;border:1px solid #e5e2ef;border-radius:24px;background:linear-gradient(145deg,#fff,#faf8ff);box-shadow:0 14px 34px rgba(31,23,55,.07)}}.tracker-card-head,.tracker-price,.tracker-actions{{display:flex;justify-content:space-between;gap:16px;align-items:center}}.tracker-card h2{{margin:.2rem 0;font-size:1.5rem}}.verified-pill{{padding:7px 10px;border-radius:99px;background:#ecfccb;color:#365314;font-size:.76rem;font-weight:850;white-space:nowrap}}.tracker-price{{margin:20px 0;padding:15px;border-radius:16px;background:#f3f0ff}}.tracker-price strong{{font-size:1.18rem}}.tracker-card dl{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.tracker-card dl div{{padding:12px;border-radius:12px;background:#fff;border:1px solid #eeeaf6}}.tracker-card dt{{color:#6b7280;font-size:.75rem}}.tracker-card dd{{margin:3px 0 0;font-weight:800}}.fit,.limit{{color:#4b5563}}.tracker-actions{{margin-top:20px;align-items:flex-start}}@media(max-width:760px){{.tracker-grid{{grid-template-columns:1fr}}.tracker-tools,.tracker-actions{{align-items:stretch;flex-direction:column}}.tracker-card dl{{grid-template-columns:1fr}}}}</style>
    <script>(function(){{const q=document.querySelector('[data-tracker-search]'),cards=[...document.querySelectorAll('[data-tracker-card]')],empty=document.querySelector('[data-tracker-empty]');if(!q)return;q.addEventListener('input',()=>{{const needle=q.value.trim().toLowerCase();let shown=0;cards.forEach(card=>{{const visible=!needle||card.dataset.search.includes(needle);card.hidden=!visible;if(visible)shown++}});empty.hidden=shown>0}})}})();</script>'''
    return shell(
        title="AI Software Price & Plan Tracker | artificial.one",
        description="Track recorded AI software prices, plan notes, evidence dates and confirmed vendor changes before you choose a product.",
        canonical_path="ai-software-price-tracker.html",
        content=content,
        structured_data={"@context": "https://schema.org", "@type": "Dataset", "name": "AI software price and plan tracker", "distribution": {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": "https://www.artificial.one/data/ai-software-price-tracker.csv"}},
    )


def write_if_changed(path: Path, value: str) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current == value:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return True


def build(check: bool = False) -> int:
    records = tracker_records()
    expected = {OUTPUT_PATH: render_page(records), JSON_PATH: render_json(records), CSV_PATH: render_csv(records)}
    stale = [path for path, value in expected.items() if not path.exists() or path.read_text(encoding="utf-8") != value]
    if check:
        if stale:
            print("Price tracker is stale: " + ", ".join(path.name for path in stale))
            return 1
        print(f"Price tracker is current ({len(records)} evidence dossiers).")
        return 0
    for path, value in expected.items():
        write_if_changed(path, value)
    print(f"Built price and plan tracker for {len(records)} evidence dossiers.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return build(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
