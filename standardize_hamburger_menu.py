#!/usr/bin/env python3
"""
Standardize hamburger menu across all HTML pages to match blog.html structure.
This script ensures all pages have:
1. Hamburger button (if missing)
2. Full mobile menu with dropdowns (Categories, Explore, Lifetime Deals)
3. JavaScript for toggling
4. Correct path prefixes
"""
import re
from pathlib import Path

# Canonical hamburger button
HAMBURGER_BTN = '''                <button id="mobile-menu-btn" class="md:hidden text-gray-600 hover:text-purple-600">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                    </svg>
                </button>'''

# Canonical mobile menu template - {prefix} will be '' or '../'
MOBILE_MENU_TEMPLATE = '''            <div id="mobile-menu" class="hidden md:hidden pb-4">
                <div class="flex flex-col space-y-3">
                    <a href="{prefix}reviews.html" class="bg-gradient-to-r from-violet-600 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold text-center">Reviews</a>
                    <div class="mobile-dropdown">
                        <button class="mobile-dropdown-btn bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-3 rounded-lg font-semibold w-full text-center flex justify-between items-center">
                            Categories <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </button>
                        <div class="mobile-dropdown-content hidden pl-4 space-y-2 mt-2">
                            <a href="{prefix}category/writing-content.html" class="block text-sm py-1">✍️ Writing & Content</a>
                            <a href="{prefix}category/design-images.html" class="block text-sm py-1">🎨 Design & Images</a>
                            <a href="{prefix}category/video-animation.html" class="block text-sm py-1">🎬 Video & Animation</a>
                            <a href="{prefix}category/coding-development.html" class="block text-sm py-1">💻 Coding & Development</a>
                            <a href="{prefix}category/productivity-business.html" class="block text-sm py-1">📊 Productivity & Business</a>
                            <a href="{prefix}category/voice-audio.html" class="block text-sm py-1">🎙️ Voice & Audio</a>
                            <a href="{prefix}category/research-data.html" class="block text-sm py-1">🔬 Research & Data</a>
                            <a href="{prefix}category/marketing-social.html" class="block text-sm py-1">📱 Marketing & Social</a>
                            <a href="{prefix}category/data-analytics.html" class="block text-sm py-1">📈 Data & Analytics</a>
                        </div>
                    </div>
                    <div class="mobile-dropdown">
                        <button class="mobile-dropdown-btn bg-gradient-to-r from-purple-600 to-pink-600 text-white px-6 py-3 rounded-lg font-semibold w-full text-center flex justify-between items-center">
                            Explore <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </button>
                        <div class="mobile-dropdown-content hidden pl-4 space-y-2 mt-2">
                            <a href="{prefix}compare/index.html" class="block text-sm py-1">🔍 Compare Tools</a>
                            <a href="{prefix}best/index.html" class="block text-sm py-1">🏆 Best Of Lists</a>
                            <a href="{prefix}tutorials/index.html" class="block text-sm py-1">📚 Tutorials</a>
                            <a href="{prefix}guides/index.html" class="block text-sm py-1">📖 Guides</a>
                        </div>
                    </div>
                    <div class="mobile-dropdown">
                        <button class="mobile-dropdown-btn bg-gradient-to-r from-green-600 to-emerald-600 text-white px-6 py-3 rounded-lg font-semibold w-full text-center flex justify-between items-center">
                            💰 Lifetime Deals <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </button>
                        <div class="mobile-dropdown-content hidden pl-4 space-y-2 mt-2">
                            <a href="{prefix}guides/best-lifetime-deal-software-2026.html" class="block text-sm py-1">🎯 Browse All Deals</a>
                            <a href="{prefix}compare/index.html" class="block text-sm py-1">🔍 Compare Tools</a>
                            <a href="{prefix}guides/use-case-startups.html" class="block text-sm py-1">🚀 Best for Startups</a>
                            <a href="{prefix}guides/use-case-freelancers.html" class="block text-sm py-1">💼 Best for Freelancers</a>
                            <a href="{prefix}guides/best-lifetime-ai-tools.html" class="block text-sm py-1">🤖 AI Tools</a>
                        </div>
                    </div>
                    <a href="{prefix}blog.html" class="bg-gradient-to-r from-green-600 to-teal-600 text-white px-6 py-3 rounded-lg font-semibold text-center">Blog</a>
                    <a href="{prefix}about.html" class="bg-gradient-to-r from-orange-600 to-red-600 text-white px-6 py-3 rounded-lg font-semibold text-center">About</a>
                </div>
            </div>'''

