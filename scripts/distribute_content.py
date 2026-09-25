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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from scripts import elephant_edge_ai
except ModuleNotFoundError:  # Direct execution: python scripts/distribute_content.py
    import elephant_edge_ai  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
NEWS_PATH = ROOT / "data" / "ai_news.json"
OFFER_ALERTS_PATH = ROOT / "data" / "offer_change_alerts.json"
APPSUMO_PATH = ROOT / "data" / "appsumo_offers.json"
SPONSORED_PATH = ROOT / "data" / "sponsored_campaigns.json"
FEED_PATH = ROOT / "feed.xml"
QUEUE_PATH = ROOT / "data" / "distribution_queue.json"
RECEIPTS_PATH = ROOT / "data" / "distribution_receipts.json"
FEED_URL = "https://artificial.one/feed.xml"
WEBSUB_HUB = "https://pubsubhubbub.appspot.com/"
SOCIAL_IMAGE_DIR = ROOT / "images" / "social-cards"
PROFILE_AVATAR = ROOT / "images" / "social" / "artificial-one-logo.png"
PROFILE_BANNER = ROOT / "images" / "social" / "bluesky-banner.jpg"
PROFILE_DISPLAY_NAME = "Artificial.One 🐘"
PROFILE_DESCRIPTION = (
    "🐘 Playful automated elephant bot for independent AI-tool comparisons, practical "
    "calculators and verified offers. Human-owned; bot-posted. artificial.one"
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
        ("ai-tool-database", "Search the AI Tool Intelligence Database", "ai-tool-database.html", "Search normalized AI tool records by workflow, category, free-plan signal and evidence status."),
        ("ai-tool-alternatives", "Find an AI tool alternative", "ai-tool-alternatives.html", "Choose a tool and switching reason to get a transparent, evidence-weighted migration shortlist."),
)


