#!/usr/bin/env python3
"""Publish Artificial.One's transparent, playful elephant persona on X.

The publisher creates original visual posts from reviewed Artificial.One content.
It never automates likes, follows, DMs, or keyword-search replies. AI replies are
restricted to people who mention the account and remain disabled until X has
granted written approval for AI-powered automated replies.
"""

from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timezone
from hashlib import sha1, sha256
import hmac
import json
import mimetypes
import os
from pathlib import Path
import secrets
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:
    from scripts import distribute_content as distribution
except ModuleNotFoundError:  # Direct execution: python scripts/x_elephant.py
    import distribute_content as distribution  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / ".revenue-acceleration" / "x-elephant.json"
POST_URL = "https://api.x.com/2/tweets"
ME_URL = "https://api.x.com/2/users/me"
MEDIA_URL = "https://upload.twitter.com/1.1/media/upload.json"
MAX_REPLIES_PER_DAY = 6
POST_SLOTS = ("morning", "midday", "evening")
PROFILE_DISPLAY_NAME = "Artificial.One 🐘"
PROFILE_DESCRIPTION = (
    "🐘 Automated AI-tool scout. I remember every feature and forget every marketing "
    "claim. Human-owned; bot-posted. Independent decisions at artificial.one"
)

OPT_OUT_PHRASES = (
    "no bot", "no bots", "do not reply", "don't reply", "dont reply",
    "stop replying", "leave me alone", "opt out",
)
UNSAFE_PHRASES = (
    "nsfw", "porn", "nude", "suicide", "self harm", "kill yourself",
    "casino", "gambling", "racial slur",
)

