#!/usr/bin/env python3
"""Verify all tools with affiliate links have blog posts."""

import os
import re
from pathlib import Path

# Get all tools with affiliate links
tools_dir = Path('tools')
tools_with_affiliates = set()

for review_file in tools_dir.glob('*-review.html'):
    try:
        content = review_file.read_text(encoding='utf-8', errors='ignore')
        if 'appsumo.8odi.net' in content:
            tool_name = review_file.stem.replace('-review', '')
            tools_with_affiliates.add(tool_name)
    except:
        continue

# Get all blog posts
blogs = set()
for f in os.listdir('.'):
    if f.startswith('blog-') and f.endswith('.html'):
        if not any(x in f for x in ['ai-', 'appsumo', 'chatgpt', 'copilot', 'free', 'midjourney', 'professional', 'worth', '57-new', 'html.html']):
            blog_name = f.replace('blog-', '').replace('.html', '')
            blogs.add(blog_name)
            
# Handle name variations - some tools have multiple review files or naming variations
# airbrush-ai-image-generator review file -> blog-airbrush-ai-image-generator.html exists
if 'airbrush-ai-image-generator' in [f.replace('blog-', '').replace('.html', '') for f in os.listdir('.') if f.startswith('blog-airbrush')]:
    blogs.add('airbrush-ai-image-generator')
# writeseed-ai-content-writer review file -> blog-writeseed-ai-content-writer.html exists  
if 'writeseed-ai-content-writer' in [f.replace('blog-', '').replace('.html', '') for f in os.listdir('.') if f.startswith('blog-writeseed')]:
    blogs.add('writeseed-ai-content-writer')

# Find missing
missing = tools_with_affiliates - blogs

print(f"Tools with affiliate links: {len(tools_with_affiliates)}")
print(f"Blog posts created: {len(blogs)}")
print(f"Missing: {len(missing)}")

if missing:
    print(f"\nTools still needing blogs ({len(missing)}):")
    for t in sorted(list(missing))[:30]:
        print(f"  - {t}")
else:
    print("\n[SUCCESS] All tools with affiliate links have blog posts!")
