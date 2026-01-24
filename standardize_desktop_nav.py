#!/usr/bin/env python3
"""Replace desktop nav with index-style canonical nav (Categories, Explore, Lifetime Deals, Blog, About, Browse Tools)."""
import re
from pathlib import Path

def desktop_nav_html(prefix: str) -> str:
    """Canonical desktop nav matching index.html. prefix is '' or '../'."""
    return f'''<div class="hidden md:flex gap-4 sm:gap-6 items-center text-sm sm:text-base">
                    <div class="dropdown">
                        <span class="text-gray-600 hover:text-indigo-600 font-medium cursor-pointer">Categories ▾</span>
                        <div class="dropdown-content">
                            <a href="{prefix}category/writing-content.html">✍️ Writing & Content</a>
                            <a href="{prefix}category/design-images.html">🎨 Design & Images</a>
                            <a href="{prefix}category/video-animation.html">🎬 Video & Animation</a>
                            <a href="{prefix}category/coding-development.html">💻 Coding & Development</a>
                            <a href="{prefix}category/productivity-business.html">📊 Productivity & Business</a>
                            <a href="{prefix}category/voice-audio.html">🎙️ Voice & Audio</a>
                            <a href="{prefix}category/research-data.html">🔬 Research & Data</a>
                            <a href="{prefix}category/marketing-social.html">📱 Marketing & Social</a>
                            <a href="{prefix}category/data-analytics.html">📈 Data & Analytics</a>
                        </div>
                    </div>
                    <div class="dropdown">
                        <span class="text-gray-600 hover:text-indigo-600 font-medium cursor-pointer">Explore ▾</span>
                        <div class="dropdown-content">
                            <a href="{prefix}compare/index.html">🔍 Compare Tools</a>
                            <a href="{prefix}best/index.html">🏆 Best Of Lists</a>
                            <a href="{prefix}tutorials/index.html">📚 Tutorials</a>
                            <a href="{prefix}guides/index.html">📖 Guides</a>
                        </div>
                    </div>
                    <div class="dropdown">
                        <span class="text-gray-600 hover:text-indigo-600 font-medium cursor-pointer">💰 Lifetime Deals ▾</span>
                        <div class="dropdown-content">
                            <a href="{prefix}guides/best-lifetime-deal-software-2026.html">🎯 Browse All Deals</a>
                            <a href="{prefix}compare/index.html">🔍 Compare Tools</a>
                            <a href="{prefix}guides/use-case-startups.html">🚀 Best for Startups</a>
                            <a href="{prefix}guides/use-case-freelancers.html">💼 Best for Freelancers</a>
                            <a href="{prefix}guides/best-lifetime-ai-tools.html">🤖 AI Tools</a>
                            <a href="{prefix}guides/best-lifetime-productivity-under-50.html">⚡ Under $50</a>
                        </div>
                    </div>
                    <a href="{prefix}blog.html" class="text-gray-600 hover:text-indigo-600 font-medium">Blog</a>
                    <a href="{prefix}about.html" class="text-gray-600 hover:text-indigo-600 font-medium">About</a>
                    <a href="{prefix}reviews.html" class="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white px-4 sm:px-6 py-2 rounded-lg font-semibold">Browse Tools</a>
                </div>'''

def get_prefix(filepath: Path) -> str:
    """Path prefix for hrefs: ../ for subdirs, '' for root."""
    parts = filepath.parts
    if len(parts) <= 1:
        return ''
    return '../'

def find_matching_div_end(html: str, start: int) -> int:
    """Find end of div starting at start (position of <). Returns index past </div> or -1."""
    depth = 0
    i = start
    in_tag = False
    in_attr = False
    quote = None
    while i < len(html):
        c = html[i]
        if in_attr:
            if c == quote and (i == 0 or html[i-1] != '\\'):
                in_attr = False
            i += 1
            continue
        if in_tag:
            if c == '>':
                in_tag = False
                if depth == 0:
                    depth = 1
                i += 1
                continue
            if (c == '"' or c == "'") and (i == 0 or html[i-1] != '\\'):
                in_attr = True
                quote = c
            i += 1
            continue
        if html[i:i+4] == '<div' and (i + 4 >= len(html) or html[i+4] in ' \t\n>/'):
            depth += 1
            in_tag = True
            i += 4
            continue
        if html[i:i+6] == '</div>':
            depth -= 1
            if depth == 0:
                return i + 6
            i += 6
            continue
        i += 1
    return -1

