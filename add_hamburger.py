#!/usr/bin/env python3
"""Add hamburger menu to Tailwind pages that don't have mobile-menu-btn."""
import re
from pathlib import Path

# Standard mobile menu HTML template. {prefix} is '' or '../'
MOBILE_MENU_HTML = '''
            <div id="mobile-menu" class="hidden md:hidden pb-4" style="border-top: 1px solid #e5e7eb; margin-top: 1rem;">
                <div class="flex flex-col space-y-3">
                    <a href="{prefix}reviews.html" class="bg-gradient-to-r from-violet-600 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Reviews</a>
                    <a href="{prefix}blog.html" class="bg-gradient-to-r from-green-600 to-teal-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Blog</a>
                    <a href="{prefix}about.html" class="bg-gradient-to-r from-orange-600 to-red-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">About</a>
                    <a href="{prefix}index.html" class="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Home</a>
                </div>
            </div>
'''

HAMBUGER_BTN = '''
                <button id="mobile-menu-btn" class="md:hidden text-gray-600 hover:text-purple-600">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                    </svg>
                </button>
'''

TOGGLE_SCRIPT = '''
<script>
document.getElementById('mobile-menu-btn').addEventListener('click', function() {
    document.getElementById('mobile-menu').classList.toggle('hidden');
});
</script>
'''

def get_prefix(content):
    """Infer path prefix from nav links (../ for subdirs, '' for root)."""
    if 'href="../' in content or 'href="../index.html"' in content:
        return '../'
    return ''

def add_hamburger_to_simple_nav(content, prefix):
    """Transform simple Tailwind nav (single div with flex) to hamburger version."""
    # Pattern: nav with one div (max-w + flex), logo + links div. Links div has "flex gap"
    # We match the inner div and replace it, adding btn + hidden md:flex to links + mobile menu
    pattern = re.compile(
        r'(<nav\s+class="bg-white\s+border-b(?:\s+border-gray-200)?\s+sticky[^>]*>)\s*'
        r'<div\s+class="max-w-6xl\s+mx-auto\s+px-4(?:\s+sm:px-6\s+lg:px-8)?\s+(?:h-16\s+sm:h-20\s+md:h-24|h-20)\s+flex\s+justify-between\s+items-center">\s*'
        r'(<a\s+href="[^"]*index\.html"[^>]*>.*?</a>)\s*'
        r'(<div\s+class=")(flex(?:\s+gap-\d+(?:\s+sm:gap-\d+)?)?(?:\s+items-center)?\s*(")[^>]*>.*?</div>)\s*'
        r'</div>\s*</nav>',
        re.DOTALL
    )
    def repl(m):
        pre, logo, div_open, links_part, div_close = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        # Add hidden md:flex to links div
        new_links = div_open.replace('flex', 'hidden md:flex', 1) + links_part
        menu = MOBILE_MENU_HTML.format(prefix=prefix)
        return (
            f'{pre}\n        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">\n'
            f'            <div class="flex justify-between items-center h-16 sm:h-20 md:h-24">\n                '
            f'{logo}\n{HAMBUGER_BTN}\n                {new_links}\n            </div>\n'
            f'{menu}\n        </div>\n    </nav>'
        )
    return pattern.sub(repl, content, count=1)

def add_hamburger_simple_alt(content, prefix):
    """Alternate simple nav: max-w div contains flex div (e.g. best/index, compare/index)."""
    # <div class="max-w-6xl mx-auto px-4 h-20 flex justify-between items-center">
    #   <a>logo</a>
    #   <div class="flex gap-6">\n <a>...</a> ... </div>
    # </div>
    pattern = re.compile(
        r'(<nav\s+class="bg-white\s+border-b(?:\s+border-gray-200)?\s+sticky[^>]*>)\s*'
        r'<div\s+class="max-w-6xl\s+mx-auto\s+px-4\s+h-20\s+flex\s+justify-between\s+items-center">\s*'
        r'(<a\s+href="[^"]*index\.html"[^>]*>.*?</a>)\s*'
        r'<div\s+class="flex\s+gap-6">\s*\n\s*'
        r'((?:<a\s+href="[^"]*"[^>]*>.*?</a>\s*\n\s*)+)'
        r'</div>\s*</div>\s*</nav>',
        re.DOTALL
    )
    def repl(m):
        pre, logo, links_block = m.group(1), m.group(2), m.group(3)
        # Add hidden md:flex to links; wrap in new structure
        menu = MOBILE_MENU_HTML.format(prefix=prefix)
        return (
            f'{pre}\n        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">\n'
            f'            <div class="flex justify-between items-center h-16 sm:h-20 md:h-24">\n                '
            f'{logo}\n{HAMBUGER_BTN}\n                <div class="hidden md:flex gap-6">\n                '
            f'{links_block}</div>\n            </div>\n{menu}\n        </div>\n    </nav>'
        )
    return pattern.sub(repl, content, count=1)

