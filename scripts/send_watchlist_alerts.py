#!/usr/bin/env python3
"""Send confirmed AI-tool change digests to double-opted-in watchlists."""

from __future__ import annotations

from html import escape
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "tool_change_history.json"
RESEND_URL = "https://api.resend.com/emails"


def request_json(url: str, *, token: str = "", payload: dict[str, Any] | None = None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, data=data, headers=headers, method="POST" if data is not None else "GET"), timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Remote watchlist request failed: {exc}") from exc


class Redis:
    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.token = token

    def command(self, *parts: str) -> Any:
        endpoint = self.url + "/" + "/".join(quote(str(part), safe="") for part in parts)
        result = request_json(endpoint, token=self.token)
        return result.get("result") if isinstance(result, dict) else None

    def active_keys(self) -> list[str]:
        cursor = "0"
        keys: list[str] = []
        for _ in range(20):
            value = self.command("SCAN", cursor, "MATCH", "watch:active:*", "COUNT", "100")
            if not isinstance(value, list) or len(value) != 2:
                break
            cursor, batch = str(value[0]), value[1]
            keys.extend(str(item) for item in batch if isinstance(item, str))
            if cursor == "0":
                break
        return sorted(set(keys))


def send_email(api_key: str, sender: str, subscription: dict[str, Any], events: list[dict[str, Any]]) -> None:
    rows = "".join(
        f'<li style="margin:0 0 16px"><strong>{escape(str(item.get("tool_name") or "AI tool"))}</strong> · {escape(str(item.get("kind") or "product"))}<br>{escape(str(item.get("message") or "A vendor-source change was confirmed."))}<br><a href="{escape(str(item.get("source_url") or "https://artificial.one/ai-tool-observatory.html"))}">Verify with vendor</a></li>'
        for item in events
    )
    unsubscribe = f'https://artificial.one/api/watchlist-subscribe?action=unsubscribe&token={quote(str(subscription.get("unsubscribe_token") or ""))}'
    text = "Artificial.One Elephant watchlist\n\n" + "\n".join(f"{item.get('tool_name')}: {item.get('message')} {item.get('source_url')}" for item in events) + f"\n\nUnsubscribe: {unsubscribe}"
    payload = {
        "from": sender,
        "to": [subscription["email"]],
        "subject": f"🐘 {len(events)} confirmed AI tool change{'s' if len(events) != 1 else ''}",
        "text": text,
        "html": f'<div style="font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:28px"><h1>Elephant watchlist</h1><p>These changes passed Artificial.One’s repeated-observation rule.</p><ul>{rows}</ul><p><a href="https://artificial.one/ai-tool-observatory.html">Open the Observatory</a></p><p style="font-size:12px;color:#667085"><a href="{escape(unsubscribe)}">Unsubscribe</a></p></div>',
    }
    request_json(RESEND_URL, token=api_key, payload=payload)


def run() -> int:
    redis_url = (os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL") or "").strip()
    redis_token = (os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or "").strip()
    resend = (os.environ.get("RESEND_API_KEY") or "").strip()
    sender = (os.environ.get("WATCHLIST_EMAIL_FROM") or "Artificial.One Watchlist <updates@artificial.one>").strip()
    if not redis_url or not redis_token or not resend:
        print("Watchlist delivery is prepared; required cloud credentials are unavailable.")
        return 0
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    events = [item for item in history.get("events", []) if isinstance(item, dict) and item.get("id")]
    if not events:
        print("No confirmed tool changes are available.")
        return 0
    redis = Redis(redis_url, redis_token)
    delivered = 0
    for key in redis.active_keys():
        raw = redis.command("GET", key)
        try:
            subscription = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            continue
        ids = {str(item) for item in subscription.get("tool_ids", [])}
        if not subscription.get("email") or not ids:
            continue
        previous = str(subscription.get("last_event_id") or "")
        if not previous:
            subscription["last_event_id"] = str(events[0]["id"])
            redis.command("SET", key, json.dumps(subscription, separators=(",", ":")))
            continue
        candidates = []
        for event in events:
            if str(event["id"]) == previous:
                break
            if str(event.get("tool_id") or "") in ids:
                candidates.append(event)
        if candidates:
            send_email(resend, sender, subscription, candidates[:12])
            delivered += 1
        subscription["last_event_id"] = str(events[0]["id"])
        redis.command("SET", key, json.dumps(subscription, separators=(",", ":")))
    print(f"Processed {len(redis.active_keys())} confirmed watchlists; delivered {delivered} change digest(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
