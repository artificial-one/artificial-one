#!/usr/bin/env python3
"""Fix footer 'Triplo AI Review' -> correct tool name for non-Triplo review pages."""
import re
from pathlib import Path

def slug_to_name(slug: str) -> str:
    """e.g. zapier-alternative -> Zapier Alternative, systeme-io -> Systeme.io"""
    s = slug.replace("-review", "").strip()
    if not s:
        return "Tool"
    # Special cases
    special = {
        "systeme-io": "Systeme.io",
        "mailerlite": "MailerLite",
        "beehiiv": "Beehiiv",
        "akiflow": "Akiflow",
        "rybbit": "Rybbit",
        "figma-alternative": "Figma Alternative",
        "clickup-alternative": "ClickUp Alternative",
        "buffer-alternative": "Buffer Alternative",
        "ahrefs-alternative": "Ahrefs Alternative",
        "hubspot-alternative": "HubSpot Alternative",
        "mailchimp-alternative": "Mailchimp Alternative",
        "loom-alternative": "Loom Alternative",
        "notion-alternative": "Notion Alternative",
        "riverside-alternative": "Riverside Alternative",
        "typeform-alternative": "Typeform Alternative",
        "zapier-alternative": "Zapier Alternative",
    }
    if s in special:
        return special[s]
    # Default: replace - with space, title case
    return s.replace("-", " ").title()

def process(f: Path) -> bool:
    try:
        c = f.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  Read error {f}: {e}")
        return False
    if "Triplo AI Review" not in c or "triplo-ai-review" in f.name:
        return False
    slug = f.stem.replace("-review", "")
    name = slug_to_name(slug)
    new_footer = f"© 2026 artificial.one - {name} Review"
    old = "<p>© 2026 artificial.one - Triplo AI Review</p>"
    new = f"<p>© 2026 artificial.one - {name} Review</p>"
    if old not in c:
        return False
    c = c.replace(old, new, 1)
    f.write_text(c, encoding="utf-8")
    return True

def main():
    root = Path(__file__).resolve().parent
    tools = root / "tools"
    n = 0
    for f in sorted(tools.glob("*-review.html")):
        if process(f):
            print(f"  + {f.relative_to(root)}")
            n += 1
    print(f"\nFixed {n} footer tool names.")

if __name__ == "__main__":
    main()
