#!/usr/bin/env python3
"""Build a safe, source-linked AI news feed from approved RSS/Atom feeds."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "data" / "ai_news_sources.json"
DATA_PATH = ROOT / "data" / "ai_news.json"
INDEX_PATH = ROOT / "index.html"
NEWS_PATH = ROOT / "news.html"
SITEMAP_PATH = ROOT / "sitemap.xml"
PARTNER_OFFERS_PATH = ROOT / "data" / "partner_offers.json"
REVENUE_STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
DATA_START = "// AI_NEWS_DATA_START"
DATA_END = "// AI_NEWS_DATA_END"
SPACE_RE = re.compile(r"\s+")
TAG_RE = re.compile(r"<[^>]+>")
AI_RELEVANCE_RE = re.compile(
    r"\b(?:ai|artificial intelligence|llms?|openai|anthropic|chatgpt|claude|gemini|"
    r"deepmind|copilot|machine learning|neural|transformers?|generative|multimodal|"
    r"models?|agents?|chatbots?|diffusion|midjourney|elevenlabs|hugging face|"
    r"fine-tun(?:e|ed|ing)|open-weight|automatic1111)\b",
    re.I,
)
NEWS_ROUTE_RULES = (
    (("voice", "audio", "speech", "narration"), ("elevenlabs", "descript")),
    (("video", "podcast", "transcript", "recording"), ("descript", "elevenlabs")),
    (("image", "creative", "advertising", "ad campaign"), ("adcreative", "beautiful-ai")),
    (("presentation", "slides", "deck"), ("beautiful-ai",)),
    (("pdf", "document", "signature", "signing"), ("foxit", "quicksigner")),
    (("website", "landing page", "conversion"), ("unbounce", "wegic")),
    (("newsletter", "email marketing", "creator"), ("kit", "kartra")),
    (("search", "seo", "visibility"), ("rank-prompt", "omniseo")),
    (("vector", "database", "agent", "developer", "model"), ("pinecone",)),
    (("course", "learning", "training", "education"), ("learnworlds", "trainual")),
    (("healthcare", "clinic", "patient"), ("carepatron",)),
)


class NewsBuildError(RuntimeError):
    """Raised when the news feed cannot be updated safely."""


def clean_text(value: str, limit: int = 180) -> str:
    value = TAG_RE.sub(" ", html.unescape(value or ""))
    value = SPACE_RE.sub(" ", value).strip()
    value = "".join(char for char in value if char >= " " or char in "\t\n")
    return value[:limit].rstrip()


def parse_date(value: str) -> datetime | None:
    value = clean_text(value, 100)
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in element:
        local_name = child.tag.rsplit("}", 1)[-1].lower()
        if local_name in names and child.text:
            return child.text
    return ""


def entry_link(element: ET.Element) -> str:
    for child in element:
        if child.tag.rsplit("}", 1)[-1].lower() != "link":
            continue
        href = child.attrib.get("href", "").strip()
        relation = child.attrib.get("rel", "alternate")
        if href and relation in ("alternate", ""):
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def allowed_url(url: str, domains: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    hostname = parsed.hostname.casefold()
    return any(hostname == domain.casefold() or hostname.endswith("." + domain.casefold()) for domain in domains)


def categorize(title: str, description: str) -> str:
    text = f"{title} {description}".casefold()
    groups = (
        ("Models & LLMs", (" llm", "model", "gpt", "claude", "gemini", "llama", "reasoning", "transformer")),
        ("Research", ("research", "paper", "benchmark", "study", "dataset")),
        ("Policy & Safety", ("safety", "security", "regulation", "copyright", "lawsuit", "policy")),
        ("AI Business", ("funding", "acquisition", "revenue", "enterprise", "partnership", "startup")),
    )
    for category, terms in groups:
        if any(term in text for term in terms):
            return category
    return "AI Tools & Products"


def is_ai_relevant(title: str, description: str = "") -> bool:
    return bool(AI_RELEVANCE_RE.search(f"{title} {description}"))


def parse_feed(xml_bytes: bytes, source: dict[str, Any]) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise NewsBuildError(f"{source['name']} returned invalid XML") from exc

    candidates = [
        element
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1].lower() in ("item", "entry")
    ]
    items: list[dict[str, str]] = []
    for element in candidates:
        title = clean_text(child_text(element, ("title",)))
        url = clean_text(entry_link(element), 1000)
        published = parse_date(child_text(element, ("pubdate", "published", "updated", "date")))
        description = clean_text(child_text(element, ("description", "summary", "content")), 500)
        if (
            not title
            or not published
            or not allowed_url(url, source["allowed_domains"])
            or not is_ai_relevant(title, description)
        ):
            continue
        items.append(
            {
                "title": title,
                "url": url,
                "source": str(source["name"]),
                "published_at": published.isoformat(),
                "display_date": published.strftime("%b %d, %Y"),
                "category": categorize(title, description),
            }
        )
    return items


def fetch_source(source: dict[str, Any]) -> list[dict[str, str]]:
    request = Request(
        str(source["feed_url"]),
        headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml", "User-Agent": "artificial.one-news-bot/1.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise NewsBuildError(f"{source['name']} returned HTTP {response.status}")
            return parse_feed(response.read(2_000_000), source)
    except NewsBuildError:
        raise
    except Exception as exc:
        raise NewsBuildError(f"{source['name']} fetch failed: {exc}") from exc


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NewsBuildError(f"Could not read {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise NewsBuildError(f"{path} must be an object with version 1")
    return value


def cached_items() -> list[dict[str, str]]:
    if not DATA_PATH.exists():
        return []
    try:
        data = load_json(DATA_PATH)
    except NewsBuildError:
        return []
    return [item for item in data.get("items", []) if isinstance(item, dict)]


def partner_picks(limit: int = 3) -> list[dict[str, str]]:
    try:
        registry = load_json(PARTNER_OFFERS_PATH)
    except NewsBuildError:
        return []
    published = [
        offer
        for offer in registry.get("offers", [])
        if isinstance(offer, dict) and offer.get("status") == "published"
    ]
    try:
        strategy = load_json(REVENUE_STRATEGY_PATH)
        ranking = strategy.get("ranking", [])
    except NewsBuildError:
        ranking = []
    positions = {str(offer_id): index for index, offer_id in enumerate(ranking)}
    published.sort(key=lambda offer: (
        positions.get(str(offer.get("id", "")), len(positions)),
        not bool(offer.get("featured")),
        str(offer.get("name", "")).casefold(),
    ))
    return [
        {
            "name": clean_text(str(offer.get("name", "")), 80),
            "category": clean_text(str(offer.get("category", "")), 80),
            "summary": clean_text(str(offer.get("summary", "")), 220),
            "slug": clean_text(str(offer.get("slug", "")), 100),
        }
        for offer in published[:limit]
        if offer.get("name") and offer.get("slug")
    ]


def related_route(item: dict[str, str], offers: dict[str, dict[str, Any]]) -> dict[str, str]:
    text = f"{item.get('title', '')} {item.get('category', '')}".casefold()
    for terms, offer_ids in NEWS_ROUTE_RULES:
        if not any(term in text for term in terms):
            continue
        for offer_id in offer_ids:
            offer = offers.get(offer_id)
            if offer:
                return {
                    "title": f"Evaluate {clean_text(str(offer['name']), 80)} for this workflow",
                    "url": f"partner-offers/{clean_text(str(offer['slug']), 100)}.html",
                    "offer_id": offer_id,
                }
    fallback = {
        "AI Business": ("Model the value of an AI subscription", "calculators/ai-software-roi-calculator.html"),
        "Policy & Safety": ("Browse independent AI software buying guides", "buyers-guides.html"),
        "Research": ("Find an AI tool for a specific workflow", "ai-tool-finder.html"),
        "Models & LLMs": ("Compare infrastructure and AI workflow tools", "ai-tool-finder.html"),
        "AI Tools & Products": ("Find the right AI tool for the job", "ai-tool-finder.html"),
    }
    title, url = fallback.get(item.get("category", ""), fallback["AI Tools & Products"])
    return {"title": title, "url": url, "offer_id": ""}


def add_related_routes(items: list[dict[str, str]]) -> list[dict[str, Any]]:
    try:
        registry = load_json(PARTNER_OFFERS_PATH)
    except NewsBuildError:
        registry = {"offers": []}
    offers = {
        str(offer.get("id")): offer
        for offer in registry.get("offers", [])
        if isinstance(offer, dict) and offer.get("status") == "published" and offer.get("id") and offer.get("slug")
    }
    return [{**item, "related": related_route(item, offers)} for item in items]


def news_identity(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key != "related"} for item in items]


def aggregate_news(config: dict[str, Any], now: datetime) -> tuple[list[dict[str, str]], list[str]]:
    previous = cached_items()
    cached_by_source: dict[str, list[dict[str, str]]] = {}
    for item in previous:
        cached_by_source.setdefault(str(item.get("source", "")), []).append(item)

    collected: list[dict[str, str]] = []
    failures: list[str] = []
    per_source_limit = int(config.get("per_source_limit", 8))
    for source in config.get("sources", []):
        if not isinstance(source, dict):
            continue
        try:
            source_items = fetch_source(source)
        except NewsBuildError as exc:
            failures.append(str(exc))
            source_items = cached_by_source.get(str(source.get("name", "")), [])
        source_items.sort(key=lambda item: item["published_at"], reverse=True)
        collected.extend(source_items[:per_source_limit])

    cutoff = now - timedelta(days=int(config.get("max_age_days", 45)))
    unique: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    for item in sorted(collected, key=lambda value: value["published_at"], reverse=True):
        published = parse_date(item.get("published_at", ""))
        title_key = re.sub(r"[^a-z0-9]+", " ", item.get("title", "").casefold()).strip()
        url = item.get("url", "")
        if not published or published < cutoff or published > now + timedelta(days=1):
            continue
        if not is_ai_relevant(item.get("title", "")):
            continue
        if not title_key or title_key in seen_titles or url in seen_urls:
            continue
        seen_titles.add(title_key)
        seen_urls.add(url)
        unique.append(item)
    return unique[: int(config.get("max_items", 36))], failures


def safe_json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2).replace("<", "\\u003c")


def update_homepage(items: list[dict[str, str]]) -> str:
    source = INDEX_PATH.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(DATA_START) + r".*?" + re.escape(DATA_END), re.S)
    replacement = f"{DATA_START}\nconst aiNewsItems = {safe_json_for_script(items[:12])};\n{DATA_END}"
    if not pattern.search(source):
        raise NewsBuildError("Homepage news data markers are missing")
    return pattern.sub(replacement, source, count=1)


def render_news_page(
    items: list[dict[str, str]], updated_at: str, picks: list[dict[str, str]] | None = None
) -> str:
    cards = "\n".join(
        f'''      <article class="card">
        <a class="story-link" href="{html.escape(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer">
          <div class="story-visual"><span>{html.escape(item["category"])}</span><strong>{html.escape(item["source"])}</strong></div>
          <div class="story-copy"><div class="meta"><time datetime="{html.escape(item["published_at"], quote=True)}">{html.escape(item["display_date"])}</time><b>Open story ↗</b></div><h2>{html.escape(item["title"])}</h2></div>
        </a>
        <div class="route"><small>RELATED DECISION GUIDE</small><a href="{html.escape(str(item.get('related', {}).get('url', 'ai-tool-finder.html')), quote=True)}" data-content-route data-related-offer-id="{html.escape(str(item.get('related', {}).get('offer_id', '')), quote=True)}" data-placement="news-card-related">{html.escape(str(item.get('related', {}).get('title', 'Find the right AI tool')))} →</a></div>
      </article>'''
        for item in items
    )
    item_list = [
        {"@type": "ListItem", "position": index, "url": item["url"], "name": item["title"]}
        for index, item in enumerate(items, 1)
    ]
    structured = safe_json_for_script({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": item_list})
    pick_cards = "".join(
        f'''<a class="pick" href="partner-offers/{html.escape(pick['slug'], quote=True)}.html"><small>{html.escape(pick['category'])}</small><strong>{html.escape(pick['name'])}</strong><span>{html.escape(pick['summary'])}</span><b>See fit &amp; current offer →</b></a>'''
        for pick in (picks or [])
    )
    picks_section = (
        f'''<section class="picks"><div><small>EDITOR'S PARTNER PICKS</small><h2>Tools worth evaluating now</h2><p>Current, verified partner destinations with clear use cases and limitations.</p></div><div class="pick-grid">{pick_cards}</div><p class="disclosure">Marked offer pages contain affiliate links. We may earn a commission at no extra cost to you.</p></section>'''
        if pick_cards
        else ""
    )
    return f'''<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Latest AI, LLM &amp; AI Tools News | artificial.one</title>
  <meta name="description" content="An automatically refreshed feed of AI, LLM and AI tool headlines from official labs and established technology publications.">
  <link rel="canonical" href="https://artificial.one/news.html">
  <meta name="affiliate-event-endpoint" content="/api/affiliate-event">
  <meta property="og:title" content="Latest AI, LLM &amp; AI Tools News | artificial.one">
  <meta property="og:description" content="Recent AI headlines, linked directly to their original sources.">
  <meta property="og:type" content="website"><meta property="og:url" content="https://artificial.one/news.html">
  <script type="application/ld+json">{structured}</script>
  <style>
    *{{box-sizing:border-box}} body{{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;color:#0f172a;background:#090914}} a{{color:inherit}} header{{position:sticky;top:0;background:rgba(255,255,255,.96);border-bottom:1px solid #e2e8f0;z-index:5}} nav{{max-width:1120px;margin:auto;padding:12px 22px;display:flex;align-items:center;justify-content:space-between;gap:24px}} nav img{{height:48px}} nav div{{display:flex;gap:22px;font-weight:650}} .news-page .hero{{min-height:0!important;background:radial-gradient(circle at 86% 10%,rgba(156,255,59,.18),transparent 18rem),linear-gradient(120deg,#17112c,#101827);text-align:left;padding:30px 22px 32px}} .hero>*{{display:block;max-width:1120px;margin-left:auto;margin-right:auto}} .hero small{{font-weight:900;letter-spacing:.15em;text-transform:uppercase;color:#9cff3b}} .hero h1{{font-size:clamp(2.2rem,5vw,3.8rem);line-height:1;margin-top:8px;margin-bottom:10px;color:#fff}} .hero p{{max-width:1120px;color:#cbd5e1;font-size:1rem;line-height:1.55;margin-top:0;margin-bottom:0}} main{{max-width:1120px;margin:auto;padding:22px 22px 80px}} .notice{{padding:12px 15px;border:1px solid rgba(156,255,59,.3);background:rgba(156,255,59,.08);border-radius:12px;color:#d9f99d;margin-bottom:22px}} .picks{{margin:0 0 32px;padding:26px;border-radius:22px;background:linear-gradient(135deg,#eef2ff,#faf5ff);border:1px solid #c7d2fe}} .picks>div:first-child>small,.pick small{{font-weight:900;letter-spacing:.1em;color:#4f46e5}} .picks h2{{margin:8px 0 4px;color:#0f172a}} .picks p{{color:#475569}} .pick-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:20px}} .pick{{display:flex;flex-direction:column;padding:19px;border-radius:16px;background:linear-gradient(145deg,#fff,#f4f0ff);border:1px solid #ddd6fe;text-decoration:none;box-shadow:0 8px 24px rgba(79,70,229,.08);transition:transform .2s ease,box-shadow .2s ease}} .pick:nth-child(2){{background:linear-gradient(145deg,#ecfeff,#fff)}} .pick:nth-child(3){{background:linear-gradient(145deg,#f7fee7,#fff)}} .pick:hover{{transform:translateY(-4px);box-shadow:0 14px 32px rgba(79,70,229,.18)}} .pick strong{{font-size:1.15rem;margin:8px 0;color:#0f172a}} .pick span{{color:#64748b;font-size:.9rem;line-height:1.5}} .pick b{{color:#4338ca;margin-top:auto;padding-top:15px;font-size:.9rem}} .picks .disclosure{{font-size:.75rem;margin-bottom:0}} .grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}} .card{{--c1:#7c3aed;--c2:#ec4899;display:flex;flex-direction:column;overflow:hidden;background:#fff;border:1px solid rgba(255,255,255,.16);border-radius:20px;box-shadow:0 16px 42px rgba(0,0,0,.28);transition:transform .2s ease,box-shadow .2s ease}} .card:nth-child(6n+2){{--c1:#0f766e;--c2:#22d3ee}} .card:nth-child(6n+3){{--c1:#c2410c;--c2:#fbbf24}} .card:nth-child(6n+4){{--c1:#1d4ed8;--c2:#8b5cf6}} .card:nth-child(6n+5){{--c1:#be123c;--c2:#fb7185}} .card:nth-child(6n+6){{--c1:#166534;--c2:#84cc16}} .card:hover{{transform:translateY(-6px);box-shadow:0 24px 56px rgba(0,0,0,.4)}} .story-link{{display:block;text-decoration:none}} .story-visual{{position:relative;min-height:142px;overflow:hidden;padding:18px;background:linear-gradient(135deg,var(--c1),var(--c2));color:#fff}} .story-visual::after{{content:"";position:absolute;right:-4px;bottom:-18px;width:148px;height:148px;background:url("images/branding/artificial-one-elephant-mark.png") center/contain no-repeat;opacity:.48;filter:drop-shadow(0 10px 20px rgba(0,0,0,.35))}} .story-visual span,.story-visual strong{{position:relative;z-index:1;display:block;max-width:64%}} .story-visual span{{font-size:.72rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}} .story-visual strong{{margin-top:8px;font-size:.9rem}} .story-copy{{padding:20px 20px 8px}} .meta{{display:flex;justify-content:space-between;gap:12px;color:#64748b;font-size:.72rem;text-transform:uppercase;font-weight:800;letter-spacing:.04em}} .meta b{{color:var(--c1)}} .card h2{{font-size:1.25rem;line-height:1.35;margin:13px 0;color:#0f172a}} .route{{margin:auto 16px 16px;padding:14px;border-radius:13px;background:linear-gradient(135deg,#eef2ff,#f5f3ff)}} .route small{{display:block;color:#6366f1;font-weight:900;letter-spacing:.08em}} .route a{{display:block;margin-top:7px;color:#4338ca;font-weight:800;text-decoration:none}} footer{{border-top:1px solid rgba(255,255,255,.12);background:#080812;padding:34px 22px;text-align:center;color:#94a3b8}} footer a{{color:#c4b5fd}} @media(max-width:900px){{.grid,.pick-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}} @media(max-width:620px){{nav div{{gap:12px;font-size:.85rem}} .grid,.pick-grid{{grid-template-columns:1fr}} .news-page .hero{{padding:24px 18px}}}}
  </style>
</head><body class="news-page">
<header><nav><a href="index.html"><img src="artificial-one-logo-large.svg" alt="artificial.one"></a><div><a href="reviews.html">Reviews</a><a href="partner-offers.html">Partner offers</a></div></nav></header>
<section class="hero"><small>Fresh stories, useful routes</small><h1>What changed in AI today</h1><p>Open the original reporting, then jump straight to a related tool guide when the story affects something you may buy.</p></section>
<main><div class="notice">Last material update: {html.escape(updated_at)} · Sources are allowlisted and feed content is treated as untrusted data.</div>{picks_section}<div class="grid">{cards}</div></main>
<footer>© {datetime.now(timezone.utc).year} artificial.one · <a href="about.html">About</a> · <a href="partner-offers.html">Partner offers</a></footer>
<script src="assets/affiliate-tracking.js" defer></script>
</body></html>
'''


def update_sitemap(source: str) -> str:
    if "https://artificial.one/news.html" in source:
        return source
    entry = "  <url><loc>https://artificial.one/news.html</loc><changefreq>daily</changefreq><priority>0.8</priority></url>\n"
    if "</urlset>" not in source:
        raise NewsBuildError("sitemap.xml has no closing urlset element")
    return source.replace("</urlset>", entry + "</urlset>", 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--cached", action="store_true", help="Rebuild pages from the saved feed without network access")
    args = parser.parse_args()
    try:
        config = load_json(SOURCES_PATH)
        now = datetime.now(timezone.utc)
        if args.check or args.cached:
            existing = load_json(DATA_PATH)
            items = existing.get("items", [])
            updated_at = str(existing.get("updated_at", ""))
            failures: list[str] = []
        else:
            items, failures = aggregate_news(config, now)
            if len(items) < 6:
                raise NewsBuildError(f"Only {len(items)} valid news items were available")
            previous = load_json(DATA_PATH) if DATA_PATH.exists() else {"items": []}
            updated_at = str(previous.get("updated_at", "")) if news_identity(items) == news_identity(previous.get("items", [])) else now.isoformat()

        items = add_related_routes(items)
        data = {"version": 1, "updated_at": updated_at, "items": items}
        desired = {
            DATA_PATH: json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            INDEX_PATH: update_homepage(items),
            NEWS_PATH: render_news_page(items, updated_at, partner_picks()),
            SITEMAP_PATH: update_sitemap(SITEMAP_PATH.read_text(encoding="utf-8")),
        }
        changed = [path for path, text in desired.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        if args.check and changed:
            print("AI news output is stale:", file=sys.stderr)
            for path in changed:
                print(f"- {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        if not args.check:
            for path, text in desired.items():
                path.write_text(text, encoding="utf-8")
        for failure in failures:
            print(f"warning: {failure}", file=sys.stderr)
        print(f"AI news feed contains {len(items)} items; updated {len(changed)} file(s).")
        return 0
    except NewsBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
