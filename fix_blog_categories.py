#!/usr/bin/env python3
"""Fix data-category attributes in blog.html"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Fix incorrectly placed data-category attributes
# Pattern: class="article-card data-category="..." bg-white
# Should be: class="article-card bg-white..." data-category="..."

def fix_category(match):
    full_match = match.group(0)
    category = match.group(1)
    # Extract the rest of the class attribute
    rest = match.group(2) if match.lastindex >= 2 else ''
    # Return properly formatted
    return f'class="article-card bg-white{rest}" data-category="{category}"'

# Fix pattern: class="article-card data-category="X" bg-white...
content = re.sub(
    r'class="article-card data-category="([^"]+)" (bg-white[^"]*)"',
    r'class="article-card \2" data-category="\1"',
    content
)

# Also handle cases where it might be in different positions
content = re.sub(
    r'class="article-card data-category="([^"]+)"([^>]*)>',
    lambda m: f'class="article-card{m.group(2)}" data-category="{m.group(1)}">',
    content
)

Path('blog.html').write_text(content, encoding='utf-8')
print("Fixed all data-category attributes!")

# Verify
matches = re.findall(r'data-category="([^"]+)"', content)
print(f"Found {len(matches)} articles with data-category attributes")
