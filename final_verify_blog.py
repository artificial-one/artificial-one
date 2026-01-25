#!/usr/bin/env python3
"""Final verification of blog.html"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Count properly
article_opens = len(re.findall(r'<article[^>]*class="article-card', content))
article_closes = content.count('</article>')

print(f"Opening article tags: {article_opens}")
print(f"Closing article tags: {article_closes}")

if article_opens == article_closes:
    print("[SUCCESS] All articles properly closed!")
else:
    print(f"[WARNING] Mismatch: {article_opens - article_closes} difference")

# Check data-category
data_cat = content.count('data-category=')
print(f"\nArticles with data-category: {data_cat}")

# Check filter buttons
filter_buttons = content.count('filterByCategory')
print(f"Filter buttons: {filter_buttons}")

# Check for corruption (articles without line breaks)
no_breaks = len(re.findall(r'</article>\s*<article', content))
if no_breaks == 0:
    print("\n[SUCCESS] No corruption - all articles have proper line breaks")
else:
    print(f"\n[WARNING] Found {no_breaks} articles without line breaks")
