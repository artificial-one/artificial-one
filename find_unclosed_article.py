#!/usr/bin/env python3
"""Find the unclosed article"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')
lines = content.split('\n')

# Find all article openings with line numbers
article_starts = []
for i, line in enumerate(lines, 1):
    if '<article' in line and 'class="article-card' in line:
        article_starts.append(i)

# Find all article closings with line numbers  
article_ends = []
for i, line in enumerate(lines, 1):
    if '</article>' in line:
        article_ends.append(i)

print(f"Article starts: {len(article_starts)}")
print(f"Article ends: {len(article_ends)}")

# Check each article to see if it has a closing tag
for i, start_line in enumerate(article_starts):
    # Find the corresponding closing tag (should be after this start)
    if i < len(article_ends):
        end_line = article_ends[i]
        if end_line < start_line:
            print(f"\nWARNING: Article starting at line {start_line} has closing tag at line {end_line} (before start!)")
    else:
        # This article has no closing tag
        print(f"\nMISSING CLOSING TAG: Article starting at line {start_line}")
        print(f"  Content: {lines[start_line-1][:100]}...")
        
        # Find where to add the closing tag - look for the pattern after this article
        # Should be before the closing </div> of the grid
        for j in range(start_line, min(start_line + 50, len(lines))):
            if '</div>' in lines[j] and '            </div>' in lines[j]:
                print(f"  Should close before line {j+1}: {lines[j][:80]}")
                # Add closing tag
                lines.insert(j, '                </article>')
                break

if len(article_starts) > len(article_ends):
    Path('blog.html').write_text('\n'.join(lines), encoding='utf-8')
    print("\nFixed: Added missing closing tag")
    
    # Verify
    new_content = '\n'.join(lines)
    new_opens = len(re.findall(r'<article[^>]*class="article-card', new_content))
    new_closes = new_content.count('</article>')
    print(f"\nAfter fix: {new_opens} opens, {new_closes} closes")
