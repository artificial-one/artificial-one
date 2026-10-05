#!/usr/bin/env python3
"""Keep public HTML metadata unique, canonical and useful after generators run."""

from __future__ import annotations

from collections import defaultdict
from html import unescape
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
DESCRIPTION = re.compile(r'<meta\b(?=[^>]*\bname=["\']description["\'])[^>]*>', re.I)
CONTENT = re.compile(r'\bcontent=(?:"([^"]*)"|\'([^\']*)\')', re.I)
CANONICAL = re.compile(r'<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>', re.I)
GENERIC_DESCRIPTION = "Categories ▾"


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def canonical_for(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    return "https://www.artificial.one/" if relative == "index.html" else f"https://www.artificial.one/{relative}"


def description_for(path: Path, source: str) -> str:
    h1 = clean((H1.search(source) or TITLE.search(source)).group(1)) if (H1.search(source) or TITLE.search(source)) else path.stem.replace("-", " ").title()
    section = path.parent.name.replace("-", " ") if path.parent != ROOT else "AI software"
    value = f"Explore {h1}: a practical {section} guide with fit, limitations, comparisons and clear next steps from artificial.one."
    return value[:157].rstrip(" ,;:.") + "."


def run(root: Path = ROOT) -> dict[str, int]:
    pages = [
        path for path in root.rglob("*.html")
        if ".git" not in path.parts
        and "Claude" not in path.parts
        and not path.name.startswith("google")
    ]
    titles: dict[str, list[Path]] = defaultdict(list)
    changed = descriptions = canonicals = unique_titles = 0
    for path in pages:
        source = path.read_text(encoding="utf-8", errors="ignore")
        match = TITLE.search(source)
        if match:
            titles[clean(match.group(1)).casefold()].append(path)

    for paths in titles.values():
        if len(paths) < 2:
            continue
        for path in sorted(paths)[1:]:
            source = path.read_text(encoding="utf-8", errors="ignore")
            match = TITLE.search(source)
            if not match:
                continue
            base = clean(match.group(1)).removesuffix(" | artificial.one")
            qualifier = path.parent.name.replace("-", " ").title() if path.parent != root else path.stem.replace("-", " ").title()
            replacement = f"<title>{base} — {qualifier} | artificial.one</title>"
            updated = source[:match.start()] + replacement + source[match.end():]
            if updated != source:
                path.write_text(updated, encoding="utf-8")
                unique_titles += 1

    for path in pages:
        source = path.read_text(encoding="utf-8", errors="ignore")
        original = source
        description = DESCRIPTION.search(source)
        content_match = CONTENT.search(description.group(0)) if description else None
        current_description = (content_match.group(1) or content_match.group(2)) if content_match else ""
        if not description or GENERIC_DESCRIPTION in current_description or len(clean(current_description)) < 55:
            tag = f'<meta name="description" content="{description_for(path, source)}">'
            if description:
                source = source[:description.start()] + tag + source[description.end():]
            else:
                source = source.replace("</title>", f"</title>\n  {tag}", 1)
            descriptions += 1
        if not CANONICAL.search(source):
            source = source.replace("</title>", f'</title>\n  <link rel="canonical" href="{canonical_for(path)}">', 1)
            canonicals += 1
        if source != original:
            path.write_text(source, encoding="utf-8")
            changed += 1
    return {"pages_changed": changed + unique_titles, "descriptions": descriptions, "canonicals": canonicals, "titles": unique_titles}


if __name__ == "__main__":
    result = run()
    print("SEO hygiene: " + ", ".join(f"{key}={value}" for key, value in result.items()))
