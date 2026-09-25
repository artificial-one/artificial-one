#!/usr/bin/env python3
"""Send one business-readable daily report for artificial.one.

The report deliberately hides operational detail. It combines verified public
business activity, current affiliate coverage, aggregate revenue/conversion
metrics and the small set of decisions that cannot legally be automated.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PRAGUE = ZoneInfo("Europe/Prague")
RESEND_URL = "https://api.resend.com/emails"
LINKEDIN_VERSION = "202608"
SOCIAL_PLATFORMS = ("linkedin", "bluesky", "x")


def load_json(path: Path, default: Any | None = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {} if default is None else default


def integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def money_map(values: dict[str, Any]) -> str:
    nonzero = [(str(currency), str(amount)) for currency, amount in sorted(values.items()) if float(amount or 0)]
    return ", ".join(f"{currency} {amount}" for currency, amount in nonzero) or "USD 0.00"


def daily_activity(payload: dict[str, Any], report_date: str) -> dict[str, Any]:
    entries = [item for item in payload.get("entries", []) if item.get("date") == report_date]
    kinds = Counter(str(item.get("kind") or "") for item in entries)
    pages_created = [item for item in entries if item.get("kind") == "webpage_created"]
    pages_updated = [item for item in entries if item.get("kind") == "webpage_updated"]
    social = [item for item in entries if item.get("kind") == "social_post_published"]
    commercial = [
        item for item in entries
        if item.get("kind") in {
            "affiliate_offers_added", "appsumo_offers_added",
            "affiliate_offer_changes_detected", "vendor_changes_detected",
        }
    ]
    highlights: list[dict[str, str]] = []
    for group in (commercial, pages_created, social, pages_updated):
        for item in group:
            summary = str(item.get("summary") or "").strip()
            if not summary or any(existing["text"] == summary for existing in highlights):
                continue
            highlights.append({"text": summary, "url": str(item.get("url") or "")})
            if len(highlights) == 5:
                break
        if len(highlights) == 5:
            break
    return {
        "entries": entries,
        "counts": kinds,
        "pages_created": len({item.get("path") for item in pages_created}),
        "pages_updated": len({item.get("path") for item in pages_updated}),
        "social_posts": len(social),
        "highlights": highlights,
    }


def opportunity_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id") or ""): item
        for item in payload.get("opportunities", [])
        if isinstance(item, dict) and item.get("id")
    }


def owner_actions(
    reconciliation: dict[str, Any], opportunities: dict[str, Any],
    marketplace: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    lookup = opportunity_lookup(opportunities)
    actions: list[dict[str, str]] = []
    labels = {
        "terms_required": "Accept the program terms",
        "external_account_required": "Finish the one-time partner account setup",
    }
    for blocker in reconciliation.get("activation_blockers", []):
        reason = str(blocker.get("reason") or "")
        if reason not in labels:
            continue
        source_id = str(blocker.get("source_id") or "")
        item = lookup.get(source_id, {})
        name = str(item.get("name") or source_id.partition(":")[2].replace("-", " ").title())
        url = str(item.get("application_url") or item.get("terms_url") or "https://dash.partnerstack.com/home")
        actions.append({
            "title": f"{labels[reason]}: {name}",
            "detail": "This requires your acceptance because it creates a legal or account commitment.",
            "url": url,
        })
    for action in (marketplace or {}).get("owner_actions", []):
        if not isinstance(action, dict):
            continue
        actions.append({
            "title": str(action.get("title") or "Review a sponsored-content request"),
            "detail": str(action.get("detail") or "Accepting creates a binding delivery commitment."),
            "url": str(action.get("url") or "https://dash.partnerstack.com/content-marketplace/requests"),
        })
    actions.sort(key=lambda action: action["title"].casefold())
    return actions


def system_work(reconciliation: dict[str, Any], opportunities: dict[str, Any]) -> list[dict[str, str]]:
    """Explain every approved relationship the automation has not published yet."""
    lookup = opportunity_lookup(opportunities)
    work: list[dict[str, str]] = []
    for blocker in reconciliation.get("activation_blockers", []):
        if str(blocker.get("reason") or "") != "active_link_pending":
            continue
        source_id = str(blocker.get("source_id") or "")
        item = lookup.get(source_id, {})
        name = str(item.get("name") or source_id.partition(":")[2].replace("-", " ").title())
        work.append({
            "title": name,
            "detail": "Approved relationship detected. The system is obtaining or verifying its affiliate link; after that it will create and publish the product page.",
        })
    return sorted(work, key=lambda item: item["title"].casefold())


def live_affiliate_destinations(partner_offers: dict[str, Any], appsumo: dict[str, Any]) -> int:
    """Count unique, public, AI-relevant destinations—not pages or database rows."""
    urls: set[str] = set()
    for item in partner_offers.get("offers", []):
        if item.get("status") == "published" and str(item.get("tracking_url") or "").startswith("https://"):
            urls.add(str(item["tracking_url"]))
    for item in appsumo.get("offers", []):
        if (
            item.get("availability") != "expired" and item.get("ai_relevant")
            and item.get("editorial_url") and str(item.get("tracking_url") or "").startswith("https://")
        ):
            urls.add(str(item["tracking_url"]))
    return len(urls)


def receipt_urn(receipt: dict[str, Any]) -> str:
    identifier = str(receipt.get("id") or "")
    return identifier.split(":", 1)[1] if ":" in identifier else identifier


def local_receipt_date(receipt: dict[str, Any]) -> date | None:
    value = str(receipt.get("published_at") or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(PRAGUE).date()
    except (ValueError, TypeError):
        return None


def bluesky_metrics(receipts: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    wanted = [receipt_urn(item) for item in receipts if item.get("platform") == "bluesky"]
    if not wanted:
        return {}
    query = "&".join(f"uris={quote(uri, safe='')}" for uri in wanted)
    request = Request(
        f"https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts?{query}",
        headers={"Accept": "application/json", "User-Agent": "artificial.one-daily-report/1.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            posts = json.load(response).get("posts", [])
    except Exception:
        return {}
    return {
        str(post.get("uri") or ""): {
            "likes": integer(post.get("likeCount")),
            "comments": integer(post.get("replyCount")),
            "reposts": integer(post.get("repostCount")),
            "quotes": integer(post.get("quoteCount")),
        }
        for post in posts if isinstance(post, dict) and post.get("uri")
    }


def linkedin_metrics(receipts: list[dict[str, Any]], token: str, author_urn: str) -> dict[str, dict[str, Any]]:
    """Read organic company-post statistics when LinkedIn has granted reporting access."""
    if not token or not author_urn:
        return {}
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "User-Agent": "artificial.one-daily-report/1.0",
    }
    result: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        if receipt.get("platform") != "linkedin":
            continue
        urn = receipt_urn(receipt)
        url = (
            "https://api.linkedin.com/rest/organizationalEntityShareStatistics"
            f"?q=organizationalEntity&organizationalEntity={quote(author_urn, safe='')}"
            f"&shares=List({quote(urn, safe='')})"
        )
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                elements = json.load(response).get("elements", [])
            totals = elements[0].get("totalShareStatistics", {}) if elements else {}
            result[urn] = {
                "likes": integer(totals.get("likeCount")),
                "comments": integer(totals.get("commentCount")),
                "reposts": integer(totals.get("shareCount")),
                "views": integer(totals.get("impressionCount")),
                "clicks": integer(totals.get("clickCount")),
            }
        except Exception:
            continue
    return result


def social_posts_for_day(
    receipts: dict[str, Any], report_date: date, metrics: dict[str, dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    metrics = metrics or {}
    grouped: dict[str, list[dict[str, Any]]] = {platform: [] for platform in SOCIAL_PLATFORMS}
    for receipt in receipts.get("receipts", []):
        if not isinstance(receipt, dict) or local_receipt_date(receipt) != report_date:
            continue
        platform = str(receipt.get("platform") or "").casefold()
        if platform not in grouped:
            grouped[platform] = []
        urn = receipt_urn(receipt)
        grouped[platform].append({
            "title": str(receipt.get("title") or receipt.get("item_id") or "Artificial.One post"),
            "url": str(receipt.get("url") or ""),
            "published_at": str(receipt.get("published_at") or ""),
            "metrics": metrics.get(urn),
        })
    for posts in grouped.values():
        posts.sort(key=lambda item: item["published_at"])
    return grouped


def social_performance(root: Path, report_date: date) -> dict[str, list[dict[str, Any]]]:
    receipts = load_json(root / "data" / "distribution_receipts.json", {"receipts": []})
    todays = [
        item for item in receipts.get("receipts", [])
        if isinstance(item, dict) and local_receipt_date(item) == report_date
    ]
    metrics: dict[str, dict[str, Any]] = {}
    metrics.update(bluesky_metrics(todays))
    metrics.update(linkedin_metrics(
        todays,
        os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip(),
        os.environ.get("LINKEDIN_AUTHOR_URN", "").strip(),
    ))
    return social_posts_for_day(receipts, report_date, metrics)


def github_health(token: str, repository: str, now: datetime) -> dict[str, Any]:
    if not token or not repository:
        return {"status": "unknown", "healthy": 0, "attention": 0, "issues": []}
    since = (now.astimezone(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"https://api.github.com/repos/{repository}/actions/runs?per_page=100&created=%3E%3D{quote(since)}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "artificial.one-daily-report/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception:
        return {"status": "unknown", "healthy": 0, "attention": 0, "issues": []}
    latest: dict[str, dict[str, Any]] = {}
    for run in payload.get("workflow_runs", []):
        name = str(run.get("name") or run.get("workflow_id") or "")
        created = str(run.get("created_at") or "")
        if name and (name not in latest or created > str(latest[name].get("created_at") or "")):
            latest[name] = run
    attention = sum(
        str(run.get("status")) == "completed" and str(run.get("conclusion")) not in {"success", "skipped", "neutral"}
        for run in latest.values()
    )
    pending = sum(str(run.get("status")) != "completed" for run in latest.values())
    healthy = len(latest) - attention - pending
    status = "healthy" if attention == 0 else "recovering"
    issues: list[dict[str, str]] = []
    for name, run in sorted(latest.items()):
        if str(run.get("status")) != "completed" or str(run.get("conclusion")) in {"success", "skipped", "neutral"}:
            continue
        failed_work = "The automation run did not complete."
        jobs_url = str(run.get("jobs_url") or "")
        if jobs_url:
            try:
                with urlopen(Request(jobs_url, headers=headers), timeout=30) as response:
                    jobs = json.load(response).get("jobs", [])
                failed_jobs = []
                for job in jobs:
                    failed_steps = [
                        str(step.get("name") or "") for step in job.get("steps", [])
                        if str(step.get("conclusion") or "") not in {"", "success", "skipped", "neutral"}
                    ]
                    if failed_steps:
                        failed_jobs.append(f"{job.get('name') or 'Job'} — {', '.join(failed_steps)}")
                    elif str(job.get("conclusion") or "") not in {"success", "skipped", "neutral"}:
                        failed_jobs.append(str(job.get("name") or "Job failed"))
                if failed_jobs:
                    failed_work = "; ".join(failed_jobs)
            except Exception:
                pass
        issues.append({
            "name": name,
            "url": str(run.get("html_url") or ""),
            "result": str(run.get("conclusion") or "needs another attempt").replace("_", " "),
            "failed_work": failed_work,
        })
    return {"status": status, "healthy": healthy, "attention": attention, "pending": pending, "issues": issues}


def report_model(
    root: Path, snapshot_path: Path, report_date: date, health: dict[str, Any],
    marketplace_status_path: Path | None = None,
) -> dict[str, Any]:
    diary = load_json(root / "data" / "business_activity_diary.json", {"entries": []})
    reconciliation = load_json(root / "data" / "affiliate_source_reconciliation.json", {})
    opportunities = load_json(root / "data" / "partner_opportunities.json", {})
    partner_offers = load_json(root / "data" / "partner_offers.json", {"offers": []})
    appsumo = load_json(root / "data" / "appsumo_offers.json", {"offers": []})
    snapshot = load_json(snapshot_path, {})
    marketplace = load_json(marketplace_status_path, {}) if marketplace_status_path else {}
    activity = daily_activity(diary, report_date.isoformat())
    partnerstack = snapshot.get("partnerstack", {})
    impact = snapshot.get("impact", {})
    acquisition = snapshot.get("acquisition", {})
    clicks = partnerstack.get("affiliate_clicks", acquisition.get("clicks", {}))
    visits = acquisition.get("visits", {})
    ps_revenue = integer(partnerstack.get("transactions", {}).get("amount_usd_cents")) / 100
    ps_commission = integer(partnerstack.get("rewards", {}).get("amount_usd_cents")) / 100
    impact_revenue = money_map(impact.get("actions", {}).get("revenue", {}))
    impact_commission = money_map(impact.get("actions", {}).get("commissions", {}))
    summary = reconciliation.get("summary", {})
    published = live_affiliate_destinations(partner_offers, appsumo)
    actions = owner_actions(reconciliation, opportunities, marketplace)
    work_queue = system_work(reconciliation, opportunities)
    social = social_performance(root, report_date)
    revenue_text = f"USD {ps_revenue:.2f} + {impact_revenue}" if impact_revenue != "USD 0.00" else f"USD {ps_revenue:.2f}"
    commission_text = f"USD {ps_commission:.2f} + {impact_commission}" if impact_commission != "USD 0.00" else f"USD {ps_commission:.2f}"
    return {
        "date": report_date,
        "activity": activity,
        "published_offers": published,
        "visits": integer(visits.get("total")),
        "visit_window_days": integer(visits.get("window_days")) or 28,
        "clicks": integer(clicks.get("total")),
        "click_window_days": integer(clicks.get("window_days")) or 28,
        "signups": integer(partnerstack.get("customers", {}).get("count")),
        "paying_customers": integer(partnerstack.get("customers", {}).get("paid_count")),
        "partnerstack_transactions": integer(partnerstack.get("transactions", {}).get("count")),
        "impact_actions": integer(impact.get("actions", {}).get("count")),
        "revenue": revenue_text,
        "commissions": commission_text,
        "owner_actions": actions,
        "system_work": work_queue,
        "social": social,
        "blocking_failures": integer(summary.get("blocking_failures")),
        "health": health,
        "content_orders": integer(marketplace.get("orders_total")),
        "content_fulfilling": integer(marketplace.get("fulfilling")),
        "content_completed": integer(marketplace.get("completed")),
    }


def management_summary(model: dict[str, Any]) -> str:
    activity = model["activity"]
    pieces: list[str] = []
    if activity["pages_created"]:
        pieces.append(f"published {activity['pages_created']} new page{'s' if activity['pages_created'] != 1 else ''}")
    if activity["pages_updated"]:
        pieces.append(f"improved {activity['pages_updated']} existing page{'s' if activity['pages_updated'] != 1 else ''}")
    if activity["social_posts"]:
        pieces.append(f"published {activity['social_posts']} social post{'s' if activity['social_posts'] != 1 else ''}")
    completed = ", ".join(pieces) if pieces else "made no new public website or social-media publication"
    return (
        f"Today the automated system {completed}. "
        f"The website currently publishes {model['published_offers']} different live, tracked affiliate destination links. "
        f"During the last {model.get('visit_window_days', 28)} days it received {model['visits']} visits, and during the last "
        f"{model.get('click_window_days', 28)} days visitors clicked an affiliate link {model['clicks']} times. "
        f"Since partner tracking began, PartnerStack reports {model['signups']} referred sign-up{'s' if model['signups'] != 1 else ''}, "
        f"including {model['paying_customers']} confirmed paying customer{'s' if model['paying_customers'] != 1 else ''}; "
        f"Impact reports {model['impact_actions']} tracked lead or sale event{'s' if model['impact_actions'] != 1 else ''}. "
        f"Sponsored-content orders: {model.get('content_fulfilling', 0)} in fulfilment and {model.get('content_completed', 0)} completed."
    )


def metric_card(label: str, value: str, background: str) -> str:
    return (
        f"<td width='25%' style='padding:6px;vertical-align:top'><div style='background:{background};"
        "border-radius:16px;padding:18px;min-height:82px'>"
        f"<div style='font-size:12px;color:#667085;text-transform:uppercase;letter-spacing:.6px'>{escape(label)}</div>"
        f"<div style='font-size:24px;font-weight:800;color:#182230;margin-top:8px'>{escape(value)}</div></div></td>"
    )


def readable_social_metrics(values: dict[str, Any] | None) -> str:
    if values is None:
        return "Engagement metrics are not available from the platform with the current API permission."
    labels = (
        ("likes", "likes"), ("comments", "comments"), ("reposts", "reposts/shares"),
        ("quotes", "quotes"), ("views", "views"), ("clicks", "post clicks"),
    )
    return " · ".join(f"{integer(values.get(key))} {label}" for key, label in labels if key in values)


def render_social(social: dict[str, list[dict[str, Any]]]) -> tuple[str, str]:
    names = {"linkedin": "LinkedIn", "bluesky": "Bluesky", "x": "X"}
    platform_html: list[str] = []
    platform_text: list[str] = []
    for platform in SOCIAL_PLATFORMS:
        posts = social.get(platform, [])
        platform_text.append(names[platform])
        if not posts:
            platform_html.append(
                f"<div style='margin:0 0 16px'><strong>{names[platform]}</strong>"
                "<div style='color:#667085;font-size:13px;margin-top:4px'>No automated post was published today.</div></div>"
            )
            platform_text.append("- No automated post was published today.")
            continue
        rows = []
        for post in posts:
            title = escape(post["title"])
            url = escape(post["url"])
            metrics = escape(readable_social_metrics(post.get("metrics")))
            rows.append(
                "<div style='background:#fff;border:1px solid #e8e3f3;border-radius:13px;padding:13px 15px;margin-top:9px'>"
                f"<a href='{url}' style='font-weight:800;color:#4737a8;text-decoration:none'>{title} →</a>"
                f"<div style='font-size:12px;color:#667085;margin-top:7px'>{metrics}</div></div>"
            )
            platform_text.append(f"- {post['title']}: {post['url']} — {readable_social_metrics(post.get('metrics'))}")
        platform_html.append(f"<div style='margin:0 0 18px'><strong>{names[platform]}</strong>{''.join(rows)}</div>")
    html = (
        '<tr><td style="padding:12px 30px"><div style="background:#f1edff;border-radius:18px;padding:22px">'
        '<h2 style="font-size:18px;margin:0 0 14px">Social media published today</h2>'
        '<p style="font-size:13px;color:#667085;margin:0 0 16px">Open any post directly and compare its live engagement.</p>'
        + "".join(platform_html) + "</div></td></tr>"
    )
    return html, "\n".join(platform_text)


def render(model: dict[str, Any]) -> tuple[str, str, str]:
    day = model["date"]
    pretty_date = day.strftime("%d %B %Y")
    subject = f"Artificial.One daily business brief — {pretty_date}"
    action_count = len(model["owner_actions"])
    summary = management_summary(model)
    social_html, social_text = render_social(model.get("social") or {})
    highlights = model["activity"]["highlights"]
    if highlights:
        highlight_html = "".join(
            "<li style='margin:0 0 10px'>" +
            (f"<a href='{escape(item['url'])}' style='color:#4737a8;text-decoration:none;font-weight:700'>{escape(item['text'])}</a>" if item["url"] else escape(item["text"])) +
            "</li>" for item in highlights
        )
        highlights_text = "\n".join(f"- {item['text']}" for item in highlights)
    else:
        highlight_html = "<li>No new public webpage or social-media post was published today.</li>"
        highlights_text = "- No new public webpage or social-media post was published today."

    if action_count:
        shown = model["owner_actions"]
        action_html = "".join(
            "<tr><td style='padding:12px 0;border-bottom:1px solid #f1d7b7'>"
            f"<div style='font-weight:800;color:#7a3f00'>{escape(action['title'])}</div>"
            f"<div style='font-size:13px;color:#7b6653;margin:5px 0 10px'>{escape(action['detail'])}</div>"
            f"<a href='{escape(action['url'])}' style='display:inline-block;background:#7c5cff;color:white;text-decoration:none;"
            "font-weight:700;border-radius:10px;padding:9px 14px'>Open the exact program</a></td></tr>"
            for action in shown
        )
        action_intro = f"{action_count} decision{'s' if action_count != 1 else ''} need your approval"
        action_text = "\n".join(f"- {item['title']}: {item['url']}" for item in shown)
    else:
        action_intro = "No action required from you today"
        action_html = "<tr><td style='padding:8px 0;color:#315c49'>No decisions are waiting for you.</td></tr>"
        action_text = "- No action required from you today. No decisions are waiting for you."

    health = model["health"]
    issues = health.get("issues") or []
    if issues:
        issue_rows = "".join(
            f"<li style='margin-bottom:8px'><strong>{escape(item['name'])}</strong>: {escape(item.get('failed_work') or item['result'])}. "
            + (f"<a href='{escape(item['url'])}' style='color:#4737a8'>Open details</a>" if item.get("url") else "")
            + " The system will retry; no action from you is currently required.</li>"
            for item in issues
        )
        health_title = "Automated work that did not finish"
        health_detail = "; ".join(f"{item['name']}: {item.get('failed_work') or item['result']}" for item in issues)
        health_html = f"<div style='background:#fff3df;border-radius:18px;padding:20px'><div style='font-weight:800'>{health_title}</div><ul style='color:#52606d;font-size:13px'>{issue_rows}</ul></div>"
    else:
        health_title = "All business automations finished normally"
        health_detail = "No automated business process needs attention."
        health_html = f"<div style='background:#e9f8f1;border-radius:18px;padding:20px'><div style='font-weight:800'>{health_title}</div></div>"

    work = model.get("system_work") or []
    if work:
        work_rows = "".join(
            f"<li style='margin-bottom:10px'><strong>{escape(item['title'])}</strong> — {escape(item['detail'])}</li>"
            for item in work
        )
        work_html = f'''<tr><td style="padding:12px 30px"><div style="background:#eef3ff;border-radius:18px;padding:22px"><h2 style="font-size:18px;margin:0 0 12px">Approved partnerships being published</h2><ul style="padding-left:20px;margin:0;color:#475467">{work_rows}</ul></div></td></tr>'''
        work_text = "\n".join(f"- {item['title']}: {item['detail']}" for item in work)
    else:
        work_html = ""
        work_text = "- None."

    html = f"""<!doctype html>
