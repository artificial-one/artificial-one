#!/usr/bin/env python3
"""Generate a commercial RSS feed and optionally distribute one useful post."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
FEED_PATH = ROOT / "feed.xml"
QUEUE_PATH = ROOT / "data" / "distribution_queue.json"
FEED_URL = "https://artificial.one/feed.xml"
WEBSUB_HUB = "https://pubsubhubbub.appspot.com/"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def queue() -> list[dict[str, str]]:
    offers = [item for item in load(OFFERS_PATH).get("offers", []) if item.get("status") == "published"]
    ranking = [str(item) for item in load(STRATEGY_PATH).get("ranking", [])]
    position = {offer_id: index for index, offer_id in enumerate(ranking)}
    offers.sort(key=lambda item: (position.get(str(item["id"]), len(position)), str(item["name"])))
    resources = (
        ("ai-stack-builder", "Build a personalized AI software shortlist", "ai-stack-builder.html", "Answer a few workflow questions and get a three-tool shortlist from the verified artificial.one catalog."),
        ("ai-software-roi", "Free AI software ROI calculator", "calculators/ai-software-roi-calculator.html", "Estimate monthly time value, net return and break-even before buying another AI subscription."),
        ("pdf-workflow-cost", "Free PDF workflow cost calculator", "calculators/pdf-workflow-cost-calculator.html", "Estimate what repetitive PDF editing, signing and document handling costs each month."),
        ("voice-production-cost", "Free AI voice production cost calculator", "calculators/voice-production-cost-calculator.html", "Compare an existing voice-production workflow with an AI-assisted scenario."),
        ("landing-page-roi", "Free landing page ROI calculator", "calculators/landing-page-roi-calculator.html", "Model how a conversion-rate change could affect monthly value before paying for a landing-page tool."),
        ("offer-updates", "AI tool pricing and plan change monitor", "offer-updates.html", "Follow confirmed changes from first-party software vendor pages and verify the current details before buying."),
    )
    result = []
    for resource_id, title, path, copy in resources:
        url = f"https://artificial.one/{path}?utm_source=distribution&utm_medium=social&utm_campaign=free-tools"
        result.append({"id": resource_id, "title": title, "url": url, "text": f"{copy} {url} #AITools"[:295]})
    for offer in offers:
        url = f"https://artificial.one/partner-offers/{offer['slug']}.html?utm_source=distribution&utm_medium=social&utm_campaign=tool-guides"
        text = f"Who is {offer['name']} best for? {offer['best_for']} Compare its use cases, limitations and current pricing notes: {url} #AITools"
        result.append({"id": str(offer["id"]), "title": f"{offer['name']} review and pricing guide", "url": url, "text": text[:295]})
    return result


def write_public_outputs(items: list[dict[str, str]]) -> None:
    QUEUE_PATH.write_text(json.dumps({"version": 1, "items": items}, indent=2) + "\n", encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    rows = "".join(
        f"<item><title>{escape(item['title'])}</title><link>{escape(item['url'])}</link><guid>{escape(item['url'])}</guid><description>{escape(item['text'])}</description><pubDate>{now}</pubDate></item>"
        for item in items
    )
    FEED_PATH.write_text(f'''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>artificial.one AI tool guides</title><link>https://artificial.one/</link><atom:link href="{FEED_URL}" rel="self" type="application/rss+xml"/><atom:link href="{WEBSUB_HUB}" rel="hub"/><description>Independent AI tool comparisons, use cases and current partner offers.</description>{rows}</channel></rss>\n''', encoding="utf-8")


def ping_websub() -> str:
    payload = urlencode({"hub.mode": "publish", "hub.url": FEED_URL}).encode("utf-8")
    request = Request(WEBSUB_HUB, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            return f"WebSub notified (HTTP {response.status})"
    except Exception as exc:
        return f"WebSub notification deferred ({type(exc).__name__})"


def post_bluesky(handle: str, password: str, text: str) -> None:
    login = Request("https://bsky.social/xrpc/com.atproto.server.createSession", data=json.dumps({"identifier": handle, "password": password}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(login, timeout=30) as response:
        session = json.load(response)
    payload = {"repo": session["did"], "collection": "app.bsky.feed.post", "record": {"$type": "app.bsky.feed.post", "text": text, "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}}
    request = Request("https://bsky.social/xrpc/com.atproto.repo.createRecord", data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {session['accessJwt']}", "Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30):
        pass


def post_webhook(url: str, item: dict[str, str]) -> None:
    request = Request(url, data=json.dumps({"source": "artificial.one", **item}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30):
        pass


def channel_item(item: dict[str, str], source: str) -> dict[str, str]:
    attributed_url = item["url"].replace("utm_source=distribution", f"utm_source={source}")
    return {
        **item,
        "url": attributed_url,
        "text": item["text"].replace(item["url"], attributed_url),
    }


def run(state_path: Path) -> str:
    items = queue()
    write_public_outputs(items)
    websub_status = ping_websub()
    flag = (os.environ.get("DISTRIBUTION_SEND_ENABLED") or "").casefold()
    handle = (os.environ.get("BLUESKY_HANDLE") or "").strip()
    password = (os.environ.get("BLUESKY_APP_PASSWORD") or "").strip()
    webhook = (os.environ.get("DISTRIBUTION_WEBHOOK_URL") or "").strip()
    connected = bool((handle and password) or webhook)
    if not items or flag == "false" or (flag != "true" and not connected):
        return f"RSS and distribution queue refreshed; {websub_status}; social posting is waiting for a connected channel"
    try:
        state = load(state_path)
    except (OSError, json.JSONDecodeError):
        state = {"version": 1, "sent": []}
    sent = list(state.get("sent", []))
    item = next((candidate for candidate in items if sha256(candidate["text"].encode()).hexdigest() not in sent), None)
    if not item:
        return f"RSS refreshed; {websub_status}; every queued guide was already distributed"
    delivered = 0
    if handle and password:
        post_bluesky(handle, password, channel_item(item, "bluesky")["text"])
        delivered += 1
    if webhook:
        post_webhook(webhook, channel_item(item, "syndication"))
        delivered += 1
    if not delivered:
        return f"RSS refreshed; {websub_status}; no external distribution account is connected"
    sent.append(sha256(item["text"].encode()).hexdigest())
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"version": 1, "sent": sent[-200:]}, indent=2) + "\n", encoding="utf-8")
    return f"{websub_status}; distributed one guide through {delivered} connected channel(s)"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / ".revenue-acceleration" / "distribution.json")
    args = parser.parse_args()
    print(run(args.state))
