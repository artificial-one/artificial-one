#!/usr/bin/env python3
"""Find missing closing article tag"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Find all article opening tags with their line numbers
lines = content.split('\n')
article_opens = []
article_closes = []

for i, line in enumerate(lines, 1):
    if '<article' in line and 'class="article-card' in line:
        article_opens.append((i, line[:100]))
    if '</article>' in line:
        article_closes.append((i, line[:100]))

print(f"Opening tags: {len(article_opens)}")
print(f"Closing tags: {len(article_closes)}")
print(f"Difference: {len(article_opens) - len(article_closes)}")

if len(article_opens) > len(article_closes):
    print("\nMissing closing tags. Last few opening tags:")
    for i, (line_num, line) in enumerate(article_opens[-5:], 1):
        print(f"  {line_num}: {line}")
    
    print("\nLast few closing tags:")
    for i, (line_num, line) in enumerate(article_closes[-5:], 1):
        print(f"  {line_num}: {line}")

# Check for articles that might be missing closing tags
# Look for article tags that don't have a matching close within reasonable distance
for i, (open_line, open_content) in enumerate(article_opens):
    if i < len(article_closes):
        close_line = article_closes[i][0]
        if close_line < open_line:
            print(f"\nWARNING: Article at line {open_line} has closing tag before it!")
    else:
        print(f"\nWARNING: Article at line {open_line} has no closing tag!")
