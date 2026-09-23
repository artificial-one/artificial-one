#!/usr/bin/env python3
"""Build the interactive Elephant decision engine, recipes and observatory."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from scripts.build_partner_offers import esc, shell
except ModuleNotFoundError:
    from build_partner_offers import esc, shell  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "tool_intelligence.json"
HISTORY_PATH = ROOT / "data" / "tool_change_history.json"
NEWS_PATH = ROOT / "data" / "ai_news.json"
OUTPUT_PATH = ROOT / "data" / "elephant_experience.json"
HOME_PATH = ROOT / "index.html"
SITEMAP_PATH = ROOT / "sitemap.xml"
SITEMAP_START = "  <!-- elephant-experience:start -->"
SITEMAP_END = "  <!-- elephant-experience:end -->"


RECIPES = (
    {
        "id": "launch-a-converting-campaign",
        "title": "Launch and measure a converting campaign",
        "outcome": "Move from campaign idea to a measurable landing-page experiment.",
        "keywords": ("advertising", "conversion", "landing", "analytics", "creative"),
        "steps": (
            "Define one audience, one promise and one conversion event.",
            "Create two evidence-based creative directions and a focused landing page.",
            "Connect lead attribution before sending traffic.",
            "Run a small test and retain the winning message, not merely the prettiest asset.",
        ),
    },
    {
        "id": "turn-recordings-into-content",
        "title": "Turn one recording into a week of content",
        "outcome": "Edit spoken content, create clips and produce accessible derivatives.",
        "keywords": ("audio", "video", "voice", "transcription", "content"),
        "steps": (
            "Record one useful long-form conversation or walkthrough.",
            "Edit the transcript and remove repetition before generating derivatives.",
            "Create short clips, captions and a concise written summary.",
            "Review every generated asset for accuracy, consent and platform fit.",
        ),
    },
    {
        "id": "build-and-sell-an-online-course",
        "title": "Build and sell an online course",
        "outcome": "Package expertise into a teachable product and a repeatable launch.",
        "keywords": ("course", "learning", "education", "email", "creator"),
        "steps": (
            "Validate a narrow learner outcome before producing lessons.",
            "Build the minimum curriculum and one practical assessment.",
            "Create a landing page and an email sequence around the learner result.",
            "Measure completion and refund signals before expanding the course.",
        ),
    },
    {
        "id": "build-a-business-website",
        "title": "Build a business website that captures demand",
        "outcome": "Publish a focused website with measurable conversion routes.",
        "keywords": ("website", "landing", "design", "seo", "conversion"),
        "steps": (
            "Choose one primary visitor and one action the site must earn.",
            "Publish a concise information architecture before polishing visual details.",
            "Add analytics, a conversion event and a fast feedback route.",
            "Improve pages from real queries and behavior rather than invented volume.",
        ),
    },
    {
        "id": "automate-document-approvals",
        "title": "Automate document review and approvals",
        "outcome": "Reduce repetitive PDF handling without weakening auditability.",
        "keywords": ("document", "pdf", "signature", "approval", "workflow"),
        "steps": (
            "Map the document journey from creation to final archive.",
            "Remove duplicate entry and define who may approve each stage.",
            "Pilot electronic signatures on one low-risk document type.",
            "Verify audit trails, identity controls, retention and jurisdictional requirements.",
        ),
    },
    {
        "id": "research-and-qualify-leads",
        "title": "Research and qualify B2B leads",
        "outcome": "Create a smaller, evidence-backed prospect list with clear intent signals.",
        "keywords": ("lead", "sales", "research", "trade", "data"),
        "steps": (
            "Define the firmographic and behavioral signals of a qualified account.",
            "Collect the minimum lawful data needed for prioritization.",
            "Score accounts using transparent criteria and verify the top segment manually.",
            "Measure qualified conversations rather than raw contact volume.",
        ),
    },
    {
        "id": "onboard-a-growing-team",
        "title": "Onboard and operate a growing team",
        "outcome": "Turn recurring knowledge into documented, measurable team workflows.",
        "keywords": ("training", "onboarding", "team", "productivity", "tracking"),
        "steps": (
            "Document the five decisions a new teammate must make correctly.",
            "Turn recurring explanations into short role-based procedures.",
            "Connect training to real work instead of passive content completion.",
            "Review monitoring, consent and employee-privacy requirements before rollout.",
        ),
    },
    {
        "id": "ship-an-ai-powered-product",
        "title": "Ship an AI-powered product",
        "outcome": "Build a useful retrieval or automation feature with measurable quality.",
        "keywords": ("developer", "database", "api", "automation", "data"),
        "steps": (
            "Define the user decision the AI feature will improve.",
            "Create a small evaluation set before choosing infrastructure.",
            "Prototype retrieval, model and fallback behavior separately.",
            "Track latency, failure rate, cost and answer quality in production.",
        ),
    },
)


def load(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def compact_tool(tool: dict[str, Any]) -> dict[str, Any]:
    links = tool.get("links", {})
    monetization = tool.get("monetization", {})
    pricing = tool.get("pricing", {})
    verification = tool.get("verification", {})
    return {
        "id": str(tool.get("id") or ""),
        "name": str(tool.get("name") or "AI tool"),
        "category": str(tool.get("category") or "AI software"),
        "summary": str(tool.get("summary") or ""),
        "best_for": str(tool.get("best_for") or ""),
        "features": [str(item) for item in tool.get("features", [])[:8]],
        "platforms": [str(item) for item in tool.get("platforms", [])[:8]],
        "free": bool(pricing.get("has_free_plan")),
        "price": str(pricing.get("label") or "Pricing not recorded"),
        "status": str(verification.get("status") or "unverified"),
        "checked": str(verification.get("last_checked") or ""),
        "profile": str(links.get("profile") or "ai-tool-database.html"),
        "source": str(links.get("source") or ""),
        "affiliate": str(links.get("affiliate") or ""),
        "monetized": bool(monetization.get("active") and links.get("affiliate")),
        "offer_id": str(monetization.get("offer_id") or tool.get("id") or ""),
    }


def match_recipe(recipe: dict[str, Any], tools: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    words = tuple(str(item).casefold() for item in recipe["keywords"])
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for tool in tools:
        hay = " ".join((tool["name"], tool["category"], tool["summary"], tool["best_for"], *tool["features"])).casefold()
        score = sum(9 if word in tool["category"].casefold() else 4 for word in words if word in hay)
        score += 2 if tool["status"] == "reviewed" else 1 if tool["status"] == "destination-checked" else 0
        score += 1 if tool["monetized"] else 0
        if score:
            ranked.append((score, tool["name"].casefold(), tool))
    return [item[2] for item in sorted(ranked, key=lambda row: (-row[0], row[1]))[:limit]]


def experience_payload() -> dict[str, Any]:
    catalog = load(CATALOG_PATH, {"tools": [], "stats": {}})
    tools = [compact_tool(item) for item in catalog.get("tools", []) if isinstance(item, dict)]
    history = load(HISTORY_PATH, {"events": [], "coverage": {}})
    news = load(NEWS_PATH, {"items": []})
    recipes = []
    for recipe in RECIPES:
        record = {key: value for key, value in recipe.items() if key != "keywords"}
        record["tools"] = [item["id"] for item in match_recipe(recipe, tools)]
        recipes.append(record)
    return {
        "version": 1,
        "updated_at": max(str(catalog.get("updated_at") or ""), str(history.get("updated_at") or ""), date.today().isoformat()),
        "methodology": "Catalogue-grounded browser-side recommendations; monetization is a one-point tie-break only.",
        "stats": {
            "tools": len(tools),
            "monetized": sum(item["monetized"] for item in tools),
            "reviewed": sum(item["status"] == "reviewed" for item in tools),
            "changes": len(history.get("events", [])),
            "recipes": len(recipes),
        },
        "tools": tools,
        "recipes": recipes,
        "changes": history.get("events", [])[:100],
        "news": [
            {"title": str(item.get("title") or ""), "url": str(item.get("url") or ""), "category": str(item.get("category") or "AI news"), "published": str(item.get("published") or "")}
            for item in news.get("items", [])[:24] if isinstance(item, dict)
        ],
    }


def script_tags(prefix: str = "") -> str:
    return f'<script src="{prefix}assets/elephant-share.js" defer></script><script src="{prefix}assets/elephant-experience.js" defer></script>'


def render_ask(payload: dict[str, Any]) -> str:
    stats = payload["stats"]
    content = f'''<section class="elephant-hero"><div class="container"><div class="elephant-orb" aria-hidden="true">🐘</div><p class="eyebrow">Catalogue-grounded decision assistant</p><h1>Ask the Elephant</h1><p class="hero-copy">Tell the elephant what you need to accomplish. It searches {stats['tools']} normalized tools, explains the fit and shows limitations before any commercial link.</p><div class="elephant-chat" data-elephant-chat><div class="chat-bubble bot">What job are we trying to finish—and what would make the software worth paying for?</div><form data-elephant-form><label class="sr-only" for="elephant-question">Describe your workflow</label><textarea id="elephant-question" rows="3" maxlength="360" placeholder="Example: I run a two-person podcast and need to edit interviews, create clips and stay under $100/month" required></textarea><div class="chat-options"><label>Team<select data-elephant-team><option value="solo">Just me</option><option value="small">2–20 people</option><option value="large">Larger organization</option></select></label><label>Budget<select data-elephant-budget><option value="flexible">Flexible</option><option value="free">Free plan preferred</option><option value="value">Best value</option></select></label><button class="btn" type="submit">Ask the Elephant →</button></div></form></div><p class="microcopy">Runs in your browser. Your question is not sent to an AI provider. Affiliate eligibility contributes only a one-point tie-break.</p></div></section><section class="container section" data-elephant-answer hidden><div class="answer-head"><div><p class="eyebrow">The elephant's shortlist</p><h2 data-elephant-summary></h2></div><button class="btn btn-secondary" type="button" data-share-elephant>Share this shortlist</button></div><div class="card-grid" data-elephant-results></div><div class="surface methodology"><h3>How this answer was made</h3><p>Matches come from recorded categories, summaries, features, platforms, pricing signals and verification status. The explanation names the evidence used; current pricing and capabilities must still be checked with the vendor.</p></div></section>{script_tags()}'''
    return shell(title="Ask the Elephant: AI Tool Decision Assistant | artificial.one", description="Describe your workflow and receive a transparent, catalogue-grounded AI tool shortlist with fit reasons and limitations.", canonical_path="ask-elephant.html", content=content, structured_data={"@context": "https://schema.org", "@type": "WebApplication", "name": "Ask the Elephant AI Tool Decision Assistant", "applicationCategory": "BusinessApplication", "isAccessibleForFree": True}, social_image="https://artificial.one/images/social/artificial-one-logo.png", social_image_alt="Ask the Artificial.One elephant for an AI tool shortlist")


def render_stack(payload: dict[str, Any]) -> str:
    content = f'''<section class="elephant-hero studio-hero"><div class="container"><p class="eyebrow">Visual decision workspace</p><h1>AI Stack Studio</h1><p class="hero-copy">Build a workflow stack, expose overlapping subscriptions and attach your own monthly-cost assumptions. Everything stays on this device until you share it.</p><form class="studio-builder" data-studio-form><label>What must the stack accomplish?<input data-studio-query maxlength="240" placeholder="Create a course, market it and support learners" required></label><label>Stack size<select data-studio-size><option value="3">Lean · 3 tools</option><option value="4">Balanced · 4 tools</option><option value="5">Expanded · 5 tools</option></select></label><button class="btn" type="submit">Compose my stack →</button></form></div></section><section class="container section" data-studio-workspace hidden><div class="answer-head"><div><p class="eyebrow">Your working stack</p><h2 data-studio-title>Recommended stack</h2></div><div class="button-row"><button class="btn btn-secondary" type="button" data-studio-share>Copy share link</button><button class="btn btn-secondary" type="button" data-studio-card>Download share card</button><button class="btn btn-secondary" type="button" data-studio-export>Export JSON</button></div></div><div class="studio-grid" data-studio-items></div><div class="studio-totals"><div><span>Your entered monthly total</span><strong data-studio-total>$0</strong></div><div><span>Potential overlaps</span><strong data-studio-overlaps>0</strong></div></div><div class="surface methodology" data-studio-notes></div></section>{script_tags()}'''
    return shell(title="AI Stack Studio: Build, Cost and Share Your AI Stack | artificial.one", description="Compose an AI software stack, enter monthly costs, detect category overlap and share the result.", canonical_path="ai-stack-studio.html", content=content, structured_data={"@context": "https://schema.org", "@type": "WebApplication", "name": "Artificial.One AI Stack Studio", "applicationCategory": "BusinessApplication", "isAccessibleForFree": True}, social_image="https://artificial.one/images/social-cards/ai-stack-builder.jpg")


def tool_link(tool: dict[str, Any], placement: str, prefix: str = "") -> str:
    profile = str(tool["profile"])
    if not profile.startswith("http"):
        profile = prefix + profile
    affiliate = ""
    if tool["monetized"] and str(tool["affiliate"]).startswith("https://"):
        affiliate = f'<a class="btn btn-small" href="{esc(tool["affiliate"])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="{esc(tool["offer_id"])}" data-placement="{esc(placement)}">Check current offer →</a>'
    return f'<article class="recipe-tool"><p class="category">{esc(tool["category"])}</p><h3>{esc(tool["name"])}</h3><p>{esc(tool["summary"])}</p><div class="button-row"><a class="link-subtle" href="{esc(profile)}">Review record</a>{affiliate}</div></article>'


def render_recipe(recipe: dict[str, Any], tools: list[dict[str, Any]]) -> str:
    matches = match_recipe(recipe, tools)
    steps = "".join(f'<li><span>{index}</span><p>{esc(step)}</p></li>' for index, step in enumerate(recipe["steps"], 1))
    cards = "".join(tool_link(tool, f"recipe-{recipe['id']}", "../") for tool in matches)
    content = f'''<section class="recipe-hero"><div class="container"><p class="eyebrow">Outcome recipe</p><h1>{esc(recipe['title'])}</h1><p class="hero-copy">{esc(recipe['outcome'])}</p><div class="button-row"><a class="btn" href="../ask-elephant.html?task={esc(recipe['title'])}">Personalize with the Elephant</a><button class="btn btn-secondary" type="button" data-recipe-card data-share-title="{esc(recipe['title'])}">Download recipe card</button></div></div></section><section class="container section"><ol class="recipe-steps">{steps}</ol><h2 class="section-title">Tools to evaluate for this workflow</h2><div class="recipe-tools">{cards}</div><div class="surface methodology"><strong>Buying rule:</strong> validate one real workflow and current plan limits before replacing an existing process. Product inclusion reflects recorded fit signals; commission eligibility is not the recipe's primary ranking factor.</div></section>{script_tags('../')}'''
    return shell(title=f"{recipe['title']} — AI Workflow Recipe | artificial.one", description=str(recipe["outcome"]), canonical_path=f"workflow-recipes/{recipe['id']}.html", content=content, prefix="../", structured_data={"@context": "https://schema.org", "@type": "HowTo", "name": recipe["title"], "description": recipe["outcome"], "step": [{"@type": "HowToStep", "position": index, "text": step} for index, step in enumerate(recipe["steps"], 1)]})


def render_recipe_hub(payload: dict[str, Any]) -> str:
    cards = "".join(f'''<a class="recipe-card" href="workflow-recipes/{esc(item['id'])}.html" data-recipe-search="{esc((item['title'] + ' ' + item['outcome']).casefold())}"><span class="elephant-mini">🐘</span><h2>{esc(item['title'])}</h2><p>{esc(item['outcome'])}</p><strong>Open the workflow →</strong></a>''' for item in payload["recipes"])
    content = f'''<section class="elephant-hero"><div class="container"><p class="eyebrow">Jobs, not logos</p><h1>AI workflow recipes</h1><p class="hero-copy">Start with the result you need. Each recipe maps a practical sequence, buying checks and relevant software records.</p><label class="recipe-search">Find a workflow<input type="search" data-recipe-search-input placeholder="Podcast, documents, leads, course…"></label></div></section><section class="container section"><div class="recipe-grid" data-recipe-grid>{cards}</div><p class="empty" data-recipe-empty hidden>No matching recipe yet. <a href="ask-elephant.html">Ask the Elephant for a custom shortlist.</a></p></section>{script_tags()}'''
    return shell(title="AI Workflow Recipes: Build a Practical Tool Stack | artificial.one", description="Outcome-led AI workflow recipes with implementation steps, transparent tool matching and current buying checks.", canonical_path="workflow-recipes.html", content=content, structured_data={"@context": "https://schema.org", "@type": "CollectionPage", "name": "Artificial.One AI workflow recipes"})


def render_observatory(payload: dict[str, Any]) -> str:
    changes = payload["changes"]
    latest = "".join(f'''<article class="change-card" data-change-kind="{esc(item.get('kind', 'product'))}"><p class="eyebrow">{esc(item.get('kind', 'product'))} · {esc(item.get('detected_on', ''))}</p><h3>{esc(item.get('tool_name', 'AI tool'))}</h3><p>{esc(item.get('message', 'A vendor-source change was confirmed.'))}</p><div class="button-row"><a class="link-subtle" href="ai-tool-database.html?q={esc(item.get('tool_id', ''))}">Open record</a><a class="link-subtle" href="{esc(item.get('source_url', ''))}" target="_blank" rel="noopener">Vendor source ↗</a><button class="btn btn-small" type="button" data-observatory-watch="{esc(item.get('tool_id', ''))}" data-tool-name="{esc(item.get('tool_name', 'AI tool'))}">Watch tool</button></div></article>''' for item in changes[:30]) or '<div class="surface"><h2>Monitoring is active</h2><p>No change has yet passed the two-observation publication rule.</p></div>'
    stats = payload["stats"]
    content = f'''<section class="observatory-hero"><div class="container"><p class="eyebrow">Repeated-source monitoring</p><h1>The AI Tool Observatory</h1><p class="hero-copy">A live view of the software landscape—without pretending every scraped difference is news.</p><div class="stat-grid"><div><strong>{stats['tools']}</strong><span>normalized tools</span></div><div><strong>{stats['monetized']}</strong><span>commercially linked</span></div><div><strong>{stats['changes']}</strong><span>confirmed changes</span></div><div><strong>{stats['recipes']}</strong><span>outcome recipes</span></div></div></div></section><section class="container section"><div class="answer-head"><div><p class="eyebrow">Confirmed signals</p><h2>What changed recently</h2></div><label>Filter<select data-change-filter><option value="all">All changes</option><option value="pricing or plan">Pricing or plan</option><option value="availability">Availability</option><option value="product">Product</option></select></label></div><div class="change-grid" data-change-grid>{latest}</div><section class="watch-center"><div><p class="eyebrow">Private by default</p><h2>Your Elephant watchlist</h2><p>Save tools in this browser. Optional email alerts use double confirmation and only fire when a monitored change passes the publication rule.</p><div data-observatory-watchlist class="watch-pills"></div></div><form data-watch-email-form><label>Email for confirmed alerts<input name="email" type="email" maxlength="180" required placeholder="you@example.com"></label><input name="website" tabindex="-1" autocomplete="off" class="honey"><label class="consent"><input name="consent" type="checkbox" required> Send only confirmed watchlist changes. I can unsubscribe at any time.</label><button class="btn" type="submit">Email my confirmation link</button><p data-watch-status aria-live="polite"></p></form></section></section>{script_tags()}'''
    return shell(title="AI Tool Observatory: Pricing, Availability and Product Changes | artificial.one", description="Follow confirmed AI software pricing, availability and product changes from repeated vendor-source observations.", canonical_path="ai-tool-observatory.html", content=content, structured_data={"@context": "https://schema.org", "@type": "Dataset", "name": "Artificial.One AI Tool Observatory", "dateModified": payload["updated_at"], "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": "https://artificial.one/data/elephant_experience.json"}]})


def render_api_docs(payload: dict[str, Any]) -> str:
    content = f'''<section class="elephant-hero"><div class="container"><p class="eyebrow">Public, privacy-safe data</p><h1>Artificial.One Tool API</h1><p class="hero-copy">Query {payload['stats']['tools']} normalized software records and confirmed change events. The public API contains no customer, click or affiliate-performance data.</p><div class="button-row"><a class="btn" href="/api/tool-catalog?limit=5">Try the API</a><a class="btn btn-secondary" href="data/tool_intelligence.json">Download the full dataset</a></div></div></section><section class="container section api-docs"><h2>Endpoints</h2><div class="surface"><code>GET /api/tool-catalog?q=video&amp;category=Marketing&amp;free=true&amp;limit=20&amp;offset=0</code><p>Returns compact tool records, filters and pagination metadata. Maximum page size: 100.</p></div><div class="surface"><code>GET /api/tool-catalog?changes=true&amp;limit=20</code><p>Returns confirmed public change events from the repeated-observation monitor.</p></div><h2>Fair-use policy</h2><p>Responses are cached and designed for prototypes, research and attribution-friendly integrations. Bulk users should use the versioned JSON or CSV downloads. Do not infer product claims beyond the included evidence status and source links.</p></section>'''
    return shell(title="Artificial.One Public AI Tool Data API", description="Query Artificial.One's privacy-safe normalized AI software catalogue and confirmed change events.", canonical_path="developers.html", content=content, structured_data={"@context": "https://schema.org", "@type": "WebAPI", "name": "Artificial.One Tool API", "documentation": "https://artificial.one/developers.html", "provider": {"@type": "Organization", "name": "Artificial.One"}})


def render_confirmed() -> str:
    content = '''<section class="elephant-hero"><div class="container"><div class="elephant-orb">🐘</div><p class="eyebrow">Watchlist confirmed</p><h1>The elephant is listening</h1><p class="hero-copy">Your selected tools are now watched. You will receive an email only when a relevant change passes the repeated-observation rule.</p><a class="btn" href="ai-tool-observatory.html">Return to the Observatory</a></div></section>'''
    return shell(title="Watchlist Confirmed | artificial.one", description="Your Artificial.One AI tool change watchlist is confirmed.", canonical_path="watchlist-confirmed.html", content=content, structured_data={"@context": "https://schema.org", "@type": "WebPage", "name": "Artificial.One watchlist confirmed"})


def update_sitemap(source: str, updated_at: str) -> str:
    pages = (
        ("ask-elephant.html", "0.95", "weekly"), ("ai-stack-studio.html", "0.9", "weekly"),
        ("workflow-recipes.html", "0.9", "weekly"), ("ai-tool-observatory.html", "0.9", "daily"),
        ("developers.html", "0.7", "weekly"),
        *((f"workflow-recipes/{recipe['id']}.html", "0.82", "monthly") for recipe in RECIPES),
    )
    rows = [SITEMAP_START]
    for path, priority, frequency in pages:
        rows.append(f"  <url><loc>https://artificial.one/{path}</loc><lastmod>{updated_at}</lastmod><changefreq>{frequency}</changefreq><priority>{priority}</priority></url>")
    rows.append(SITEMAP_END)
    block = "\n".join(rows)
    if SITEMAP_START in source and SITEMAP_END in source:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), block, source, flags=re.S)
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + block + "\n</urlset>\n"


def update_homepage(source: str, payload: dict[str, Any]) -> str:
    count = str(payload["stats"]["tools"])
    source = re.sub(r"<strong>\d+</strong> tools tracked", f"<strong>{count}</strong> tools tracked", source)
    source = re.sub(r"<strong>\d+</strong><span>tools monitored for meaningful changes</span>", f"<strong>{count}</strong><span>tools monitored for meaningful changes</span>", source)
    return source


def outputs() -> dict[Path, str]:
    payload = experience_payload()
    tools = payload["tools"]
    result: dict[Path, str] = {
        OUTPUT_PATH: json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        ROOT / "ask-elephant.html": render_ask(payload),
        ROOT / "ai-stack-studio.html": render_stack(payload),
        ROOT / "workflow-recipes.html": render_recipe_hub(payload),
        ROOT / "ai-tool-observatory.html": render_observatory(payload),
        ROOT / "developers.html": render_api_docs(payload),
        ROOT / "watchlist-confirmed.html": render_confirmed(),
        HOME_PATH: update_homepage(HOME_PATH.read_text(encoding="utf-8"), payload),
        SITEMAP_PATH: update_sitemap(SITEMAP_PATH.read_text(encoding="utf-8"), str(payload["updated_at"])),
    }
    result.update({ROOT / "workflow-recipes" / f"{recipe['id']}.html": render_recipe(recipe, tools) for recipe in RECIPES})
    return result


def build(check: bool = False) -> int:
    expected = outputs()
    stale = [str(path.relative_to(ROOT)) for path, value in expected.items() if not path.exists() or path.read_text(encoding="utf-8") != value]
    if check:
        if stale:
            print("Elephant experience build is stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        payload = json.loads(expected[OUTPUT_PATH])
        print(f"Elephant experience is current ({payload['stats']['tools']} tools, {payload['stats']['recipes']} recipes).")
        return 0
    for path, value in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8", newline="")
    payload = json.loads(expected[OUTPUT_PATH])
    print(f"Built Elephant decision engine with {payload['stats']['tools']} tools and {payload['stats']['recipes']} recipes.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    raise SystemExit(build(arguments.check))
