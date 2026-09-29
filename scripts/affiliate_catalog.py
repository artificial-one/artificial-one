#!/usr/bin/env python3
"""Shared, source-agnostic helpers for the monetized software catalogue."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
TOOL_INTELLIGENCE_PATH = ROOT / "data" / "tool_intelligence.json"

CLUSTERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("content-writing", "Content & Writing", ("writing", "content", "copy", "document", "pdf", "translation")),
    ("video-creative", "Video & Creative", ("video", "design", "creative", "image", "presentation", "visual")),
    ("audio-voice", "Audio & Voice", ("audio", "voice", "podcast", "music", "speech")),
    ("marketing-sales", "Marketing & Sales", ("marketing", "sales", "advert", "email", "social", "crm", "lead", "conversion")),
    ("seo-visibility", "SEO & Visibility", ("seo", "search", "visibility", "keyword", "traffic")),
    ("automation-productivity", "Automation & Productivity", ("automation", "productivity", "workflow", "collaboration", "scheduling", "assistant")),
    ("data-development", "Data & Development", ("data", "development", "developer", "code", "database", "analytics", "api", "hosting")),
    ("business-operations", "Business Operations", ("business", "operations", "finance", "commerce", "customer", "hr", "legal", "security", "project")),
    ("education-training", "Education & Training", ("education", "training", "course", "learning", "practice", "research")),
)


def valid_https(value: Any) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme == "https" and bool(parsed.netloc)


def cluster_for(*values: Any) -> tuple[str, str]:
    fields = [str(value or "").casefold() for value in values]
    category = fields[0] if fields else ""
    context = " ".join(fields[1:])
    scored: list[tuple[int, int, str, str]] = []
    for index, (slug, label, needles) in enumerate(CLUSTERS):
        category_hits = sum(needle in category for needle in needles)
        context_hits = sum(needle in context for needle in needles)
        scored.append((category_hits * 8 + context_hits, -index, slug, label))
    score, _priority, slug, label = max(scored)
    if score:
        return slug, label
    return "business-operations", "Business Operations"


def profile_path(tool: dict[str, Any]) -> str:
    links = tool.get("links") if isinstance(tool.get("links"), dict) else {}
    value = str(links.get("profile") or links.get("partner_guide") or "").strip().lstrip("/")
    return value if value.endswith(".html") else ""


def monetized_tools(path: Path = TOOL_INTELLIGENCE_PATH) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in payload.get("tools", []):
        if not isinstance(tool, dict):
            continue
        monetization = tool.get("monetization") if isinstance(tool.get("monetization"), dict) else {}
        links = tool.get("links") if isinstance(tool.get("links"), dict) else {}
        identifier = str(monetization.get("offer_id") or tool.get("id") or "").strip()
        if not identifier or identifier in seen or not monetization.get("active"):
            continue
        if not valid_https(links.get("affiliate")) or not profile_path(tool):
            continue
        item = dict(tool)
        item["offer_id"] = identifier
        item["affiliate_url"] = str(links["affiliate"])
        item["profile_path"] = profile_path(tool)
        cluster_slug, cluster_label = cluster_for(
            tool.get("category"), tool.get("best_for"), tool.get("summary"), tool.get("search_text")
        )
        item["cluster_slug"] = cluster_slug
        item["cluster_label"] = cluster_label
        result.append(item)
        seen.add(identifier)
    return sorted(result, key=lambda item: str(item.get("name") or "").casefold())


def safe_slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")
