#!/usr/bin/env python3
"""Add hamburger to compare/* individual pages (excl. index) and blog-* text-logo pages."""
import re
from pathlib import Path

# Compare nav: logo + dropdown + Reviews, Blog, About. We replace with hamburger version.
COMPARE_NAV_PATTERN = re.compile(
    r'<nav class="bg-white border-b border-gray-200 sticky top-0 z-50">\s*'
    r'<div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">\s*'
    r'<div class="flex justify-between items-center h-20">\s*'
    r'<a href="\.\./index\.html"><img src="\.\./artificial-one-logo-large\.svg" alt="artificial\.one" class="h-20"></a>\s*'
    r'<div class="flex gap-6 items-center">\s*'
    r'<a href="\.\./reviews\.html"[^>]*>Reviews</a>\s*'
    r'<div class="dropdown">.*?</div>\s*</div>\s*'
    r'<a href="\.\./blog\.html"[^>]*>Blog</a>\s*'
    r'<a href="\.\./about\.html"[^>]*>About</a>\s*'
    r'</div>\s*</div>\s*</div>\s*</nav>',
    re.DOTALL
)

COMPARE_NAV_REPLACEMENT = '''<nav class="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center h-16 sm:h-20 md:h-24">
                <a href="../index.html"><img src="../artificial-one-logo-large.svg" alt="artificial.one" class="h-16 sm:h-20 md:h-24"></a>
                <button id="mobile-menu-btn" class="md:hidden text-gray-600 hover:text-purple-600">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                    </svg>
                </button>
                <div class="hidden md:flex gap-6 items-center">
                    <a href="../reviews.html" class="text-gray-600 hover:text-purple-600">Reviews</a>
                    <div class="dropdown">
                        <span class="text-gray-600 hover:text-purple-600 cursor-pointer">Categories ▾</span>
                        <div class="dropdown-content">
                            <a href="../category/writing-content.html">✍️ Writing & Content</a>
                            <a href="../category/design-images.html">🎨 Design & Images</a>
                            <a href="../category/video-animation.html">🎬 Video & Animation</a>
                            <a href="../category/coding-development.html">💻 Coding & Development</a>
                            <a href="../category/productivity-business.html">📊 Productivity & Business</a>
                            <a href="../category/voice-audio.html">🎙️ Voice & Audio</a>
                            <a href="../category/research-data.html">🔬 Research & Data</a>
                            <a href="../category/marketing-social.html">📱 Marketing & Social</a>
                            <a href="../category/data-analytics.html">📈 Data & Analytics</a>
                        </div>
                    </div>
                    <a href="../blog.html" class="text-gray-600 hover:text-purple-600">Blog</a>
                    <a href="../about.html" class="text-gray-600 hover:text-purple-600">About</a>
                </div>
            </div>
            <div id="mobile-menu" class="hidden md:hidden pb-4" style="border-top: 1px solid #e5e7eb; margin-top: 1rem;">
                <div class="flex flex-col space-y-3">
                    <a href="../reviews.html" class="bg-gradient-to-r from-violet-600 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Reviews</a>
                    <a href="../blog.html" class="bg-gradient-to-r from-green-600 to-teal-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Blog</a>
                    <a href="../about.html" class="bg-gradient-to-r from-orange-600 to-red-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">About</a>
                    <a href="../index.html" class="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Home</a>
                </div>
            </div>
        </div>
    </nav>'''

TOGGLE_SCRIPT = '''
<script>
document.getElementById('mobile-menu-btn').addEventListener('click', function() {
    document.getElementById('mobile-menu').classList.toggle('hidden');
});
</script>
'''

def add_script(content):
    if "getElementById('mobile-menu-btn')" in content or 'getElementById("mobile-menu-btn")' in content:
        return content
    return re.sub(r'\s*</body>', TOGGLE_SCRIPT + '\n</body>', content, count=1)

