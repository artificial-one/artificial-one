#!/usr/bin/env python3
"""Debug filter mismatch - check if button categories match article data-category values"""

import re
from pathlib import Path
from collections import Counter

content = Path('blog.html').read_text(encoding='utf-8')

# Get all actual data-category values from articles
category_pattern = r'data-category="([^"]+)"'
all_categories = re.findall(category_pattern, content)
category_counts = Counter(all_categories)

print("Actual data-category values in articles:")
for cat, count in sorted(category_counts.items()):
    print(f"  {cat}: {count}")

# Get filter button categories
button_pattern = r"filterByCategory\('([^']+)'\)"
button_categories = re.findall(button_pattern, content)

print("\n\nFilter button categories:")
for cat in sorted(set(button_categories)):
    count = category_counts.get(cat, 0)
    print(f"  {cat}: {count} articles")

# Check for mismatches
print("\n\nMismatches:")
for btn_cat in sorted(set(button_categories)):
    if btn_cat == 'all':
        continue
    count = category_counts.get(btn_cat, 0)
    if count == 0:
        print(f"  WARNING: Button '{btn_cat}' has NO matching articles!")

# Check for articles with categories that don't have buttons
print("\n\nArticles with categories that don't have filter buttons:")
for cat, count in sorted(category_counts.items()):
    if cat not in button_categories and cat != 'all':
        print(f"  {cat}: {count} articles (no button for this)")

# Check specific problematic categories
print("\n\nChecking specific categories mentioned by user:")
problem_cats = ['education', 'ecommerce', 'seo-content', 'data', 'video', 'design', 'writing', 'productivity']
for cat in problem_cats:
    count = category_counts.get(cat, 0)
    # Find articles with this category
    articles = re.findall(rf'<article[^>]*data-category="{cat}"[^>]*>.*?</article>', content, re.DOTALL)
    print(f"  {cat}: Count={count}, Found {len(articles)} complete articles in HTML")
