#!/usr/bin/env python3
"""
Improve meta descriptions for review pages with better format.
"""
import re
from pathlib import Path

def extract_tool_info(content):
    """Extract tool information from HTML."""
    info = {}
    
    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).replace(' | artificial.one', '').replace('Review 2026:', 'Review:').strip()
        info['name'] = title.split(' Review')[0].strip()
    
    # Extract rating
    rating_match = re.search(r'(\d+\.?\d*)/10|(\d+\.?\d*)/5', content)
    if rating_match:
        info['rating'] = rating_match.group(1) or rating_match.group(2)
    
    # Extract price
    price_match = re.search(r'\$(\d+)\s*(one-time|lifetime|super|deal)', content, re.IGNORECASE)
    if price_match:
        info['price'] = f"${price_match.group(1)}"
    else:
        monthly_match = re.search(r'\$(\d+)/mo', content, re.IGNORECASE)
        if monthly_match:
            info['price'] = f"${monthly_match.group(1)}/mo"
    
    # Check if it's a deal
    info['is_deal'] = 'lifetime' in content.lower() or 'one-time' in content.lower() or 'super deal' in content.lower()
    
    return info

def generate_meta_description(info):
    """Generate improved meta description."""
    name = info.get('name', 'Tool')
    rating = info.get('rating', '')
    price = info.get('price', '')
    is_deal = info.get('is_deal', False)
    
    if is_deal and price:
        desc = f"{name} Review 2026: {rating}/10 Rating. Get {price} lifetime deal vs subscription. See pros, cons, pricing & alternatives. Read our honest review →"
    elif rating and price:
        desc = f"{name} Review 2026: {rating}/10 Rating. {price}. See pros, cons, pricing & alternatives. Read our honest review →"
    elif rating:
        desc = f"{name} Review 2026: {rating}/10 Rating. See pros, cons, features & pricing. Read our honest review →"
    else:
        desc = f"{name} Review 2026: Complete guide covering features, pricing, pros & cons. Read our honest review →"
    
    # Ensure it's under 160 characters
    if len(desc) > 160:
        desc = desc[:157] + "..."
    
    return desc

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        
        # Skip if not a tool review
        if '/tools/' not in str(filepath) or 'review' not in str(filepath).lower():
            return False
        
        # Extract tool info
        info = extract_tool_info(content)
        
        # Generate new meta description
        new_desc = generate_meta_description(info)
        
        # Find and replace meta description
        meta_desc_pattern = r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']\s*>'
        
        if re.search(meta_desc_pattern, content, re.IGNORECASE):
            content = re.sub(
                meta_desc_pattern,
                f'<meta name="description" content="{new_desc}">',
                content,
                flags=re.IGNORECASE
            )
        else:
            # Add meta description if missing (before closing head tag)
            head_close = content.find('</head>')
            if head_close > 0:
                content = content[:head_close] + f'    <meta name="description" content="{new_desc}">\n' + content[head_close:]
        
        # Only write if content changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Process tool review pages."""
    root = Path('.')
    html_files = []
    
    # Find tool review pages
    for html_file in root.rglob('tools/*review.html'):
        if any(part.startswith('.') for part in html_file.parts):
            continue
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} tool review files")
    print("Improving meta descriptions...")
    print()
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            print(f"[OK] Updated {filepath}")
    
    print(f"\n[SUCCESS] Completed! Updated {updated_count} files.")

if __name__ == '__main__':
    main()