def attributed_url(path: str, campaign: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"https://artificial.one/{path}{separator}utm_source=distribution&utm_medium=social&utm_campaign={campaign}"


def appsumo_candidates() -> list[dict[str, Any]]:
    return [
        item for item in load(APPSUMO_PATH).get("offers", [])
        if item.get("availability") == "active" and item.get("ai_relevant") and item.get("editorial_url")
    ]


def daily_editorial(as_of: date, offers: list[dict[str, Any]]) -> dict[str, Any]:
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
        thread = [
            "Use it before buying: enter realistic costs, time savings and workflow assumptions.",
            "The result is a decision aid—not a promise of savings. Confirm live pricing and limits before subscribing.",
        ]
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
        thread = [
            f"Source: {source}. Category: {category}. The briefing links to the original reporting.",
            "We also connect the story to a practical decision guide when there is a relevant workflow—not a forced product pitch.",
        ]
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
        thread = [
            f"Best for: {str(offer.get('best_for') or 'teams evaluating this workflow')}"[:295],
            f"Before buying: {str(offer.get('watch_out') or offer.get('pricing_note') or 'verify the current plan limits.')}"[:295],
        ]
    elif day == 3:
        offer = offers[(week + 5) % len(offers)]
        title = f"Before you buy {offer['name']}"
        description = str(offer.get("watch_out") or offer.get("pricing_note") or "Check current limits, pricing and workflow fit before subscribing.")
        path = f"partner-offers/{offer['slug']}.html"
        text = f"Buyer checklist · {edition}\n\n{description}\n\nRead the independent fit guide ↓\n#AITools"
        campaign, kind = "editorial-buyer-guides", "partner-guide"
        thread = [
            f"Best for: {str(offer.get('best_for') or 'teams evaluating this workflow')}"[:295],
            f"Pricing check: {str(offer.get('pricing_note') or 'verify the current vendor terms.')}"[:295],
        ]
    elif day == 4:
        alerts = list(load(OFFER_ALERTS_PATH).get("alerts", []))
        if alerts:
            alert = alerts[week % len(alerts)]
            name = str(alert.get("name") or alert.get("offer_name") or "an AI tool")
            detail = str(alert.get("summary") or alert.get("message") or "A monitored vendor page changed. Verify the current details before buying.")
            title, description, path = f"Offer update: {name}", detail, "offer-updates.html"
            thread = [
                "The change monitor requires repeated first-party observations before publishing an alert.",
                "Always verify the final price, limits and terms on the vendor page before buying.",
            ]
        else:
            deals = appsumo_candidates()
            if deals:
                deal = deals[week % len(deals)]
                title = f"Live AppSumo AI deal check: {deal['name']}"
                description = f"The {deal['category']} destination is active and its independent fit guide is available."
                path = "appsumo-ai-tools.html"
                thread = [
                    "Availability is checked automatically. AppSumo remains the source of truth for today's price, limits and refund terms.",
                    "We do not claim a countdown or discount unless it is verified on the live destination.",
                ]
            else:
                offer = offers[(week + 11) % len(offers)]
                title = f"Current pricing check: {offer['name']}"
                description = str(offer.get("pricing_note") or "Verify the current plan and limits before subscribing.")
                path = f"partner-offers/{offer['slug']}.html"
                thread = [
                    f"Best for: {str(offer.get('best_for') or 'teams evaluating this workflow')}"[:295],
                    f"Before buying: {str(offer.get('watch_out') or 'verify current limits.')}"[:295],
                ]
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
        thread = [
            "The briefing uses allowlisted sources and links back to original reporting.",
            "Use the related calculators and buying guides to turn news into a concrete software decision.",
        ]

    return {
        "id": item_id,
        "image_key": "daily-editorial",
        "daily": "true",
        "kind": kind,
        "title": title,
        "description": description,
        "page_path": path,
        "image": "https://artificial.one/images/social-cards/daily-editorial.jpg",
        "vertical_image": "https://artificial.one/images/social-cards/daily-editorial-vertical.jpg",
        "image_alt": f"{title} — daily editorial from Artificial.One",
        "url": f"{attributed_url(path, campaign)}&utm_content={as_of.isoformat()}",
        "text": text[:295],
        "thread": thread,
    }


def queue(as_of: date | None = None) -> list[dict[str, Any]]:
    as_of = as_of or datetime.now(timezone.utc).date()
    offers = published_offers()
    result = []
    for campaign in load(SPONSORED_PATH).get("campaigns", []):
        dates = [str(value) for value in campaign.get("social_publish_dates", [])]
        if as_of.isoformat() not in dates:
            continue
        target = str(campaign.get("target_url") or campaign.get("page_url") or "")
        result.append({
            "id": f"sponsored-{campaign['order_key']}-{as_of.isoformat()}",
            "kind": "sponsored-campaign",
            "daily": "true",
            "title": f"Sponsored: {campaign['brand']}",
            "description": str(campaign.get("brief") or "")[:240],
            "page_path": f"sponsored/{campaign['slug']}.html",
            "image": "https://artificial.one/images/social-cards/daily-editorial.jpg",
            "image_alt": f"Sponsored partner feature for {campaign['brand']} on Artificial.One",
            "url": target,
            "text": (
                f"Sponsored partner feature · {campaign['brand']}\n\n"
                f"{str(campaign.get('brief') or '')[:170]}\n\n"
                "Paid placement; independent rankings are unchanged. Learn more ↓\n#Sponsored #AITools"
            )[:295],
            "linkedin_copy": (
                f"Sponsored partner feature: {campaign['brand']}\n\n"
                f"{str(campaign.get('brief') or '')[:500]}\n\n"
                "This is a paid placement. Artificial.One keeps its independent rankings separate."
            ),
        })
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


def linkedin_bonus_item(as_of: date | None = None) -> dict[str, Any] | None:
    """Build the second, weekday-only LinkedIn post.

    It reuses reviewed site inventory and existing visual cards, but gives the
    post a more conversational LinkedIn-native angle.  Weekends deliberately
    remain at one post per day, yielding twelve scheduled posts per week.
    """
    as_of = as_of or datetime.now(timezone.utc).date()
    if as_of.weekday() >= 5:
        return None
    inventory = queue(as_of)[1:]
    if not inventory:
        return None
    item = dict(inventory[(as_of.toordinal() * 5 + as_of.weekday()) % len(inventory)])
    hooks = (
        "Monday confession: our software stack does not need another shiny tab.",
        "Hot take: ‘AI-powered’ is not a buying criterion. Workflow fit is.",
        "Tiny game: keep it, trial it, or delete it?",
        "The expensive AI tool is the one nobody actually uses.",
        "Friday software therapy: let’s talk about the subscription you forgot to cancel.",
    )
    questions = (
        "What is the one job you would make this tool prove before paying?",
        "Would this remove real work—or merely create a new dashboard to check?",
        "Which verdict would you give it: keep, trial, or delete?",
        "What would make this earn a permanent place in your stack?",
        "Which AI subscription is currently fighting for its life in your budget?",
    )
    item.update({
        "id": f"linkedin-play-{as_of.isoformat()}",
        "kind": "linkedin-play",
        "title": f"{hooks[as_of.weekday()]} {item['title']}",
        "url": item["url"].replace("utm_campaign=", "utm_campaign=linkedin-playful-"),
        "linkedin_copy": (
            f"{hooks[as_of.weekday()]}\n\n"
            f"Today’s candidate: {item['title']}\n\n"
            f"{item['description']}\n\n"
            f"{questions[as_of.weekday()]}"
        ),
        "image_alt": f"{item['title']} — playful AI tool discussion from Artificial.One",
    })
    return item


def linkedin_reviewed_brief(item: dict[str, Any]) -> str:
    return "\n".join([
        f"Title: {str(item.get('title') or '').strip()}",
        f"Reviewed context: {str(item.get('description') or '').strip()}",
        f"Editorial fallback: {str(item.get('linkedin_copy') or item.get('text') or '').strip()}",
        "Brand voice: playful, practical Artificial.One elephant; skeptical of AI hype.",
    ])


def linkedin_edge_copy(
    item: dict[str, Any], state: dict[str, Any],
) -> tuple[str, bool]:
    fallback = str(item.get("linkedin_copy") or item.get("text") or item.get("description") or "").strip()
    enabled = (os.environ.get("ELEPHANT_EDGE_AI_ENABLED") or "").casefold() == "true"
    if not enabled:
        return fallback, False
    recent = [str(value) for value in state.get("recent_linkedin_ai_copy") or []]
    generated = elephant_edge_ai.generate_linkedin_post(
        linkedin_reviewed_brief(item), str(item.get("id") or item.get("title") or "linkedin"), recent,
    )
    return (generated, True) if generated else (fallback, False)


def remember_linkedin_ai_copy(state: dict[str, Any], copy: str, used_ai: bool) -> None:
    if not used_ai:
        return
    recent = list(state.get("recent_linkedin_ai_copy") or [])
    recent.append(copy)
    state["recent_linkedin_ai_copy"] = recent[-100:]


def write_public_outputs(items: list[dict[str, Any]]) -> None:
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


def linkedin_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def linkedin_author_urn(access_token: str, configured: str = "") -> str:
    if configured:
        return configured
    profile = request_json(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    member_id = str(profile.get("sub") or "").strip()
    if not member_id:
        raise ValueError("LinkedIn OpenID profile did not return a member identifier")
    return f"urn:li:person:{member_id}"


def linkedin_commentary(item: dict[str, Any]) -> str:
    """Turn a compact social item into a useful professional-network post."""
    lead = str(item.get("linkedin_copy") or item.get("text") or item.get("description") or item["title"]).strip()
    context = str(item.get("description") or "").strip()
    paragraphs = [lead]
    if context and context.casefold() not in lead.casefold():
        paragraphs.append(context)
    paragraphs.extend([
        f"Explore the guide: {item['url']}",
        "#ArtificialIntelligence #AITools #BusinessAutomation",
    ])
    return "\n\n".join(paragraphs)[:3000]


def register_linkedin_image(access_token: str, author_urn: str) -> tuple[str, str]:
    payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": author_urn,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent",
            }],
        }
    }
    response = request_json(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        data=payload,
        headers=linkedin_headers(access_token),
    )
    value = response["value"]
    mechanism = value["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]
    return str(value["asset"]), str(mechanism["uploadUrl"])


def upload_linkedin_image(upload_url: str, image_path: Path) -> None:
    request = Request(
        upload_url,
        data=image_path.read_bytes(),
        headers={"Content-Type": mimetypes.guess_type(image_path.name)[0] or "image/jpeg"},
        method="PUT",
    )
    with urlopen(request, timeout=60):
        pass


def create_linkedin_post(access_token: str, payload: dict[str, Any]) -> str:
    request = Request(
        "https://api.linkedin.com/v2/ugcPosts",
        data=json.dumps(payload).encode("utf-8"),
        headers=linkedin_headers(access_token),
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        post_urn = response.headers.get("X-RestLi-Id") or response.headers.get("x-restli-id")
    if not post_urn:
        raise ValueError("LinkedIn accepted the post but did not return its identifier")
    return str(post_urn)


def linkedin_post_url(post_urn: str) -> str:
    return f"https://www.linkedin.com/feed/update/{post_urn}/"


def post_linkedin(access_token: str, author_urn: str, item: dict[str, Any]) -> dict[str, str]:
    author_urn = linkedin_author_urn(access_token, author_urn)
    image_path = ROOT / item["image"].split("https://artificial.one/", 1)[-1]
    if not image_path.exists():
        raise FileNotFoundError(f"Social card is missing: {image_path}")
    asset_urn, upload_url = register_linkedin_image(access_token, author_urn)
    upload_linkedin_image(upload_url, image_path)
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": linkedin_commentary(item)},
                "shareMediaCategory": "IMAGE",
                "media": [{
                    "status": "READY",
                    "description": {"text": str(item["description"])[:200]},
                    "media": asset_urn,
                    "title": {"text": str(item["title"])[:200]},
                }],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    post_urn = create_linkedin_post(access_token, payload)
    return {"urn": post_urn, "url": linkedin_post_url(post_urn)}


def append_receipt(path: Path, platform: str, item: dict[str, Any], result: dict[str, str]) -> None:
    try:
        payload = load(path)
    except (OSError, json.JSONDecodeError):
        payload = {"version": 1, "receipts": []}
    receipts = list(payload.get("receipts") or [])
    receipt_id = f"{platform}:{result['urn']}"
    if not any(candidate.get("id") == receipt_id for candidate in receipts if isinstance(candidate, dict)):
        receipts.append({
            "id": receipt_id,
            "platform": platform,
            "item_id": item["id"],
            "title": item["title"],
            "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "url": result["url"],
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "receipts": receipts[-1000:]}, indent=2) + "\n", encoding="utf-8")


def receipt_has_item(path: Path, platform: str, item_id: str) -> bool:
    try:
        receipts = load(path).get("receipts", [])
    except (OSError, json.JSONDecodeError):
        return False
    return any(
        isinstance(receipt, dict)
        and receipt.get("platform") == platform
        and receipt.get("item_id") == item_id
        for receipt in receipts
    )


def linkedin_token_warning(expires_at: str) -> str:
    if not expires_at:
        return ""
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    except ValueError:
        return "LinkedIn token expiry setting is invalid"
    days = (expiry - datetime.now(timezone.utc)).total_seconds() / 86400
    if days <= 0:
        return "LinkedIn access token has expired; reconnect LinkedIn"
    if days <= 14:
        return f"LinkedIn access token expires in {max(1, int(days))} day(s); reconnect it now"
    return ""


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


def ensure_bluesky_profile(session: dict[str, Any], refresh: bool = False) -> bool:
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
    if value.get("displayName") != PROFILE_DISPLAY_NAME:
        value["displayName"] = PROFILE_DISPLAY_NAME
        changed = True
    if value.get("description") != PROFILE_DESCRIPTION:
        value["description"] = PROFILE_DESCRIPTION
        changed = True
    if (refresh or not value.get("avatar")) and PROFILE_AVATAR.exists():
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


def refresh_bluesky_profile(handle: str, password: str) -> str:
    """Force the public Bluesky identity to match the repository brand asset."""
    if not handle or not password:
        raise RuntimeError("BLUESKY_HANDLE and BLUESKY_APP_PASSWORD are required")
    if not PROFILE_AVATAR.exists():
        raise FileNotFoundError(f"Bluesky profile logo is missing: {PROFILE_AVATAR}")
    session = request_json(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        data={"identifier": handle, "password": password},
    )
    ensure_bluesky_profile(session, refresh=True)
    return f"Bluesky profile refreshed for {handle} from {PROFILE_AVATAR.name}"


def bluesky_record(item: dict[str, Any], thumbnail: dict[str, Any]) -> dict[str, Any]:
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


def bluesky_reply_record(text: str, root: dict[str, str], parent: dict[str, str]) -> dict[str, Any]:
    return {
        "$type": "app.bsky.feed.post",
        "text": text[:295],
        "langs": ["en"],
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reply": {
            "root": {"uri": root["uri"], "cid": root["cid"]},
            "parent": {"uri": parent["uri"], "cid": parent["cid"]},
        },
    }


