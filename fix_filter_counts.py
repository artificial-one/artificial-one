#!/usr/bin/env python3
"""Fix filter counts - ensure they match actual filterable articles"""

import re
from pathlib import Path
from collections import Counter

content = Path('blog.html').read_text(encoding='utf-8')

# Get all actual data-category values from articles
category_pattern = r'<article[^>]*class="article-card[^>]*data-category="([^"]+)"[^>]*>'
categories = re.findall(category_pattern, content)
category_counts = Counter(categories)

print("Actual category counts:")
for cat, count in sorted(category_counts.items()):
    print(f"  {cat}: {count}")

# The JavaScript should be counting these correctly, but let's verify the filter logic
# Check if there are any articles that might not be getting counted

# Read the JavaScript section
js_start = content.find('<script>', content.find('let currentCategoryFilter'))
js_end = content.find('</script>', js_start)
js_code = content[js_start:js_end]

print("\n\nChecking JavaScript filter logic...")
print("Current updateCounts function should count all articles with data-category")

# The issue might be that the count is correct, but the filter is not working
# Let's verify the filter function matches correctly

# Check if all articles are within the grid container
grid_start = content.find('<div class="grid md:grid-cols-2')
grid_end = content.find('</div>', content.rfind('</article>'))
grid_content = content[grid_start:grid_end]

articles_in_grid = len(re.findall(r'<article[^>]*class="article-card', grid_content))
print(f"\nArticles in grid container: {articles_in_grid}")
print(f"Total articles: {len(categories)}")

if articles_in_grid != len(categories):
    print("WARNING: Some articles might be outside the grid!")
