#!/usr/bin/env python3
"""Check if all articles are inside the blog-grid container"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Find the blog-grid section
grid_start = content.find('id="blog-grid"')
if grid_start == -1:
    print("ERROR: blog-grid id not found!")
    exit(1)

# Find where the grid section ends (before the next section)
grid_section_end = content.find('</section>', content.find('</section>', grid_start) + 1)
grid_content = content[grid_start:grid_section_end]

# Count articles in grid
articles_in_grid = len(re.findall(r'<article[^>]*data-category="([^"]+)"', grid_content))
print(f"Articles inside blog-grid section: {articles_in_grid}")

# Count all articles
all_articles = len(re.findall(r'data-category="([^"]+)"', content))
print(f"Total articles with data-category: {all_articles}")

if articles_in_grid != all_articles:
    print(f"\nWARNING: {all_articles - articles_in_grid} articles are OUTSIDE the blog-grid!")

# Check specific categories
print("\n\nChecking specific categories inside grid:")
categories = ['education', 'ecommerce', 'seo-content', 'data', 'video', 'design', 'writing', 'productivity']
for cat in categories:
    count_in_grid = len(re.findall(rf'data-category="{cat}"', grid_content))
    count_total = len(re.findall(rf'data-category="{cat}"', content))
    if count_in_grid != count_total:
        print(f"  {cat}: {count_total} total, but only {count_in_grid} in grid!")
    else:
        print(f"  {cat}: {count_total} articles (all in grid)")

# Check if there are any articles before or after the grid
before_grid = content[:grid_start]
after_grid = content[grid_section_end:]
articles_before = len(re.findall(r'<article[^>]*data-category=', before_grid))
articles_after = len(re.findall(r'<article[^>]*data-category=', after_grid))

if articles_before > 0:
    print(f"\nWARNING: {articles_before} articles found BEFORE blog-grid section!")
if articles_after > 0:
    print(f"WARNING: {articles_after} articles found AFTER blog-grid section!")
