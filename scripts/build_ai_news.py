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
ARCHIVE_PATH = ROOT / "data" / "ai_news_archive.json"
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
                "description": description,
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
    archive_urls: dict[str, str] = {}
    if ARCHIVE_PATH.exists():
        try:
            archive = load_json(ARCHIVE_PATH)
            archive_urls = {
                str(record.get("source", {}).get("url") or ""): str(record.get("path") or "")
                for record in archive.get("articles", []) if isinstance(record, dict)
            }
        except NewsBuildError:
            archive_urls = {}
    enriched: list[dict[str, Any]] = []
    for item in items:
        value: dict[str, Any] = {**item, "related": related_route(item, offers)}
        archive_url = archive_urls.get(str(item.get("url") or ""), "")
        if archive_url:
            value["archive_url"] = archive_url
        enriched.append(value)
    return enriched


def news_identity(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key not in {"related", "archive_url"}} for item in items]


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


def reader_excerpt(item: dict[str, Any], limit: int = 220) -> str:
    value = clean_text(str(item.get("description") or ""), 520)
    if " appeared first on " in value.casefold() and "The article " in value:
        value = value.split("The article ", 1)[0].strip()
    if not value:
        value = f"The latest reporting from {item.get('source', 'a trusted technology source')}."
    if len(value) > limit:
        value = value[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return value


def story_destination(item: dict[str, Any]) -> tuple[str, str]:
    if item.get("archive_url"):
        return str(item["archive_url"]), "Read the briefing"
    return str(item["url"]), "Read the story"


def story_visual(item: dict[str, Any]) -> tuple[str, str, str]:
    palettes = {
        "Models & LLMs": ("#5b21b6", "#8b5cf6", "LLM"),
        "Research": ("#0369a1", "#22d3ee", "LAB"),
        "Policy & Safety": ("#be123c", "#fb7185", "SAFE"),
        "AI Business": ("#b45309", "#fbbf24", "BIZ"),
        "AI Tools & Products": ("#047857", "#84cc16", "AI"),
    }
    return palettes.get(str(item.get("category") or ""), ("#4338ca", "#c084fc", "AI"))


def render_news_page(
    items: list[dict[str, str]], updated_at: str, picks: list[dict[str, str]] | None = None
) -> str:
    if not items:
        raise NewsBuildError("The news page needs at least one story")

    def link_attributes(item: dict[str, Any]) -> str:
        return "" if item.get("archive_url") else ' target="_blank" rel="noopener noreferrer"'

    featured = items[0]
    featured_url, featured_cta = story_destination(featured)
    featured_c1, featured_c2, featured_mark = story_visual(featured)
    featured_search = clean_text(f"{featured.get('title', '')} {featured.get('source', '')} {featured.get('description', '')}", 700).casefold()
    featured_markup = f'''<article class="lead-story" data-news-card data-category="{html.escape(featured['category'], quote=True)}" data-search="{html.escape(featured_search, quote=True)}" style="--c1:{featured_c1};--c2:{featured_c2}">
      <a class="story-link" href="{html.escape(featured_url, quote=True)}"{link_attributes(featured)}>
        <div class="lead-copy"><div class="story-meta"><span>{html.escape(featured['category'])}</span><time datetime="{html.escape(featured['published_at'], quote=True)}">{html.escape(featured['display_date'])}</time></div><h2>{html.escape(featured['title'])}</h2><p>{html.escape(reader_excerpt(featured, 300))}</p><strong>{html.escape(featured_cta)} <span aria-hidden="true">→</span></strong></div>
        <div class="lead-art" aria-hidden="true"><b>{featured_mark}</b><span></span></div>
      </a>
    </article>'''

    cards: list[str] = []
    for item in items[1:]:
        destination, cta = story_destination(item)
        c1, c2, mark = story_visual(item)
        searchable = clean_text(f"{item.get('title', '')} {item.get('source', '')} {item.get('description', '')}", 700).casefold()
        cards.append(f'''<article class="story-card" data-news-card data-category="{html.escape(item['category'], quote=True)}" data-search="{html.escape(searchable, quote=True)}" style="--c1:{c1};--c2:{c2}">
          <a class="story-link" href="{html.escape(destination, quote=True)}"{link_attributes(item)}>
            <div class="story-art" aria-hidden="true"><span>{mark}</span><i></i></div>
            <div class="story-body"><div class="story-meta"><span>{html.escape(item['category'])}</span><time datetime="{html.escape(item['published_at'], quote=True)}">{html.escape(item['display_date'])}</time></div><h2>{html.escape(item['title'])}</h2><p>{html.escape(reader_excerpt(item))}</p><div class="story-foot"><span>{html.escape(item['source'])}</span><strong>{html.escape(cta)} →</strong></div></div>
          </a>
        </article>''')
    cards_markup = "\n".join(cards)
    categories = list(dict.fromkeys(str(item.get("category") or "AI News") for item in items))
    filters = "".join(
        f'<button type="button" data-news-filter="{html.escape(category, quote=True)}">{html.escape(category)}</button>'
        for category in categories
    )
    item_list = [
        {"@type": "ListItem", "position": index, "url": "https://artificial.one/" + item["archive_url"] if item.get("archive_url") else item["url"], "name": item["title"]}
        for index, item in enumerate(items, 1)
    ]
    structured = safe_json_for_script({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": item_list})
    return f'''<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Latest AI, LLM &amp; AI Tools News | artificial.one</title>
  <meta name="description" content="The AI stories worth knowing today—clear summaries, useful context and memorable Elephant commentary.">
  <link rel="canonical" href="https://artificial.one/news.html">
  <meta property="og:title" content="Latest AI, LLM &amp; AI Tools News | artificial.one">
  <meta property="og:description" content="The AI stories worth knowing today, presented clearly and without the noise.">
  <meta property="og:type" content="website"><meta property="og:url" content="https://artificial.one/news.html">
  <script type="application/ld+json">{structured}</script>
  <style>
    *{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#fff;color:#111827;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}a{{color:inherit}}.site-header{{position:sticky;top:0;z-index:20;background:rgba(9,9,20,.96);backdrop-filter:blur(16px);border-bottom:1px solid rgba(255,255,255,.08)}}nav{{max-width:1180px;margin:auto;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;gap:24px}}.brand{{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none;font-weight:900;font-size:1.03rem}}.brand img{{width:43px;height:43px;object-fit:contain}}.brand em{{font-style:normal;color:#9cff3b}}.nav-links{{display:flex;gap:22px;align-items:center}}.nav-links a{{color:#e5e7eb;text-decoration:none;font-weight:750;font-size:.92rem}}.nav-links a:hover{{color:#9cff3b}}.masthead{{max-width:1180px;margin:auto;padding:66px 24px 34px}}.kicker{{display:inline-flex;align-items:center;gap:8px;margin:0 0 14px;color:#6d28d9;font-size:.78rem;font-weight:950;letter-spacing:.14em;text-transform:uppercase}}.kicker::before{{content:"";width:28px;height:4px;border-radius:99px;background:linear-gradient(90deg,#8b5cf6,#9cff3b)}}.masthead h1{{max-width:860px;margin:0;font-size:clamp(3rem,7vw,6.5rem);line-height:.92;letter-spacing:-.065em}}.masthead h1 span{{color:#7c3aed}}.masthead>p:last-child{{max-width:720px;margin:22px 0 0;color:#4b5563;font-size:1.16rem;line-height:1.7}}main{{max-width:1180px;margin:auto;padding:0 24px 90px}}.lead-story{{margin:12px 0 58px;border-radius:30px;overflow:hidden;background:linear-gradient(135deg,var(--c1),var(--c2));box-shadow:0 24px 70px rgba(76,29,149,.19)}}.lead-story[hidden],.story-card[hidden]{{display:none}}.lead-story .story-link{{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(260px,.7fr);min-height:410px;color:#fff;text-decoration:none}}.lead-copy{{padding:48px}}.lead-copy h2{{max-width:760px;margin:18px 0 16px;font-size:clamp(2.15rem,4.4vw,4.25rem);line-height:1.01;letter-spacing:-.045em}}.lead-copy p{{max-width:700px;color:rgba(255,255,255,.88);font-size:1.08rem;line-height:1.65}}.lead-copy>strong{{display:inline-block;margin-top:18px;padding:13px 18px;border-radius:99px;background:#fff;color:#17112c}}.story-meta{{display:flex;align-items:center;gap:12px;font-size:.73rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}}.story-meta span{{padding:7px 10px;border-radius:99px;background:rgba(255,255,255,.18)}}.lead-art{{position:relative;display:grid;place-items:center;overflow:hidden;background:radial-gradient(circle,rgba(255,255,255,.22),transparent 60%)}}.lead-art::before,.lead-art::after,.story-art::before{{content:"";position:absolute;border:1px solid rgba(255,255,255,.24);border-radius:50%}}.lead-art::before{{width:340px;height:340px}}.lead-art::after{{width:230px;height:230px}}.lead-art b{{position:relative;z-index:2;font-size:5rem;letter-spacing:-.12em;text-shadow:0 18px 40px rgba(0,0,0,.24)}}.lead-art span{{position:absolute;right:-25px;bottom:-28px;width:270px;height:270px;background:url("images/branding/artificial-one-elephant-mark.png") center/contain no-repeat;opacity:.48;filter:drop-shadow(0 18px 35px rgba(0,0,0,.3))}}.section-head{{display:flex;justify-content:space-between;gap:30px;align-items:end;margin-bottom:22px}}.section-head h2{{margin:0;font-size:clamp(2rem,4vw,3.2rem);letter-spacing:-.04em}}.section-head p{{max-width:470px;margin:0;color:#6b7280;line-height:1.6}}.news-tools{{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:0 0 28px}}.news-search{{position:relative;flex:1 1 270px}}.news-search input{{width:100%;min-height:48px;padding:0 17px 0 44px;border:1px solid #d1d5db;border-radius:14px;background:#fff;color:#111827;font:inherit;box-shadow:0 5px 18px rgba(15,23,42,.05)}}.news-search::before{{content:"⌕";position:absolute;left:16px;top:9px;color:#7c3aed;font-size:1.35rem}}.filters{{display:flex;flex-wrap:wrap;gap:8px}}.filters button{{border:1px solid #ddd6fe;border-radius:99px;background:#faf5ff;color:#5b21b6;padding:10px 13px;font:inherit;font-size:.8rem;font-weight:850;cursor:pointer}}.filters button:hover,.filters button.active{{background:#5b21b6;color:#fff;border-color:#5b21b6}}.story-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}}.story-card{{overflow:hidden;border:1px solid #e5e7eb;border-radius:23px;background:#fff;box-shadow:0 12px 36px rgba(15,23,42,.08);transition:transform .22s ease,box-shadow .22s ease}}.story-card:hover{{transform:translateY(-6px);box-shadow:0 23px 55px rgba(15,23,42,.14)}}.story-card .story-link{{display:flex;flex-direction:column;height:100%;text-decoration:none}}.story-art{{position:relative;display:grid;place-items:center;min-height:160px;overflow:hidden;background:linear-gradient(135deg,var(--c1),var(--c2));color:#fff}}.story-art::before{{width:170px;height:170px}}.story-art::after{{content:"";position:absolute;right:-25px;bottom:-34px;width:145px;height:145px;background:url("images/branding/artificial-one-elephant-mark.png") center/contain no-repeat;opacity:.42}}.story-art span{{position:relative;z-index:2;font-size:2.7rem;font-weight:950;letter-spacing:-.06em}}.story-art i{{position:absolute;left:24px;top:24px;width:48px;height:8px;border-radius:99px;background:#9cff3b;transform:rotate(-9deg)}}.story-body{{display:flex;flex-direction:column;flex:1;padding:23px}}.story-body .story-meta{{color:#6b7280}}.story-body .story-meta span{{color:var(--c1);background:#f5f3ff}}.story-body h2{{margin:16px 0 12px;font-size:1.35rem;line-height:1.25;letter-spacing:-.025em}}.story-body>p{{margin:0;color:#5b6472;line-height:1.58;font-size:.94rem}}.story-foot{{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-top:auto;padding-top:22px;color:#6b7280;font-size:.79rem;font-weight:750}}.story-foot strong{{color:var(--c1);text-align:right}}.empty{{padding:40px;border:1px dashed #c4b5fd;border-radius:20px;color:#6b7280;text-align:center}}footer{{border-top:1px solid #e5e7eb;background:#fff;padding:34px 24px;color:#6b7280}}.footer-inner{{max-width:1180px;margin:auto;display:flex;justify-content:space-between;gap:24px;align-items:center}}footer a{{color:#5b21b6;font-weight:800;text-decoration:none}}@media(max-width:900px){{.lead-story .story-link{{grid-template-columns:1fr}}.lead-art{{min-height:230px}}.story-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:650px){{.nav-links a:not(:last-child){{display:none}}.masthead{{padding-top:46px}}.lead-copy{{padding:29px}}.lead-story .story-link{{min-height:0}}.section-head{{display:block}}.section-head p{{margin-top:10px}}.story-grid{{grid-template-columns:1fr}}.footer-inner{{display:block}}}}
  </style>
</head><body class="news-page">
<header class="site-header"><nav><a class="brand" href="index.html"><img src="images/social/artificial-one-logo.png" alt="Artificial.One elephant"><span>artificial<em>.</em>one</span></a><div class="nav-links"><a href="index.html">Ask Elephant</a><a href="buyers-guides.html">Buyer guides</a><a href="news.html">AI news</a></div></nav></header>
<section class="masthead"><p class="kicker">The Elephant Wire</p><h1>AI news <span>worth knowing.</span></h1><p>Fresh stories about models, tools, research, business and safety—summarized clearly, with enough context to understand why they matter.</p></section>
<main>{featured_markup}<section aria-labelledby="latest-title"><div class="section-head"><div><p class="kicker">Latest stories</p><h2 id="latest-title">Keep up without the noise.</h2></div><p>Browse the newest developments or jump straight to the topic you care about.</p></div><div class="news-tools"><label class="news-search"><span hidden>Search stories</span><input type="search" data-news-search placeholder="Search AI news…"></label><div class="filters"><button class="active" type="button" data-news-filter="">All</button>{filters}</div></div><div class="story-grid">{cards_markup}</div><p class="empty" data-news-empty hidden>No stories match that search yet.</p></section></main>
<footer><div class="footer-inner"><span>© {datetime.now(timezone.utc).year} artificial.one</span><span><a href="about.html">About</a> · <a href="privacy.html">Privacy</a> · <a href="mailto:hello@artificial.one">Contact</a></span></div></footer>
<script>(function(){{var search=document.querySelector('[data-news-search]'),buttons=[].slice.call(document.querySelectorAll('[data-news-filter]')),stories=[].slice.call(document.querySelectorAll('[data-news-card]')),empty=document.querySelector('[data-news-empty]'),selected='';function update(){{var q=(search.value||'').trim().toLowerCase(),shown=0;stories.forEach(function(story){{var match=(!selected||story.dataset.category===selected)&&(!q||(story.dataset.search||'').indexOf(q)>-1);story.hidden=!match;if(match)shown++;}});empty.hidden=shown!==0;}}buttons.forEach(function(button){{button.addEventListener('click',function(){{selected=button.dataset.newsFilter||'';buttons.forEach(function(value){{value.classList.toggle('active',value===button);}});update();}});}});search.addEventListener('input',update);}})();</script>
</body></html>
'''


def update_sitemap(source: str) -> str:
    entries: list[str] = []
    if "https://artificial.one/news.html" not in source:
        entries.append("  <url><loc>https://artificial.one/news.html</loc><changefreq>daily</changefreq><priority>0.8</priority></url>\n")
    if ARCHIVE_PATH.exists():
        try:
            archive = load_json(ARCHIVE_PATH)
            for record in archive.get("articles", []):
                url = "https://artificial.one/" + str(record.get("path") or "")
                if record.get("path") and url not in source:
                    entries.append(f"  <url><loc>{html.escape(url)}</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>\n")
        except NewsBuildError:
            pass
    if not entries:
        return source
    if "</urlset>" not in source:
        raise NewsBuildError("sitemap.xml has no closing urlset element")
    return source.replace("</urlset>", "".join(entries) + "</urlset>", 1)


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
            NEWS_PATH: render_news_page(items, updated_at),
            SITEMAP_PATH: update_sitemap(SITEMAP_PATH.read_text(encoding="utf-8")),
        }
        changed = [path for path, text in desired.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        if args.check and changed:
            print("AI news output is stale:", file=sys.stderr)
            for path in changed:
                print(f"- {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        if not args.check:
            for path in changed:
                path.write_text(desired[path], encoding="utf-8")
        for failure in failures:
            print(f"warning: {failure}", file=sys.stderr)
        print(f"AI news feed contains {len(items)} items; updated {len(changed)} file(s).")
        return 0
    except NewsBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