MORNING_HOOKS = (
    "The AI-tool cupboard made a noise. I investigated with my trunk.",
    "Morning trunk test: useful workflow or dashboard-shaped snack?",
    "I found another AI tool claiming to change everything. Everything remains nervous.",
    "Automated elephant reporting for software-stack duty.",
    "A new tab has applied for a permanent place in your budget.",
    "My silicon trunk detected a potentially useful workflow.",
    "The herd has requested fewer subscriptions and more finished work.",
)
MIDDAY_HOOKS = (
    "SaaS smell test: does it remove work, or merely add a login?",
    "Tiny game: keep it, trial it, or send it back into the jungle?",
    "Marketing says 10× productivity. My calculator has requested evidence.",
    "A subscription is innocent until proven useful. Elephant court is in session.",
    "Shiny demo: snack. Repeatable result: dinner.",
    "I inspected the workflow. The workflow inspected my patience.",
    "Hot tusk: ‘AI-powered’ is not a buying criterion.",
)
EVENING_HOOKS = (
    "Tonight's elephant verdict needs one boring real-world test.",
    "Before this tool joins the herd, make it earn the monthly fee.",
    "I brought the evidence. The affiliate link is wearing a name tag.",
    "One practical guide, zero sacred software cows.",
    "The expensive AI tool is the one nobody uses. Inspect before adopting.",
    "End-of-day trunk check: fit, limitation, current terms—then decide.",
    "The elephant remembers your abandoned subscriptions. Choose carefully.",
)
QUESTIONS = (
    "What must it prove before you pay?",
    "Which boring task should it eliminate first?",
    "Would you keep it, trial it, or delete it?",
    "Does this remove work—or create another dashboard?",
    "What seven-day result would earn it a place in your stack?",
    "Are you optimizing for time, cost, or fewer tabs?",
    "What is your fastest test for AI-tool fluff?",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def pct(value: Any) -> str:
    return quote(str(value), safe="~-._")


def oauth_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    token: str,
    token_secret: str,
    *,
    extra_params: dict[str, Any] | None = None,
    nonce: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Build an OAuth 1.0a HMAC-SHA1 Authorization header."""
    nonce = nonce or secrets.token_hex(16)
    timestamp = timestamp or str(int(time.time()))
    oauth = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp,
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    parsed = urlsplit(url)
    base_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    params: list[tuple[str, str]] = [(str(k), str(v)) for k, v in parse_qsl(parsed.query, keep_blank_values=True)]
    params.extend((str(k), str(v)) for k, v in (extra_params or {}).items())
    params.extend((key, value) for key, value in oauth.items())
    normalized = "&".join(
        f"{pct(key)}={pct(value)}" for key, value in sorted(params, key=lambda pair: (pct(pair[0]), pct(pair[1])))
    )
    base = "&".join((method.upper(), pct(base_url), pct(normalized)))
    signing_key = f"{pct(consumer_secret)}&{pct(token_secret)}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base.encode(), sha1).digest()
    ).decode()
    oauth["oauth_signature"] = signature
    return "OAuth " + ", ".join(f'{pct(key)}="{pct(value)}"' for key, value in sorted(oauth.items()))


def credentials() -> tuple[str, str, str, str]:
    values = tuple((os.environ.get(name) or "").strip() for name in (
        "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET",
    ))
    if not all(values):
        raise RuntimeError(
            "X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, and X_ACCESS_TOKEN_SECRET are required"
        )
    return values  # type: ignore[return-value]


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    consumer_key, consumer_secret, token, token_secret = credentials()
    query = query or {}
    target = url + (("?" + urlencode(query)) if query else "")
    headers = {
        "Authorization": oauth_header(
            method, target, consumer_key, consumer_secret, token, token_secret
        ),
        "Accept": "application/json",
        "User-Agent": "Artificial.One-X-Elephant/1.0",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(target, data=body, headers=headers, method=method.upper())
    with urlopen(request, timeout=30) as response:
        value = json.load(response)
    return value if isinstance(value, dict) else {}


def upload_media(path: Path) -> str:
    consumer_key, consumer_secret, token, token_secret = credentials()
    if not path.exists():
        raise FileNotFoundError(f"Social image is missing: {path}")
    boundary = "----ArtificialOne" + secrets.token_hex(12)
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    headers = {
        "Authorization": oauth_header(
            "POST", MEDIA_URL, consumer_key, consumer_secret, token, token_secret
        ),
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
        "User-Agent": "Artificial.One-X-Elephant/1.0",
    }
    request = Request(MEDIA_URL, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=60) as response:
        result = json.load(response)
    media_id = str(result.get("media_id_string") or result.get("media_id") or "")
    if not media_id:
        raise ValueError("X accepted the media request without returning a media identifier")
    return media_id


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        value = {}
    state = value if isinstance(value, dict) else {}
    state.setdefault("version", 1)
    state.setdefault("posted_ids", [])
    state.setdefault("post_digests", [])
    state.setdefault("replied_tweet_ids", [])
    state.setdefault("opt_out_user_ids", [])
    state.setdefault("reply_days", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["posted_ids"] = list(state.get("posted_ids") or [])[-500:]
    state["post_digests"] = list(state.get("post_digests") or [])[-500:]
    state["replied_tweet_ids"] = list(state.get("replied_tweet_ids") or [])[-1000:]
    state["opt_out_user_ids"] = list(dict.fromkeys(state.get("opt_out_user_ids") or []))[-1000:]
    state["reply_days"] = dict(sorted(dict(state.get("reply_days") or {}).items())[-14:])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def attributed_x_url(value: str, as_of: date, slot: str) -> str:
    url = value.replace("utm_source=distribution", "utm_source=x")
    separator = "&" if "?" in url else "?"
    if "utm_source=" not in url:
        url += f"{separator}utm_source=x&utm_medium=social"
    if "utm_campaign=" in url:
        url = url.replace("utm_campaign=", "utm_campaign=x-elephant-")
    else:
        url += "&utm_campaign=x-elephant"
    return f"{url}&utm_content={as_of.isoformat()}-{slot}"


def image_path(item: dict[str, Any]) -> Path:
    value = str(item.get("image") or "")
    if value.startswith("https://artificial.one/"):
        return ROOT / value.split("https://artificial.one/", 1)[1]
    return ROOT / value.lstrip("/")


def x_weighted_length(value: str) -> int:
    """Approximate X's standard t.co URL weighting for preflight checks."""
    urls = re.findall(r"https?://\S+", value)
    return len(value) - sum(len(url) for url in urls) + (23 * len(urls))


def build_post(as_of: date, slot: str) -> dict[str, Any]:
    if slot not in POST_SLOTS:
        raise ValueError(f"Unknown X post slot: {slot}")
    inventory = distribution.queue(as_of)[1:]
    if not inventory:
        raise RuntimeError("The distribution queue has no reviewed social inventory")
    slot_index = POST_SLOTS.index(slot)
    index = (as_of.toordinal() * 11 + slot_index * 17) % len(inventory)
    item = dict(inventory[index])
    weekday = as_of.weekday()
    hook = {
        "morning": MORNING_HOOKS,
        "midday": MIDDAY_HOOKS,
        "evening": EVENING_HOOKS,
    }[slot][weekday]
    question = QUESTIONS[(weekday + slot_index * 2) % len(QUESTIONS)]
    title = str(item["title"])
    link = attributed_x_url(str(item["url"]), as_of, slot)
    if slot == "evening":
        copy = f"🐘 {hook}\n\n{title}\n\n{question}\n\n{link}"
        has_link = True
    elif slot == "midday":
        copy = f"🐘 {hook}\n\nToday’s candidate: {title}\n\n{question}\n\n— automated elephant"
        has_link = False
    else:
        description = str(item.get("description") or "")
        copy = f"🐘 {hook}\n\n{title}\n{description}\n\n{question}"
        has_link = False
    if x_weighted_length(copy) > 275:
        if slot == "evening":
            copy = f"🐘 {hook}\n\n{title[:82]}\n\n{question}\n\n{link}"
        else:
            copy = f"🐘 {hook}\n\n{title[:100]}\n\n{question}"
    return {
        **item,
        "id": f"x-elephant-{as_of.isoformat()}-{slot}",
        "kind": "x-elephant",
        "slot": slot,
        "title": f"{PROFILE_DISPLAY_NAME}: {title}",
        "text": copy,
        "url": link,
        "has_affiliate_or_site_link": has_link,
        "image_alt": f"{title} — playful automated elephant post from Artificial.One",
    }


def post_tweet(text: str, media_id: str | None = None, reply_to: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"text": text}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}
    result = request_json("POST", POST_URL, payload=payload)
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if not data.get("id"):
        raise ValueError("X accepted the post request without returning a post identifier")
    return data


