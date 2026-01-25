#!/usr/bin/env python3
"""Fix blog.html structure - ensure all articles are properly closed"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Count opening and closing tags
open_count = len(re.findall(r'<article[^>]*>', content))
close_count = content.count('</article>')

print(f"Opening tags: {open_count}")
print(f"Closing tags: {close_count}")

if open_count > close_count:
    print(f"\nMissing {open_count - close_count} closing tag(s)")
    
    # Find the last article that might be missing a closing tag
    # Look for the pattern: </article> followed by </div> (closing grid)
    # If we find articles after the last </article>, they need closing tags
    
    # Find all article opening tags and their positions
    article_positions = []
    for match in re.finditer(r'<article[^>]*class="article-card', content):
        article_positions.append(match.start())
    
    # Find all closing tags
    close_positions = []
    for match in re.finditer(r'</article>', content):
        close_positions.append(match.end())
    
    # Check if the last article has a closing tag
    if len(article_positions) > len(close_positions):
        last_article_pos = article_positions[-1]
        last_close_pos = close_positions[-1] if close_positions else 0
        
        if last_article_pos > last_close_pos:
            print(f"\nLast article starts at position {last_article_pos} but last closing tag is at {last_close_pos}")
            print("Adding missing closing tag...")
            
            # Find where to insert the closing tag (before </div> that closes the grid)
            # Look for the pattern: </div> that closes the grid (after last article)
            insert_pattern = r'(                    </div>\n\n            </div>)'
            match = re.search(insert_pattern, content[last_article_pos:])
            if match:
                insert_pos = last_article_pos + match.start()
                content = content[:insert_pos] + '                </article>\n\n' + content[insert_pos:]
                print("Added missing closing tag!")
            else:
                # Try to find the closing div pattern
                # Look for </div> that appears after the last article content
                pattern = r'(                    </div>\s*\n\s*</div>\s*\n\s*</div>\s*\n\s*</section>)'
                match = re.search(pattern, content[last_article_pos:])
                if match:
                    insert_pos = last_article_pos + match.start()
                    content = content[:insert_pos] + '                </article>\n\n' + content[insert_pos:]
                    print("Added missing closing tag before section close!")
                else:
                    # Last resort: add before the closing </div> of the grid
                    # Find the pattern: </div> that closes the grid div
                    lines = content.split('\n')
                    for i in range(len(lines) - 1, -1, -1):
                        if '            </div>' in lines[i] and i > last_article_pos // 100:  # Approximate
                            # Check if there's an article before this
                            before_text = '\n'.join(lines[:i])
                            if '</article>' not in before_text.split('<article')[-1] if '<article' in before_text else True:
                                lines.insert(i, '                </article>')
                                content = '\n'.join(lines)
                                print("Added missing closing tag before grid close!")
                                break

Path('blog.html').write_text(content, encoding='utf-8')

# Verify
open_count_after = len(re.findall(r'<article[^>]*>', content))
close_count_after = content.count('</article>')
print(f"\nAfter fix:")
print(f"Opening tags: {open_count_after}")
print(f"Closing tags: {close_count_after}")

if open_count_after == close_count_after:
    print("[SUCCESS] All articles properly closed!")
else:
    print(f"[WARNING] Still {open_count_after - close_count_after} mismatch")
