#!/usr/bin/env python3
"""Fix breadcrumb backslashes in JSON-LD and add email capture to tool pages. Run from repo root."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMAIL_BLOCK = '''
        <div class="my-6 p-4 bg-gray-50 rounded-xl border border-gray-200" data-beehiiv-form="newsletter">
            <p class="text-sm font-medium text-gray-700 mb-2">Get weekly AI tool deals delivered free.</p>
            <form class="flex flex-wrap gap-2" action="#" method="post" data-beehiiv-subscribe>
                <input type="email" name="email" placeholder="you@example.com" class="flex-1 min-w-[200px] px-3 py-2 border border-gray-300 rounded-lg text-sm" required />
                <button type="submit" class="px-4 py-2 bg-purple-600 text-white rounded-lg font-semibold text-sm hover:bg-purple-700">Subscribe</button>
            </form>
        </div>
'''

def fix_breadcrumbs(content: str) -> str:
    """Replace artificial.one/xxx\\ with artificial.one/xxx/ in JSON-LD URLs."""
    # Match URL with backslash (e.g. tools\\slug.html) and replace \\ with /
    return re.sub(r'(https?://artificial\.one/[^"]*)\\\\([^"]*)', r'\1/\2', content)

def add_email_to_tool_page(content: str) -> str:
    """Insert email block after first </p> following </header> (intro paragraph)."""
    if 'data-beehiiv-form="newsletter"' in content or 'data-beehiiv-subscribe' in content:
        return content
    header_pos = content.find("<header")
    if header_pos == -1:
        return content
    # Find first </p> after <header (intro paragraph)
    p_end = content.find("</p>", header_pos)
    if p_end == -1:
        return content
    idx = p_end + len("</p>")
    return content[:idx] + "\n" + EMAIL_BLOCK + content[idx:]

def main():
    breadcrumb_fixes = 0
    email_adds = 0
    dirs = ["tools", "best", "compare", "guides", "tutorials", "category"]
    for dir_name in dirs:
        d = ROOT / dir_name
        if not d.is_dir():
            continue
        for f in d.rglob("*.html"):
            try:
                text = f.read_text(encoding="utf-8")
                orig = text
                if "\\\\" in text or '\\\\' in text:
                    text = fix_breadcrumbs(text)
                    if text != orig:
                        f.write_text(text, encoding="utf-8")
                        breadcrumb_fixes += 1
            except Exception as e:
                print(f"Error {f}: {e}")
    # Email block: only /tools/ pages (152)
    tools_dir = ROOT / "tools"
    for f in tools_dir.glob("*.html"):
        if f.name == "placeholder" or f.name.startswith("index"):
            continue
        try:
            text = f.read_text(encoding="utf-8")
            if "data-beehiiv-form" in text:
                continue
            new_text = add_email_to_tool_page(text)
            if new_text != text:
                f.write_text(new_text, encoding="utf-8")
                email_adds += 1
        except Exception as e:
            print(f"Error {f}: {e}")
    print(f"Breadcrumb fixes: {breadcrumb_fixes}")
    print(f"Email block added: {email_adds}")

if __name__ == "__main__":
    main()
