#!/usr/bin/env python3
"""Remove duplicate Zenler article"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Find Article 200 (the duplicate Zenler)
# Article 45 is the first one, Article 200 is the duplicate
pattern = r'(<!-- Article 200: Zenler -->.*?</article>\s*\n)'
match = re.search(pattern, content, re.DOTALL)

if match:
    print("Found duplicate Zenler article (Article 200)")
    # Remove it
    content = content[:match.start()] + content[match.end():]
    Path('blog.html').write_text(content, encoding='utf-8')
    print("Removed duplicate Zenler article")
    
    # Verify
    zenler_count = content.count('blog-zenler.html')
    print(f"blog-zenler.html now appears {zenler_count} times (should be 2 - once in article, once in link)")
else:
    print("Could not find duplicate Zenler article")

# Also verify education count
education_count = len(re.findall(r'data-category="education"', content))
print(f"\nEducation articles after fix: {education_count}")
