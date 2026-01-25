#!/usr/bin/env python3
"""
Apply conversion recommendations to tool review pages with AppSumo affiliate links:
- Fix duplicate rel="nofollow sponsored nofollow sponsored" -> "noopener nofollow sponsored"
- Add sticky CTA bar (CSS + HTML + JS) for deal pages
- Add disclosure near main CTA, specific CTA copy, Related tools section
- Replace "super deal" / "super access" with "lifetime deal" / "lifetime access"
- Update "See More" link to "Browse All 75+ Lifetime Deals" + ../guides/
"""
import re
from pathlib import Path

STICKY_CSS = """
        #sticky-cta-bar { position: fixed; bottom: 0; left: 0; right: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 20px; display: none; align-items: center; justify-content: center; gap: 16px; flex-wrap: wrap; z-index: 9999; box-shadow: 0 -4px 20px rgba(0,0,0,0.15); }
        #sticky-cta-bar.visible { display: flex; }
        #sticky-cta-bar .sticky-cta-text { font-size: 1rem; font-weight: 600; }
        #sticky-cta-bar .sticky-cta-btn { background: white; color: #667eea; padding: 10px 24px; border-radius: 6px; font-weight: 700; text-decoration: none; white-space: nowrap; }
        #sticky-cta-bar .sticky-cta-btn:hover { background: #f0f0f0; }
        @media (max-width: 640px) { #sticky-cta-bar { flex-direction: column; gap: 10px; padding: 12px; } #sticky-cta-bar .sticky-cta-text { text-align: center; font-size: 0.95rem; } }
"""

STICKY_JS = """
(function() {
    var bar = document.getElementById('sticky-cta-bar');
    var cta = document.getElementById('main-cta-box');
    if (!bar || !cta) return;
    var ctaTop = cta.getBoundingClientRect().top + window.pageYOffset;
    function check() {
        if (window.pageYOffset > Math.min(400, ctaTop - 100)) bar.classList.add('visible');
        else bar.classList.remove('visible');
    }
    window.addEventListener('scroll', check);
    window.addEventListener('resize', function() { ctaTop = cta.getBoundingClientRect().top + window.pageYOffset; });
})();
"""

def tool_name_from_path(path: Path) -> str:
    """e.g. neuronwriter-review.html -> NeuronWriter"""
    name = path.stem.replace("-review", "").replace("-", " ")
    return name.title()

def tool_name_from_title(content: str) -> str | None:
    m = re.search(r"<title>([^<]+?) Review [^<]*</title>", content, re.I)
    if m:
        return m.group(1).strip()
    return None

def extract_appsumo_url(content: str) -> str | None:
    m = re.search(r'href="(https?://appsumo\.8odi\.net[^"]+)"', content)
    return m.group(1) if m else None

def extract_price(content: str) -> str:
    m = re.search(r'\$(\d+)\s*\(normally|\$(\d+)\s*one-time|\$(\d+)\s*[\(\)]', content)
    if m:
        for g in m.groups():
            if g:
                return f"${g}"
    m = re.search(r'>\$(\d+)<', content)
    return f"${m.group(1)}" if m else "$69"

