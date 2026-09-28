#!/usr/bin/env python3
"""Mechanically align legacy landing pages with current evidence and brand language."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "about.html", ROOT / "reviews.html", ROOT / "blog.html")
TOOL_PAGES = tuple(sorted((ROOT / "tools").glob("*.html")))
GUIDE_PAGES = tuple(sorted((ROOT / "guides").glob("*.html")))
COMPARE_PAGES = tuple(sorted((ROOT / "compare").glob("*.html")))
EDITORIAL_PAGES = (
    ROOT / "sitemap.html",
    ROOT / "blog-57-new-appsumo-deals-2026.html",
    ROOT / "blog-appsumo-writers-designers-2026.html",
)
TOOL_STYLE_MARKER = "<!-- AI1 LEGACY TOOL SHELL -->"
LEGACY_TOOL_STYLE = "../assets/legacy-tool-pages.css?v=20260928a"
EDITORIAL_HEADER_MARKER = "<!-- AI1 LEGACY EDITORIAL SHELL -->"


def normalize(source: str) -> str:
    source = source.replace("artificial-one-logo-large.svg", "images/social/artificial-one-logo.png")
    source = source.replace(
        "Learn how artificial.one uses best-in-class AI agents to test and review 220+ AI tools. Automated testing with human oversight for unbiased reviews.",
        "Learn how artificial.one tracks 634 tools and maintains 220 source-backed reviews with automated monitoring and transparent commercial disclosures.",
    )
    source = source.replace(
        "The artificial.one project runs <strong>best-in-class AI agents</strong> to automatically test and review AI tools at scale. Our autonomous systems work 24/7 to evaluate 220+ tools across writing, design, video, coding, and more.",
        "The artificial.one project uses <strong>automated monitoring and source-backed editorial review</strong> to track product, pricing and availability changes at scale. The system continuously maintains evidence for 220 reviewed tools across writing, design, video, coding and more.",
    )
    source = source.replace("Automated Testing", "Automated Monitoring")
    source = source.replace("Test 220+ tools continuously—something impossible for human reviewers.", "Monitor 634 tools continuously and route meaningful changes into human-readable decision pages.")
    source = source.replace("Same testing methodology applied to every tool, every time.", "The same evidence and verification rules are applied to every reviewed tool.")
    source = source.replace("Browse 220+ AI tools, all tested and reviewed by our AI agents.", "Browse 220 source-backed AI-tool reviews maintained by automated monitoring.")
    source = source.replace("We only recommend tools we’ve tested and believe are worth your time.", "We recommend tools only when current sources support a useful buyer fit, and we state important limitations before the click.")
    source = source.replace("The artificial.one project runs best-in-class AI agents to automatically test and review AI tools at scale.", "The artificial.one project uses automated monitoring and source-backed editorial review at scale.")
    source = source.replace("Our AI agents test each tool with real-world scenarios, measuring quality, speed, accuracy, and usability.", "Our system checks official product evidence, live destinations, pricing notes and buyer-relevant limitations.")
    source = source.replace("Test 220+ tools continuously\u2014something impossible for human reviewers.", "Monitor 634 tools continuously and route meaningful changes into buyer-facing reviews.")
    source = source.replace("We believe AI can review AI more thoroughly, consistently, and objectively than humanly possible. Our agents perform hundreds of tests, analyze outputs, measure performance, and write detailed reviews—all automatically.", "We use automation to monitor official sources consistently, detect changes and maintain buyer-facing review pages. We distinguish monitored records, source-backed reviews and verified partner offers rather than presenting automated monitoring as firsthand product use.")
    source = source.replace("We've tested 283+ AI tools so you don't have to. Real pros, cons, and ratings from actual use.", "Compare source-backed AI-tool profiles with visible pros, limitations and pricing notes. Confirm live terms before buying.")
    source = source.replace("We tested both AI assistants for 30 days on real tasks. Here's what we found.", "We compared published features, pricing and documented workflows. Here is what the available evidence shows.")
    source = source.replace("As an AI agent reviewing 283+ tools, I tested ", "Using source-backed product research, we reviewed ")
    source = source.replace(" for 30 days. Here's how ", ". Here is how ")
    source = re.sub(
        r"Here is how it eliminated my biggest productivity bottleneck and saved me 15\+[^<\n]*",
        "Here is what its published workflow suggests and what buyers should verify.",
        source,
    )
    source = re.sub(
        r"Using source-backed product research, we reviewed ([^.<\n]+)\.[^<\n]*",
        r"Using source-backed product research, we reviewed \1. See its published workflow, trade-offs and buyer checks.",
        source,
    )
    source = re.sub(
        r"How ([^<\n]+?) Transformed My [^<\n]+",
        r"How \1 Fits This Workflow",
        source,
    )
    if "assets/affiliate-tracking.js" not in source and "</body>" in source:
        source = source.replace("</body>", '    <script src="assets/affiliate-tracking.js" defer></script>\n</body>', 1)
    return source


def normalize_guide_page(source: str) -> str:
    """Repair legacy guide-relative links and preserve usable mobile layout."""
    source = source.replace('href="guides/', 'href="')
    if 'name="viewport"' not in source and "</head>" in source:
        source = source.replace(
            "</head>",
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n</head>',
            1,
        )
    if not re.search(r"<style\b|<link[^>]+rel=[\"']stylesheet[\"']|cdn\.tailwindcss", source, re.I):
        source = source.replace(
            "</head>",
            '    <link rel="stylesheet" href="../assets/legacy-editorial-pages.css">\n</head>',
            1,
        )
        source = re.sub(r"<body([^>]*)>", r'<body\1 class="legacy-editorial-page">', source, count=1, flags=re.I)
    if "legacy-editorial-pages.css" in source:
        source = ensure_editorial_shell(source, "../")
    return source


def normalize_compare_page(source: str) -> str:
    source = source.replace(
        'href="/best-lifetime-deal-software-2026/"',
        'href="../guides/best-lifetime-deal-software-2026.html"',
    )
    if 'name="viewport"' not in source and "</head>" in source:
        source = source.replace(
            "</head>",
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n</head>',
            1,
        )
    if not re.search(r"<style\b|<link[^>]+rel=[\"']stylesheet[\"']|cdn\.tailwindcss", source, re.I):
        source = source.replace(
            "</head>",
            '    <link rel="stylesheet" href="../assets/legacy-editorial-pages.css">\n</head>',
            1,
        )
        source = re.sub(r"<body([^>]*)>", r'<body\1 class="legacy-editorial-page">', source, count=1, flags=re.I)
    if "legacy-editorial-pages.css" in source:
        source = ensure_editorial_shell(source, "../")
    return source


def ensure_editorial_shell(source: str, prefix: str) -> str:
    source = source.replace(
        "images/artificial-one-elephant-mark.png",
        "images/branding/artificial-one-elephant-mark.png",
    )
    if EDITORIAL_HEADER_MARKER in source:
        return source
    header = f'''{EDITORIAL_HEADER_MARKER}<header class="legacy-editorial-header">
      <a class="legacy-editorial-brand" href="{prefix}index.html"><img src="{prefix}images/branding/artificial-one-elephant-mark.png" alt=""><span>artificial.one</span></a>
      <nav class="legacy-editorial-nav" aria-label="Primary navigation"><a href="{prefix}ask-elephant.html">Ask Elephant</a><a href="{prefix}reviews.html">Reviews</a><a href="{prefix}buyers-guides.html">Buyer Guides</a><a href="{prefix}news.html">News</a></nav>
    </header>'''
    return re.sub(r"(<body[^>]*>)", rf"\1{header}", source, count=1, flags=re.I)


def normalize_editorial_page(source: str) -> str:
    if 'name="viewport"' not in source and "</head>" in source:
        source = source.replace(
            "</head>",
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n</head>',
            1,
        )
    if "legacy-editorial-pages.css" not in source and "</head>" in source:
        source = source.replace(
            "</head>",
            '    <link rel="stylesheet" href="assets/legacy-editorial-pages.css">\n</head>',
            1,
        )
    if "legacy-editorial-page" not in source:
        source = re.sub(r"<body([^>]*)>", r'<body\1 class="legacy-editorial-page">', source, count=1, flags=re.I)
    return ensure_editorial_shell(source, "")


def normalize_tool_page(source: str) -> str:
    """Apply the current shell without rewriting a legacy review's content."""
    source = source.replace('<body class="bg-white">', '<body class="bg-white legacy-tool-page">', 1)
    source = source.replace("<body>", '<body class="legacy-tool-page">', 1)
    source = source.replace('href="guides/', 'href="../guides/')
    source = re.sub(
        r"\.\./assets/legacy-tool-pages\.css(?:\?v=[^\"']+)?",
        LEGACY_TOOL_STYLE,
        source,
    )
    if TOOL_STYLE_MARKER not in source and "</head>" in source:
        styles = (
            f"    {TOOL_STYLE_MARKER}\n"
            '    <link rel="stylesheet" href="../assets/decision-engine.css">\n'
            f'    <link rel="stylesheet" href="{LEGACY_TOOL_STYLE}">\n'
        )
        source = source.replace("</head>", styles + "</head>", 1)
    if "assets/affiliate-tracking.js" not in source and "</body>" in source:
        source = source.replace(
            "</body>",
            '    <script src="../assets/affiliate-tracking.js" defer></script>\n</body>',
            1,
        )
    return source


