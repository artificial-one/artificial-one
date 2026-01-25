#!/usr/bin/env python3
"""
Find top tools with affiliate links for blog post creation.
"""

import re
from pathlib import Path

def extract_tool_info(filepath):
    """Extract tool name, rating, and affiliate link from review file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        info = {'file': filepath.name}
        
        # Extract tool name from title
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
        if title_match:
            title = title_match.group(1)
            # Extract product name (usually before "Review")
            product_match = re.search(r'^([^R]+?)\s+Review', title, re.IGNORECASE)
            if product_match:
                info['name'] = product_match.group(1).strip()
            else:
                info['name'] = title.split('Review')[0].strip()
        
        # Extract rating
        rating_match = re.search(r'(\d+\.?\d*)/5', content)
        if rating_match:
            info['rating'] = float(rating_match.group(1))
        else:
            info['rating'] = 0
        
        # Extract affiliate link
        affiliate_match = re.search(r'https://appsumo\.8odi\.net/[^\s"\'<>)]+', content)
        if affiliate_match:
            info['affiliate'] = affiliate_match.group(0)
        else:
            return None
        
        # Extract price if available
        price_match = re.search(r'\$(\d+)\s+lifetime', content, re.IGNORECASE)
        if price_match:
            info['price'] = price_match.group(1)
        else:
            info['price'] = 'Unknown'
        
        return info
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None

def main():
    """Find all tools with affiliate links and rank them."""
    tools_dir = Path('tools')
    tools_with_affiliates = []
    
    for review_file in tools_dir.glob('*-review.html'):
        info = extract_tool_info(review_file)
        if info:
            tools_with_affiliates.append(info)
    
    # Sort by rating (highest first)
    tools_with_affiliates.sort(key=lambda x: x['rating'], reverse=True)
    
    print(f"Found {len(tools_with_affiliates)} tools with affiliate links\n")
    print("Top 20 tools by rating:")
    print("-" * 80)
    for i, tool in enumerate(tools_with_affiliates[:20], 1):
        print(f"{i:2d}. {tool['name']:40s} Rating: {tool['rating']:.1f}/5  Price: ${tool['price']}")
    
    # Save to file for reference
    with open('top_affiliate_tools.txt', 'w', encoding='utf-8') as f:
        f.write("Top Tools with Affiliate Links (sorted by rating)\n")
        f.write("=" * 80 + "\n\n")
        for i, tool in enumerate(tools_with_affiliates[:30], 1):
            f.write(f"{i:2d}. {tool['name']}\n")
            f.write(f"    File: {tool['file']}\n")
            f.write(f"    Rating: {tool['rating']}/5\n")
            f.write(f"    Price: ${tool['price']}\n")
            f.write(f"    Affiliate: {tool['affiliate']}\n\n")
    
    print(f"\nFull list saved to top_affiliate_tools.txt")

if __name__ == '__main__':
    main()
