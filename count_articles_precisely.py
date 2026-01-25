#!/usr/bin/env python3
"""Precisely count articles and find the missing closing tag"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Find all article-card articles with their positions
article_matches = list(re.finditer(r'<article[^>]*class="article-card[^>]*>', content))
close_matches = list(re.finditer(r'</article>', content))

print(f"Article-card openings: {len(article_matches)}")
print(f"Closing tags: {len(close_matches)}")

# Check each article to see if it has a closing tag after it
for i, article_match in enumerate(article_matches):
    article_start = article_match.end()
    
    # Find the next closing tag after this article
    next_close = None
    for close_match in close_matches:
        if close_match.start() > article_start:
            next_close = close_match
            break
    
    if next_close is None:
        print(f"\nArticle {i+1} at position {article_start} has NO closing tag!")
        # Get some context
        start_line = content[:article_start].count('\n') + 1
        print(f"  Starts at line {start_line}")
        print(f"  Content: {content[article_start:article_start+100]}...")
    else:
        # Check if there's another article between this and its closing tag
        next_article = None
        for j in range(i+1, len(article_matches)):
            if article_matches[j].start() < next_close.start():
                next_article = article_matches[j]
                break
        
        if next_article:
            print(f"\nArticle {i+1} at line {content[:article_match.start()].count(chr(10))+1} might have issue")
            print(f"  Next article starts before its closing tag")

# The last article should have a closing tag
if len(article_matches) > len(close_matches):
    last_article = article_matches[-1]
    last_article_line = content[:last_article.start()].count('\n') + 1
    print(f"\nLast article at line {last_article_line} might be missing closing tag")
    
    # Find where to add it - should be before the closing </div> of the grid
    # Look for pattern: </div> that closes the grid (after last article content)
    after_last = content[last_article.end():]
    # Find the closing </div> pattern
    div_close = re.search(r'(\s+</div>\s*\n\s+</div>\s*\n\s+</div>\s*\n\s+</section>)', after_last)
    if div_close:
        insert_pos = last_article.end() + div_close.start()
        # Insert closing tag
        content = content[:insert_pos] + '                </article>\n\n' + content[insert_pos:]
        Path('blog.html').write_text(content, encoding='utf-8')
        print(f"Added missing closing tag at position {insert_pos}")
        
        # Verify
        new_opens = len(re.findall(r'<article[^>]*class="article-card', content))
        new_closes = content.count('</article>')
        print(f"After fix: {new_opens} opens, {new_closes} closes")
