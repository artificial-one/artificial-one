#!/usr/bin/env python3
"""Monitor first-party offer sources and publish confirmed generic change alerts."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from hashlib import sha256
from html import unescape
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from scripts.build_partner_offers import esc, shell
except ModuleNotFoundError:
    from build_partner_offers import esc, shell  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
ALERTS_PATH = ROOT / "data" / "offer_change_alerts.json"
OUTPUT_PATH = ROOT / "offer-updates.html"
SIGNAL_RE = re.compile(r"\b(price|pricing|plan|trial|free|month|annual|year|credit|limit|subscription|availability)\b", re.I)


def load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default)
    return value if isinstance(value, dict) else dict(default)


def public_offers() -> list[dict[str, Any]]:
    return [item for item in load(OFFERS_PATH, {"offers": []}).get("offers", []) if isinstance(item, dict) and item.get("status") == "published"]


def source_for(offer: dict[str, Any]) -> str:
    evidence = [item for item in offer.get("evidence", []) if isinstance(item, dict)]
    product = next((item for item in evidence if "product" in str(item.get("label") or "").casefold()), None)
    selected = product or (evidence[0] if evidence else {})
    value = str(selected.get("url") or "")
    return value if urlparse(value).scheme == "https" else ""


def extract_signal(raw: str) -> str:
    raw = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", raw, flags=re.I | re.S)
    title = re.findall(r"<(?:title|h1|h2)[^>]*>(.*?)</(?:title|h1|h2)>", raw, re.I | re.S)
    meta = re.findall(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)', raw, re.I)
    visible = re.sub(r"<[^>]+>", "\n", raw)
    lines = [re.sub(r"\s+", " ", unescape(item)).strip() for item in [*title, *meta, *visible.splitlines()]]
    selected: list[str] = []
    for line in lines:
        if 8 <= len(line) <= 300 and (line in lines[: len(title) + len(meta)] or SIGNAL_RE.search(line)) and line not in selected:
            selected.append(line)
        if len(selected) >= 40:
            break
    return "\n".join(selected)


def fetch_offer(offer: dict[str, Any]) -> tuple[str, str, str] | None:
    url = source_for(offer)
    if not url:
        return None
    request = Request(url, headers={"User-Agent": "artificial.one offer monitor/1.0 (+https://artificial.one/about.html)", "Accept": "text/html,application/xhtml+xml"})
    try:
        with urlopen(request, timeout=20) as response:
            content_type = str(response.headers.get("content-type") or "")
            if response.status >= 400 or "html" not in content_type:
                return None
            raw = response.read(1_500_000).decode("utf-8", errors="ignore")
    except Exception:
        return None
    signal = extract_signal(raw)
    if len(signal) < 20:
        return None
    return str(offer["id"]), url, sha256(signal.encode()).hexdigest()


def observe(offers: list[dict[str, Any]], state: dict[str, Any], today: date) -> tuple[list[dict[str, str]], int]:
    records = state.setdefault("offers", {})
    alerts: list[dict[str, str]] = []
    successful = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch_offer, offer) for offer in offers]
        for future in as_completed(futures):
            result = future.result()
            if not result:
                continue
            successful += 1
            offer_id, source_url, fingerprint = result
            record = records.setdefault(offer_id, {})
            if not record.get("stable_hash"):
                record.update({"stable_hash": fingerprint, "source_url": source_url, "checked_on": today.isoformat()})
                continue
            if fingerprint == record.get("stable_hash"):
                record.pop("pending_hash", None)
                record.pop("pending_seen", None)
            elif fingerprint == record.get("pending_hash"):
                record["pending_seen"] = int(record.get("pending_seen") or 1) + 1
                if record["pending_seen"] >= 2:
                    record.update({"stable_hash": fingerprint, "changed_on": today.isoformat()})
                    record.pop("pending_hash", None)
                    record.pop("pending_seen", None)
                    alerts.append({"offer_id": offer_id, "detected_on": today.isoformat(), "message": "The vendor’s product, pricing, plan or availability information changed. Recheck the current details before subscribing.", "source_url": source_url})
            else:
                record.update({"pending_hash": fingerprint, "pending_seen": 1})
            record["checked_on"] = today.isoformat()
    state["updated_at"] = today.isoformat()
    return alerts, successful


def render_updates(offers: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> str:
    by_id = {str(item["id"]): item for item in offers}
    cards: list[str] = []
    for alert in alerts:
        offer = by_id.get(str(alert.get("offer_id") or ""))
        if not offer:
            continue
        cards.append(f'''<article class="rounded-2xl border border-amber-200 bg-amber-50 p-6"><p class="text-xs font-bold uppercase tracking-widest text-amber-700">Change detected {esc(alert.get('detected_on'))}</p><h2 class="mt-2 text-2xl font-black">{esc(offer['name'])}</h2><p class="mt-3 text-slate-700">{esc(alert.get('message'))}</p><div class="mt-5 flex gap-4"><a class="font-bold text-indigo-700" href="partner-offers/{esc(offer['slug'])}.html">Review fit</a><a class="font-bold text-slate-700" href="{esc(alert.get('source_url'))}" rel="noopener" target="_blank">Verify with vendor</a></div></article>''')
    listing = "".join(cards) if cards else '<div class="rounded-2xl border border-slate-200 bg-white p-8"><h2 class="text-2xl font-black">No confirmed changes yet</h2><p class="mt-3 text-slate-600">The monitor requires the same change on two consecutive checks before publishing an alert.</p></div>'
    content = f'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Vendor-source monitor</p><h1 class="mt-4 text-4xl font-black md:text-6xl">AI tool pricing and plan updates</h1><p class="mt-5 max-w-3xl text-lg text-slate-600">Confirmed changes from first-party product pages. Always verify the live vendor page before purchasing.</p></div></section><section class="mx-auto grid max-w-5xl gap-6 px-5 py-10 md:grid-cols-2">{listing}</section>'''
    return shell(title="AI Tool Pricing and Plan Updates | artificial.one", description="Monitor confirmed pricing, plan and availability changes from AI software vendors.", canonical_path="offer-updates.html", content=content, social_image="https://artificial.one/images/social-cards/offer-updates.jpg", social_image_alt="AI tool pricing and plan change monitor — free decision tool from Artificial.One", structured_data={"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI tool pricing and plan updates"})


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def run(state_path: Path, cached: bool = False, check: bool = False) -> int:
    offers = public_offers()
    public = load(ALERTS_PATH, {"version": 1, "alerts": [], "method": "two-observation-vendor-source-monitor"})
    if not cached and not check:
        state = load(state_path, {"version": 1, "offers": {}})
        new_alerts, successful = observe(offers, state, date.today())
        if new_alerts:
            public["alerts"] = (new_alerts + list(public.get("alerts", [])))[:30]
            public["updated_at"] = date.today().isoformat()
        write_json(state_path, state)
        write_json(ALERTS_PATH, public)
    else:
        successful = 0
    expected = render_updates(offers, list(public.get("alerts", [])))
    stale = not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != expected
    if check:
        if stale:
            print("Offer update page is stale.", file=sys.stderr)
            return 1
        print("Offer update page is current.")
        return 0
    OUTPUT_PATH.write_text(expected, encoding="utf-8")
    print(f"Offer monitor checked {successful} vendor source(s); {len(public.get('alerts', []))} confirmed alert(s) published.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / ".offer-monitor" / "private-state.json")
    parser.add_argument("--cached", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.state, args.cached, args.check))