<html><body style="margin:0;background:#f4f1fb;font-family:Arial,Helvetica,sans-serif;color:#182230">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f1fb"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="760" cellspacing="0" cellpadding="0" style="width:100%;max-width:760px;background:#ffffff;border-radius:24px;overflow:hidden;box-shadow:0 10px 30px rgba(55,35,110,.08)">
<tr><td style="padding:32px;background:linear-gradient(135deg,#eee7ff,#e5f8ef)">
  <div style="font-size:13px;font-weight:800;letter-spacing:1px;color:#6448c8">ARTIFICIAL.ONE</div>
  <h1 style="margin:10px 0 5px;font-size:30px;line-height:1.15">Daily business brief</h1>
  <div style="color:#667085">{escape(pretty_date)} · one report, only business outcomes</div>
</td></tr>
<tr><td style="padding:28px 30px 10px"><h2 style="font-size:19px;margin:0 0 10px">Executive summary</h2><p style="margin:0;color:#475467;line-height:1.65">{escape(summary)}</p></td></tr>
<tr><td style="padding:14px 24px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
  {metric_card('Revenue', model['revenue'], '#f1edff')}
  {metric_card('Commissions', model['commissions'], '#fff3df')}
  {metric_card(f"Site visits · last {model.get('visit_window_days', 28)} days", str(model['visits']), '#e9f8f1')}
  {metric_card(f"Affiliate clicks · last {model.get('click_window_days', 28)} days", str(model['clicks']), '#eaf3ff')}
