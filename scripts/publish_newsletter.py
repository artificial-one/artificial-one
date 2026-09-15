#!/usr/bin/env python3
"""Build a weekly AI-tools edition and optionally send it through beehiiv."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "ai_news.json"
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
ALERTS_PATH = ROOT / "data" / "offer_change_alerts.json"
OUTPUT_PATH = ROOT / "newsletter" / "latest.html"
BEEHIIV_API = "https://api.beehiiv.com/v2"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def ranked_offers(limit: int = 3) -> list[dict[str, Any]]:
    offers = [item for item in load(OFFERS_PATH).get("offers", []) if item.get("status") == "published"]
    ranking = [str(item) for item in load(STRATEGY_PATH).get("ranking", [])]
    position = {offer_id: index for index, offer_id in enumerate(ranking)}
    return sorted(offers, key=lambda item: (position.get(str(item["id"]), len(position)), str(item["name"])))[:limit]


def build_edition(today: date | None = None) -> tuple[str, str, str]:
    today = today or date.today()
    news = [item for item in load(NEWS_PATH).get("items", []) if isinstance(item, dict)][:5]
    offers = ranked_offers(3)
    try:
        alerts = [item for item in load(ALERTS_PATH).get("alerts", []) if isinstance(item, dict)][:3]
    except (OSError, json.JSONDecodeError, ValueError):
        alerts = []
    title = f"AI tools and developments worth your time — {today.isoformat()}"
    news_html = "".join(
        f'<li style="margin:0 0 12px"><a href="{escape(str(item["url"]), quote=True)}">{escape(str(item["title"]))}</a> <span style="color:#667085">— {escape(str(item.get("source") or "Source"))}</span></li>'
        for item in news
    )
    offer_html = "".join(
        f'''<div style="border:1px solid #e4e7ec;border-radius:12px;padding:18px;margin:14px 0">
          <h3 style="margin:0 0 8px">{escape(str(offer['name']))}</h3>
          <p>{escape(str(offer['summary']))}</p><p><strong>Best for:</strong> {escape(str(offer['best_for']))}</p>
          <p><a href="https://artificial.one/partner-offers/{escape(str(offer['slug']), quote=True)}.html?utm_source=newsletter&amp;utm_medium=email&amp;utm_campaign=weekly-tools">Review pricing and fit →</a></p>
        </div>'''
        for offer in offers
    )
    alert_html = "".join(
        f'<li style="margin:0 0 10px">{escape(str(item.get("message") or "Vendor information changed."))} <a href="https://artificial.one/offer-updates.html?utm_source=newsletter&amp;utm_medium=email&amp;utm_campaign=weekly-tools">See verified update →</a></li>'
        for item in alerts
    )
    alert_section = f"<h2>Confirmed tool changes</h2><ul>{alert_html}</ul>" if alert_html else ""
    body = f'''<p>Here is this week’s compact briefing: important AI developments plus tools that solve concrete work problems.</p>
      <h2>What changed in AI</h2><ul>{news_html}</ul>
      <p><a href="https://artificial.one/news.html?utm_source=newsletter&amp;utm_medium=email&amp;utm_campaign=weekly-tools">Browse the continuously updated AI news feed →</a></p>
      <p><a href="https://artificial.one/ai-stack-builder.html?utm_source=newsletter&amp;utm_medium=email&amp;utm_campaign=weekly-tools"><strong>Build a personalized three-tool AI shortlist →</strong></a></p>
      {alert_section}<h2>Three tools to evaluate</h2>{offer_html}
      <p style="font-size:12px;color:#667085">Some tool links are affiliate links. artificial.one may earn a commission at no extra cost to you. Recommendations are not guaranteed endorsements.</p>'''
    digest = sha256((title + body).encode("utf-8")).hexdigest()
    return title, body, digest


def render_archive(title: str, body: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} | artificial.one</title><meta name="description" content="The latest artificial.one AI news and tool briefing."><link rel="canonical" href="https://artificial.one/newsletter/latest.html"><meta name="affiliate-event-endpoint" content="/api/affiliate-event"><style>body{{font-family:Arial,sans-serif;color:#101828;max-width:760px;margin:auto;padding:30px;line-height:1.6}}a{{color:#4338ca}}header,footer{{padding:20px 0;border-bottom:1px solid #e4e7ec}}footer{{border-top:1px solid #e4e7ec;border-bottom:0;margin-top:30px}}</style></head><body><header><a href="../index.html">artificial.one</a></header><main><h1>{escape(title)}</h1>{body}</main><footer><a href="../news.html">AI news</a> · <a href="../ai-tool-finder.html">AI tool finder</a></footer><script src="../assets/affiliate-tracking.js" defer></script></body></html>'''


def beehiiv_publish(api_key: str, publication_id: str, title: str, body: str, send: bool) -> str:
    payload = json.dumps({
        "title": title,
        "body_content": body,
        "status": "confirmed" if send else "draft",
        "custom_link_tracking_enabled": True,
        "social_share": "none",
    }).encode("utf-8")
    request = Request(
        f"{BEEHIIV_API}/publications/{publication_id}/posts",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=45) as response:
        result = json.load(response)
    return str(result.get("data", {}).get("id") or "created")


def run(state_path: Path, force: bool = False) -> str:
    title, body, digest = build_edition()
    week_key = f"{date.today().isocalendar().year}-W{date.today().isocalendar().week:02d}"
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(render_archive(title, body), encoding="utf-8")
    try:
        state = load(state_path)
    except (OSError, json.JSONDecodeError, ValueError):
        state = {"version": 1}
    if state.get("last_week") == week_key and not force:
        return "archive refreshed; newsletter already processed"
    api_key = (os.environ.get("BEEHIIV_API_KEY") or "").strip()
    publication_id = (os.environ.get("BEEHIIV_PUBLICATION_ID") or "").strip()
    enabled = (os.environ.get("BEEHIIV_SEND_ENABLED") or "").casefold() == "true"
    if not api_key or not publication_id:
        return "archive refreshed; beehiiv is not connected"
    post_id = beehiiv_publish(api_key, publication_id, title, body, enabled)
    state.update({"version": 1, "last_week": week_key, "last_digest": digest, "last_post_id": post_id, "sent": enabled})
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return f"beehiiv {'sent' if enabled else 'drafted'} {post_id}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / ".revenue-acceleration" / "newsletter.json")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(run(args.state, args.force))
