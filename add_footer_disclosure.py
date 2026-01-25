#!/usr/bin/env python3
"""
Add affiliate disclosure to footer on all HTML pages that have © 2026 artificial.one
but don't already contain "We use affiliate links".
"""
import re
from pathlib import Path

DISCLOSURE_P = '<p class="text-sm opacity-90 mt-2">We use affiliate links. We may earn a commission if you buy through our links (no extra cost to you).</p>'

def process_file(filepath: Path) -> bool:
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  Read error: {e}")
        return False

    if "We use affiliate links" in content or "we may earn a commission" in content.lower():
        return False
    if "© 2026 artificial.one" not in content:
        return False

    # Insert disclosure between </p> and </footer> (footer's single <p>© 2026...</p>)
    # Match: <p>© 2026 artificial.one - ...</p> followed by whitespace and </footer>
    pattern = r'(<p[^>]*>© 2026 artificial\.one[^<]*</p>)(\s*)(</footer>)'
    def repl(m):
        p, ws, end = m.group(1), m.group(2), m.group(3)
        nl = "\n" if "\n" in ws else " "
        indent = "        " if "\n" in ws else " "
        return p + nl + indent + DISCLOSURE_P + nl + "    " + end
    new_content = re.sub(pattern, repl, content, count=1)
    if new_content != content:
        filepath.write_text(new_content, encoding="utf-8")
        return True
    return False

def main():
    root = Path(__file__).resolve().parent
    dirs = ["guides", "tools", "best", "category", "compare", "tutorials"]
    total = 0
    for d in dirs:
        folder = root / d
        if not folder.is_dir():
            continue
        for f in folder.rglob("*.html"):
            if process_file(f):
                print(f"  + {f.relative_to(root)}")
                total += 1
    # Blog posts in root
    for f in root.glob("blog-*.html"):
        if process_file(f):
            print(f"  + {f.name}")
            total += 1
    print(f"\nUpdated {total} files with footer disclosure.")

if __name__ == "__main__":
    main()
