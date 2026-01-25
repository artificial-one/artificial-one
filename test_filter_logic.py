#!/usr/bin/env python3
"""Test filter logic to find why counts don't match"""

import re
from pathlib import Path
from collections import defaultdict

content = Path('blog.html').read_text(encoding='utf-8')

# Find all articles with their data-category
articles = []
for match in re.finditer(r'<article[^>]*class="article-card[^>]*data-category="([^"]+)"[^>]*>', content):
    start = match.start()
    # Find the closing tag
    end_match = re.search(r'</article>', content[start:])
    if end_match:
        article_html = content[start:start+end_match.end()]
        category = match.group(1)
        articles.append({
            'category': category,
            'html': article_html[:200]  # First 200 chars for debugging
        })

# Count by category
category_counts = defaultdict(int)
for article in articles:
    category_counts[article['category']] += 1

print("Articles found by category:")
for cat in sorted(category_counts.keys()):
    print(f"  {cat}: {category_counts[cat]}")

# Check education specifically
education_articles = [a for a in articles if a['category'] == 'education']
print(f"\n\nEducation articles: {len(education_articles)}")

# Check if any articles might be malformed
print("\nChecking for potential issues...")

# Check for articles without proper structure
malformed = []
for i, article in enumerate(articles):
    if 'class="article-card' not in article['html']:
        malformed.append(i)
    if '</article>' not in article['html']:
        malformed.append(i)

if malformed:
    print(f"Found {len(malformed)} potentially malformed articles")
else:
    print("All articles appear properly structured")

# Check if there are duplicate article entries
print("\nChecking for duplicates...")
seen_titles = {}
duplicates = []
for article in articles:
    title_match = re.search(r'<a href="([^"]+)"', article['html'])
    if title_match:
        href = title_match.group(1)
        if href in seen_titles:
            duplicates.append(href)
        seen_titles[href] = True

if duplicates:
    print(f"Found {len(duplicates)} duplicate articles:")
    for dup in duplicates[:5]:
        print(f"  - {dup}")
else:
    print("No duplicates found")
