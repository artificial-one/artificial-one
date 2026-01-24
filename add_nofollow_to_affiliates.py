#!/usr/bin/env python3
"""
Add rel="nofollow sponsored" to affiliate links.
This complies with Google guidelines and prevents passing PageRank to external sites.
"""
import re
from pathlib import Path

def update_affiliate_link(match):
    """Update affiliate link with rel="nofollow sponsored"."""
    link = match.group(0)
    
    # Check if already has rel attribute
    if re.search(r'rel\s*=', link, re.IGNORECASE):
        # Update existing rel
        link = re.sub(
            r'rel\s*=\s*["\']([^"\']*)["\']',
            lambda m: f'rel="{m.group(1)} nofollow sponsored"',
            link,
            flags=re.IGNORECASE
        )
    else:
        # Add rel attribute before closing >
        link = re.sub(r'(>)', r' rel="nofollow sponsored"\1', link)
    
    return link

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        
        # Find affiliate links (AppSumo, Impact, etc.)
        affiliate_patterns = [
            r'<a\s+[^>]*href\s*=\s*["\']https?://appsumo\.8odi\.net[^"\']*["\'][^>]*>',
            r'<a\s+[^>]*href\s*=\s*["\']https?://[^"\']*appsumo[^"\']*["\'][^>]*>',
            r'<a\s+[^>]*href\s*=\s*["\']https?://[^"\']*impact\.com[^"\']*["\'][^>]*>',
            # Add more affiliate link patterns as needed
        ]
        
        for pattern in affiliate_patterns:
            content = re.sub(pattern, update_affiliate_link, content, flags=re.IGNORECASE)
        
        # Also check for common affiliate link text patterns
        # Links with "Get Deal", "Lifetime Deal", "Buy Now", etc.
        deal_pattern = r'<a\s+([^>]*href\s*=\s*["\']https?://[^"\']*["\'])([^>]*)>([^<]*(?:deal|buy|purchase|affiliate|commission)[^<]*)</a>'
        
        def add_rel_to_deal_link(match):
            full_tag = match.group(0)
            # Check if it's already an affiliate link or if it needs rel
            if 'appsumo' in full_tag.lower() or 'impact' in full_link.lower():
                if 'rel=' not in full_tag.lower():
                    return re.sub(r'(>)', r' rel="nofollow sponsored"\1', full_tag)
            return full_tag
        
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
    """Process all HTML files."""
    root = Path('.')
    html_files = []
    
    # Find all HTML files
    for html_file in root.rglob('*.html'):
        # Skip hidden directories and .git
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if '.git' in html_file.parts:
            continue
        
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} HTML files")
    print("Adding rel='nofollow sponsored' to affiliate links...")
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            print(f"[OK] Updated affiliate links in {filepath}")
    
    print(f"\nCompleted! Updated {updated_count} files.")
    print("\nNote: Please manually verify a few affiliate links to ensure")
    print("they now have rel='nofollow sponsored' attributes.")

if __name__ == '__main__':
    main()