def create_bluesky_post(session: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    payload = {"repo": session["did"], "collection": "app.bsky.feed.post", "record": record}
    return request_json(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        data=payload,
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
    )


def post_bluesky(handle: str, password: str, item: dict[str, Any]) -> dict[str, str]:
    login = Request("https://bsky.social/xrpc/com.atproto.server.createSession", data=json.dumps({"identifier": handle, "password": password}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(login, timeout=30) as response:
        session = json.load(response)
    profile_branded = ensure_bluesky_profile(session)
    image_path = ROOT / item["image"].split("https://artificial.one/", 1)[-1]
    if not image_path.exists():
        raise FileNotFoundError(f"Social card is missing: {image_path}")
    thumbnail = upload_bluesky_blob(session["accessJwt"], image_path)
    result = create_bluesky_post(session, bluesky_record(item, thumbnail))
    root = {"uri": str(result["uri"]), "cid": str(result["cid"])}
    parent = root
    replies = 0
    reply_error = ""
    for text in list(item.get("thread") or [])[:3]:
        try:
            response = create_bluesky_post(session, bluesky_reply_record(str(text), root, parent))
            parent = {"uri": str(response["uri"]), "cid": str(response["cid"])}
            replies += 1
        except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
            # The root post has already succeeded. Do not fail the whole run and
            # duplicate it tomorrow merely because a supporting reply failed.
            reply_error = f"; reply delivery stopped after {replies}: {type(exc).__name__}"
            break
    urn = str(result["uri"])
    rkey = urn.rsplit("/", 1)[-1]
    return {
        "urn": urn,
        "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
        "note": (
            f"visual thread posted ({urn}; {replies} replies); "
            f"profile branded={str(profile_branded).lower()}{reply_error}"
        ),
    }


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


def post_webhook(url: str, item: dict[str, Any]) -> None:
    request = Request(url, data=json.dumps({"source": "artificial.one", **item}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30):
        pass


def channel_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    attributed_url = item["url"].replace("utm_source=distribution", f"utm_source={source}")
    return {
        **item,
        "url": attributed_url,
    }


def channel_state(state: dict[str, Any], channel: str) -> dict[str, list[str]]:
    channels = state.setdefault("channels", {})
    if channel in channels:
        return channels[channel]
    # Version 2 used one global state. It represented the channels that existed
    # then (Bluesky and the generic webhook), but must not suppress a newly
    # connected LinkedIn channel.
    inherited = channel in {"bluesky", "syndication"}
    channels[channel] = {
        "sent": list(state.get("sent", [])) if inherited else [],
        "sent_ids": list(state.get("sent_ids", [])) if inherited else [],
    }
    return channels[channel]


def save_distribution_state(path: Path, state: dict[str, Any]) -> None:
    channels = {}
    for name, value in dict(state.get("channels") or {}).items():
        channels[name] = {
            "sent": list(value.get("sent") or [])[-400:],
            "sent_ids": list(value.get("sent_ids") or [])[-400:],
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 3,
        "channels": channels,
        "recent_linkedin_ai_copy": list(state.get("recent_linkedin_ai_copy") or [])[-100:],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def publish_linkedin_bonus(state_path: Path, as_of: date | None = None) -> str:
    """Publish the second weekday LinkedIn item without touching other channels."""
    item = linkedin_bonus_item(as_of)
    if item is None:
        return "Weekend cadence retained: no second LinkedIn post is scheduled"
    flag = (os.environ.get("DISTRIBUTION_SEND_ENABLED") or "").casefold()
    token = (os.environ.get("LINKEDIN_ACCESS_TOKEN") or "").strip()
    author = (os.environ.get("LINKEDIN_AUTHOR_URN") or "").strip()
    warning = linkedin_token_warning((os.environ.get("LINKEDIN_TOKEN_EXPIRES_AT") or "").strip())
    if warning:
        print(f"::warning::{warning}")
    if flag != "true":
        return "Playful LinkedIn post prepared; cloud sending is disabled"
    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN is required for the playful publisher")
    try:
        state = load(state_path)
    except (OSError, json.JSONDecodeError):
        state = {"version": 3, "channels": {}}
    delivered = channel_item(item, "linkedin")
    generated_copy, used_ai = linkedin_edge_copy(delivered, state)
    delivered["linkedin_copy"] = generated_copy
    digest = sha256(linkedin_commentary(delivered).encode()).hexdigest()
    progress = channel_state(state, "linkedin-playful")
    if (
        item["id"] in progress["sent_ids"]
        or digest in progress["sent"]
        or receipt_has_item(RECEIPTS_PATH, "linkedin", item["id"])
    ):
        return "Today’s playful LinkedIn post was already published"
    result = post_linkedin(token, author, delivered)
    append_receipt(RECEIPTS_PATH, "linkedin", delivered, result)
    progress["sent"].append(digest)
    progress["sent_ids"].append(item["id"])
    remember_linkedin_ai_copy(state, generated_copy, used_ai)
    save_distribution_state(state_path, state)
    return f"Playful LinkedIn image post published ({result['url']})"


def run(state_path: Path, as_of: date | None = None) -> str:
    items = queue(as_of)
    write_public_outputs(items)
    websub_status = ping_websub()
    flag = (os.environ.get("DISTRIBUTION_SEND_ENABLED") or "").casefold()
    handle = (os.environ.get("BLUESKY_HANDLE") or "").strip()
    password = (os.environ.get("BLUESKY_APP_PASSWORD") or "").strip()
    linkedin_token = (os.environ.get("LINKEDIN_ACCESS_TOKEN") or "").strip()
    linkedin_author = (os.environ.get("LINKEDIN_AUTHOR_URN") or "").strip()
    linkedin_expiry = (os.environ.get("LINKEDIN_TOKEN_EXPIRES_AT") or "").strip()
    webhook = (os.environ.get("DISTRIBUTION_WEBHOOK_URL") or "").strip()
    delete_rkey = (os.environ.get("BLUESKY_DELETE_RKEY") or "").strip()
    mark_sent_id = (os.environ.get("BLUESKY_MARK_SENT_ID") or "").strip()
    connected = bool((handle and password) or linkedin_token or webhook)
    try:
        state = load(state_path)
    except (OSError, json.JSONDecodeError):
        state = {"version": 3, "channels": {}}
    maintenance_notes: list[str] = []
    state_changed = False
    if delete_rkey and handle and password:
        maintenance_notes.append(delete_bluesky_post(handle, password, delete_rkey))
    if mark_sent_id:
        marked_item = next((candidate for candidate in items if candidate["id"] == mark_sent_id), None)
        if marked_item:
            bluesky_state = channel_state(state, "bluesky")
            digest = sha256(marked_item["text"].encode()).hexdigest()
            if digest not in bluesky_state["sent"]:
                bluesky_state["sent"].append(digest)
                bluesky_state["sent_ids"].append(marked_item["id"])
                state_changed = True
                maintenance_notes.append(f"marked {mark_sent_id} as distributed")
    if state_changed:
        save_distribution_state(state_path, state)
    token_warning = linkedin_token_warning(linkedin_expiry)
    if token_warning:
        print(f"::warning::{token_warning}")
    maintenance = f"; {'; '.join(maintenance_notes)}" if maintenance_notes else ""
    if not items or flag == "false" or (flag != "true" and not connected):
        return f"RSS and distribution queue refreshed; {websub_status}; social posting is waiting for a connected channel{maintenance}"
    # Only today's editorial item is eligible for automatic publishing. The rest
    # remain in RSS as discovery inventory, preventing deployment or retries from
    # draining several posts on the same day.
    item = next((candidate for candidate in items if candidate.get("daily") == "true"), None)
    if not item:
        return f"RSS refreshed; {websub_status}; no daily editorial is available"
    digest = sha256(item["text"].encode()).hexdigest()
    delivered = 0
    delivery_notes: list[str] = []
    failures: list[str] = []
    linkedin_delivery: dict[str, Any] = {}

    def publish_linkedin_item() -> dict[str, str]:
        prepared = channel_item(item, "linkedin")
        generated_copy, used_ai = linkedin_edge_copy(prepared, state)
        prepared["linkedin_copy"] = generated_copy
        linkedin_delivery.update({"item": prepared, "copy": generated_copy, "used_ai": used_ai})
        return post_linkedin(linkedin_token, linkedin_author, prepared)

    channels: list[tuple[str, bool, Any]] = [
        ("bluesky", bool(handle and password), lambda: post_bluesky(handle, password, channel_item(item, "bluesky"))),
        ("linkedin", bool(linkedin_token), publish_linkedin_item),
        ("syndication", bool(webhook), lambda: post_webhook(webhook, channel_item(item, "syndication"))),
    ]
    already_sent = 0
    for name, enabled, publish in channels:
        if not enabled:
            continue
        progress = channel_state(state, name)
        if item["id"] in progress["sent_ids"] or digest in progress["sent"]:
            already_sent += 1
            continue
        try:
            result = publish()
            if name == "linkedin":
                prepared = linkedin_delivery.get("item") or item
                append_receipt(RECEIPTS_PATH, name, prepared, result)
                remember_linkedin_ai_copy(
                    state,
                    str(linkedin_delivery.get("copy") or ""),
                    bool(linkedin_delivery.get("used_ai")),
                )
                delivery_notes.append(f"LinkedIn image post published ({result['url']})")
            elif name == "bluesky":
                prepared = channel_item(item, "bluesky")
                append_receipt(RECEIPTS_PATH, name, prepared, result)
                delivery_notes.append(str(result["note"]))
            elif result:
                delivery_notes.append(str(result))
            progress["sent"].append(digest)
            progress["sent_ids"].append(item["id"])
            save_distribution_state(state_path, state)
            delivered += 1
        except (HTTPError, URLError, TimeoutError, OSError, KeyError, ValueError) as exc:
            failures.append(f"{name}: {type(exc).__name__}")
    if not delivered:
        if already_sent and not failures:
            return f"RSS refreshed; {websub_status}; today's editorial post was already distributed to every connected channel"
        if failures:
            raise RuntimeError("Social delivery failed without marking the item sent: " + ", ".join(failures))
        return f"RSS refreshed; {websub_status}; no external distribution account is connected"
    detail = f"; {'; '.join(delivery_notes)}" if delivery_notes else ""
    failure_note = f"; delivery failures: {', '.join(failures)}" if failures else ""
    if failures:
        print(f"::warning::Some social channels failed and remain eligible for retry: {', '.join(failures)}")
    return f"{websub_status}; distributed one guide through {delivered} connected channel(s){detail}{failure_note}{maintenance}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / ".revenue-acceleration" / "distribution.json")
    parser.add_argument("--linkedin-bonus", action="store_true", help="Publish the second weekday LinkedIn post only")
    parser.add_argument(
        "--refresh-bluesky-profile",
        action="store_true",
        help="Replace the Bluesky avatar and canonical profile copy from repository assets",
    )
    args = parser.parse_args()
    if args.refresh_bluesky_profile:
        print(refresh_bluesky_profile(
            (os.environ.get("BLUESKY_HANDLE") or "").strip(),
            (os.environ.get("BLUESKY_APP_PASSWORD") or "").strip(),
        ))
    elif args.linkedin_bonus:
        print(publish_linkedin_bonus(args.state))
    else:
        print(run(args.state))
