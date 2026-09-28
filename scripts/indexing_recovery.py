#!/usr/bin/env python3
"""Build crawl discovery assets, audit commercial pages, and notify IndexNow."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from html import unescape
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from scripts.build_partner_offers import esc, shell
except ModuleNotFoundError:
    from build_partner_offers import esc, shell  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
SITEMAP_PATH = ROOT / "sitemap.xml"
REPORT_PATH = ROOT / "data" / "indexing_recovery.json"
SEARCH_STRATEGY_PATH = ROOT / "data" / "search_growth_strategy.json"
HUB_PATH = ROOT / "buyers-guides.html"
SITE = "https://artificial.one"
INDEXNOW_KEY = "a10e20260915d74b93c2f18e7a45c901"
SITEMAP_START = "  <!-- indexing-recovery:start -->"
SITEMAP_END = "  <!-- indexing-recovery:end -->"
HREF_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)', re.I)
CANONICAL_RE = re.compile(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']([^"\']+)', re.I)


def priority_pages() -> list[Path]:
    paths = [
        ROOT / "ai-tool-database.html",
        ROOT / "ai-tool-alternatives.html",
        ROOT / "ai-tool-changes.html",
        ROOT / "ai-tool-finder.html",
        ROOT / "ai-stack-builder.html",
        ROOT / "ask-elephant.html",
        ROOT / "ai-stack-studio.html",
        ROOT / "ai-tool-observatory.html",
        ROOT / "workflow-recipes.html",
        ROOT / "developers.html",
        ROOT / "decision-tools.html",
        ROOT / "offer-updates.html",
        ROOT / "partner-offers.html",
        ROOT / "appsumo-ai-tools.html",
        ROOT / "sponsor.html",
    ]
    for folder in ("partner-offers", "search-intent", "calculators"):
        paths.extend(sorted((ROOT / folder).glob("*.html")))
    return [path for path in paths if path.exists()]


def page_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S) or re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", match.group(1) if match else path.stem)
    return unescape(re.sub(r"\s+", " ", value).strip())


def crawl_priority_paths(paths: list[Path]) -> list[Path]:
    strategy = load_public_json(SEARCH_STRATEGY_PATH)
    by_relative = {"/" + path.relative_to(ROOT).as_posix(): path for path in paths}
    result: list[Path] = []
    for value in strategy.get("crawl_priority", []):
        candidate = by_relative.get(str(value))
        if candidate and candidate not in result:
            result.append(candidate)
    return result


def render_hub(paths: list[Path], crawl_priority: list[Path] | None = None) -> str:
    priority = list(crawl_priority or [])
    priority_position = {path: index for index, path in enumerate(priority)}
    groups: dict[str, list[Path]] = {"Decision tools": [], "Partner reviews": [], "Comparisons and buying guides": []}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("partner-offers/"):
            groups["Partner reviews"].append(path)
        elif relative.startswith("search-intent/"):
            groups["Comparisons and buying guides"].append(path)
        else:
            groups["Decision tools"].append(path)

    metadata = {
        "Decision tools": {
            "kind": "plan",
            "label": "Plan & calculate",
            "icon": "◇",
            "description": "Turn a fuzzy software decision into a shortlist, stack or simple cost calculation.",
        },
        "Partner reviews": {
            "kind": "review",
            "label": "Tool fit guides",
            "icon": "✓",
            "description": "See who a tool suits, what to check and where its limits may matter before you buy.",
        },
        "Comparisons and buying guides": {
            "kind": "compare",
            "label": "Compare & price",
            "icon": "⇄",
            "description": "Compare alternatives, use cases and pricing questions side by side.",
        },
    }

    def card_description(label: str, title: str) -> str:
        lowered = title.casefold()
        if "calculator" in lowered or "worth the cost" in lowered:
            return "Put your own numbers in and see whether the software can justify its cost."
        if " vs " in lowered:
            return "Compare the two options around the decision that matters, not just their feature lists."
        if "pricing" in lowered:
            return "Understand the pricing questions and plan limits worth checking before you commit."
        if label == "Partner reviews":
            return "A practical look at fit, limitations and the current path to the product."
        if label == "Comparisons and buying guides":
            return "A focused guide for choosing the better route for this particular job."
        return "A practical decision tool that helps turn your requirements into a clearer next step."

    ordered_by_group: dict[str, list[Path]] = {}
    for label, members in groups.items():
        ordered_by_group[label] = sorted(
            members,
            key=lambda item: (priority_position.get(item, len(priority_position)), page_title(item).casefold()),
        )

    featured_preferences = {
        "Decision tools": ["ai-tool-finder.html", "calculators/ai-software-roi-calculator.html"],
        "Partner reviews": ["partner-offers/elevenlabs-ai-voice.html", "partner-offers/descript-ai-video-editing.html"],
        "Comparisons and buying guides": ["search-intent/best-artificial-intelligence-tools.html", "search-intent/best-productivity-business-tools.html"],
    }
    featured: list[tuple[str, Path]] = []
    for label in groups:
        by_relative = {item.relative_to(ROOT).as_posix(): item for item in ordered_by_group[label]}
        selected = [by_relative[value] for value in featured_preferences[label] if value in by_relative]
        fallback = [item for item in priority if item in ordered_by_group[label] and item not in selected]
        fallback.extend(item for item in ordered_by_group[label] if item not in selected and item not in fallback)
        selected.extend(fallback[: 2 - len(selected)])
        featured.extend((label, item) for item in selected[:2])
    if len(featured) < 6:
        used = {item for _, item in featured}
        for item in priority:
            if item in used:
                continue
            label = next((name for name, members in ordered_by_group.items() if item in members), "Decision tools")
            featured.append((label, item))
            used.add(item)
            if len(featured) == 6:
                break

    def render_card(label: str, item: Path, *, featured_card: bool = False) -> str:
        info = metadata[label]
        title = page_title(item)
        relative = item.relative_to(ROOT).as_posix()
        search = f"{title} {label} {info['description']}".casefold()
        classes = "buyer-card buyer-card-featured" if featured_card else "buyer-card"
        return (
            f'<a class="{classes}" href="{esc(relative)}" data-guide-card '
            f'data-guide-kind="{esc(info["kind"])}" data-guide-search="{esc(search)}">'
            f'<span class="guide-card-top"><span class="guide-card-icon" aria-hidden="true">{info["icon"]}</span>'
            f'<span class="guide-card-type">{esc(info["label"])}</span></span>'
            f'<strong>{esc(title)}</strong><span class="guide-card-copy">{esc(card_description(label, title))}</span>'
            f'<span class="guide-card-link">Open guide <span aria-hidden="true">→</span></span></a>'
        )

    featured_cards = "".join(render_card(label, item, featured_card=True) for label, item in featured)
    all_cards = "".join(
        render_card(label, item)
        for label, members in ordered_by_group.items()
        for item in members
    )
    total = sum(len(members) for members in groups.values())
    plan_count = len(groups["Decision tools"])
    review_count = len(groups["Partner reviews"])
    compare_count = len(groups["Comparisons and buying guides"])

    content = f'''<div class="buyer-library">
<section class="buyer-hero"><div class="buyer-shell buyer-hero-grid"><div class="buyer-hero-copy"><p class="buyer-eyebrow">The AI buyer's library</p><h1>Make a smarter software choice.</h1><p class="buyer-intro">Start with the decision in front of you—not a wall of product logos. Find clear tool-fit guides, honest comparisons and calculators built to answer one useful question at a time.</p><div class="buyer-hero-actions"><a class="buyer-primary-action" href="#find-a-guide">Find my guide <span aria-hidden="true">↓</span></a><a class="buyer-secondary-action" href="index.html#build">Ask the Elephant</a></div><div class="buyer-stats" aria-label="Library contents"><span><strong>{total}</strong> useful guides</span><span><strong>{review_count}</strong> tool-fit checks</span><span><strong>{compare_count}</strong> comparisons</span></div></div><div class="buyer-hero-art" aria-hidden="true"><span class="buyer-orbit buyer-orbit-one">Fit?</span><span class="buyer-orbit buyer-orbit-two">Cost?</span><span class="buyer-orbit buyer-orbit-three">Better?</span><img src="images/branding/artificial-one-elephant-mark.png" alt=""></div></div></section>

<section class="buyer-route-section" aria-labelledby="buyer-route-title"><div class="buyer-shell"><div class="buyer-section-heading"><div><p class="buyer-eyebrow">Choose your route</p><h2 id="buyer-route-title">What are you trying to decide?</h2></div><p>Pick the question closest to yours. You can always search the complete library below.</p></div><div class="buyer-route-grid"><button class="buyer-route buyer-route-plan" type="button" data-route-kind="plan"><span class="buyer-route-number">01</span><span class="buyer-route-icon" aria-hidden="true">◇</span><strong>What should I use?</strong><small>Shortlists, stack builders and calculators</small><span class="buyer-route-link">Explore {plan_count} tools →</span></button><button class="buyer-route buyer-route-review" type="button" data-route-kind="review"><span class="buyer-route-number">02</span><span class="buyer-route-icon" aria-hidden="true">✓</span><strong>Is this tool right for me?</strong><small>Fit, limitations and buying checks</small><span class="buyer-route-link">Explore {review_count} fit guides →</span></button><button class="buyer-route buyer-route-compare" type="button" data-route-kind="compare"><span class="buyer-route-number">03</span><span class="buyer-route-icon" aria-hidden="true">⇄</span><strong>Which option is better?</strong><small>Comparisons, pricing and use cases</small><span class="buyer-route-link">Explore {compare_count} comparisons →</span></button></div></div></section>

<section class="buyer-featured" aria-labelledby="buyer-featured-title"><div class="buyer-shell"><div class="buyer-section-heading"><div><p class="buyer-eyebrow">Editor's shortlist</p><h2 id="buyer-featured-title">Good places to start</h2></div><p>A balanced selection of decision tools, product-fit guides and comparisons worth opening first.</p></div><div class="buyer-featured-grid">{featured_cards}</div></div></section>

<section class="buyer-catalog" id="find-a-guide" aria-labelledby="buyer-catalog-title"><div class="buyer-shell"><div class="buyer-section-heading buyer-catalog-heading"><div><p class="buyer-eyebrow">Browse the library</p><h2 id="buyer-catalog-title">Find the guide for your decision</h2></div><p>Search by product, job or question. Every result opens a practical guide—not another directory.</p></div><div class="buyer-controls"><label class="buyer-search"><span class="sr-only">Search buyer guides</span><span aria-hidden="true">⌕</span><input type="search" placeholder="Try “video editing”, “pricing” or a product name…" data-guide-search-input autocomplete="off"></label><div class="buyer-filter-row" role="group" aria-label="Filter guides"><button type="button" class="is-active" data-guide-filter="all" aria-pressed="true">All guides</button><button type="button" data-guide-filter="plan" aria-pressed="false">Plan &amp; calculate</button><button type="button" data-guide-filter="review" aria-pressed="false">Tool fit</button><button type="button" data-guide-filter="compare" aria-pressed="false">Compare &amp; price</button></div></div><p class="buyer-result-count" data-guide-result-count>Showing {min(18, total)} of {total} guides</p><div class="buyer-card-grid" data-guide-grid>{all_cards}</div><div class="buyer-empty" data-guide-empty hidden><span aria-hidden="true">🐘</span><h3>No guide matches that search yet.</h3><p>Try a broader job or product name—or ask the Elephant to build a shortlist for you.</p><a href="index.html#build">Ask the Elephant →</a></div><div class="buyer-more-wrap"><button class="buyer-more" type="button" data-guide-more>Show more guides <span aria-hidden="true">↓</span></button></div></div></section>
</div>''' + '''
<script>
(function() {
  var root = document.querySelector('.buyer-library');
  if (!root) return;
  var input = root.querySelector('[data-guide-search-input]');
  var cards = Array.prototype.slice.call(root.querySelectorAll('[data-guide-grid] [data-guide-card]'));
  var filters = Array.prototype.slice.call(root.querySelectorAll('[data-guide-filter]'));
  var routes = Array.prototype.slice.call(root.querySelectorAll('[data-route-kind]'));
  var count = root.querySelector('[data-guide-result-count]');
  var empty = root.querySelector('[data-guide-empty]');
  var more = root.querySelector('[data-guide-more]');
  var limit = 18;
  var active = 'all';
  root.classList.add('is-ready');
  function apply(reset) {
    if (reset) limit = 18;
    var query = (input.value || '').trim().toLowerCase();
    var matches = cards.filter(function(card) {
      return (active === 'all' || card.dataset.guideKind === active) && (!query || card.dataset.guideSearch.indexOf(query) !== -1);
    });
    cards.forEach(function(card) { card.hidden = true; });
    matches.slice(0, limit).forEach(function(card) { card.hidden = false; });
    count.textContent = matches.length ? 'Showing ' + Math.min(limit, matches.length) + ' of ' + matches.length + ' guide' + (matches.length === 1 ? '' : 's') : 'No matching guides';
    empty.hidden = matches.length !== 0;
    more.hidden = matches.length <= limit;
  }
  input.addEventListener('input', function() { apply(true); });
  filters.forEach(function(button) {
    button.addEventListener('click', function() {
      active = button.dataset.guideFilter;
      filters.forEach(function(item) { var selected = item === button; item.classList.toggle('is-active', selected); item.setAttribute('aria-pressed', String(selected)); });
      apply(true);
    });
  });
  routes.forEach(function(button) {
    button.addEventListener('click', function() {
      active = button.dataset.routeKind;
      var selected = filters.find(function(item) { return item.dataset.guideFilter === active; });
      if (selected) selected.click();
      document.getElementById('find-a-guide').scrollIntoView({behavior: 'smooth'});
    });
  });
  more.addEventListener('click', function() { limit += 18; apply(false); });
  apply(false);
})();
</script>'''
    return shell(
        title="AI Software Buying Guides, Comparisons and Calculators | artificial.one",
        description="Find practical AI software buying guides, product-fit checks, comparisons and calculators built around the decision you need to make.",
        canonical_path="buyers-guides.html",
        content=content,
        structured_data={"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI software buyer's library"},
    )


def _local_path(source: Path, href: str) -> str | None:
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    base = SITE + "/" + source.relative_to(ROOT).as_posix()
    parsed = urlparse(urljoin(base, href))
    if parsed.netloc.casefold().removeprefix("www.") != "artificial.one":
        return None
    path = parsed.path.lstrip("/") or "index.html"
    return path if path.endswith(".html") else None


def audit(paths: list[Path], virtual: dict[Path, str] | None = None, sitemap_text: str | None = None) -> dict[str, Any]:
    virtual = virtual or {}
    incoming: Counter[str] = Counter()
    all_pages = sorted({path for path in ROOT.rglob("*.html") if ".git" not in path.parts} | set(virtual))
    for source in all_pages:
        text = virtual.get(source) or source.read_text(encoding="utf-8", errors="ignore")
        for href in HREF_RE.findall(text):
            target = _local_path(source, href)
            if target:
                incoming[target] += 1
    sitemap = sitemap_text if sitemap_text is not None else SITEMAP_PATH.read_text(encoding="utf-8", errors="ignore")
    issues: list[dict[str, str]] = []
    depths: Counter[str] = Counter()
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        text = virtual.get(path) or path.read_text(encoding="utf-8", errors="ignore")
        expected = f"{SITE}/{relative}"
        canonical = CANONICAL_RE.search(text)
        if not canonical or canonical.group(1).rstrip("/") != expected.rstrip("/"):
            issues.append({"path": relative, "issue": "canonical"})
        if re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex', text, re.I):
            issues.append({"path": relative, "issue": "noindex"})
        if expected not in sitemap and path != HUB_PATH:
            issues.append({"path": relative, "issue": "sitemap"})
        count = incoming[relative]
        depths["0" if count == 0 else "1" if count < 3 else "3+"] += 1
        if count == 0 and path != HUB_PATH:
            issues.append({"path": relative, "issue": "no_internal_link"})
    return {
        "version": 1,
        "updated_at": content_lastmod(),
        "method": "static-commercial-indexability-audit",
        "priority_pages": len(paths),
        "issues": issues,
        "incoming_link_distribution": dict(depths),
        "indexnow": {"key_location": f"{SITE}/{INDEXNOW_KEY}.txt", "submission_enabled": True},
        "note": "This report covers static crawl signals. Google indexing verdicts remain private in the Search Console monitor.",
    }


def content_lastmod() -> str:
    values: list[str] = []
    for relative in ("data/partner_offers.json", "data/search_growth_strategy.json"):
        try:
            value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            candidate = str(value.get("updated_at") or "")
            date.fromisoformat(candidate)
            values.append(candidate)
        except (OSError, ValueError, json.JSONDecodeError, AttributeError):
            continue
    return max(values) if values else date.today().isoformat()


def update_sitemap(source: str) -> str:
    rows = [SITEMAP_START]
    rows.append(f"  <url><loc>{SITE}/buyers-guides.html</loc><lastmod>{content_lastmod()}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>")
    if (ROOT / "offer-updates.html").exists():
        alerts = load_public_json(ROOT / "data" / "offer_change_alerts.json")
        rows.append(f"  <url><loc>{SITE}/offer-updates.html</loc><lastmod>{alerts.get('updated_at') or content_lastmod()}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>")
    rows.append(SITEMAP_END)
    row = "\n".join(rows)
    if SITEMAP_START in source and SITEMAP_END in source:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), row, source, flags=re.S)
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + row + "\n</urlset>\n"


def load_public_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def changed_urls() -> list[str]:
    commands = (("git", "diff", "--name-only", "HEAD"), ("git", "diff", "--name-only", "HEAD^", "HEAD"))
    paths: set[str] = set()
    for command in commands:
        try:
            output = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True).stdout
        except OSError:
            continue
        for value in output.splitlines():
            relative = value.strip().replace("\\", "/")
            if relative.endswith((".html", ".xml")) and not relative.startswith((".git/", "newsletter/")):
                paths.add(relative)
    return [f"{SITE}/{path}" for path in sorted(paths)][:10000]


def submit_indexnow(urls: list[str], state_path: Path) -> str:
    if (os.environ.get("INDEXNOW_SUBMIT_ENABLED") or "").casefold() != "true":
        return "IndexNow submission disabled"
    state = load_public_json(state_path)
    pending = sorted(set(str(item) for item in state.get("pending_urls", []) if str(item).startswith(SITE + "/")) | set(urls))[:10000]
    if not pending:
        return "IndexNow has no changed URLs"
    body = json.dumps({"host": "artificial.one", "key": INDEXNOW_KEY, "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt", "urlList": pending}).encode()
    request = Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({"version": 1, "pending_urls": [], "submitted_on": date.today().isoformat()}, indent=2) + "\n", encoding="utf-8")
            return f"IndexNow accepted {len(pending)} changed URLs (HTTP {response.status})"
    except Exception as exc:
        # Search-engine notification is best-effort and must never block a site build.
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"version": 1, "pending_urls": pending}, indent=2) + "\n", encoding="utf-8")
        return f"IndexNow notification deferred ({type(exc).__name__})"


def write_if_changed(path: Path, text: str) -> bool:
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    if previous == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def build(check: bool = False, submit: bool = False, state_path: Path = ROOT / ".indexnow" / "private-state.json") -> int:
    pages = priority_pages()
    priority = crawl_priority_paths(pages)
    hub = render_hub(pages, priority)
    virtual = {HUB_PATH: hub}
    pages_with_hub = [*pages, HUB_PATH]
    sitemap = SITEMAP_PATH.read_text(encoding="utf-8")
    expected_sitemap = update_sitemap(sitemap)
    report = json.dumps(audit(pages_with_hub, virtual, expected_sitemap), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    stale = (not HUB_PATH.exists() or HUB_PATH.read_text(encoding="utf-8") != hub or not REPORT_PATH.exists() or REPORT_PATH.read_text(encoding="utf-8") != report or sitemap != expected_sitemap)
    if check:
        if stale:
            print("Indexing recovery assets are stale.", file=sys.stderr)
            return 1
        print(f"Indexing recovery assets are current ({len(pages_with_hub)} priority pages).")
        return 0
    write_if_changed(HUB_PATH, hub)
    write_if_changed(REPORT_PATH, report)
    write_if_changed(SITEMAP_PATH, expected_sitemap)
    status = submit_indexnow(changed_urls(), state_path) if submit else "IndexNow not requested"
    print(f"Audited {len(pages_with_hub)} priority pages; {status}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--state", type=Path, default=ROOT / ".indexnow" / "private-state.json")
    args = parser.parse_args()
    return build(check=args.check, submit=args.submit, state_path=args.state)


if __name__ == "__main__":
    raise SystemExit(main())