def add_hamburger_inline_links(content, prefix):
    """Simple nav with inline links (no newlines): <div class="flex gap-6"><a>...</a><a>...</a></div>"""
    pattern = re.compile(
        r'(<nav\s+class="bg-white\s+border-b(?:\s+border-gray-200)?\s+sticky[^>]*>)\s*'
        r'<div\s+class="max-w-6xl\s+mx-auto\s+px-4\s+h-20\s+flex\s+justify-between\s+items-center">\s*'
        r'(<a\s+href="[^"]*index\.html"[^>]*>.*?</a>)\s*'
        r'<div\s+class="flex\s+gap-6">(.*?)</div>\s*'
        r'</div>\s*</nav>',
        re.DOTALL
    )
    def repl(m):
        pre, logo, links_inner = m.group(1), m.group(2), m.group(3).strip()
        menu = MOBILE_MENU_HTML.format(prefix=prefix)
        return (
            f'{pre}\n        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">\n'
            f'            <div class="flex justify-between items-center h-16 sm:h-20 md:h-24">\n                '
            f'{logo}\n{HAMBUGER_BTN}\n                <div class="hidden md:flex gap-6 items-center">'
            f'{links_inner}</div>\n            </div>\n{menu}\n        </div>\n    </nav>'
        )
    return pattern.sub(repl, content, count=1)

def add_hamburger_blog_root(content):
    """Blog-style nav: max-w-4xl, root (no prefix), 4 links incl. Home."""
    pattern = re.compile(
        r'(<nav\s+class="bg-white\s+border-b\s+border-gray-200\s+sticky[^>]*>)\s*'
        r'<div\s+class="max-w-4xl\s+mx-auto\s+px-4\s+sm:px-6\s+lg:px-8">\s*'
        r'<div\s+class="flex\s+justify-between\s+items-center\s+h-16\s+sm:h-20\s+md:h-24">\s*'
        r'(<a\s+href="index\.html"[^>]*>.*?</a>)\s*'
        r'<div\s+class="flex\s+gap-4\s+sm:gap-6\s+items-center\s+text-sm\s+sm:text-base">(.*?)</div>\s*'
        r'</div>\s*</div>\s*</nav>',
        re.DOTALL
    )
    def repl(m):
        pre, logo, links_inner = m.group(1), m.group(2), m.group(3).strip()
        menu = MOBILE_MENU_HTML.format(prefix='')
        return (
            f'{pre}\n    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">\n'
            f'        <div class="flex justify-between items-center h-16 sm:h-20 md:h-24">\n            '
            f'{logo}\n            {HAMBUGER_BTN.strip()}\n            '
            f'<div class="hidden md:flex gap-4 sm:gap-6 items-center text-sm sm:text-base">{links_inner}</div>\n'
            f'        </div>\n        {menu.strip()}\n    </div>\n</nav>'
        )
    return pattern.sub(repl, content, count=1)

def add_script_before_body(content):
    """Add mobile menu toggle script before </body> if not already present."""
    if 'mobile-menu-btn' in content and 'getElementById(\'mobile-menu\')' not in content:
        # Page has hamburger but no our script - might have different script
        pass
    if 'getElementById(\'mobile-menu-btn\')' in content or "getElementById('mobile-menu-btn')" in content:
        return content  # already has toggle
    # Insert before </body>
    script = TOGGLE_SCRIPT
    content = re.sub(r'\s*</body>', script + '\n</body>', content, count=1)
    return content

def process_file(p: Path) -> bool:
    """Add hamburger to file if missing. Returns True if modified."""
    try:
        content = p.read_text(encoding='utf-8')
    except Exception:
        return False
    if 'mobile-menu-btn' in content or 'id="mobile-menu"' in content:
        return False  # already has hamburger
    if 'tailwindcss.com' not in content:
        return False  # skip non-Tailwind
    if p.name == 'index.html' and ('React' in content or 'id="root"' in content):
        return False  # skip React index
    if '<nav' not in content:
        return False

    prefix = get_prefix(content)
    original = content

    content = add_hamburger_inline_links(content, prefix)
    if content == original:
        content = add_hamburger_simple_alt(content, prefix)
    if content == original:
        content = add_hamburger_to_simple_nav(content, prefix)
    if content == original:
        content = add_hamburger_blog_root(content)

    if content != original:
        content = add_script_before_body(content)
        p.write_text(content, encoding='utf-8')
        return True
    return False

def main():
    added = 0
    for p in sorted(Path('.').rglob('*.html')):
        if process_file(p):
            print(p)
            added += 1
    print(f'Added hamburger to {added} files')

if __name__ == '__main__':
    main()
