#!/usr/bin/env python3
"""Check category counts and verify filter logic"""

import re
from pathlib import Path
from collections import Counter

content = Path('blog.html').read_text(encoding='utf-8')

# Extract all data-category values
categories = re.findall(r'data-category="([^"]+)"', content)
category_counts = Counter(categories)

print("Category counts from data-category attributes:")
for cat, count in sorted(category_counts.items()):
    print(f"  {cat}: {count}")

# Also check what category labels are in the articles
print("\n\nCategory labels in articles:")
label_pattern = r'<div class="text-sm text-[a-z]+-600 font-semibold mb-2">([^<]+)</div>'
labels = re.findall(label_pattern, content)
label_counts = Counter(labels)

for label, count in sorted(label_counts.items()):
    print(f"  {label}: {count}")

# Check for education specifically
print("\n\nEducation articles:")
education_articles = re.findall(r'<article[^>]*data-category="education"[^>]*>.*?</article>', content, re.DOTALL)
print(f"Found {len(education_articles)} education articles")

# Check if there are any display:none or hidden articles
hidden = content.count('style="display: none"')
print(f"\nArticles with display:none: {hidden}")
