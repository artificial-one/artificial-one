#!/usr/bin/env python3
"""
Script to optimize HTML review files with:
1. Update title to include "2026" and "Lifetime Deal"
2. Add meta description
3. Ensure 3-5 affiliate links
4. Add FAQ section
5. Add "Who should buy this?" section
"""

import os
import re
from pathlib import Path

def extract_product_info(html_content):
    """Extract product name, rating, price, and affiliate link from HTML"""
    info = {}
    
    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
    if title_match:
        title = title_match.group(1)
        # Extract product name (usually before "Review")
        product_match = re.search(r'^([^R]+?)\s+Review', title, re.IGNORECASE)
        if product_match:
            info['product_name'] = product_match.group(1).strip()
        else:
            info['product_name'] = title.split('Review')[0].strip()
    
    # Extract rating
    rating_match = re.search(r'Rating.*?(\d+\.?\d*)/5', html_content, re.IGNORECASE)
    if rating_match:
        info['rating'] = rating_match.group(1)
    
    # Extract price
    price_match = re.search(r'\$(\d+)\s+lifetime', html_content, re.IGNORECASE)
    if price_match:
        info['price'] = price_match.group(1)
    
    # Extract affiliate link
    affiliate_match = re.search(r'https://appsumo\.8odi\.net/([^\s"\'<>]+)', html_content)
    if affiliate_match:
        info['affiliate_link'] = affiliate_match.group(0)
    
    # Extract quick verdict
    verdict_match = re.search(r'Quick Verdict.*?<p[^>]*>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE)
    if verdict_match:
        info['quick_verdict'] = re.sub(r'<[^>]+>', '', verdict_match.group(1)).strip()
    
    return info

def optimize_file(filepath):
    """Optimize a single HTML file"""
    print(f"Processing {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    info = extract_product_info(content)
    
    # Check if already optimized (has FAQ section)
    if 'Frequently Asked Questions' in content or 'FAQ' in content:
        print(f"  {filepath} already has FAQ section, skipping...")
        return False
    
    print(f"  Product: {info.get('product_name', 'Unknown')}")
    print(f"  Rating: {info.get('rating', 'N/A')}/5")
    print(f"  Price: ${info.get('price', 'N/A')}")
    print(f"  Affiliate: {info.get('affiliate_link', 'Not found')}")
    
    return True

def main():
    tools_dir = Path('tools')
    html_files = list(tools_dir.glob('*.html'))
    
    files_to_optimize = []
    for filepath in html_files:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            if 'appsumo' in content or 'lifetime deal' in content:
                if optimize_file(filepath):
                    files_to_optimize.append(filepath)
    
    print(f"\nTotal files to optimize: {len(files_to_optimize)}")
    return files_to_optimize

if __name__ == '__main__':
    main()
