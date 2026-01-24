#!/usr/bin/env python3
"""
Check current SEO status of HTML files.
Reports on canonical tags, structured data, meta tags, etc.
"""
import re
from pathlib import Path
from collections import defaultdict

def check_file(filepath):
    """Check SEO elements in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        status = {
            'file': str(filepath),
            'has_canonical': bool(re.search(r'<link\s+rel=["\']canonical["\']', content, re.IGNORECASE)),
            'has_structured_data': bool(re.search(r'<script\s+type=["\']application/ld\+json["\']', content, re.IGNORECASE)),
            'has_meta_description': bool(re.search(r'<meta\s+name=["\']description["\'][^>]*>', content, re.IGNORECASE)),
            'has_og_tags': bool(re.search(r'<meta\s+property=["\']og:', content, re.IGNORECASE)),
            'has_og_image': bool(re.search(r'<meta\s+property=["\']og:image["\']', content, re.IGNORECASE)),
            'has_title': bool(re.search(r'<title>', content, re.IGNORECASE)),
            'affiliate_links': len(re.findall(r'https?://appsumo\.8odi\.net', content, re.IGNORECASE)),
            'affiliate_links_nofollow': len(re.findall(r'https?://appsumo\.8odi\.net[^>]*rel=["\'][^"\']*nofollow', content, re.IGNORECASE)),
            'has_breadcrumbs': bool(re.search(r'breadcrumb|Breadcrumb', content, re.IGNORECASE)),
        }
        
        return status
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}

def main():
    """Check SEO status of all HTML files."""
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
    
    print(f"Checking {len(html_files)} HTML files...\n")
    
    stats = defaultdict(int)
    issues = []
    
    for filepath in sorted(html_files):
        status = check_file(filepath)
        
        # Count stats
        if status.get('has_canonical'):
            stats['canonical'] += 1
        else:
            issues.append(f"[X] Missing canonical: {status['file']}")
        
        if status.get('has_structured_data'):
            stats['structured_data'] += 1
        else:
            if '/tools/' in status['file'] or 'blog-' in status['file']:
                issues.append(f"[!] Missing structured data: {status['file']}")
        
        if status.get('has_meta_description'):
            stats['meta_description'] += 1
        else:
            issues.append(f"[X] Missing meta description: {status['file']}")
        
        if status.get('has_og_tags'):
            stats['og_tags'] += 1
        
        if status.get('has_og_image'):
            stats['og_image'] += 1
        
        if status.get('has_title'):
            stats['title'] += 1
        
        if status.get('affiliate_links', 0) > 0:
            stats['affiliate_pages'] += 1
            if status.get('affiliate_links_nofollow', 0) < status.get('affiliate_links', 0):
                issues.append(f"[!] Affiliate links missing nofollow: {status['file']}")
    
    # Print summary
    print("=" * 60)
    print("SEO STATUS SUMMARY")
    print("=" * 60)
    print(f"\nTotal HTML files: {len(html_files)}")
    print(f"\n[OK] Files with canonical tags: {stats['canonical']}/{len(html_files)} ({stats['canonical']/len(html_files)*100:.1f}%)")
    print(f"[OK] Files with structured data: {stats['structured_data']}/{len(html_files)} ({stats['structured_data']/len(html_files)*100:.1f}%)")
    print(f"[OK] Files with meta descriptions: {stats['meta_description']}/{len(html_files)} ({stats['meta_description']/len(html_files)*100:.1f}%)")
    print(f"[OK] Files with OG tags: {stats['og_tags']}/{len(html_files)} ({stats['og_tags']/len(html_files)*100:.1f}%)")
    print(f"[OK] Files with OG images: {stats['og_image']}/{len(html_files)} ({stats['og_image']/len(html_files)*100:.1f}%)")
    print(f"[OK] Files with titles: {stats['title']}/{len(html_files)} ({stats['title']/len(html_files)*100:.1f}%)")
    print(f"[OK] Pages with affiliate links: {stats['affiliate_pages']}")
    
    # Print issues
    if issues:
        print(f"\n[!] Found {len(issues)} issues:")
        for issue in issues[:20]:  # Show first 20
            print(f"  {issue}")
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more issues")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)
    
    if stats['canonical'] < len(html_files):
        print("1. Run: python add_canonical_tags.py")
    
    if stats['structured_data'] < len(html_files) * 0.5:
        print("2. Run: python add_structured_data.py")
    
    if stats['og_image'] < len(html_files) * 0.1:
        print("3. Create OG images for top pages")
    
    if issues and any('nofollow' in i for i in issues):
        print("4. Run: python add_nofollow_to_affiliates.py")
    
    print("\nFor detailed recommendations, see SEO_RECOMMENDATIONS.md")

if __name__ == '__main__':
    main()