</tr></table></td></tr>
<tr><td style="padding:12px 30px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
  <td style="background:#f7f5fd;border-radius:18px;padding:22px"><h2 style="font-size:18px;margin:0 0 13px">What the system delivered today</h2><ul style="padding-left:20px;margin:0;color:#475467;line-height:1.5">{highlight_html}</ul></td>
</tr></table></td></tr>
{social_html}
<tr><td style="padding:12px 30px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
  <td style="background:#fff8ea;border-radius:18px;padding:22px"><h2 style="font-size:18px;margin:0 0 4px">{escape(action_intro)}</h2>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{action_html}</table></td>
</tr></table></td></tr>
<tr><td style="padding:0 30px 12px"><div style="background:#eef3ff;border-radius:14px;padding:14px 18px;color:#475467;font-size:13px;line-height:1.5">
  <strong style="color:#26324a">How to read these numbers:</strong> {model['published_offers']} is the number of different tracked affiliate destinations currently available on the website. {model['clicks']} is how many times visitors clicked any of those links during the last {model.get('click_window_days', 28)} days. These numbers measure inventory and traffic, so they are not expected to match.
</div></td></tr>
<tr><td style="padding:0 30px 12px"><div style="background:#e9f8f1;border-radius:14px;padding:14px 18px;color:#315c49;font-size:13px;line-height:1.55">
  <strong>Results reported by affiliate networks · since tracking began</strong><br>
  PartnerStack referred sign-ups: <strong>{model['signups']}</strong> · confirmed paying customers: <strong>{model['paying_customers']}</strong> · recorded transactions: <strong>{model.get('partnerstack_transactions', 0)}</strong><br>
  Impact tracked lead or sale events: <strong>{model['impact_actions']}</strong>