# JavaScript for mobile menu toggling
MOBILE_MENU_SCRIPT = '''<script>
document.getElementById('mobile-menu-btn').addEventListener('click', function() {
    document.getElementById('mobile-menu').classList.toggle('hidden');
});
document.querySelectorAll('.mobile-dropdown-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        this.classList.toggle('active');
        this.nextElementSibling.classList.toggle('hidden');
    });
});
</script>'''

def get_path_prefix(file_path):
    """Determine path prefix based on file location."""
    path = Path(file_path)
    # If file is in root directory
    if path.parent.name == '.' or path.parent.name == 'artificial.one':
        return ''
    # If file is in a subdirectory (tools/, compare/, category/, etc.)
    return '../'

def has_hamburger_button(content):
    """Check if hamburger button exists."""
    return 'id="mobile-menu-btn"' in content

def has_mobile_menu(content):
    """Check if mobile menu exists."""
    return 'id="mobile-menu"' in content

def find_mobile_menu_end_regex(content):
    """Find and replace mobile menu using regex."""
    # Match mobile menu div and all its content until closing </div> for the nav
    # This pattern matches from <div id="mobile-menu" to the closing </div> before </nav>
    pattern = r'<div\s+id="mobile-menu"[^>]*>.*?</div>\s*</div>\s*</nav>'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        # Return the position just before the closing </div> of nav
        return match.start(), match.end() - len('</div>\n    </nav>')
    return None, None

def standardize_hamburger_menu(content, prefix):
    """Standardize hamburger menu in content."""
    modified = False
    
    # Step 1: Add hamburger button if missing
    if not has_hamburger_button(content):
        # Look for nav structure - try multiple patterns
        # Pattern 1: Logo followed by desktop menu with hidden md:flex
        nav_pattern1 = r'(<a\s+href="[^"]*index\.html"[^>]*>.*?</a>)\s*(<div\s+class="hidden\s+md:flex)'
        match = re.search(nav_pattern1, content, re.DOTALL)
        if match:
            logo_end = match.end(1)
            # Insert hamburger button
            content = content[:logo_end] + '\n                ' + HAMBURGER_BTN + '\n                ' + content[logo_end:]
            modified = True
        else:
            # Pattern 2: Logo followed by any div with flex (simpler nav)
            nav_pattern2 = r'(<a\s+href="[^"]*index\.html"[^>]*>.*?</a>)\s*(<div\s+class="[^"]*flex[^"]*")'
            match = re.search(nav_pattern2, content, re.DOTALL)
            if match:
                logo_end = match.end(1)
                # Insert hamburger button
                content = content[:logo_end] + '\n                ' + HAMBURGER_BTN + '\n                ' + content[logo_end:]
                modified = True
    
    # Step 2: Replace or add mobile menu
    if has_mobile_menu(content):
        # Find existing mobile menu and replace it using regex
        menu_start, menu_end = find_mobile_menu_end_regex(content)
        if menu_start is not None and menu_end is not None:
            new_menu = MOBILE_MENU_TEMPLATE.format(prefix=prefix)
            content = content[:menu_start] + new_menu + '\n        ' + content[menu_end:]
            modified = True
    else:
        # Add mobile menu before closing nav div
        # Look for closing </div> after desktop menu
        nav_close_pattern = r'(</div>\s*</div>\s*</nav>)'
        match = re.search(nav_close_pattern, content)
        if match:
            insert_pos = match.start()
            new_menu = '\n            ' + MOBILE_MENU_TEMPLATE.format(prefix=prefix) + '\n        '
            content = content[:insert_pos] + new_menu + content[insert_pos:]
            modified = True
    
    # Step 3: Ensure JavaScript is present
    script_pattern = r'<script>\s*document\.getElementById\([\'"]mobile-menu-btn[\'"]\)'
    if not re.search(script_pattern, content):
        # Add script before </body>
        body_close = content.rfind('</body>')
        if body_close != -1:
            content = content[:body_close] + '\n' + MOBILE_MENU_SCRIPT + '\n' + content[body_close:]
            modified = True
    
    return content, modified

def process_file(file_path):
    """Process a single HTML file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Skip index.html (React-based, different structure)
        if file_path.name == 'index.html' and 'React' in content:
            return False
        
        prefix = get_path_prefix(file_path)
        new_content, modified = standardize_hamburger_menu(content, prefix)
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all HTML files."""
    root = Path('.')
    html_files = list(root.rglob('*.html'))
    
    # Exclude index.html if it's React-based
    html_files = [f for f in html_files if not (f.name == 'index.html' and 'React' in f.read_text(encoding='utf-8')[:5000])]
    
    modified_count = 0
    for html_file in html_files:
        if process_file(html_file):
            modified_count += 1
            print(f"Updated: {html_file}")
    
    print(f"\nStandardized hamburger menu in {modified_count} files")

if __name__ == '__main__':
    main()