def replace_desktop_nav(html: str, prefix: str) -> str:
    """Replace desktop nav block with canonical. Returns modified html or same if no match."""
    # Match <div class="hidden md:flex ..."> (desktop nav container)
    pat = re.compile(r'<div\s+class="hidden\s+md:flex\s+[^"]*"[^>]*>', re.IGNORECASE)
    m = pat.search(html)
    if not m:
        return html
    start = m.start()
    end = find_matching_div_end(html, m.start())
    if end == -1:
        return html
    new_block = desktop_nav_html(prefix)
    return html[:start] + new_block + html[end:]

def replace_desktop_nav_id(html: str, prefix: str) -> str:
    """Replace <div id="desktop-nav" ...> (inline-style guides/tools)."""
    pat = re.compile(r'<div\s+id="desktop-nav"[^>]*>', re.IGNORECASE)
    m = pat.search(html)
    if not m:
        return html
    start = m.start()
    end = find_matching_div_end(html, m.start())
    if end == -1:
        return html
    new_block = desktop_nav_html(prefix)
    return html[:start] + new_block + html[end:]

def ensure_dropdown_css(html: str) -> str:
    """Ensure .dropdown styles exist (for pages that only had simple nav)."""
    if '.dropdown' in html and 'dropdown-content' in html:
        return html
    # Insert minimal dropdown CSS before </style> or </head>
    css = '''
        .dropdown { position: relative; display: inline-block; }
        .dropdown .dropdown-content { display: none; position: absolute; background: white; min-width: 240px; box-shadow: 0 8px 16px rgba(0,0,0,0.15); border-radius: 8px; z-index: 100; top: calc(100% + 5px); left: -15px; padding: 12px 0; }
        .dropdown:hover .dropdown-content, .dropdown .dropdown-content:hover { display: block; }
        .dropdown-content a { color: #4b5563; padding: 14px 20px; text-decoration: none; display: block; }
        .dropdown-content a:hover { background: #f3f4f6; color: #6366f1; }
'''
    if '</style>' in html:
        html = html.replace('</style>', css + '</style>', 1)
    elif '<style>' in html:
        html = html.replace('<style>', '<style>' + css, 1)
    elif '</head>' in html:
        html = html.replace('</head>', '<style>' + css + '</style></head>', 1)
    return html

def ensure_tailwind(html: str) -> str:
    """Add Tailwind CDN if missing (needed for hidden md:flex nav)."""
    if 'tailwindcss.com' in html:
        return html
    if '</head>' not in html:
        return html
    tailwind = '<script src="https://cdn.tailwindcss.com"></script>\n'
    return html.replace('</head>', tailwind + '</head>', 1)

def process(p: Path) -> bool:
    try:
        content = p.read_text(encoding='utf-8')
    except Exception:
        return False
    if p.name == 'index.html' and ('id="root"' in content or 'React' in content):
        return False
    if '<nav' not in content and 'desktop-nav' not in content:
        return False
    prefix = get_prefix(p)
    original = content

    # Try hidden md:flex desktop nav (Tailwind)
    content = replace_desktop_nav(content, prefix)
    if content == original:
        content = replace_desktop_nav_id(content, prefix)

    if content != original:
        content = ensure_dropdown_css(content)
        content = ensure_tailwind(content)
        p.write_text(content, encoding='utf-8')
        return True
    return False

def main():
    n = 0
    for path in sorted(Path('.').rglob('*.html')):
        if process(path):
            print(path)
            n += 1
    print(f'Updated desktop nav on {n} files')

if __name__ == '__main__':
    main()
