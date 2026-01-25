#!/usr/bin/env python3
"""Verify and fix blog.html structure"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Count article-card articles specifically
article_card_opens = len(re.findall(r'<article[^>]*class="article-card', content))
article_closes = content.count('</article>')

print(f"article-card articles: {article_card_opens}")
print(f"Closing </article> tags: {article_closes}")

# Check for articles without line breaks (corruption)
# Look for </article> immediately followed by <article (no newline)
no_break = re.search(r'</article>\s*<article', content)
if no_break:
    print("\nWARNING: Found articles without line breaks!")
    # Fix by adding newline
    content = re.sub(r'(</article>)\s*(<article)', r'\1\n\n                \2', content)
    print("Fixed: Added line breaks between articles")
else:
    print("\n[OK] All articles have proper line breaks")

# Ensure all articles have data-category
articles_without_cat = []
for match in re.finditer(r'<article[^>]*class="article-card[^>]*>', content):
    article_tag = match.group(0)
    if 'data-category=' not in article_tag:
        articles_without_cat.append(match.start())

if articles_without_cat:
    print(f"\nWARNING: {len(articles_without_cat)} articles missing data-category")
else:
    print("\n[OK] All articles have data-category attributes")

# Save if we made changes
if no_break:
    Path('blog.html').write_text(content, encoding='utf-8')
    print("\nSaved fixes to blog.html")

print(f"\nFinal count:")
print(f"  Opening tags: {len(re.findall(r'<article[^>]*class=\"article-card', content))}")
print(f"  Closing tags: {content.count('</article>')}")