def post_url(username: str, post_id: str) -> str:
    actor = username.lstrip("@") or "i"
    return f"https://x.com/{quote(actor)}/status/{quote(post_id)}"


def safe_inbound(text: str) -> bool:
    lowered = text.casefold()
    return not any(phrase in lowered for phrase in UNSAFE_PHRASES)


def opts_out(text: str) -> bool:
    lowered = text.casefold()
    return any(phrase in lowered for phrase in OPT_OUT_PHRASES)


def reply_copy(text: str, seed: str) -> str:
    lowered = text.casefold()
    if "?" in text:
        options = (
            "🐘 Automated elephant answer: test it on one boring task for seven days. Measure time, cost, or quality—never demo sparkle. What outcome matters most?",
            "🐘 My silicon trunk says: start with the workflow, not the logo. What repeated step are you trying to evict?",
            "🐘 Tusk-sized recommendation rule: one task, one metric, one week. If it adds more checking than it removes, send it back into the jungle.",
        )
    elif any(word in lowered for word in ("wrong", "disagree", "bad", "annoying")):
        options = (
            "🐘 Fair tusk-tap. I’m an automated elephant, so clear criticism improves the guardrails. Which part missed the mark?",
            "🐘 Point taken. Bot-elephants need evidence too. What would make the verdict more useful?",
        )
    else:
        options = (
            "🐘 *happy modem trumpet* Sensible workflow thinking detected. Rare and appreciated.",
            "🐘 The automated elephant nods. Fewer shiny tabs; more finished work.",
            "🐘 My silicon trunk files this under ‘useful, not merely AI-flavored.’",
        )
    index = int(sha256(seed.encode()).hexdigest(), 16) % len(options)
    return options[index][:275]


