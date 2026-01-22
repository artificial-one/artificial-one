#!/usr/bin/env python3
"""
Sitemap Generator for artificial.one
Run this in your repo: python generate_sitemap.py
"""

import os
from datetime import datetime

def generate_sitemap(base_url="https://artificial.one"):
    """Generate sitemap.xml from all HTML files in current directory"""
    
    sitemap_entries = []
    
    # Priority and changefreq rules
    def get_priority_and_freq(filepath):
        if filepath == 'index.html':
            return ('1.0', 'daily')
        elif filepath == 'reviews.html':
            return ('0.9', 'daily')
        elif filepath.startswith('guides/best-lifetime-deal-software'):
            return ('0.9', 'weekly')
        elif filepath.startswith('guides/use-case'):
            return ('0.8', 'weekly')
        elif filepath.startswith('guides/best-') or filepath.startswith('guides/appsumo'):
            return ('0.8', 'weekly')
        elif filepath.startswith('tools/') and filepath.endswith('-review.html'):
            return ('0.7', 'monthly')
        elif filepath.startswith('compare/'):
            return ('0.7', 'monthly')
        elif filepath.startswith('category/'):
            return ('0.8', 'weekly')
        elif filepath.startswith('best/'):
            return ('0.7', 'weekly')
        elif filepath.startswith('tutorials/'):
            return ('0.6', 'monthly')
        elif filepath.startswith('blog'):
            return ('0.6', 'monthly')
        else:
            return ('0.6', 'monthly')
    
    # Walk through all directories
    for root, dirs, files in os.walk('.'):
        # Skip hidden and git directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.endswith('.html'):
                # Get relative path
                filepath = os.path.join(root, file)
                filepath = filepath.replace('.\\', '').replace('./', '')
                filepath = filepath.replace('\\', '/')
                
                # Get priority and frequency
                priority, changefreq = get_priority_and_freq(filepath)
                
                # Create URL
                if filepath == 'index.html':
                    url = base_url + '/'
                else:
                    url = base_url + '/' + filepath
                
                sitemap_entries.append({
                    'url': url,
                    'priority': priority,
                    'changefreq': changefreq
                })
    
    # Sort by priority (highest first)
    sitemap_entries.sort(key=lambda x: float(x['priority']), reverse=True)
    
    # Generate XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for entry in sitemap_entries:
        xml += '  <url>\n'
        xml += f'    <loc>{entry["url"]}</loc>\n'
        xml += f'    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n'
        xml += f'    <changefreq>{entry["changefreq"]}</changefreq>\n'
        xml += f'    <priority>{entry["priority"]}</priority>\n'
        xml += '  </url>\n'
    
    xml += '</urlset>\n'
    
    # Write to file
    with open('sitemap.xml', 'w', encoding='utf-8') as f:
        f.write(xml)
    
    print(f"✅ Generated sitemap.xml with {len(sitemap_entries)} pages")
    print(f"📍 Saved to: sitemap.xml")
    
    # Show summary
    by_folder = {}
    for entry in sitemap_entries:
        folder = entry['url'].split('/')[3] if len(entry['url'].split('/')) > 3 else 'root'
        by_folder[folder] = by_folder.get(folder, 0) + 1
    
    print("\n📊 Pages by folder:")
    for folder, count in sorted(by_folder.items(), key=lambda x: x[1], reverse=True):
        print(f"  {folder}: {count} pages")

if __name__ == '__main__':
    generate_sitemap()
