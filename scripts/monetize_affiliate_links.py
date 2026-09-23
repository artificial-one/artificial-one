#!/usr/bin/env python3
"""Normalize affiliate links and add contextual revenue placements.

The script is deterministic so it can run unattended in GitHub Actions. It
only promotes offers whose registry status is ``published`` and whose target
files either match an explicit rule or pass the configured relevance score.
"""

from __future__ import annotations

import argparse
from fnmatch import fnmatch
import html
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "partner_offers.json"
PLACEMENTS_PATH = ROOT / "data" / "affiliate_placements.json"
TRACKING_ASSET = "assets/affiliate-tracking.js"
TRACKING_ENDPOINT = "/api/affiliate-event"
ANCHOR_RE = re.compile(r"<a\b[^>]*\bhref=(?P<quote>['\"])(?P<url>[^'\"]+)(?P=quote)[^>]*>", re.I)
MANAGED_RE = re.compile(
    r"<!-- affiliate-placement:(?P<id>[a-z0-9-]+):start -->.*?"
    r"<!-- affiliate-placement:(?P=id):end -->",
    re.I | re.S,
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
AUTO_EXCLUDED = {
    "about.html", "contact.html", "disclosure.html", "index.html",
    "news.html", "partner-offers.html", "partners.html", "privacy.html",
    "terms.html", "ai-tool-finder.html", "partner-opportunities.html",
}
STOP_WORDS = {
    "about", "after", "against", "and", "artificial", "best", "business",
    "change", "choose", "current", "for", "from", "into", "more", "one",
    "platform", "pricing", "software", "teams", "that", "the", "their",
    "this", "tool", "tools", "use", "using", "verify", "with", "your",
}


class MonetizationError(ValueError):
    """Raised when monetization configuration is unsafe or incomplete."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MonetizationError(f"Could not load {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise MonetizationError(f"{path} must be an object with version 1")
    return value


def published_offers(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    offers: dict[str, dict[str, Any]] = {}
    for item in registry.get("offers", []):
        if not isinstance(item, dict) or item.get("status") != "published":
            continue
        offer_id = str(item.get("id", "")).strip()
        tracking_url = str(item.get("tracking_url", "")).strip()
        if not offer_id or not tracking_url.startswith("https://"):
            raise MonetizationError("Published offers require an id and HTTPS tracking_url")
        offers[offer_id] = item
    return offers


def _set_attribute(tag: str, name: str, value: str) -> str:
    # Accept quoted, unquoted and boolean HTML attributes. Generated pages use
    # the compact boolean form for data-affiliate-offer; treating that as
    # absent would append a duplicate attribute and make the pipeline oscillate.
    pattern = re.compile(
        rf"\s{name}(?:=(?:(['\"])(.*?)\1|[^\s>]+))?(?=\s|/?>)",
        re.I | re.S,
    )
    replacement = f' {name}="{html.escape(value, quote=True)}"'
    existing = pattern.search(tag)
    if existing:
        if not value and "=" not in existing.group(0):
            return tag
        return pattern.sub(replacement, tag, count=1)
    return tag[:-1] + replacement + ">"


def _merge_rel(tag: str) -> str:
    match = re.search(r"\srel=(['\"])(.*?)\1", tag, re.I | re.S)
    values = match.group(2).split() if match else []
    for required in ("nofollow", "sponsored", "noopener"):
        if required not in values:
            values.append(required)
    return _set_attribute(tag, "rel", " ".join(values))


def normalize_links(text: str, offers: dict[str, dict[str, Any]]) -> tuple[str, set[str]]:
    by_url: dict[str, str] = {}
    for offer_id, offer in offers.items():
        urls = [str(offer["tracking_url"]), *[str(url) for url in offer.get("legacy_urls", [])]]
        by_url.update((url, offer_id) for url in urls if url)

    found: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        offer_id = by_url.get(match.group("url"))
        if not offer_id:
            return match.group(0)
        found.add(offer_id)
        tag = _merge_rel(match.group(0))
        tag = _set_attribute(tag, "data-affiliate-offer", "")
        tag = _set_attribute(tag, "data-offer-id", offer_id)
        if not re.search(r"\sdata-placement=", tag, re.I):
            tag = _set_attribute(tag, "data-placement", "existing-contextual-link")
        return tag

    return ANCHOR_RE.sub(replace, text), found


def relative_asset_path(page: Path) -> str:
    depth = len(page.relative_to(ROOT).parts) - 1
    return "../" * depth + TRACKING_ASSET


def ensure_tracking_script(text: str, page: Path) -> str:
    if "affiliate-tracking.js" in text:
        return text
    close = re.search(r"</body\s*>", text, re.I)
    if not close:
        raise MonetizationError(f"{page.relative_to(ROOT)} has no </body> tag")
    script = f'<script src="{relative_asset_path(page)}" defer></script>\n'
    return text[: close.start()] + script + text[close.start() :]


def ensure_tracking_endpoint(text: str, page: Path) -> str:
    pattern = re.compile(
        r'<meta\s+name=([\'\"])affiliate-event-endpoint\1\s+content=([\'\"])(.*?)\2\s*/?>',
        re.I | re.S,
    )
    tag = f'<meta name="affiliate-event-endpoint" content="{TRACKING_ENDPOINT}">'
    if pattern.search(text):
        return pattern.sub(tag, text, count=1)
    close = re.search(r"</head\s*>", text, re.I)
    if not close:
        raise MonetizationError(f"{page.relative_to(ROOT)} has no </head> tag")
    return text[: close.start()] + f"  {tag}\n" + text[close.start() :]


def strip_trailing_whitespace(text: str) -> str:
    """Keep generated diffs clean without changing the document's final newline."""
    had_final_newline = text.endswith("\n")
    cleaned = "\n".join(line.rstrip() for line in text.splitlines())
    return cleaned + ("\n" if had_final_newline else "")


def render_placement(rule: dict[str, Any], offer: dict[str, Any]) -> str:
    placement_id = str(rule["id"])
    offer_id = str(offer["id"])
    return f'''\n    <!-- affiliate-placement:{html.escape(placement_id)}:start -->
    <aside class="my-10 rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-purple-50 p-6 shadow-sm" aria-label="Sponsored recommendation">
      <p class="text-xs font-bold uppercase tracking-wide text-indigo-700">Sponsored partner</p>
      <h2 class="mt-2 text-2xl font-bold text-gray-900">{html.escape(str(rule["headline"]))}</h2>
      <p class="mt-3 text-gray-700">{html.escape(str(rule["copy"]))}</p>
      <a href="{html.escape(str(offer["tracking_url"]), quote=True)}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer="" data-offer-id="{html.escape(offer_id)}" data-placement="{html.escape(placement_id)}" class="mt-5 inline-block rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-700">{html.escape(str(rule["cta_label"]))} →</a>
      <a href="https://artificial.one/partner-offers/{html.escape(str(offer["slug"]))}.html" class="ml-0 mt-4 inline-block font-semibold text-indigo-700 hover:underline sm:ml-4">Read our decision guide →</a>
      <p class="mt-3 text-xs text-gray-600">We may earn a commission if you subscribe through this link, at no extra cost to you.</p>
    </aside>
    <!-- affiliate-placement:{html.escape(placement_id)}:end -->\n'''


def insertion_index(text: str, page: Path) -> int:
    # React/JSX pages contain apparent HTML tags inside a Babel script. A raw
    # HTML placement inserted there would break the JavaScript, so append it
    # to the real document body instead.
    if re.search(r"<script[^>]+type=(['\"])text/babel\1", text, re.I):
        matches = list(re.finditer(r"</body\s*>", text, re.I))
        if matches:
            return matches[-1].start()
    matches = list(re.finditer(r"</article\s*>", text, re.I))
    if matches:
        return matches[-1].start()
    matches = list(re.finditer(r"<footer\b", text, re.I))
    if matches:
        return matches[-1].start()
    matches = list(re.finditer(r"</body\s*>", text, re.I))
    if matches:
        return matches[-1].start()
    raise MonetizationError(f"{page.relative_to(ROOT)} has no safe placement insertion point")


def selected_pages(rule: dict[str, Any]) -> list[Path]:
    patterns = rule.get("path_patterns", [])
    if not isinstance(patterns, list) or not patterns:
        raise MonetizationError(f"Placement {rule.get('id')} requires path_patterns")
    selected: set[Path] = set()
    for page in ROOT.rglob("*.html"):
        relative = page.relative_to(ROOT).as_posix()
        if relative.startswith("partner-offers/") or any(fnmatch(relative, str(pattern)) for pattern in patterns):
            if not relative.startswith("partner-offers/"):
                selected.add(page)
    return sorted(selected)


def _tokens(value: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(value.casefold()) if len(token) > 2 and token not in STOP_WORDS}


def page_signal(relative: str, text: str) -> tuple[set[str], str]:
    title = " ".join(re.findall(r"<(?:title|h1)[^>]*>(.*?)</(?:title|h1)>", text, re.I | re.S))
    descriptions = " ".join(re.findall(r'<meta[^>]+(?:name=["\']description["\'][^>]+content|content)=["\']([^"\']+)', text, re.I))
    signal = re.sub(r"<[^>]+>", " ", f"{relative} {title} {descriptions}")
    return _tokens(signal), re.sub(r"[^a-z0-9]+", "", signal.casefold())


def offer_relevance(offer: dict[str, Any], page_tokens: set[str], compact_page: str) -> int:
    name = str(offer.get("name") or "")
    name_tokens = _tokens(name)
    category_tokens = _tokens(str(offer.get("category") or ""))
    use_case_tokens = _tokens(" ".join(str(item) for item in offer.get("use_cases", [])))
    audience_tokens = _tokens(str(offer.get("best_for") or ""))
    score = 8 * len(name_tokens & page_tokens)
    score += 4 * len(category_tokens & page_tokens)
    score += 2 * len(use_case_tokens & page_tokens)
    score += len(audience_tokens & page_tokens)
    compact_name = re.sub(r"[^a-z0-9]+", "", name.casefold())
    if len(compact_name) >= 5 and compact_name in compact_page:
        score += 20
    return score


def automatic_page_rules(
    config: dict[str, Any], offers: dict[str, dict[str, Any]], already_selected: set[Path]
) -> dict[Path, dict[str, Any]]:
    settings = config.get("automatic", {})
    if not isinstance(settings, dict) or not settings.get("enabled"):
        return {}
    roots = tuple(str(item) for item in settings.get("eligible_roots", []))
    minimum = max(1, int(settings.get("minimum_score") or 8))
    limit = max(0, min(1000, int(settings.get("max_pages") or 0)))
    candidates: list[tuple[int, str, Path, dict[str, Any]]] = []
    tracking_urls = tuple(str(item["tracking_url"]) for item in offers.values())
    for page in ROOT.rglob("*.html"):
        relative = page.relative_to(ROOT).as_posix()
        if (
            page in already_selected
            or relative in AUTO_EXCLUDED
            or relative.startswith(("partner-offers/", "search-intent/", ".git/"))
            or (roots and not relative.startswith(roots))
        ):
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        # Re-score an existing automatic placement from the page's underlying
        # content. Otherwise its own CTA would make the next run exclude it,
        # causing the generator to oscillate between adding and removing it.
        scoring_text = MANAGED_RE.sub("", text)
        if "data-affiliate-offer" in scoring_text or any(url in scoring_text for url in tracking_urls):
            continue
        tokens, compact = page_signal(relative, scoring_text)
        if not tokens:
            continue
        ranked = sorted(
            ((offer_relevance(offer, tokens, compact), offer_id, offer) for offer_id, offer in offers.items()),
            key=lambda item: (-item[0], item[1]),
        )
        score, offer_id, offer = ranked[0]
        if score < minimum:
            continue
        rule = {
            "id": f"auto-context-{offer_id}",
            "offer_id": offer_id,
            "headline": f"A relevant option for this workflow: {offer['name']}",
            "copy": str(offer.get("why_consider") or offer.get("summary") or ""),
            "cta_label": str(offer.get("cta_label") or f"Explore {offer['name']}"),
        }
        candidates.append((score, relative, page, rule))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return {page: rule for _score, _relative, page, rule in candidates[:limit]}


def apply(root: Path = ROOT, check: bool = False) -> list[Path]:
    if root != ROOT:
        raise MonetizationError("Alternate roots are not supported")
    offers = published_offers(load_json(REGISTRY_PATH))
    config = load_json(PLACEMENTS_PATH)
    placements = config.get("placements", [])
    if not isinstance(placements, list):
        raise MonetizationError("placements must be a list")

    page_rules: dict[Path, list[dict[str, Any]]] = {}
    for rule in placements:
        if not isinstance(rule, dict):
            raise MonetizationError("Each placement must be an object")
        offer_id = str(rule.get("offer_id", ""))
        if offer_id not in offers:
            continue
        for field in ("id", "headline", "copy", "cta_label"):
            if not str(rule.get(field, "")).strip():
                raise MonetizationError(f"Placement for {offer_id} is missing {field}")
        for page in selected_pages(rule):
            # One contextual commercial block per page keeps recommendations
            # useful and avoids turning high-intent articles into link farms.
            page_rules.setdefault(page, [rule])

    for page, rule in automatic_page_rules(config, offers, set(page_rules)).items():
        page_rules.setdefault(page, [rule])

    candidate_pages = set(page_rules)
    for page in ROOT.rglob("*.html"):
        relative = page.relative_to(ROOT).as_posix()
        if relative.startswith("partner-offers/"):
            continue
        page_text = page.read_text(encoding="utf-8", errors="ignore")
        if "<!-- affiliate-placement:" in page_text:
            candidate_pages.add(page)
        elif any(str(offer["tracking_url"]) in page_text for offer in offers.values()):
            candidate_pages.add(page)
        elif any(
            str(url) in page_text
            for offer in offers.values()
            for url in offer.get("legacy_urls", [])
        ):
            candidate_pages.add(page)

    changed: list[Path] = []
    for page in sorted(candidate_pages):
        original = page.read_text(encoding="utf-8")
        desired_rules = page_rules.get(page, [])
        desired_ids = {str(rule["id"]) for rule in desired_rules}
        is_babel_page = bool(
            re.search(r"<script[^>]+type=(['\"])text/babel\1", original, re.I)
        )
        if is_babel_page:
            # Move any placement emitted by an older generator version out of
            # JSX source before rebuilding it at the real </body> boundary.
            text = MANAGED_RE.sub("", original)
        else:
            text = MANAGED_RE.sub(
                lambda match: match.group(0) if match.group("id") in desired_ids else "",
                original,
            )
        text, found = normalize_links(text, offers)
        for rule in desired_rules:
            offer_id = str(rule["offer_id"])
            placement_id = str(rule["id"])
            pattern = re.compile(
                rf"<!-- affiliate-placement:{re.escape(placement_id)}:start -->.*?"
                rf"<!-- affiliate-placement:{re.escape(placement_id)}:end -->",
                re.I | re.S,
            )
            block = render_placement(rule, offers[offer_id]).strip()
            if pattern.search(text):
                text = pattern.sub(block, text, count=1)
                found.add(offer_id)
                continue
            if offer_id in found:
                continue
            index = insertion_index(text, page)
            text = text[:index] + "\n" + block + "\n" + text[index:]
            found.add(offer_id)
        if found or "data-affiliate-offer" in text:
            text = ensure_tracking_endpoint(text, page)
            text = ensure_tracking_script(text, page)
        text = strip_trailing_whitespace(text)
        if text != original:
            changed.append(page)
            if not check:
                page.write_text(text, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated monetization changes are pending")
    args = parser.parse_args()
    try:
        changed = apply(check=args.check)
    except MonetizationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.check and changed:
        print("Affiliate monetization output is stale:")
        for page in changed:
            print(f"- {page.relative_to(ROOT)}")
        return 1
    print(f"{'Would update' if args.check else 'Updated'} {len(changed)} monetized page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