def process_compare(p: Path) -> bool:
    if p.name == 'index.html':
        return False
    try:
        content = p.read_text(encoding='utf-8')
    except Exception:
        return False
    if 'mobile-menu-btn' in content:
        return False
    # Match nav - dropdown .*? may not match across newlines in some engines; use [\s\S]*?
    pat = re.compile(
        r'<nav class="bg-white border-b border-gray-200 sticky top-0 z-50">\s*'
        r'<div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">\s*'
        r'<div class="flex justify-between items-center h-20">\s*'
        r'<a href="\.\./index\.html"><img src="\.\./artificial-one-logo-large\.svg" alt="artificial\.one" class="h-20"></a>\s*'
        r'<div class="flex gap-6 items-center">\s*'
        r'<a href="\.\./reviews\.html"[^>]*>Reviews</a>\s*'
        r'<div class="dropdown">[\s\S]*?</div>\s*</div>\s*'
        r'<a href="\.\./blog\.html"[^>]*>Blog</a>\s*'
        r'<a href="\.\./about\.html"[^>]*>About</a>\s*'
        r'</div>\s*</div>\s*</div>\s*</nav>',
        re.DOTALL
    )
    new_content = pat.sub(COMPARE_NAV_REPLACEMENT, content, count=1)
    if new_content == content:
        return False
    new_content = add_script(new_content)
    p.write_text(new_content, encoding='utf-8')
    return True

def process_blog_text_logo(p: Path) -> bool:
    """Blog pages with text logo 'artificial.one' and only Reviews + Blog."""
    try:
        content = p.read_text(encoding='utf-8')
    except Exception:
        return False
    if 'mobile-menu-btn' in content:
        return False
    # Match: nav, max-w-4xl, text logo, flex gap-6 with Reviews + Blog
    pat = re.compile(
        r'<nav class="bg-white border-b border-gray-200 sticky top-0 z-50">\s*'
        r'<div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">\s*'
        r'<div class="flex justify-between items-center h-16">\s*'
        r'<a href="index\.html" class="text-2xl font-bold[^"]*">[\s\S]*?artificial\.one[\s\S]*?</a>\s*'
        r'<div class="flex gap-6">\s*'
        r'<a href="reviews\.html"[^>]*>Reviews</a>\s*'
        r'<a href="blog\.html"[^>]*>Blog</a>\s*'
        r'</div>\s*</div>\s*</div>\s*</nav>',
        re.DOTALL
    )
    repl = '''<nav class="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center h-16 sm:h-20 md:h-24">
                <a href="index.html" class="text-2xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                    artificial.one
                </a>
                <button id="mobile-menu-btn" class="md:hidden text-gray-600 hover:text-purple-600">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                    </svg>
                </button>
                <div class="hidden md:flex gap-6 items-center">
                    <a href="reviews.html" class="text-gray-600 hover:text-purple-600 transition-colors">Reviews</a>
                    <a href="blog.html" class="text-gray-900 hover:text-purple-600 font-medium transition-colors">Blog</a>
                </div>
            </div>
            <div id="mobile-menu" class="hidden md:hidden pb-4" style="border-top: 1px solid #e5e7eb; margin-top: 1rem;">
                <div class="flex flex-col space-y-3">
                    <a href="reviews.html" class="bg-gradient-to-r from-violet-600 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Reviews</a>
                    <a href="blog.html" class="bg-gradient-to-r from-green-600 to-teal-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Blog</a>
                    <a href="about.html" class="bg-gradient-to-r from-orange-600 to-red-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">About</a>
                    <a href="index.html" class="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold text-center block">Home</a>
                </div>
            </div>
        </div>
    </nav>'''
    new_content = pat.sub(repl, content, count=1)
    if new_content == content:
        return False
    new_content = add_script(new_content)
    p.write_text(new_content, encoding='utf-8')
    return True

def main():
    compare_dir = Path('compare')
    blog_root = Path('.')
    n_compare = 0
    n_blog = 0
    for p in sorted(compare_dir.glob('*.html')):
        if process_compare(p):
            print('compare', p.name)
            n_compare += 1
    for p in sorted(blog_root.glob('blog-*.html')):
        if process_blog_text_logo(p):
            print('blog', p.name)
            n_blog += 1
    print(f'Compare: {n_compare}, Blog text-logo: {n_blog}')

if __name__ == '__main__':
    main()
