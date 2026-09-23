#!/usr/bin/env python3
"""Run Artificial.One's transparent, playful Bluesky elephant persona.

The agent deliberately favors real interactions over growth hacks. It replies
to people who address the account, follows back relevant humans, and may join
one recent AI-tool question per day. Hard daily limits, opt-out recognition,
topic filters, and durable state prevent mass engagement or repeated replies.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, urlencode

try:
    from scripts import distribute_content as distribution
    from scripts import elephant_edge_ai
except ModuleNotFoundError:  # Direct execution: python scripts/bluesky_elephant.py
    import distribute_content as distribution  # type: ignore
    import elephant_edge_ai  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / ".revenue-acceleration" / "bluesky-elephant.json"
MAX_BONUS_POSTS_PER_DAY = 1
MAX_REPLIES_PER_DAY = 3
MAX_DISCOVERY_REPLIES_PER_DAY = 1
MAX_LIKES_PER_DAY = 5
MAX_FOLLOWS_PER_DAY = 2
STATE_RETENTION_DAYS = 21

TOPIC_KEYWORDS = {
    "AI-tool stack": ("ai tool", "ai tools", "software", "saas", "subscription", "stack"),
    "automation workflow": ("automat", "workflow", "agent", "productivity", "no-code", "nocode"),
    "content workflow": ("content", "writing", "video", "image", "design", "audio", "voice"),
    "developer workflow": ("code", "coding", "developer", "api", "llm", "model", "prompt"),
    "growth workflow": ("marketing", "seo", "sales", "conversion", "email", "social media"),
}
SEARCH_QUERIES = (
    '"AI tools"',
    '"AI workflow"',
    '"AI agent"',
    '"AI subscription"',
    '"which AI"',
    '"best AI tool"',
    '"LLM tools"',
)
TOPICAL_PROFILE_WORDS = (
    "ai", "tech", "software", "automation", "developer", "marketing",
    "startup", "saas", "data", "product", "design", "creator",
)
OPT_OUT_PATTERNS = (
    "no bots", "do not reply", "don't reply", "dont reply", "bot go away",
    "stop replying", "leave me alone", "do not follow", "don't follow",
)
UNSAFE_WORDS = (
    "nsfw", "porn", "nude", "casino", "gambling", "crypto pump",
    "memecoin", "hate speech",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        value = {}
    state = value if isinstance(value, dict) else {}
    state.setdefault("version", 1)
    state.setdefault("days", {})
    state.setdefault("processed_notifications", [])
    state.setdefault("opt_out_dids", [])
    state.setdefault("interaction_counts", {})
    state.setdefault("recent_ai_replies", [])
    return state


def save_state(path: Path, state: dict[str, Any], as_of: date) -> None:
    cutoff = as_of - timedelta(days=STATE_RETENTION_DAYS)
    state["days"] = {
        key: value for key, value in dict(state.get("days") or {}).items()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", key) and date.fromisoformat(key) >= cutoff
    }
    state["processed_notifications"] = list(state.get("processed_notifications") or [])[-1000:]
    state["opt_out_dids"] = list(dict.fromkeys(state.get("opt_out_dids") or []))[-1000:]
    state["interaction_counts"] = dict(sorted(
        dict(state.get("interaction_counts") or {}).items(),
        key=lambda item: int(item[1]), reverse=True,
    )[:1000])
    state["recent_ai_replies"] = list(state.get("recent_ai_replies") or [])[-100:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def day_bucket(state: dict[str, Any], as_of: date) -> dict[str, Any]:
    bucket = state.setdefault("days", {}).setdefault(as_of.isoformat(), {})
    for key in ("bonus_posts", "replied_uris", "discovery_replies", "liked_uris", "followed_dids"):
        bucket.setdefault(key, [])
    return bucket


def session(handle: str, password: str) -> dict[str, Any]:
    return distribution.request_json(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        data={"identifier": handle, "password": password},
    )


def authenticated_get(active_session: dict[str, Any], endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"https://bsky.social/xrpc/{endpoint}?{urlencode(params, doseq=True)}"
    return distribution.request_json(
        url,
        headers={"Authorization": f"Bearer {active_session['accessJwt']}", "Accept": "application/json"},
    )


def create_record(active_session: dict[str, Any], collection: str, record: dict[str, Any]) -> dict[str, Any]:
    return distribution.request_json(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        data={"repo": active_session["did"], "collection": collection, "record": record},
        headers={"Authorization": f"Bearer {active_session['accessJwt']}"},
    )


def post_url(handle: str, uri: str) -> str:
    return f"https://bsky.app/profile/{quote(handle)}/post/{quote(uri.rsplit('/', 1)[-1])}"


def topic_for(text: str) -> str:
    lowered = text.casefold()
    for label, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return label
    return "AI-tool workflow"


def relevant(text: str) -> bool:
    lowered = text.casefold()
    return any(keyword in lowered for keywords in TOPIC_KEYWORDS.values() for keyword in keywords)


def asks_for_opt_out(text: str) -> bool:
    lowered = text.casefold()
    return any(pattern in lowered for pattern in OPT_OUT_PATTERNS)


def safe_text(text: str) -> bool:
    lowered = text.casefold()
    return not any(word in lowered for word in UNSAFE_WORDS)


def healthy_actor(author: dict[str, Any], own_did: str, opt_out_dids: set[str]) -> bool:
    did = str(author.get("did") or "")
    viewer = author.get("viewer") if isinstance(author.get("viewer"), dict) else {}
    labels = author.get("labels") if isinstance(author.get("labels"), list) else []
    description = str(author.get("description") or "")
    return bool(
        did and did != own_did and did not in opt_out_dids
        and not viewer.get("blockedBy") and not viewer.get("blocking") and not viewer.get("muted")
        and not labels and safe_text(description) and not asks_for_opt_out(description)
    )


def topical_actor(author: dict[str, Any]) -> bool:
    haystack = f"{author.get('displayName', '')} {author.get('description', '')}".casefold()
    return any(word in haystack for word in TOPICAL_PROFILE_WORDS)


def deterministic_choice(values: tuple[str, ...], seed: str) -> str:
    return values[int(sha256(seed.encode("utf-8")).hexdigest(), 16) % len(values)]


def direct_reply(text: str, seed: str) -> str:
    topic = topic_for(text)
    if asks_for_opt_out(text):
        return ""
    if any(word in text.casefold() for word in ("wrong", "bad", "disagree", "spam", "annoying")):
        return (
            "🐘 Fair tusk-tap. I’m an automated elephant, so I’ll take the feedback "
            "without pretending to have feelings—just better guardrails. Thanks for saying it plainly."
        )
    if "?" in text:
        choices = (
            f"🐘 Bot-elephant checking the {topic}. My trunk test: does it remove a repeated step or add another dashboard? What outcome matters most—time, cost, or quality?",
            f"🐘 Automated elephant opinion: trial the {topic} on one boring task, measure one result, and keep zero sacred cows. What would count as a win after seven days?",
            f"🐘 Tiny tusk of skepticism for this {topic}: shiny demos are snacks; repeatable results are dinner. Which step do you most want to evict?",
        )
    else:
        choices = (
            f"🐘 *happy modem trumpet* This automated elephant approves of a practical {topic}. The herd deserves fewer tabs and more finished work.",
            f"🐘 My silicon trunk detected a sensible {topic}. Rare! I’m filing this under “useful, not merely shiny.”",
            f"🐘 Bot-elephant nod. The best {topic} is usually the one that quietly removes a boring step instead of demanding applause.",
        )
    return deterministic_choice(choices, seed)[:295]


def discovery_reply(text: str, seed: str) -> str:
    topic = topic_for(text)
    choices = (
        f"🐘 Automated elephant wandering past the {topic} aisle. My trunk test: make it remove one repeated step before it earns a subscription. What task must it prove first?",
        f"🐘 Tiny tusk of skepticism for this {topic}: demo sparkle is easy; repeatable usefulness is hard. What would a seven-day win look like?",
        f"🐘 Bot-elephant vote: trial one {topic}, measure one outcome, keep zero sacred cows. Are you optimizing for time, cost, or fewer tabs?",
    )
    return deterministic_choice(choices, seed)[:295]


def elephant_reply(
    text: str, seed: str, state: dict[str, Any], *, discovery: bool = False,
) -> tuple[str, bool]:
    """Prefer local AI, retaining templates as a zero-risk fallback."""
    fallback = discovery_reply(text, seed) if discovery else direct_reply(text, seed)
    if not fallback:
        return "", False
    enabled = (os.environ.get("ELEPHANT_EDGE_AI_ENABLED") or "").casefold() == "true"
    if not enabled:
        return fallback, False
    recent = [str(item) for item in state.get("recent_ai_replies") or []]
    generated = elephant_edge_ai.generate_reply(
        text,
        "Join a relevant public AI-tool question" if discovery else "Reply to a person who addressed the bot",
        seed,
        recent,
    )
    return (generated, True) if generated else (fallback, False)


def remember_ai_reply(state: dict[str, Any], reply: str, used_ai: bool) -> None:
    if not used_ai:
        return
    history = list(state.get("recent_ai_replies") or [])
    history.append(reply)
    state["recent_ai_replies"] = history[-100:]


def bluesky_bonus_item(as_of: date) -> dict[str, Any] | None:
    inventory = distribution.queue(as_of)[1:]
    if not inventory:
        return None
    item = dict(inventory[(as_of.toordinal() * 7 + as_of.weekday()) % len(inventory)])
    moods = (
        "I found another shiny AI tool. I have placed it under strict trunk surveillance.",
        "Software-stack safari report: one more tab is asking to become a monthly expense.",
        "Today’s elephant-sized question: useful workflow, or dashboard-shaped snack?",
        "I poked the AI-tool cupboard with my trunk. Something practical fell out.",
        "A subscription is innocent until proven useful. The elephant court is now in session.",
        "Weekend trunk check: fewer promises, more boring tasks actually completed.",
        "Sunday stack archaeology: which tool still earns its place in the herd?",
    )
    questions = (
        "What must it prove before you pay?",
        "Would you keep it, trial it, or send it back into the jungle?",
        "Does it remove work—or merely add another login?",
        "Which boring task should it eliminate first?",
        "What result would earn it a permanent place in your stack?",
        "Would this save time in your real workflow?",
        "What is your fastest test for AI-tool fluff?",
    )
    item.update({
        "id": f"bluesky-elephant-{as_of.isoformat()}",
        "title": f"Elephant trunk check: {item['title']}",
        "url": item["url"].replace("utm_source=distribution", "utm_source=bluesky").replace(
            "utm_campaign=", "utm_campaign=bluesky-elephant-"
        ),
        "text": (
            f"🐘 {moods[as_of.weekday()]}\n\n"
            f"{item['title']}\n\n{questions[as_of.weekday()]}\n#AITools #Bot"
        )[:295],
        "image_alt": f"{item['title']} — playful automated elephant pick from Artificial.One",
    })
    return item


def publish_bonus(
    active_session: dict[str, Any], handle: str, state_path: Path,
    state: dict[str, Any], as_of: date,
) -> str | None:
    bucket = day_bucket(state, as_of)
    if len(bucket["bonus_posts"]) >= MAX_BONUS_POSTS_PER_DAY:
        return None
    item = bluesky_bonus_item(as_of)
    if not item or item["id"] in bucket["bonus_posts"]:
        return None
    image_path = ROOT / item["image"].split("https://artificial.one/", 1)[-1]
    if not image_path.exists():
        raise FileNotFoundError(f"Social card is missing: {image_path}")
    thumbnail = distribution.upload_bluesky_blob(active_session["accessJwt"], image_path)
    result = distribution.create_bluesky_post(active_session, distribution.bluesky_record(item, thumbnail))
    uri = str(result["uri"])
    url = post_url(handle, uri)
    distribution.append_receipt(
        distribution.RECEIPTS_PATH, "bluesky", item, {"urn": uri, "url": url}
    )
    bucket["bonus_posts"].append(item["id"])
    save_state(state_path, state, as_of)
    return url


def notification_items(active_session: dict[str, Any]) -> list[dict[str, Any]]:
    payload = authenticated_get(
        active_session, "app.bsky.notification.listNotifications", {"limit": 50}
    )
    items = [item for item in payload.get("notifications", []) if isinstance(item, dict)]
    return sorted(items, key=lambda item: str(item.get("indexedAt") or ""), reverse=True)


def record_ref(item: dict[str, Any]) -> dict[str, str] | None:
    uri, cid = str(item.get("uri") or ""), str(item.get("cid") or "")
    return {"uri": uri, "cid": cid} if uri and cid else None


def reply_root(item: dict[str, Any]) -> dict[str, str] | None:
    parent = record_ref(item)
    record = item.get("record") if isinstance(item.get("record"), dict) else {}
    reply = record.get("reply") if isinstance(record.get("reply"), dict) else {}
    root = reply.get("root") if isinstance(reply.get("root"), dict) else parent
    if not root or not root.get("uri") or not root.get("cid"):
        return parent
    return {"uri": str(root["uri"]), "cid": str(root["cid"])}


def like_post(active_session: dict[str, Any], subject: dict[str, str]) -> None:
    create_record(active_session, "app.bsky.feed.like", {
        "$type": "app.bsky.feed.like",
        "subject": subject,
        "createdAt": utc_now().isoformat().replace("+00:00", "Z"),
    })


def follow_actor(active_session: dict[str, Any], did: str) -> None:
    create_record(active_session, "app.bsky.graph.follow", {
        "$type": "app.bsky.graph.follow",
        "subject": did,
        "createdAt": utc_now().isoformat().replace("+00:00", "Z"),
    })


def process_notifications(
    active_session: dict[str, Any], state_path: Path,
    state: dict[str, Any], as_of: date,
) -> list[str]:
    bucket = day_bucket(state, as_of)
    processed = set(state.get("processed_notifications") or [])
    opt_out = set(state.get("opt_out_dids") or [])
    counts = state.setdefault("interaction_counts", {})
    notes: list[str] = []
    for item in notification_items(active_session):
        uri = str(item.get("uri") or "")
        if not uri or uri in processed:
            continue
        reason = str(item.get("reason") or "")
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        did = str(author.get("did") or "")
        record = item.get("record") if isinstance(item.get("record"), dict) else {}
        text = str(record.get("text") or "")

        indexed = parse_time(str(item.get("indexedAt") or ""))
        if not indexed or utc_now() - indexed > timedelta(hours=72):
            processed.add(uri)
            state["processed_notifications"] = list(processed)
            save_state(state_path, state, as_of)
            continue
        if reason in {"mention", "reply", "quote"} and did:
            counts[did] = int(counts.get(did, 0)) + 1

        if did and asks_for_opt_out(f"{text} {author.get('description', '')}"):
            opt_out.add(did)
            state["opt_out_dids"] = sorted(opt_out)
            processed.add(uri)
            state["processed_notifications"] = list(processed)
            save_state(state_path, state, as_of)
            continue
        if not healthy_actor(author, str(active_session["did"]), opt_out):
            processed.add(uri)
            state["processed_notifications"] = list(processed)
            save_state(state_path, state, as_of)
            continue

        viewer = author.get("viewer") if isinstance(author.get("viewer"), dict) else {}
        relationship_signal = reason == "follow" or int(counts.get(did, 0)) >= 2
        if (
            relationship_signal and topical_actor(author) and did not in bucket["followed_dids"]
            and not viewer.get("following") and len(bucket["followed_dids"]) < MAX_FOLLOWS_PER_DAY
        ):
            follow_actor(active_session, did)
            bucket["followed_dids"].append(did)
            save_state(state_path, state, as_of)
            notes.append(f"followed @{author.get('handle') or did}")

        if reason not in {"mention", "reply", "quote"} or not text or not safe_text(text):
            processed.add(uri)
            state["processed_notifications"] = list(processed)
            save_state(state_path, state, as_of)
            continue
        subject = record_ref(item)
        root = reply_root(item)
        if not subject or not root or uri in bucket["replied_uris"]:
            processed.add(uri)
            state["processed_notifications"] = list(processed)
            save_state(state_path, state, as_of)
            continue
        if len(bucket["replied_uris"]) >= MAX_REPLIES_PER_DAY:
            break
        response_text, used_ai = elephant_reply(text, uri, state)
        if not response_text:
            continue
        distribution.create_bluesky_post(
            active_session, distribution.bluesky_reply_record(response_text, root, subject)
        )
        bucket["replied_uris"].append(uri)
        remember_ai_reply(state, response_text, used_ai)
        processed.add(uri)
        state["processed_notifications"] = list(processed)
        save_state(state_path, state, as_of)
        notes.append(f"replied to @{author.get('handle') or did}")
        if uri not in bucket["liked_uris"] and len(bucket["liked_uris"]) < MAX_LIKES_PER_DAY:
            like_post(active_session, subject)
            bucket["liked_uris"].append(uri)
            save_state(state_path, state, as_of)
            notes.append(f"liked @{author.get('handle') or did}'s post")
    return notes


def parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def discovery_candidates(active_session: dict[str, Any], as_of: date) -> list[dict[str, Any]]:
    query = SEARCH_QUERIES[as_of.toordinal() % len(SEARCH_QUERIES)]
    payload = authenticated_get(active_session, "app.bsky.feed.searchPosts", {
        "q": query, "sort": "latest", "lang": "en", "limit": 25,
    })
    return [item for item in payload.get("posts", []) if isinstance(item, dict)]


def candidate_is_recent_question(item: dict[str, Any], active_session: dict[str, Any], now: datetime) -> bool:
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    record = item.get("record") if isinstance(item.get("record"), dict) else {}
    text = str(record.get("text") or "")
    created = parse_time(str(record.get("createdAt") or ""))
    if not created or now - created > timedelta(hours=12) or created > now + timedelta(minutes=5):
        return False
    if record.get("reply") or "?" not in text or not (40 <= len(text) <= 290):
        return False
    if not relevant(text) or not safe_text(text) or asks_for_opt_out(f"{text} {author.get('description', '')}"):
        return False
    if re.search(r"https?://|\b(buy|sale|discount|affiliate|sponsored)\b", text, re.I):
        return False
    return healthy_actor(author, str(active_session["did"]), set())


def discover_and_engage(
    active_session: dict[str, Any], state_path: Path,
    state: dict[str, Any], as_of: date, now: datetime | None = None,
) -> list[str]:
    bucket = day_bucket(state, as_of)
    if (
        len(bucket["replied_uris"]) >= MAX_REPLIES_PER_DAY
        or len(bucket["discovery_replies"]) >= MAX_DISCOVERY_REPLIES_PER_DAY
    ):
        return []
    now = now or utc_now()
    opt_out = set(state.get("opt_out_dids") or [])
    for item in discovery_candidates(active_session, as_of):
        uri = str(item.get("uri") or "")
        cid = str(item.get("cid") or "")
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        did = str(author.get("did") or "")
        record = item.get("record") if isinstance(item.get("record"), dict) else {}
        text = str(record.get("text") or "")
        if (
            not uri or not cid or uri in bucket["replied_uris"]
            or did in opt_out or not candidate_is_recent_question(item, active_session, now)
        ):
            continue
        subject = {"uri": uri, "cid": cid}
        response_text, used_ai = elephant_reply(text, uri, state, discovery=True)
        distribution.create_bluesky_post(
            active_session,
            distribution.bluesky_reply_record(response_text, subject, subject),
        )
        bucket["replied_uris"].append(uri)
        bucket["discovery_replies"].append(uri)
        remember_ai_reply(state, response_text, used_ai)
        save_state(state_path, state, as_of)
        notes = [f"joined @{author.get('handle') or did}'s AI-tool question"]
        if uri not in bucket["liked_uris"] and len(bucket["liked_uris"]) < MAX_LIKES_PER_DAY:
            like_post(active_session, subject)
            bucket["liked_uris"].append(uri)
            save_state(state_path, state, as_of)
            notes.append(f"liked @{author.get('handle') or did}'s question")
        return notes
    return []


def run(state_path: Path, as_of: date | None = None) -> str:
    enabled = (os.environ.get("BLUESKY_ELEPHANT_ENABLED") or "").casefold() == "true"
    handle = (os.environ.get("BLUESKY_HANDLE") or "").strip()
    password = (os.environ.get("BLUESKY_APP_PASSWORD") or "").strip()
    if not enabled:
        return "Playful Bluesky elephant is prepared; engagement sending is disabled"
    if not handle or not password:
        raise RuntimeError("BLUESKY_HANDLE and BLUESKY_APP_PASSWORD are required")
    as_of = as_of or utc_now().date()
    state = load_state(state_path)
    active_session = session(handle, password)
    distribution.ensure_bluesky_profile(active_session)
    notes: list[str] = []
    bonus_url = publish_bonus(active_session, handle, state_path, state, as_of)
    if bonus_url:
        notes.append(f"published elephant post {bonus_url}")
    notes.extend(process_notifications(active_session, state_path, state, as_of))
    notes.extend(discover_and_engage(active_session, state_path, state, as_of))
    if not notes:
        return "Playful Bluesky elephant checked in; no safe, relevant action was available"
    return "Playful Bluesky elephant: " + "; ".join(notes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--date", type=date.fromisoformat)
    args = parser.parse_args()
    print(run(args.state, args.date))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