def process_file(filepath: Path) -> bool:
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  Read error {filepath}: {e}")
        return False

    if "appsumo.8odi.net" not in content:
        return False

    original = content
    tool = tool_name_from_title(content) or tool_name_from_path(filepath)
    price = extract_price(content)
    url = extract_appsumo_url(content)
    if not url:
        return False

    # 1. Fix duplicate rel
    content = re.sub(
        r'rel="noopener nofollow sponsored nofollow sponsored"',
        'rel="noopener nofollow sponsored"',
        content
    )
    content = re.sub(
        r'rel=\'noopener nofollow sponsored nofollow sponsored\'',
        'rel="noopener nofollow sponsored"',
        content
    )

    # 2. Add sticky CTA CSS if missing
    if "#sticky-cta-bar" not in content and "sticky-cta-bar" not in content:
        content = re.sub(
            r'(\.mobile-dropdown-btn\.active svg \{ transform: rotate\(180deg\); \}\s*)</style>',
            r'\1' + STICKY_CSS + "\n    </style>",
            content,
            count=1
        )

    # 3. Add id="main-cta-box" to first .cta-box
    if 'id="main-cta-box"' not in content and 'class="cta-box"' in content:
        content = content.replace(
            '<div class="cta-box">',
            '<div class="cta-box" id="main-cta-box">',
            1
        )

    # 4. CTA box: "Get X super deal" -> "Get X for $Y — lifetime access", "Get Super Access" -> "Claim X deal", add disclosure
    if 'Get Super Access →' in content:
        content = content.replace('Get Super Access →', f'Claim {tool} deal →', 1)
    if 'Get Super Access' in content:
        content = content.replace('Get Super Access', f'Claim {tool} deal', 1)

    cta_h2_pat = re.compile(r'(<div class="cta-box"[^>]*>)\s*<h2>Get ([^<]+) super deal</h2>')
    content = cta_h2_pat.sub(
        rf'\1\n            <h2>Get \2 for {price} — lifetime access</h2>',
        content,
        count=1
    )

    # Add disclosure after 60-day guarantee if missing
    if "We may earn a commission if you purchase through our link" not in content:
        content = re.sub(
            r'(<p style="font-size: 0\.9em; margin-top: 15px; opacity: 0\.9;">60-day money-back guarantee</p>\s*)(</div>)',
            r'\1            <p style="font-size: 0.85em; margin-top: 10px; opacity: 0.85;">We may earn a commission if you purchase through our link.</p>\n        \2',
            content,
            count=1
        )
    # variant: margin-top: 12px
    if "We may earn a commission if you purchase through our link" not in content:
        content = re.sub(
            r'(<p style="font-size: 0\.9em; margin-top: 12px; opacity: 0\.9;">60-day money-back guarantee</p>\s*)(</div>)',
            r'\1            <p style="font-size: 0.85em; margin-top: 10px; opacity: 0.85;">We may earn a commission if you purchase through our link.</p>\n        \2',
            content,
            count=1
        )

    # 5. Replace "Get X super deal →" in secondary CTA
    content = re.sub(
        re.escape(f'Get {tool} super deal →'),
        f'Claim {tool} {price} deal →',
        content,
        count=1
    )
    content = re.sub(
        r'Get ([A-Za-z0-9 ]+) super deal →',
        lambda m: f'Claim {m.group(1)} {price} deal →',
        content,
        count=1
    )

    # 6. "Get the super deal here" -> "Claim the deal here"
    content = re.sub(
        r'Get the super deal here →',
        'Claim the deal here →',
        content,
        flags=re.I
    )
    content = re.sub(
        r'Get NeuronWriter super deal on hot deal →',
        'Claim NeuronWriter deal →',
        content
    )

    # 7. super deal / super access -> lifetime deal / lifetime access (generic)
    content = re.sub(r'\bsuper deal\b', 'lifetime deal', content, flags=re.I)
    content = re.sub(r'\bsuper access\b', 'lifetime access', content, flags=re.I)
    content = re.sub(r'\bAt \$(\d+) super\b', r'At $\1 one-time', content)
    content = re.sub(r'\$(\d+) super\b', r'$\1 one-time', content)

    # 8. "Is X really super access?" -> "Is X really lifetime access?"
    content = re.sub(
        r'Is ([A-Za-z0-9 ]+) really super access\?',
        r'Is \1 really lifetime access?',
        content,
        flags=re.I
    )
    content = re.sub(
        r'How does the super deal work\?',
        'How does the lifetime deal work?',
        content,
        flags=re.I
    )

    # 9. Related tools section + sticky bar + JS: only if not already present (check HTML, not CSS)
    has_sticky_html = 'id="sticky-cta-bar"' in content
    if "Related Tools" not in content and "Related tools" not in content and not has_sticky_html:
        # Find the "See More" / "← More" / "Browse All" link block (flexible)
        see_more_pat = re.compile(
            r'<div style="text-align: center; margin: 60px 0;">\s*<a href="[^"]*best-lifetime[^"]*"[^>]*>[^<]*</a>\s*</div>\s*</div>\s*<footer>',
            re.DOTALL
        )
        related = f'''        <section style="margin-top: 60px;">
            <h2>Related Tools &amp; Alternatives</h2>
            <p style="margin-bottom: 20px; color: #555;">Compare {tool} with similar tools and lifetime deals:</p>
            <ul style="list-style: none; margin: 0; padding: 0;">
                <li style="margin-bottom: 10px;"><a href="triplo-ai-review.html" style="color: #667eea; font-weight: 600;">Triplo AI</a> — AI assistant, lifetime deal</li>
                <li style="margin-bottom: 10px;"><a href="neuronwriter-review.html" style="color: #667eea; font-weight: 600;">NeuronWriter</a> — SEO writing, one-time price</li>
                <li style="margin-bottom: 10px;"><a href="tidycal-review.html" style="color: #667eea; font-weight: 600;">TidyCal</a> — Scheduling, lifetime deal</li>
                <li style="margin-bottom: 10px;"><a href="cursor-review.html" style="color: #667eea; font-weight: 600;">Cursor</a> — AI code editor</li>
                <li style="margin-bottom: 10px;"><a href="../guides/best-lifetime-ai-tools.html" style="color: #667eea; font-weight: 600;">Best AI Lifetime Deals</a> — Browse all 75+ deals</li>
            </ul>
        </section>

        <div style="text-align: center; margin: 60px 0;">
            <a href="../guides/best-lifetime-ai-tools.html" style="display: inline-block; background: #667eea; color: white; padding: 12px 30px; border-radius: 5px; text-decoration: none; font-weight: 600;">← Browse All 75+ Lifetime Deals</a>
        </div>
    </div>

    <div id="sticky-cta-bar" data-tool="{tool}" data-price="{price}" data-url="{url}">
        <span class="sticky-cta-text">Get {tool} — {price} one-time · 60-day guarantee</span>
        <a href="{url}" class="sticky-cta-btn" target="_blank" rel="noopener nofollow sponsored">Claim deal →</a>
    </div>

    <footer>'''
        match = see_more_pat.search(content)
        if match:
            content = content[:match.start()] + related + content[match.end():]

    # 10. Update "See More AI Tools" / "See More Super Deals" etc. to "Browse All 75+ Lifetime Deals" + ../guides/
    content = re.sub(
        r'<a href="guides/best-lifetime-ai-tools\.html"([^>]*)>← See More AI Tools with Super Access</a>',
        r'<a href="../guides/best-lifetime-ai-tools.html"\1>← Browse All 75+ Lifetime Deals</a>',
        content
    )
    content = re.sub(
        r'<a href="([^"]*best-lifetime[^"]*)"([^>]*)>← See More [^<]*</a>',
        r'<a href="../guides/best-lifetime-ai-tools.html"\2>← Browse All 75+ Lifetime Deals</a>',
        content
    )
    content = re.sub(
        r'<a href="([^"]*best-lifetime[^"]*)"([^>]*)>← More AI [^<]*</a>',
        r'<a href="../guides/best-lifetime-ai-tools.html"\2>← Browse All 75+ Lifetime Deals</a>',
        content
    )
    content = re.sub(
        r'<a href="([^"]*best-lifetime[^"]*)"([^>]*)>← See More Super Deals</a>',
        r'<a href="../guides/best-lifetime-ai-tools.html"\2>← Browse All 75+ Lifetime Deals</a>',
        content
    )

    # 11. Add sticky CTA scroll JS before </script></body> (only if we have sticky bar HTML)
    if 'id="sticky-cta-bar"' in content and "ctaTop = cta.getBoundingClientRect" not in content:
        # forEach(btn => { btn.addEventListener(..., function() { ... }); });
        js_block = re.compile(
            r'(document\.querySelectorAll\([\'"]\.mobile-dropdown-btn[\'"]\)\.forEach\(btn => \{[\s\S]*?\}\);[\s\S]*?\}\);)\s*(</script>\s*</body>)',
            re.DOTALL
        )
        def add_sticky_js(m):
            return m.group(1) + "\n" + STICKY_JS + "\n" + m.group(2)
        content = js_block.sub(add_sticky_js, content, count=1)

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True
    return False

def main():
    root = Path(__file__).resolve().parent
    tools_dir = root / "tools"
    if not tools_dir.is_dir():
        print("tools/ not found")
        return
    total = 0
    for f in sorted(tools_dir.glob("*-review.html")):
        if "triplo-ai" in f.name:
            continue
        if process_file(f):
            print(f"  + {f.relative_to(root)}")
            total += 1
    print(f"\nUpdated {total} deal review files.")

if __name__ == "__main__":
    main()
