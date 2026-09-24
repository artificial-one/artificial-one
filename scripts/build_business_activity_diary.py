#!/usr/bin/env python3
"""Build a business-readable diary from verifiable automated outcomes.

The diary intentionally excludes tests, validation, caches, workflow success,
and technical-only code changes. Repository entries come only from commits made
by GitHub Actions. Social entries come from the public Bluesky feed, so a queued
post is never reported as published.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import html
import json
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "business_activity_diary.json"
DOCUMENT_PATH = ROOT / "docs" / "AUTOMATED_BUSINESS_DIARY.md"
TIMEZONE = ZoneInfo("Europe/Prague")
DEFAULT_SINCE = "2026-09-15"
DEFAULT_BLUESKY_HANDLE = "artificial-one.bsky.social"
RECEIPTS_PATH = ROOT / "data" / "distribution_receipts.json"
BOT_MARKERS = ("github-actions[bot]", "41898282+github-actions[bot]")
INTERNAL_HTML = {"partner-opportunities.html"}
SPECIAL_PUBLIC_HTML = {"newsletter/latest.html"}


def git(root: Path, *args: str, allow_failure: bool = False) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode and not allow_failure:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def json_at(root: Path, revision: str, path: str) -> dict[str, Any]:
    raw = git(root, "show", f"{revision}:{path}", allow_failure=True)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def title_at(root: Path, revision: str, path: str) -> str:
    raw = git(root, "show", f"{revision}:{path}", allow_failure=True)
    match = re.search(r"<title>(.*?)</title>", raw, re.I | re.S)
    if match:
        return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return Path(path).stem.replace("-", " ").title()


def public_url(path: str) -> str:
    if path == "index.html":
        return "https://artificial.one/"
    return "https://artificial.one/" + quote(path.replace("\\", "/"), safe="/")


def public_html(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized.endswith(".html")
        and normalized not in INTERNAL_HTML
        and normalized not in SPECIAL_PUBLIC_HTML
        and not normalized.startswith("docs/")
    )


def new_records(before: dict[str, Any], after: dict[str, Any], collection: str, key: str) -> list[dict[str, Any]]:
    old = {
        str(item.get(key) or ""): item
        for item in before.get(collection, [])
        if isinstance(item, dict) and item.get(key)
    }
    return [
        item for item in after.get(collection, [])
        if isinstance(item, dict) and item.get(key) and str(item.get(key)) not in old
    ]


def event(event_id: str, occurred_at: str, kind: str, summary: str, **extra: Any) -> dict[str, Any]:
    local = datetime.fromisoformat(occurred_at.replace("Z", "+00:00")).astimezone(TIMEZONE)
    value = {
        "id": event_id,
        "date": local.date().isoformat(),
        "occurred_at": local.isoformat(timespec="seconds"),
        "kind": kind,
        "summary": summary,
    }
    value.update({key: val for key, val in extra.items() if val not in (None, "", [])})
    return value


def repository_events(root: Path, since: str) -> list[dict[str, Any]]:
    log = git(root, "log", f"--since={since}T00:00:00Z", "--format=%H%x1f%aI%x1f%an%x1f%ae%x1f%s")
    entries: list[dict[str, Any]] = []
    for line in log.splitlines():
        fields = line.split("\x1f", 4)
        if len(fields) != 5:
            continue
        sha, timestamp, author, email, subject = fields
        if not any(marker in f"{author} {email}" for marker in BOT_MARKERS):
            continue
        parent = f"{sha}^"
        changes = git(root, "diff-tree", "--root", "--no-commit-id", "--name-status", "-r", "--no-renames", sha)
        changed_paths: dict[str, str] = {}
        for change in changes.splitlines():
            parts = change.split("\t", 1)
            if len(parts) == 2:
                changed_paths[parts[1].replace("\\", "/")] = parts[0][0]

        for path, status in sorted(changed_paths.items()):
            if not public_html(path):
                continue
            source_revision = parent if status == "D" else sha
            kind = {"A": "webpage_created", "D": "webpage_retired"}.get(status, "webpage_updated")
            verb = {"A": "Published", "D": "Retired"}.get(status, "Updated")
            entries.append(event(
                f"git:{sha}:{status}:{path}", timestamp, kind,
                f"{verb} webpage: {title_at(root, source_revision, path)}",
                url=public_url(path), path=path, source_commit=sha[:12],
            ))

        if "feed.xml" in changed_paths:
            entries.append(event(
                f"git:{sha}:rss", timestamp, "distribution_updated",
                "Published an updated RSS feed for content distribution.", source_commit=sha[:12],
            ))

        structured = (
            ("data/ai_news.json", "items", "url", "news_items_added", "Added {count} new AI-news items to the live briefing."),
            ("data/partner_offers.json", "offers", "id", "affiliate_offers_added", "Activated {count} new tracked affiliate offers."),
            ("data/partner_opportunities.json", "opportunities", "id", "affiliate_opportunities_found", "Discovered {count} new affiliate opportunities for evaluation."),
            ("data/appsumo_offers.json", "offers", "id", "appsumo_offers_added", "Imported {count} new AppSumo offers with monetization data."),
            ("data/tool_change_history.json", "events", "id", "vendor_changes_detected", "Published {count} confirmed vendor pricing, plan, or availability changes."),
        )
        for path, collection, key, kind, template in structured:
            if path not in changed_paths:
                continue
            before = json_at(root, parent, path)
            after = json_at(root, sha, path)
            added = new_records(before, after, collection, key)
            if not added:
                continue
            labels = [str(item.get("title") or item.get("name") or item.get("tool_name") or item.get(key)) for item in added]
            entries.append(event(
                f"git:{sha}:{kind}", timestamp, kind, template.format(count=len(added)),
                details=labels, source_commit=sha[:12],
            ))

        if "data/offer_change_alerts.json" in changed_paths:
            added = new_records(
                json_at(root, parent, "data/offer_change_alerts.json"),
                json_at(root, sha, "data/offer_change_alerts.json"),
                "alerts", "source_url",
            )
            if added:
                entries.append(event(
                    f"git:{sha}:offer_changes", timestamp, "affiliate_offer_changes_detected",
                    f"Published {len(added)} confirmed change alerts for monetized offers.",
                    details=[str(item.get("offer_id") or item.get("source_url")) for item in added], source_commit=sha[:12],
                ))

        # These are public business assets but are not ordinary site pages.
        if "newsletter/latest.html" in changed_paths:
            entries.append(event(
                f"git:{sha}:newsletter", timestamp, "newsletter_edition_updated",
                "Published a refreshed web newsletter edition (email sending is not currently connected).",
                url="https://artificial.one/newsletter/latest.html", source_commit=sha[:12],
            ))
        social_images = [
            path for path, path_status in changed_paths.items()
            if path.startswith("images/social") and path_status != "D"
        ]
        if social_images:
            entries.append(event(
                f"git:{sha}:social_creatives", timestamp, "social_creatives_updated",
                f"Created or refreshed {len(social_images)} social-media creative assets.",
                details=social_images, source_commit=sha[:12],
            ))
    return entries


def bluesky_events(handle: str) -> list[dict[str, Any]]:
    query = urlencode({"actor": handle, "limit": 100, "filter": "posts_no_replies"})
    request = Request(
        "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?" + query,
        headers={"Accept": "application/json", "User-Agent": "artificial.one-business-diary/1.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception:
        return []
    result: list[dict[str, Any]] = []
    for item in payload.get("feed", []):
        post = item.get("post") if isinstance(item, dict) else None
        record = post.get("record") if isinstance(post, dict) else None
        if not isinstance(record, dict) or not record.get("createdAt") or not post.get("uri"):
            continue
        uri = str(post["uri"])
        rkey = uri.rsplit("/", 1)[-1]
        text = re.sub(r"\s+", " ", str(record.get("text") or "")).strip()
        summary = text[:180] + ("…" if len(text) > 180 else "")
        result.append(event(
            f"bluesky:{uri}", str(record["createdAt"]), "social_post_published",
            f"Published Bluesky post: {summary}",
            url=f"https://bsky.app/profile/{quote(handle)}/post/{quote(rkey)}",
        ))
    return result


def receipt_events(root: Path) -> list[dict[str, Any]]:
    """Load public-safe delivery receipts written only after API success."""
    try:
        payload = json.loads((root / RECEIPTS_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    result: list[dict[str, Any]] = []
    for receipt in payload.get("receipts", []):
        if not isinstance(receipt, dict) or not receipt.get("id") or not receipt.get("published_at"):
            continue
        platform_key = str(receipt.get("platform") or "social network").casefold()
        platform = "LinkedIn" if platform_key == "linkedin" else platform_key.title()
        result.append(event(
            str(receipt["id"]), str(receipt["published_at"]), "social_post_published",
            f"Published {platform} post: {receipt.get('title') or receipt.get('item_id') or 'Artificial.One guide'}",
            url=receipt.get("url"),
        ))
    return result


def load_existing(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"entries": []}
    return value if isinstance(value, dict) else {"entries": []}


def render_markdown(payload: dict[str, Any]) -> str:
    entries = payload["entries"]
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in entries:
        by_date[item["date"]].append(item)
    lines = [
        "# Automated Business Activity Diary",
        "",
        "This is the evidence-based diary of productive work completed by artificial.one’s cloud automation. It records business outcomes—not technical execution. A workflow run, test, validation, cache refresh, or report generation is deliberately excluded unless it produced a public page, published content, a confirmed social post, a monetizable offer, or another concrete business asset.",
        "",
        f"**Timezone:** Europe/Prague  ",
        f"**History begins:** {payload['history_begins']}  ",
        f"**Latest recorded activity:** {payload.get('last_activity_at') or 'None yet'}",
        "",
        "## Daily productive system",
        "",
        "GitHub schedules are stated in UTC; Prague local time is UTC+2 during summer and UTC+1 during winter. GitHub may start scheduled work later than the nominal minute.",
        "",
        "- **AI news publishing — 00:41, 06:41, 12:41 and 18:41 UTC:** refreshes the homepage and news briefing with newly found items from allowlisted AI sources, then updates search discovery.",
        "- **AI tool intelligence — 04:37 UTC daily:** updates the public tool database and publishes confirmed pricing, plan, or availability changes.",
        "- **Partner offer publishing — 05:17 UTC daily and when offer data changes:** creates or refreshes approved affiliate pages and contextual affiliate placements.",
        "- **Affiliate opportunity discovery — 05:41 UTC daily:** finds new programs, reviews public policy signals, and automatically publishes offers only when an approved partnership and usable tracking link already exist.",
        "- **Search growth — 06:11 UTC daily:** creates or refreshes commercial-intent pages and applies guarded search improvements based on Search Console demand.",
        "- **Affiliate-network and AppSumo monitoring — 07:23 UTC daily:** imports new monetizable AppSumo assets, refreshes availability, creates missing Impact links where authorized, and updates corresponding pages.",
        "- **Revenue optimization and distribution — 08:13 UTC daily:** ranks offers, improves conversion routes, refreshes decision tools and creatives, publishes one confirmed item to each connected social channel, and updates RSS and the web newsletter.",
        "- **Playful Bluesky elephant — 10:37 and 17:47 UTC daily:** publishes one extra visual elephant-persona post, answers recent mentions, joins at most one relevant AI-tool question, appreciates useful posts, and selectively follows back relevant people within strict anti-spam limits.",
        "- **Playful LinkedIn edition — 14:43 UTC Monday–Friday:** publishes a second original visual post with a conversational hook and a genuine discussion question. Together with the daily edition, LinkedIn receives twelve posts per week.",
        "- **Business diary — 20:15 UTC daily:** records the verified outcomes below in one consolidated roll-up.",
        "",
        "### Connected versus prepared channels",
        "",
        "- **Active:** website publishing, PartnerStack, Impact/AppSumo, Awin, Bluesky, LinkedIn, RSS, IndexNow, Search Console analysis, private email monitoring.",
        "- **Prepared but not currently sending:** Beehiiv newsletter delivery (credentials absent) and Google paid advertising (live controls absent). The generated web newsletter and paid-campaign plan are recorded only as website/planning assets, never as sent campaigns.",
        "",
        "## Diary",
        "",
    ]
    if not by_date:
        lines.extend(["No productive activities have been recorded yet.", ""])
    for day in sorted(by_date, reverse=True):
        items = sorted(by_date[day], key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
        lines.extend([f"### {day}", ""])
        for item in items:
            when = datetime.fromisoformat(item["occurred_at"]).strftime("%H:%M")
            summary = str(item["summary"])
            if item.get("url"):
                summary = f"[{summary}]({item['url']})"
            lines.append(f"- **{when}** — {summary}")
            for detail in item.get("details", []):
                lines.append(f"  - {detail}")
        lines.append("")
    lines.extend([
        "## Audit boundaries",
        "",
        "Included evidence: GitHub Actions bot commits that changed public business assets, structured additions to public offer/news/change inventories, posts confirmed through Bluesky’s public feed, and LinkedIn receipts written only after LinkedIn accepted a post.",
        "",
        "Excluded noise: workflow starts/completions, unit tests, syntax checks, validation passes, dependency setup, cache operations, private monitoring totals, and code-only maintenance. Search submission is represented through the resulting discoverable content rather than as a technical job event.",
        "",
    ])
    return "\n".join(lines)


def build(root: Path, since: str, handle: str, fetch_social: bool = True) -> dict[str, Any]:
    existing = load_existing(root / DATA_PATH.relative_to(ROOT))
    preserved_social = {
        item["id"]: item for item in existing.get("entries", [])
        if isinstance(item, dict) and str(item.get("id", "")).startswith("bluesky:")
    }
    entries = repository_events(root, since)
    if fetch_social:
        for item in bluesky_events(handle):
            preserved_social[item["id"]] = item
    for item in receipt_events(root):
        preserved_social[item["id"]] = item
    entries.extend(preserved_social.values())
    deduped = {item["id"]: item for item in entries}
    ordered = sorted(deduped.values(), key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
    payload = {
        "version": 1,
        "history_begins": since,
        "timezone": "Europe/Prague",
        "last_activity_at": ordered[0]["occurred_at"] if ordered else None,
        "method": "GitHub Actions publication commits plus confirmed social-network posts",
        "entries": ordered,
    }
    data_path = root / DATA_PATH.relative_to(ROOT)
    document_path = root / DOCUMENT_PATH.relative_to(ROOT)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    document_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default=DEFAULT_SINCE)
    parser.add_argument("--bluesky-handle", default=DEFAULT_BLUESKY_HANDLE)
    parser.add_argument("--no-social", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        parser.error("--since must be YYYY-MM-DD")
    before_data = DATA_PATH.read_text(encoding="utf-8") if DATA_PATH.exists() else None
    before_doc = DOCUMENT_PATH.read_text(encoding="utf-8") if DOCUMENT_PATH.exists() else None
    payload = build(ROOT, args.since, args.bluesky_handle, fetch_social=not args.no_social)
    if args.check:
        after_data = DATA_PATH.read_text(encoding="utf-8")
        after_doc = DOCUMENT_PATH.read_text(encoding="utf-8")
        if before_data != after_data or before_doc != after_doc:
            raise SystemExit("Business diary is stale; run scripts/build_business_activity_diary.py")
    print(f"Business diary contains {len(payload['entries'])} productive activities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
