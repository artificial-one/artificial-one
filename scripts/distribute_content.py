#!/usr/bin/env python3
"""Generate a commercial RSS feed and optionally distribute one useful post."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape
import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
NEWS_PATH = ROOT / "data" / "ai_news.json"
OFFER_ALERTS_PATH = ROOT / "data" / "offer_change_alerts.json"
FEED_PATH = ROOT / "feed.xml"
QUEUE_PATH = ROOT / "data" / "distribution_queue.json"
FEED_URL = "https://artificial.one/feed.xml"
WEBSUB_HUB = "https://pubsubhubbub.appspot.com/"
SOCIAL_IMAGE_DIR = ROOT / "images" / "social-cards"
PROFILE_AVATAR = ROOT / "images" / "social" / "bluesky-avatar.png"
PROFILE_BANNER = ROOT / "images" / "social" / "bluesky-banner.jpg"
PROFILE_DISPLAY_NAME = "Artificial.One"
PROFILE_DESCRIPTION = (
    "Independent AI tool comparisons, practical calculators and verified partner offers. "
    "Find the right tools before you buy: artificial.one"
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def published_offers() -> list[dict[str, Any]]:
    offers = [item for item in load(OFFERS_PATH).get("offers", []) if item.get("status") == "published"]
    ranking = [str(item) for item in load(STRATEGY_PATH).get("ranking", [])]
    position = {offer_id: index for index, offer_id in enumerate(ranking)}
    offers.sort(key=lambda item: (position.get(str(item["id"]), len(position)), str(item["name"])))
    return offers


RESOURCES = (
        ("ai-stack-builder", "Build a personalized AI software shortlist", "ai-stack-builder.html", "Answer a few workflow questions and get a three-tool shortlist from the verified artificial.one catalog."),
        ("ai-software-roi", "Free AI software ROI calculator", "calculators/ai-software-roi-calculator.html", "Estimate monthly time value, net return and break-even before buying another AI subscription."),
        ("pdf-workflow-cost", "Free PDF workflow cost calculator", "calculators/pdf-workflow-cost-calculator.html", "Estimate what repetitive PDF editing, signing and document handling costs each month."),
        ("voice-production-cost", "Free AI voice production cost calculator", "calculators/voice-production-cost-calculator.html", "Compare an existing voice-production workflow with an AI-assisted scenario."),
        ("landing-page-roi", "Free landing page ROI calculator", "calculators/landing-page-roi-calculator.html", "Model how a conversion-rate change could affect monthly value before paying for a landing-page tool."),
        ("offer-updates", "AI tool pricing and plan change monitor", "offer-updates.html", "Follow confirmed changes from first-party software vendor pages and verify the current details before buying."),
)


def attributed_url(path: str, campaign: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"https://artificial.one/{path}{separator}utm_source=distribution&utm_medium=social&utm_campaign={campaign}"


def daily_editorial(as_of: date, offers: list[dict[str, Any]]) -> dict[str, str]:
    """Create one deterministic, fresh editorial post for the supplied day.

    The seven-day rotation is deliberately data-driven rather than generative-AI
    dependent, so it continues in GitHub Actions without a laptop or paid model key.
    """
    day = as_of.weekday()
    week = as_of.toordinal() // 7
    # Avoid platform-specific strftime flags for removing a leading zero.
    edition = f"{as_of.strftime('%b')} {as_of.day}"
    item_id = f"daily-{as_of.isoformat()}"

    if day == 0:
        resource_id, title, path, description = RESOURCES[week % len(RESOURCES)]
        text = f"Monday tool pick · {edition}\n\n{description}\n\nTry the free tool ↓\n#AITools #Productivity"
        campaign, kind = "editorial-free-tools", "free-tool"
    elif day == 1:
        news = list(load(NEWS_PATH).get("items", []))
        story = news[0] if news else {}
        headline = str(story.get("title") or "This week's important AI developments")
        source = str(story.get("source") or "our monitored AI sources")
        category = str(story.get("category") or "AI news")
        title = "AI news worth watching"
        description = f"{headline} — a {category.casefold()} report from {source}."
        path = "news.html"
        text = f"AI news watch · {edition}\n\n{headline}\n\nSee the source and related guides in today's briefing ↓\n#AI #AITools"
        campaign, kind = "editorial-ai-news", "ai-news"
    elif day in (2, 5):
        offer = offers[(week * 2 + (1 if day == 5 else 0)) % len(offers)]
        use_cases = list(offer.get("use_cases") or [])
        use_case = str(use_cases[week % len(use_cases)]) if use_cases else str(offer.get("best_for", "a practical AI workflow"))
        title = f"One practical way to use {offer['name']}"
        description = use_case.rstrip(".") + "."
        path = f"partner-offers/{offer['slug']}.html"
        label = "Weekend workflow" if day == 5 else "Workflow Wednesday"
        text = f"{label} · {edition}\n\n{description}\n\nCheck the fit, limitations and current pricing before you buy ↓\n#AITools #Productivity"
        campaign, kind = "editorial-workflows", "partner-guide"
    elif day == 3:
        offer = offers[(week + 5) % len(offers)]
        title = f"Before you buy {offer['name']}"
        description = str(offer.get("watch_out") or offer.get("pricing_note") or "Check current limits, pricing and workflow fit before subscribing.")
        path = f"partner-offers/{offer['slug']}.html"
        text = f"Buyer checklist · {edition}\n\n{description}\n\nRead the independent fit guide ↓\n#AITools"
        campaign, kind = "editorial-buyer-guides", "partner-guide"
    elif day == 4:
        alerts = list(load(OFFER_ALERTS_PATH).get("alerts", []))
        if alerts:
            alert = alerts[week % len(alerts)]
            name = str(alert.get("name") or alert.get("offer_name") or "an AI tool")
            detail = str(alert.get("summary") or alert.get("message") or "A monitored vendor page changed. Verify the current details before buying.")
            title, description, path = f"Offer update: {name}", detail, "offer-updates.html"
        else:
            offer = offers[(week + 11) % len(offers)]
            title = f"Current pricing check: {offer['name']}"
            description = str(offer.get("pricing_note") or "Verify the current plan and limits before subscribing.")
            path = f"partner-offers/{offer['slug']}.html"
        text = f"Friday offer check · {edition}\n\n{description}\n\nVerify the latest details before you buy ↓\n#AITools #SaaS"
        campaign, kind = "editorial-offer-updates", "offer-update"
    else:
        news = list(load(NEWS_PATH).get("items", []))
        categories = []
        for story in news:
            category = str(story.get("category") or "AI news")
            if category not in categories:
                categories.append(category)
            if len(categories) == 3:
                break
        topics = ", ".join(categories) if categories else "AI tools, models and industry changes"
        title = "Your weekly independent AI briefing"
        description = f"The latest on {topics}, with practical tool guides for the week ahead."
        path = "news.html"
        text = f"Sunday AI briefing · {edition}\n\n{description}\n\nCatch up in a few minutes ↓\n#AI #AITools"
        campaign, kind = "weekly-roundup", "ai-news"

    return {
        "id": item_id,
        "image_key": "daily-editorial",
        "daily": "true",
        "kind": kind,
        "title": title,
        "description": description,
        "page_path": path,
        "image": "https://artificial.one/images/social-cards/daily-editorial.jpg",
        "image_alt": f"{title} — daily editorial from Artificial.One",
        "url": f"{attributed_url(path, campaign)}&utm_content={as_of.isoformat()}",
        "text": text[:295],
    }


def queue(as_of: date | None = None) -> list[dict[str, str]]:
    as_of = as_of or datetime.now(timezone.utc).date()
    offers = published_offers()
    result = []
    if offers:
        result.append(daily_editorial(as_of, offers))
    for index, (resource_id, title, path, copy) in enumerate(RESOURCES):
        url = attributed_url(path, "free-tools")
        hooks = (
            "Stop guessing which AI tools fit your workflow.",
            "Can this free calculator save you from a bad software purchase?",
            "A better AI-tool decision starts with the numbers.",
        )
        text = f"{hooks[index % len(hooks)]}\n\n{copy}\n\nFree tool ↓\n#AITools #Productivity"
        result.append({
            "id": resource_id,
            "kind": "free-tool",
            "title": title,
            "description": copy,
            "page_path": path,
            "image": f"https://artificial.one/images/social-cards/{resource_id}.jpg",
            "image_alt": f"{title} — free decision tool from Artificial.One",
            "url": url,
            "text": text[:295],
        })
    for index, offer in enumerate(offers):
        url = attributed_url(f"partner-offers/{offer['slug']}.html", "tool-guides")
        intros = (
            f"Is {offer['name']} right for your workflow?",
            f"Before paying for {offer['name']}, check the fit.",
            f"Who actually benefits from {offer['name']}?",
        )
        description = f"Best for: {offer['best_for']}"
        text = (
            f"{intros[index % len(intros)]}\n\n"
            "See practical use cases, limitations and current pricing notes before you buy.\n\n"
            "Independent guide ↓\n#AITools"
        )
        result.append({
            "id": str(offer["id"]),
            "kind": "partner-guide",
            "title": f"{offer['name']} review and pricing guide",
            "description": description,
            "page_path": f"partner-offers/{offer['slug']}.html",
            "image": f"https://artificial.one/images/social-cards/{offer['id']}.jpg",
            "image_alt": f"Independent {offer['name']} fit, use-case and pricing guide from Artificial.One",
            "url": url,
            "text": text[:295],
        })
    return result


def write_public_outputs(items: list[dict[str, str]]) -> None:
    QUEUE_PATH.write_text(json.dumps({"version": 1, "items": items}, indent=2) + "\n", encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    rows = "".join(
        f"<item><title>{escape(item['title'])}</title><link>{escape(item['url'])}</link><guid>{escape(item['url'])}</guid><description>{escape(item['text'])}</description><media:content url=\"{escape(item['image'])}\" medium=\"image\"/><media:title>{escape(item['image_alt'])}</media:title><pubDate>{now}</pubDate></item>"
        for item in items
    )
    FEED_PATH.write_text(f'''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>artificial.one AI tool guides</title><link>https://artificial.one/</link><atom:link href="{FEED_URL}" rel="self" type="application/rss+xml"/><atom:link href="{WEBSUB_HUB}" rel="hub"/><description>Independent AI tool comparisons, use cases and current partner offers.</description>{rows}</channel></rss>\n''', encoding="utf-8")


def ping_websub() -> str:
    payload = urlencode({"hub.mode": "publish", "hub.url": FEED_URL}).encode("utf-8")
    request = Request(WEBSUB_HUB, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            return f"WebSub notified (HTTP {response.status})"
    except Exception as exc:
        return f"WebSub notification deferred ({type(exc).__name__})"


def request_json(url: str, *, data: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = Request(url, data=payload, headers=request_headers, method="POST" if data is not None else "GET")
    with urlopen(request, timeout=30) as response:
        value = json.load(response)
    return value if isinstance(value, dict) else {}


def upload_bluesky_blob(access_token: str, path: Path) -> dict[str, Any]:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    request = Request(
        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
        data=path.read_bytes(),
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": mime_type},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)["blob"]


def ensure_bluesky_profile(session: dict[str, Any]) -> bool:
    query = urlencode({"repo": session["did"], "collection": "app.bsky.actor.profile", "rkey": "self"})
    try:
        current = request_json(
            f"https://bsky.social/xrpc/com.atproto.repo.getRecord?{query}",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
        )
        value = dict(current.get("value") or {})
        current_cid = current.get("cid")
    except HTTPError as exc:
        if exc.code not in (400, 404):
            raise
        value, current_cid = {}, None

    value.setdefault("$type", "app.bsky.actor.profile")
    changed = False
    branding_missing = not value.get("avatar") or not value.get("banner")
    if branding_missing and value.get("displayName") != PROFILE_DISPLAY_NAME:
        value["displayName"] = PROFILE_DISPLAY_NAME
        changed = True
    if branding_missing and value.get("description") != PROFILE_DESCRIPTION:
        value["description"] = PROFILE_DESCRIPTION
        changed = True
    if not value.get("avatar") and PROFILE_AVATAR.exists():
        value["avatar"] = upload_bluesky_blob(session["accessJwt"], PROFILE_AVATAR)
        changed = True
    if not value.get("banner") and PROFILE_BANNER.exists():
        value["banner"] = upload_bluesky_blob(session["accessJwt"], PROFILE_BANNER)
        changed = True
    if not changed:
        return False

    payload: dict[str, Any] = {
        "repo": session["did"],
        "collection": "app.bsky.actor.profile",
        "rkey": "self",
        "record": value,
    }
    if current_cid:
        payload["swapRecord"] = current_cid
    request_json(
        "https://bsky.social/xrpc/com.atproto.repo.putRecord",
        data=payload,
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
    )
    return True


def bluesky_record(item: dict[str, str], thumbnail: dict[str, Any]) -> dict[str, Any]:
    return {
        "$type": "app.bsky.feed.post",
        "text": item["text"],
        "langs": ["en"],
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {
            "$type": "app.bsky.embed.external",
            "external": {
                "uri": item["url"],
                "title": item["title"],
                "description": item["description"],
                "thumb": thumbnail,
            },
        },
    }


def post_bluesky(handle: str, password: str, item: dict[str, str]) -> str:
    login = Request("https://bsky.social/xrpc/com.atproto.server.createSession", data=json.dumps({"identifier": handle, "password": password}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(login, timeout=30) as response:
        session = json.load(response)
    profile_branded = ensure_bluesky_profile(session)
    image_path = ROOT / item["image"].split("https://artificial.one/", 1)[-1]
    if not image_path.exists():
        raise FileNotFoundError(f"Social card is missing: {image_path}")
    thumbnail = upload_bluesky_blob(session["accessJwt"], image_path)
    record = bluesky_record(item, thumbnail)
    payload = {"repo": session["did"], "collection": "app.bsky.feed.post", "record": record}
    request = Request("https://bsky.social/xrpc/com.atproto.repo.createRecord", data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {session['accessJwt']}", "Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    return f"visual card posted ({result.get('uri', 'record created')}); profile branded={str(profile_branded).lower()}"


def delete_bluesky_post(handle: str, password: str, rkey: str) -> str:
    session = request_json(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        data={"identifier": handle, "password": password},
    )
    try:
        request_json(
            "https://bsky.social/xrpc/com.atproto.repo.deleteRecord",
            data={
                "repo": session["did"],
                "collection": "app.bsky.feed.post",
                "rkey": rkey,
            },
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
        )
    except HTTPError as exc:
        if exc.code not in (400, 404):
            raise
        return f"duplicate post {rkey} was already absent"
    return f"duplicate post {rkey} deleted"


def post_webhook(url: str, item: dict[str, str]) -> None:
    request = Request(url, data=json.dumps({"source": "artificial.one", **item}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30):
        pass


def channel_item(item: dict[str, str], source: str) -> dict[str, str]:
    attributed_url = item["url"].replace("utm_source=distribution", f"utm_source={source}")
    return {
        **item,
        "url": attributed_url,
    }


def run(state_path: Path, as_of: date | None = None) -> str:
    items = queue(as_of)
    write_public_outputs(items)
    websub_status = ping_websub()
    flag = (os.environ.get("DISTRIBUTION_SEND_ENABLED") or "").casefold()
    handle = (os.environ.get("BLUESKY_HANDLE") or "").strip()
    password = (os.environ.get("BLUESKY_APP_PASSWORD") or "").strip()
    webhook = (os.environ.get("DISTRIBUTION_WEBHOOK_URL") or "").strip()
    delete_rkey = (os.environ.get("BLUESKY_DELETE_RKEY") or "").strip()
    mark_sent_id = (os.environ.get("BLUESKY_MARK_SENT_ID") or "").strip()
    connected = bool((handle and password) or webhook)
    try:
        state = load(state_path)
    except (OSError, json.JSONDecodeError):
        state = {"version": 1, "sent": []}
    sent = list(state.get("sent", []))
    sent_ids = list(state.get("sent_ids", []))
    maintenance_notes: list[str] = []
    state_changed = False
    if delete_rkey and handle and password:
        maintenance_notes.append(delete_bluesky_post(handle, password, delete_rkey))
    if mark_sent_id:
        marked_item = next((candidate for candidate in items if candidate["id"] == mark_sent_id), None)
        if marked_item:
            digest = sha256(marked_item["text"].encode()).hexdigest()
            if digest not in sent:
                sent.append(digest)
                state_changed = True
                maintenance_notes.append(f"marked {mark_sent_id} as distributed")
    if state_changed:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"version": 2, "sent": sent[-400:], "sent_ids": sent_ids[-400:]}, indent=2) + "\n", encoding="utf-8")
    maintenance = f"; {'; '.join(maintenance_notes)}" if maintenance_notes else ""
    if not items or flag == "false" or (flag != "true" and not connected):
        return f"RSS and distribution queue refreshed; {websub_status}; social posting is waiting for a connected channel{maintenance}"
    # Only today's editorial item is eligible for automatic publishing. The rest
    # remain in RSS as discovery inventory, preventing deployment or retries from
    # draining several posts on the same day.
    item = next((candidate for candidate in items if candidate.get("daily") == "true"), None)
    if item and (item["id"] in sent_ids or sha256(item["text"].encode()).hexdigest() in sent):
        item = None
    if not item:
        return f"RSS refreshed; {websub_status}; today's editorial post was already distributed"
    delivered = 0
    delivery_notes = []
    if handle and password:
        delivery_notes.append(post_bluesky(handle, password, channel_item(item, "bluesky")))
        delivered += 1
    if webhook:
        post_webhook(webhook, channel_item(item, "syndication"))
        delivered += 1
    if not delivered:
        return f"RSS refreshed; {websub_status}; no external distribution account is connected"
    sent.append(sha256(item["text"].encode()).hexdigest())
    sent_ids.append(item["id"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"version": 2, "sent": sent[-400:], "sent_ids": sent_ids[-400:]}, indent=2) + "\n", encoding="utf-8")
    detail = f"; {'; '.join(delivery_notes)}" if delivery_notes else ""
    return f"{websub_status}; distributed one guide through {delivered} connected channel(s){detail}{maintenance}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / ".revenue-acceleration" / "distribution.json")
    args = parser.parse_args()
    print(run(args.state))