</div></td></tr>
{work_html}
<tr><td style="padding:12px 30px 30px">{health_html}</td></tr>
<tr><td style="background:#26203b;color:#d9d3eb;padding:22px 30px;font-size:12px;line-height:1.6">
  Prepared automatically for senior-management review. Financial figures are aggregate and contain no customer identities.<br>
  <a href="https://artificial.one/" style="color:#bba8ff">Open artificial.one</a>
</td></tr></table></td></tr></table></body></html>"""

    text = "\n".join([
        "ARTIFICIAL.ONE — DAILY BUSINESS BRIEF", pretty_date, "", "EXECUTIVE SUMMARY", summary, "",
        "KEY NUMBERS",
        f"Revenue: {model['revenue']}", f"Commissions: {model['commissions']}",
        f"Site visits (last {model.get('visit_window_days', 28)} days): {model['visits']}",
        f"Outbound affiliate clicks (last {model.get('click_window_days', 28)} days): {model['clicks']}",
        f"Different live tracked affiliate destinations currently on the website: {model['published_offers']}",
        f"PartnerStack referred sign-ups (since tracking began): {model['signups']}",
        f"PartnerStack confirmed paying customers (since tracking began): {model['paying_customers']}",
        f"PartnerStack recorded transactions (since tracking began): {model.get('partnerstack_transactions', 0)}",
        f"Impact tracked lead or sale events (since tracking began): {model['impact_actions']}", "",
        "DELIVERED TODAY", highlights_text, "", "SOCIAL MEDIA PUBLISHED TODAY", social_text, "", "YOUR ACTIONS", action_text, "",
        "APPROVED PARTNERSHIPS BEING PUBLISHED", work_text, "",
        "AUTOMATION STATUS", health_title, health_detail,
    ]) + "\n"
    return subject, text, html


def send_email(api_key: str, sender: str, recipient: str, subject: str, text: str, html: str) -> None:
    payload = json.dumps({"from": sender, "to": [recipient], "subject": subject, "text": text, "html": html}).encode()
    request = Request(RESEND_URL, data=payload, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "User-Agent": "artificial.one-daily-report/1.0",
    }, method="POST")
    with urlopen(request, timeout=40) as response:
        if response.status >= 300:
            raise RuntimeError(f"Daily report delivery failed with HTTP {response.status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path(".daily-executive/affiliate-snapshot.json"))
    parser.add_argument("--state", type=Path, default=Path(".daily-executive/state.json"))
    parser.add_argument("--marketplace-status", type=Path, default=Path(".content-marketplace/status.json"))
    parser.add_argument("--email-to", default="")
    parser.add_argument("--email-from", default="Artificial.One Daily Brief <onboarding@resend.dev>")
    parser.add_argument("--date", default="")
    parser.add_argument("--output-html", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    now = datetime.now(PRAGUE)
    report_date = date.fromisoformat(args.date) if args.date else now.date()
    state = load_json(args.state, {})
    if args.email_to and not args.force and state.get("last_sent_date") == report_date.isoformat():
        print(f"Daily executive report already sent for {report_date.isoformat()}.")
        return 0
    health = github_health(os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", ""), now)
    model = report_model(ROOT, args.snapshot, report_date, health, args.marketplace_status)
    subject, text, html = render(model)
    if args.output_html:
        args.output_html.parent.mkdir(parents=True, exist_ok=True)
        args.output_html.write_text(html, encoding="utf-8")
    if args.email_to:
        api_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("RESEND_API_KEY is required to send the daily report")
        send_email(api_key, args.email_from, args.email_to, subject, text, html)
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps({
            "last_sent_date": report_date.isoformat(),
            "last_sent_at": now.isoformat(timespec="seconds"),
            "subject": subject,
        }, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared executive report for {report_date.isoformat()}: {subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