def main(check: bool = False) -> int:
    stale: list[str] = []
    for path in PAGES:
        current = path.read_text(encoding="utf-8")
        expected = normalize(current)
        if path.name == "blog.html":
            expected = expected.replace("blog-midjourney-dalle.html", "blog-midjourney-vs-dalle.html")
        if current == expected:
            continue
        if check:
            stale.append(path.name)
        else:
            path.write_text(expected, encoding="utf-8")
    for path in GUIDE_PAGES:
        current = path.read_text(encoding="utf-8")
        expected = normalize_guide_page(current)
        if current == expected:
            continue
        if check:
            stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.write_text(expected, encoding="utf-8")
    for path in COMPARE_PAGES:
        current = path.read_text(encoding="utf-8")
        expected = normalize_compare_page(current)
        if current == expected:
            continue
        if check:
            stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.write_text(expected, encoding="utf-8")
    for path in EDITORIAL_PAGES:
        current = path.read_text(encoding="utf-8")
        expected = normalize_editorial_page(current)
        if current == expected:
            continue
        if check:
            stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.write_text(expected, encoding="utf-8")
    for path in TOOL_PAGES:
        current = path.read_text(encoding="utf-8")
        expected = normalize_tool_page(current)
        if current == expected:
            continue
        if check:
            stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.write_text(expected, encoding="utf-8")
    if stale:
        sample = ", ".join(stale[:12])
        suffix = f" (+{len(stale) - 12} more)" if len(stale) > 12 else ""
        print("Legacy brand normalization is stale: " + sample + suffix)
        return 1
    print("Legacy brand and evidence language are aligned.")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main("--check" in sys.argv))
