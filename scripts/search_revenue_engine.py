#!/usr/bin/env python3
"""Run the guarded Search Console -> affiliate revenue optimization loop."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

try:
    from scripts.growth_search_console import (
        GrowthError,
        affiliate_paths,
        authorized_session,
        build_opportunities,
        load_service_account,
        query_search_analytics,
        send_email,
        submit_sitemap,
    )
except ModuleNotFoundError:  # Direct execution
    from growth_search_console import (  # type: ignore
        GrowthError,
        affiliate_paths,
        authorized_session,
        build_opportunities,
        load_service_account,
        query_search_analytics,
        send_email,
        submit_sitemap,
    )


ROOT = Path(__file__).resolve().parents[1]
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
REVENUE_STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
PUBLIC_STRATEGY_PATH = ROOT / "data" / "search_growth_strategy.json"
INSPECTION_API = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
MIN_QUERY_IMPRESSIONS = 20
MIN_EXPERIMENT_IMPRESSIONS = 80
EXPERIMENT_DAYS = 14
MAX_EXPERIMENT_DAYS = 28
MAX_NEW_EXPERIMENTS = 3
MAX_INSPECTIONS = 40
CONTENT_PRIORITY_DAYS = 7
MIN_DEMAND_PAGE_IMPRESSIONS = 30
MAX_DEMAND_PAGES = 12
MAX_CRAWL_PRIORITY = 40
CTR_WIN_RATIO = 1.10
CTR_REVERT_RATIO = 0.80
POSITION_REVERT_DELTA = 2.0


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default)
    return value if isinstance(value, dict) else dict(default)


def page_path(url: str) -> str:
    parsed = urlparse(url)
    return "/" + parsed.path.lstrip("/")


def revenue_weights() -> dict[str, float]:
    registry = load_json(OFFERS_PATH, {"offers": []})
    strategy = load_json(REVENUE_STRATEGY_PATH, {"ranking": []})
    ranking = [str(item) for item in strategy.get("ranking", [])]
    position = {offer_id: index for index, offer_id in enumerate(ranking)}
    result: dict[str, float] = {}
    for offer in registry.get("offers", []):
        if not isinstance(offer, dict) or offer.get("status") != "published":
            continue
        offer_id = str(offer.get("id", ""))
        slug = str(offer.get("slug", ""))
        rank = position.get(offer_id, len(position))
        # The daily revenue optimizer already blends anonymous impressions,
        # clicks, signups, customers, transaction value and commission value.
        result[f"/partner-offers/{slug}.html"] = max(1.0, 2.6 - rank * 0.06)
    return result


def revenue_weighted_opportunities(
    rows: list[dict[str, Any]], monetized: set[str], weights: dict[str, float]
) -> list[dict[str, Any]]:
    opportunities = build_opportunities(rows, monetized, limit=250)
    commercial_terms = ("alternative", "best ", "compare", "comparison", "coupon", "discount", "pricing", "price", "review", " vs ")
    for item in opportunities:
        path = page_path(str(item["page"]))
        query = f" {str(item['query']).casefold()} "
        intent_boost = 1.35 if any(term in query for term in commercial_terms) else 1.0
        if intent_boost > 1:
            item["commercial"] = True
        item["score"] = round(float(item["score"]) * weights.get(path, 1.0) * intent_boost, 2)
    return sorted(opportunities, key=lambda item: (-float(item["score"]), -int(item["impressions"])))[:50]


def aggregate_pages(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "position_total": 0.0})
    for row in rows:
        keys = row.get("keys", [])
        if not isinstance(keys, list) or not keys:
            continue
        path = page_path(str(keys[0]))
        impressions = max(0.0, float(row.get("impressions") or 0))
        totals[path]["clicks"] += max(0.0, float(row.get("clicks") or 0))
        totals[path]["impressions"] += impressions
        totals[path]["position_total"] += max(0.0, float(row.get("position") or 0)) * impressions
    result: dict[str, dict[str, float]] = {}
    for path, metrics in totals.items():
        impressions = metrics["impressions"]
        if impressions:
            result[path] = {
                "clicks": metrics["clicks"],
                "impressions": impressions,
                "ctr": metrics["clicks"] / impressions,
                "position": metrics["position_total"] / impressions,
            }
    return result


def load_public_strategy(path: Path) -> dict[str, Any]:
    value = load_json(path, {})
    if value.get("version") != 1 or not isinstance(value.get("experiments"), dict):
        return {
            "version": 1,
            "method": "guarded-search-snippet-experiments",
            "experiments": {},
            "content_priority": [],
            "demand_pages": [],
            "crawl_priority": [],
            "privacy": "No queries, traffic totals, customer data or revenue totals are published.",
        }
    return value


def update_crawl_priority(
    inspections: list[dict[str, str]], public: dict[str, Any], today: date
) -> list[str]:
    """Expose only affected local paths so the site can strengthen discovery safely."""
    eligible_prefixes = ("/partner-offers/", "/search-intent/", "/calculators/")
    eligible_exact = {
        "/",
        "/ai-tool-finder.html",
        "/ai-stack-builder.html",
        "/appsumo-ai-tools.html",
        "/buyers-guides.html",
        "/decision-tools.html",
        "/partner-offers.html",
    }
    selected: list[str] = []
    for item in inspections:
        if item.get("status") != "ISSUE":
            continue
        path = page_path(str(item.get("url") or ""))
        if path not in eligible_exact and not path.startswith(eligible_prefixes):
            continue
        if path not in selected:
            selected.append(path)
        if len(selected) >= MAX_CRAWL_PRIORITY:
            break
    previous = [str(item) for item in public.get("crawl_priority", [])]
    if selected == previous:
        return []
    public["crawl_priority"] = selected
    public["updated_at"] = today.isoformat()
    if selected:
        return [f"Prioritized {len(selected)} affected commercial URLs for stronger internal discovery."]
    return ["Cleared the crawl-priority queue after priority URLs passed inspection."]


def _search_tokens(value: str) -> set[str]:
    stop = {"and", "best", "for", "from", "how", "software", "the", "tool", "tools", "use", "using", "with"}
    return {item for item in re.findall(r"[a-z0-9]+", value.casefold()) if len(item) > 2 and item not in stop}


def demand_catalog() -> dict[str, dict[str, Any]]:
    """Return reviewed page concepts; raw Search Console queries never become copy."""
    registry = load_json(OFFERS_PATH, {"offers": []})
    result: dict[str, dict[str, Any]] = {}
    for offer in registry.get("offers", []):
        if not isinstance(offer, dict) or offer.get("status") != "published":
            continue
        for index, use_case in enumerate(offer.get("use_cases", [])):
            concept_id = f"{offer.get('id')}-use-case-{index + 1}"
            result[concept_id] = {
                "offer_id": str(offer.get("id") or ""),
                "offer_slug": str(offer.get("slug") or ""),
                "offer_tokens": _search_tokens(str(offer.get("name") or "")),
                "use_case_tokens": _search_tokens(str(use_case)),
            }
    return result


def update_demand_pages(
    rows: list[dict[str, Any]], public: dict[str, Any], private: dict[str, Any], today: date
) -> list[str]:
    """Activate only reviewed concepts when aggregate search demand clears a gate."""
    catalog = demand_catalog()
    totals: dict[str, int] = defaultdict(int)
    for row in rows:
        keys = row.get("keys", [])
        if not isinstance(keys, list) or len(keys) < 2:
            continue
        page = page_path(str(keys[0]))
        query_tokens = _search_tokens(str(keys[1]))
        impressions = max(0, int(float(row.get("impressions") or 0)))
        if not query_tokens or not impressions:
            continue
        for concept_id, concept in catalog.items():
            page_matches = concept["offer_slug"] and concept["offer_slug"] in page
            offer_matches = bool(concept["offer_tokens"] & query_tokens)
            use_case_overlap = len(concept["use_case_tokens"] & query_tokens)
            if (page_matches or offer_matches) and use_case_overlap >= 2:
                totals[concept_id] += impressions
    eligible = [item for item, count in sorted(totals.items(), key=lambda pair: (-pair[1], pair[0])) if count >= MIN_DEMAND_PAGE_IMPRESSIONS]
    current = [str(item) for item in public.get("demand_pages", []) if str(item) in catalog]
    selected = current[:]
    for item in eligible:
        if item not in selected:
            selected.append(item)
        if len(selected) >= MAX_DEMAND_PAGES:
            break
    private["demand_page_signals"] = {item: {"impressions": totals[item], "observed_on": today.isoformat()} for item in eligible}
    if selected == current:
        return []
    public["demand_pages"] = selected
    public["updated_at"] = today.isoformat()
    return [f"Activated {len(selected) - len(current)} reviewed commercial page concept(s) from aggregate demand."]


def offer_ids_by_path() -> dict[str, str]:
    registry = load_json(OFFERS_PATH, {"offers": []})
    return {
        f"/partner-offers/{item['slug']}.html": str(item["id"])
        for item in registry.get("offers", [])
        if isinstance(item, dict) and item.get("status") == "published" and item.get("slug") and item.get("id")
    }


def update_content_priority(
    opportunities: list[dict[str, Any]], public: dict[str, Any], private: dict[str, Any], today: date
) -> list[str]:
    """Publish only offer IDs selected by demand, never queries or metrics."""
    last_update = private.get("content_priority_updated_on")
    try:
        if last_update and (today - date.fromisoformat(str(last_update))).days < CONTENT_PRIORITY_DAYS:
            return []
    except ValueError:
        pass
    mapping = offer_ids_by_path()
    selected: list[str] = []
    for item in opportunities:
        if int(item.get("impressions") or 0) < MIN_EXPERIMENT_IMPRESSIONS:
            continue
        offer_id = mapping.get(page_path(str(item.get("page") or "")))
        if offer_id and offer_id not in selected:
            selected.append(offer_id)
        if len(selected) >= 8:
            break
    if not selected or selected == public.get("content_priority", []):
        return []
    public["content_priority"] = selected
    public["updated_at"] = today.isoformat()
    private["content_priority_updated_on"] = today.isoformat()
    return [f"Updated the public-safe build priority for {len(selected)} partner pages from aggregate search demand."]


def update_experiments(
    rows: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    weights: dict[str, float],
    public: dict[str, Any],
    private: dict[str, Any],
    today: date,
) -> list[str]:
    actions: list[str] = []
    original_public = json.dumps(public.get("experiments", {}), sort_keys=True)
    metrics = aggregate_pages(rows)
    public_experiments = public.setdefault("experiments", {})
    private_experiments = private.setdefault("experiments", {})

    # Reconcile state if a previous run persisted its private cache but was
    # interrupted before the privacy-safe strategy commit.
    for path, record in private_experiments.items():
        if not isinstance(record, dict) or path in public_experiments:
            continue
        status = str(record.get("status") or "")
        if status == "running":
            public_experiments[path] = {"variant": "commercial", "status": "running"}
        elif status == "winner":
            public_experiments[path] = {"variant": "commercial", "status": "winner"}
        elif status in {"reverted", "complete"}:
            winner = str(record.get("winner") or "control")
            public_experiments[path] = {
                "variant": winner,
                "status": "winner" if winner == "commercial" else "reverted",
            }

    for path, record in list(private_experiments.items()):
        if not isinstance(record, dict) or record.get("status") != "running":
            continue
        current = metrics.get(path)
        if not current or current["impressions"] < MIN_EXPERIMENT_IMPRESSIONS:
            continue
        try:
            age = (today - date.fromisoformat(str(record["started_on"]))).days
        except (KeyError, ValueError):
            continue
        if age < EXPERIMENT_DAYS:
            continue
        baseline_ctr = max(float(record.get("baseline_ctr") or 0), 0.0001)
        baseline_position = float(record.get("baseline_position") or current["position"])
        ctr_ratio = current["ctr"] / baseline_ctr
        ranking_drop = current["position"] - baseline_position
        if ctr_ratio < CTR_REVERT_RATIO or ranking_drop > POSITION_REVERT_DELTA:
            record["status"] = "reverted"
            record["winner"] = "control"
            public_experiments[path] = {"variant": "control", "status": "reverted"}
            actions.append(f"Reverted {path}: performance crossed a safety threshold.")
        elif ctr_ratio >= CTR_WIN_RATIO and ranking_drop <= 1.0:
            record["status"] = "winner"
            record["winner"] = "commercial"
            public_experiments[path] = {"variant": "commercial", "status": "winner"}
            actions.append(f"Kept winning commercial snippet for {path}.")
        elif age >= MAX_EXPERIMENT_DAYS:
            record["status"] = "complete"
            winner = "commercial" if ctr_ratio >= 1.0 and ranking_drop <= 1.0 else "control"
            record["winner"] = winner
            public_experiments[path] = {"variant": winner, "status": "winner" if winner == "commercial" else "reverted"}
            actions.append(f"Closed {path} experiment with {winner} copy.")

    eligible: list[str] = []
    seen: set[str] = set()
    for item in opportunities:
        path = page_path(str(item["page"]))
        current = metrics.get(path)
        if (
            path in weights
            and path not in private_experiments
            and path not in seen
            and current
            and current["impressions"] >= MIN_EXPERIMENT_IMPRESSIONS
            and 3 <= current["position"] <= 20
        ):
            eligible.append(path)
            seen.add(path)
    for path in eligible[:MAX_NEW_EXPERIMENTS]:
        current = metrics[path]
        private_experiments[path] = {
            "status": "running",
            "variant": "commercial",
            "started_on": today.isoformat(),
            "baseline_ctr": round(current["ctr"], 8),
            "baseline_position": round(current["position"], 3),
            "baseline_impressions": int(current["impressions"]),
        }
        public_experiments[path] = {"variant": "commercial", "status": "running"}
        actions.append(f"Started guarded commercial-snippet experiment for {path}.")

    if json.dumps(public_experiments, sort_keys=True) != original_public:
        public["updated_at"] = today.isoformat()
    private["updated_at"] = datetime.now(timezone.utc).isoformat()
    return actions


def inspection_targets(site_url: str, weights: dict[str, float]) -> list[str]:
    base = site_url.rstrip("/")
    priorities = ["/", "/ai-tool-finder.html", "/partner-offers.html"]
    priorities.extend(path for path, _ in sorted(weights.items(), key=lambda item: -item[1]))
    search_pages = sorted((ROOT / "search-intent").glob("*.html")) if (ROOT / "search-intent").exists() else []
    priorities.extend("/" + page.relative_to(ROOT).as_posix() for page in search_pages)
    unique: list[str] = []
    for path in priorities:
        url = base + (path if path.startswith("/") else "/" + path)
        if url not in unique:
            unique.append(url)
    return unique[:MAX_INSPECTIONS]


def _canonical_key(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    return parsed.netloc.casefold().removeprefix("www."), parsed.path.rstrip("/") or "/"


def inspect_urls(session: Any, site_url: str, urls: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for url in urls:
        try:
            response = session.post(INSPECTION_API, json={"inspectionUrl": url, "siteUrl": site_url}, timeout=35)
            if response.status_code >= 400:
                results.append({"url": url, "status": "API_ERROR", "detail": f"HTTP {response.status_code}"})
                continue
            inspection = response.json().get("inspectionResult", {})
            index = inspection.get("indexStatusResult", {}) if isinstance(inspection, dict) else {}
            problems: list[str] = []
            verdict = str(index.get("verdict") or "UNKNOWN")
            if verdict != "PASS":
                problems.append(str(index.get("coverageState") or verdict))
            for field, good in (("robotsTxtState", "ALLOWED"), ("indexingState", "INDEXING_ALLOWED"), ("pageFetchState", "SUCCESSFUL")):
                value = str(index.get(field) or "")
                if value and value != good:
                    problems.append(f"{field}={value}")
            google_canonical = str(index.get("googleCanonical") or "")
            user_canonical = str(index.get("userCanonical") or "")
            if google_canonical and user_canonical and _canonical_key(google_canonical) != _canonical_key(user_canonical):
                problems.append("Google-selected canonical differs")
            results.append(
                {
                    "url": url,
                    "status": "PASS" if not problems else "ISSUE",
                    "detail": "; ".join(problems) or "Indexed and crawlable",
                    "last_crawl": str(index.get("lastCrawlTime") or "Not yet crawled"),
                    "rich_results": str((inspection.get("richResultsResult") or {}).get("verdict") or "UNKNOWN") if isinstance(inspection, dict) else "UNKNOWN",
                }
            )
        except Exception as exc:  # One URL must not prevent the remaining audit.
            results.append({"url": url, "status": "API_ERROR", "detail": type(exc).__name__})
    return results


def inspection_signature(results: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"url": item["url"], "status": item["status"], "detail": item["detail"]} for item in results if item["status"] != "PASS"]


def render_report(
    opportunities: list[dict[str, Any]], inspections: list[dict[str, str]], actions: list[str], start: date, end: date
) -> tuple[str, str, str]:
    issues = [item for item in inspections if item["status"] != "PASS"]
    subject = f"Artificial.One search revenue engine — {end.isoformat()}"
    summary = f"Analyzed {start.isoformat()}–{end.isoformat()}: {len(opportunities)} revenue-weighted search opportunities, {len(inspections)} inspected URLs, {len(issues)} indexing/API issues, {len(actions)} SEO experiment actions."
    text_lines = [subject, "", summary, "", "INDEX AUDIT"]
    text_lines.extend(
        f"- {item['status']}: {item['url']} — {item['detail']}; last crawl {item.get('last_crawl', 'unknown')}; rich results {item.get('rich_results', 'unknown')}"
        for item in inspections[:MAX_INSPECTIONS]
    )
    if not inspections:
        text_lines.append("- No URL was inspected.")
    text_lines.extend(["", "SEO EXPERIMENTS"])
    text_lines.extend(f"- {item}" for item in actions or ["No experiment changed today."])
    text_lines.extend(["", "TOP REVENUE-WEIGHTED OPPORTUNITIES"])
    text_lines.extend(
        f"- {item['query']} — position {item['position']}, {item['impressions']} impressions, gap {item['estimated_click_gap']} — {item['page']}"
        for item in opportunities[:20]
    )
    if not opportunities:
        text_lines.append("- Search Console has not accumulated enough eligible data yet.")
    text_lines.extend(["", "PRIVACY", "Raw queries and performance baselines remain in the private workflow/email. No customer identity or private total is committed to the public repository."])

    issue_rows = "".join(f"<tr><td>{escape(item['status'])}</td><td>{escape(item['url'])}</td><td>{escape(item['detail'])}</td><td>{escape(item.get('last_crawl', 'unknown'))}</td><td>{escape(item.get('rich_results', 'unknown'))}</td></tr>" for item in inspections[:MAX_INSPECTIONS]) or "<tr><td colspan='5'>No URL was inspected.</td></tr>"
    opportunity_rows = "".join(f"<tr><td>{escape(str(item['query']))}</td><td>{item['position']}</td><td>{item['impressions']}</td><td>{item['estimated_click_gap']}</td><td>{'Revenue' if item['commercial'] else 'Audience'}</td></tr>" for item in opportunities[:20]) or "<tr><td colspan='5'>Not enough eligible data yet.</td></tr>"
    action_rows = "".join(f"<li>{escape(item)}</li>" for item in actions) or "<li>No experiment changed today.</li>"
    style = "border-collapse:collapse;width:100%;font-size:13px"
    cell = "<style>th,td{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left}</style>"
    html = f'''<!doctype html><html><body style="font-family:Arial,sans-serif;color:#101828;line-height:1.5;max-width:880px;margin:auto;padding:24px">{cell}
      <h1>Artificial.One search revenue engine</h1><p>{escape(summary)}</p>
      <h2>Index audit</h2><table style="{style}"><tr><th>Status</th><th>URL</th><th>Detail</th><th>Last crawl</th><th>Rich results</th></tr>{issue_rows}</table>
      <h2>SEO experiments</h2><ul>{action_rows}</ul>
      <h2>Revenue-weighted opportunities</h2><table style="{style}"><tr><th>Query</th><th>Position</th><th>Impressions</th><th>Click gap</th><th>Path</th></tr>{opportunity_rows}</table>
      <p style="color:#667085;font-size:12px">Private aggregate search telemetry only. No customer identities are included or published.</p>
    </body></html>'''
    return subject, "\n".join(text_lines) + "\n", html


def write_if_changed(path: Path, value: dict[str, Any]) -> bool:
    encoded = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    if previous == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=os.environ.get("GSC_SITE_URL") or "https://www.artificial.one/")
    parser.add_argument("--sitemap", default="https://www.artificial.one/sitemap.xml")
    parser.add_argument("--email-to", default="hello@artificial.one")
    parser.add_argument("--email-from", default="Artificial.One Growth <onboarding@resend.dev>")
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--private-state", type=Path, default=ROOT / ".search-growth" / "private-state.json")
    parser.add_argument("--public-strategy", type=Path, default=PUBLIC_STRATEGY_PATH)
    args = parser.parse_args()
    try:
        raw_credentials = os.environ.get("GSC_SERVICE_ACCOUNT_JSON", "").strip()
        session = authorized_session(load_service_account(raw_credentials) if raw_credentials else None)
        end = date.today() - timedelta(days=3)
        start = end - timedelta(days=max(1, args.days) - 1)
        rows = query_search_analytics(session, args.site, start, end)
        weights = revenue_weights()
        opportunities = revenue_weighted_opportunities(rows, affiliate_paths(), weights)
        public = load_public_strategy(args.public_strategy)
        private = load_json(args.private_state, {"version": 1, "experiments": {}, "last_index_issues": []})
        actions = update_experiments(rows, opportunities, weights, public, private, date.today())
        actions.extend(update_content_priority(opportunities, public, private, date.today()))
        actions.extend(update_demand_pages(rows, public, private, date.today()))
        inspections = inspect_urls(session, args.site, inspection_targets(args.site, weights))
        actions.extend(update_crawl_priority(inspections, public, date.today()))
        current_issues = inspection_signature(inspections)
        if current_issues != private.get("last_index_issues", []):
            actions.append(f"Index audit changed: {len(current_issues)} priority URLs currently need attention.")
        private["last_index_issues"] = current_issues
        public_changed = write_if_changed(args.public_strategy, public)
        write_if_changed(args.private_state, private)
        submit_sitemap(session, args.site, args.sitemap)
        resend_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not resend_key:
            raise GrowthError("RESEND_API_KEY is not configured")
        subject, text, html = render_report(opportunities, inspections, actions, start, end)
        send_email(resend_key, args.email_from, args.email_to, subject, text, html)
        github_output = os.environ.get("GITHUB_OUTPUT", "")
        if github_output:
            with Path(github_output).open("a", encoding="utf-8") as handle:
                handle.write(f"public_changed={'true' if public_changed else 'false'}\n")
                handle.write(f"opportunities={len(opportunities)}\nissues={len(current_issues)}\nactions={len(actions)}\n")
        print(f"Analyzed {len(rows)} rows, inspected {len(inspections)} URLs, found {len(opportunities)} opportunities, took {len(actions)} guarded actions.")
        return 0
    except GrowthError as exc:
        print(f"Search revenue engine failed: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
