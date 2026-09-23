#!/usr/bin/env python3
"""Mechanically align legacy landing pages with current evidence and brand language."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "about.html", ROOT / "reviews.html", ROOT / "blog.html")


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


def main(check: bool = False) -> int:
    stale: list[str] = []
    for path in PAGES:
        current = path.read_text(encoding="utf-8")
        expected = normalize(current)
        if current == expected:
            continue
        if check:
            stale.append(path.name)
        else:
            path.write_text(expected, encoding="utf-8")
    if stale:
        print("Legacy brand normalization is stale: " + ", ".join(stale))
        return 1
    print("Legacy brand and evidence language are aligned.")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main("--check" in sys.argv))