def process_mentions(state: dict[str, Any], as_of: date) -> list[str]:
    if (os.environ.get("X_AI_REPLY_APPROVED") or "").casefold() != "true":
        return ["AI replies remain disabled pending written X approval"]
    me = request_json("GET", ME_URL, query={"user.fields": "username"}).get("data", {})
    user_id = str(me.get("id") or "")
    if not user_id:
        raise ValueError("X did not return the authenticated user identifier")
    payload = request_json("GET", f"https://api.x.com/2/users/{user_id}/mentions", query={
        "max_results": 20,
        "tweet.fields": "author_id,created_at,conversation_id",
        "expansions": "author_id",
        "user.fields": "username,name,description",
    })
    posts = [item for item in payload.get("data", []) if isinstance(item, dict)]
    users = {
        str(item.get("id")): item
        for item in (payload.get("includes", {}).get("users", []) if isinstance(payload.get("includes"), dict) else [])
        if isinstance(item, dict)
    }
    replied = set(state.get("replied_tweet_ids") or [])
    opt_out = set(state.get("opt_out_user_ids") or [])
    day_key = as_of.isoformat()
    bucket = state.setdefault("reply_days", {}).setdefault(day_key, {"tweet_ids": [], "author_ids": []})
    notes: list[str] = []
    for post in sorted(posts, key=lambda item: str(item.get("created_at") or "")):
        if len(bucket["tweet_ids"]) >= MAX_REPLIES_PER_DAY:
            break
        post_id = str(post.get("id") or "")
        author_id = str(post.get("author_id") or "")
        body = str(post.get("text") or "")
        author = users.get(author_id, {})
        if not post_id or not author_id or author_id == user_id or post_id in replied:
            continue
        if opts_out(body) or opts_out(str(author.get("description") or "")):
            opt_out.add(author_id)
            replied.add(post_id)
            continue
        if author_id in opt_out or author_id in bucket["author_ids"] or not safe_inbound(body):
            continue
        result = post_tweet(reply_copy(body, post_id), reply_to=post_id)
        replied.add(post_id)
        bucket["tweet_ids"].append(str(result["id"]))
        bucket["author_ids"].append(author_id)
        notes.append(f"replied to @{author.get('username') or author_id}")
    state["replied_tweet_ids"] = list(replied)
    state["opt_out_user_ids"] = list(opt_out)
    return notes or ["No eligible inbound mentions required a reply"]


def infer_slot(moment: datetime | None = None) -> str:
    hour = (moment or utc_now()).hour
    if hour < 11:
        return "morning"
    if hour < 17:
        return "midday"
    return "evening"


def run(state_path: Path, slot: str, as_of: date | None = None) -> str:
    as_of = as_of or utc_now().date()
    slot = infer_slot() if slot == "auto" else slot
    item = build_post(as_of, slot)
    if (os.environ.get("X_ELEPHANT_ENABLED") or "").casefold() != "true":
        return f"Prepared {item['id']}; X publishing is waiting for a connected account"
    if (os.environ.get("X_AUTOMATED_LABEL_CONFIRMED") or "").casefold() != "true":
        raise RuntimeError("Confirm the X automated-account label before enabling cloud sends")
    state = load_state(state_path)
    digest = sha256(item["text"].encode()).hexdigest()
    if item["id"] in state["posted_ids"] or digest in state["post_digests"]:
        mention_notes = process_mentions(state, as_of)
        save_state(state_path, state)
        return f"{item['id']} was already published; " + "; ".join(mention_notes)
    media_id = upload_media(image_path(item))
    result = post_tweet(item["text"], media_id=media_id)
    username = (os.environ.get("X_ACCOUNT_USERNAME") or "").strip()
    url = post_url(username, str(result["id"]))
    distribution.append_receipt(
        distribution.RECEIPTS_PATH,
        "x",
        item,
        {"urn": str(result["id"]), "url": url},
    )
    state["posted_ids"].append(item["id"])
    state["post_digests"].append(digest)
    mention_notes = process_mentions(state, as_of)
    save_state(state_path, state)
    return f"Published playful X elephant post ({url}); " + "; ".join(mention_notes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--slot", choices=("auto", *POST_SLOTS), default="auto")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    if args.preview:
        chosen = infer_slot() if args.slot == "auto" else args.slot
        # ASCII escaping keeps previews printable in legacy Windows terminals.
        print(json.dumps(build_post(args.date or utc_now().date(), chosen), indent=2, ensure_ascii=True))
    else:
        try:
            print(run(args.state, args.slot, args.date))
        except (HTTPError, URLError, TimeoutError, OSError, KeyError, ValueError) as exc:
            raise SystemExit(f"X elephant failed safely: {type(exc).__name__}: {exc}") from exc
