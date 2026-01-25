#!/usr/bin/env python3
"""Verify all education articles are properly structured"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Find all education articles with full context
education_pattern = r'(<article[^>]*data-category="education"[^>]*>.*?</article>)'
education_articles = re.findall(education_pattern, content, re.DOTALL)

print(f"Found {len(education_articles)} education articles:\n")

for i, article in enumerate(education_articles, 1):
    # Extract title
    title_match = re.search(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', article)
    if title_match:
        href = title_match.group(1)
        title = title_match.group(2)
        print(f"{i}. {title}")
        print(f"   Link: {href}")
    
    # Check if article has proper closing tag
    if '</article>' in article:
        print(f"   ✓ Has closing tag")
    else:
        print(f"   ✗ MISSING closing tag!")
    
    # Check structure
    if 'class="article-card' in article:
        print(f"   ✓ Has article-card class")
    else:
        print(f"   ✗ MISSING article-card class")
    
    print()

# Check for any articles that might be malformed
print("\nChecking for structural issues...")
all_articles = re.findall(r'<article[^>]*class="article-card[^>]*data-category="education"[^>]*>', content)
print(f"Articles with data-category='education': {len(all_articles)}")

# Check if all are properly closed
closing_tags = content.count('</article>')
print(f"Total closing </article> tags: {closing_tags}")
