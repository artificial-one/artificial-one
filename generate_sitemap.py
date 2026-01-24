#!/usr/bin/env python3
"""
Generate a complete sitemap.xml with all HTML pages on the site.
Updates lastmod to today's date (2026-01-24).
"""
from pathlib import Path
from datetime import date

def get_priority(path):
    """Determine priority based on page location."""
    path_str = str(path)
    
    # Root pages
    if path.name == 'index.html':
        return 1.0
    if path.name in ['reviews.html', 'blog.html']:
        return 0.9
    
    # Important guide pages
    if 'best-lifetime-deal-software-2026' in path_str:
        return 0.9
    
    # Category pages
    if '/category/' in path_str:
        return 0.8
    
    # Guide pages
    if '/guides/' in path_str:
        return 0.7
    
    # Tool review pages
    if '/tools/' in path_str:
        return 0.7
    
    # Blog posts
    if 'blog-' in path.name:
        return 0.6
    
    # Compare, best, tutorials
    if any(x in path_str for x in ['/compare/', '/best/', '/tutorials/']):
        return 0.6
    
    # About and other pages
    return 0.5

def get_changefreq(path):
    """Determine change frequency based on page type."""
    path_str = str(path)
    
    # Homepage and reviews page update frequently
    if path.name in ['index.html', 'reviews.html']:
        return 'daily'
    
    # Blog and tool reviews update weekly
    if '/tools/' in path_str or 'blog-' in path.name or '/blog/' in path_str:
        return 'weekly'
    
    # Category and guide pages update less frequently
    if any(x in path_str for x in ['/category/', '/guides/']):
        return 'weekly'
    
    # Everything else is monthly
    return 'monthly'

def generate_sitemap():
    """Generate sitemap.xml with all HTML pages."""
    root = Path('.')
    base_url = 'https://artificial.one'
    today = '2026-01-24'
    
    # Find all HTML files
    html_files = []
    for html_file in root.rglob('*.html'):
        # Skip hidden directories and node_modules
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if 'node_modules' in html_file.parts:
            continue
        
        html_files.append(html_file)
    
    # Sort files for consistent ordering
    html_files.sort()
    
    # Generate sitemap XML
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>']
    sitemap.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for html_file in html_files:
        # Convert path to URL
        url_path = str(html_file).replace('\\', '/')
        
        # Remove leading './' if present
        if url_path.startswith('./'):
            url_path = url_path[2:]
        
        # Handle index.html at root
        if url_path == 'index.html':
            url = f'{base_url}/'
        else:
            url = f'{base_url}/{url_path}'
        
        priority = get_priority(html_file)
        changefreq = get_changefreq(html_file)
        
        sitemap.append('  <url>')
        sitemap.append(f'    <loc>{url}</loc>')
        sitemap.append(f'    <lastmod>{today}</lastmod>')
        sitemap.append(f'    <changefreq>{changefreq}</changefreq>')
        sitemap.append(f'    <priority>{priority}</priority>')
        sitemap.append('  </url>')
    
    sitemap.append('</urlset>')
    
    # Write sitemap
    sitemap_content = '\n'.join(sitemap)
    Path('sitemap.xml').write_text(sitemap_content, encoding='utf-8')
    
    print(f'Generated sitemap.xml with {len(html_files)} URLs')
    print(f'Last modified date: {today}')

if __name__ == '__main__':
    generate_sitemap()
