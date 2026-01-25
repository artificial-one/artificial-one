#!/usr/bin/env python3
"""Extract all categories from blog.html"""

import re
from pathlib import Path

content = Path('blog.html').read_text(encoding='utf-8')

# Extract all categories
categories = re.findall(r'<div class="text-sm text-[a-z]+-600 font-semibold mb-2">([^<]+)</div>', content)
unique_categories = sorted(set(categories))

print(f"Found {len(unique_categories)} unique categories:\n")
for i, cat in enumerate(unique_categories, 1):
    count = categories.count(cat)
    print(f"{i}. {cat} ({count} articles)")

# Map categories to slugs for filtering
category_map = {
    'SEO & CONTENT': 'seo-content',
    'PRODUCTIVITY': 'productivity',
    'BUSINESS': 'business',
    'COMPARISON': 'comparison',
    'DESIGN': 'design',
    'VOICE & AUDIO': 'voice',
    'FREE TOOLS': 'free-tools',
    'VIDEO': 'video',
    'WORTH IT': 'worth-it',
    'CODING': 'coding',
    'DEALS': 'deals',
    'DATA': 'data',
    'MARKETING': 'marketing',
    'SAVINGS': 'savings',
    'WRITING & CONTENT': 'writing',
    'VIDEO & ANIMATION': 'video',
    'DESIGN & IMAGES': 'design',
    'PRODUCTIVITY & BUSINESS': 'productivity',
    'E-COMMERCE & SUPPORT': 'ecommerce',
    'SOCIAL MEDIA & MARKETING': 'marketing',
    'MARKETING & PRODUCTIVITY': 'marketing',
    'DESIGN & E-COMMERCE': 'design',
    'MARKETING & ANALYTICS': 'marketing',
    'SALES & MARKETING': 'marketing',
    'MARKETING & CONVERSION': 'marketing',
    'EDUCATION & BUSINESS': 'education',
    'DATA & ANALYTICS': 'data',
}

print("\n\nCategory mapping for filters:")
for cat in unique_categories:
    slug = category_map.get(cat, cat.lower().replace(' ', '-').replace('&', '').replace(' ', ''))
    print(f"  '{cat}' -> '{slug}'")
