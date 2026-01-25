#!/usr/bin/env python3
"""Verify blog.html structure and check for corruption"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Count articles
article_count = content.count('<!-- Article')
print(f"Total articles: {article_count}")

# Check for proper article tags
article_tags = len(re.findall(r'<article[^>]*>', content))
article_closes = content.count('</article>')
print(f"Opening <article> tags: {article_tags}")
print(f"Closing </article> tags: {article_closes}")

if article_tags != article_closes:
    print("WARNING: Mismatch in article tags!")

# Check for articles without line breaks (potential corruption)
# Look for </article><article patterns
no_break_pattern = r'</article>\s*<article'
matches = re.findall(no_break_pattern, content)
if matches:
    print(f"\nWARNING: Found {len(matches)} articles without line breaks between them")
    print("These need to be fixed!")
else:
    print("\n✓ All articles have proper line breaks")

# Check data-category attributes
data_cat_count = content.count('data-category=')
print(f"\nArticles with data-category: {data_cat_count}")

if data_cat_count == article_tags:
    print("✓ All articles have data-category attributes")
else:
    print(f"WARNING: {article_tags - data_cat_count} articles missing data-category")

# Check for any malformed article tags
malformed = re.findall(r'<article[^>]*class="article-card[^"]*data-category="[^"]*"[^>]*class=', content)
if malformed:
    print(f"\nWARNING: Found {len(malformed)} malformed article tags")
else:
    print("\n✓ All article tags are properly formatted")
