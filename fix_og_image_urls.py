#!/usr/bin/env python3
"""
Fix OG image URLs to point to correct tool-specific images instead of default.
"""
import re
from pathlib import Path

def get_correct_og_image_url(filepath):
    """Get the correct OG image URL for a file."""
    base_url = "https://artificial.one"
    path_str = str(filepath).replace('\\', '/')
    
    if filepath.name == 'index.html':
        return f'{base_url}/images/og-homepage.jpg'
    elif '/tools/' in path_str or filepath.parent.name == 'tools':
        tool_name = filepath.stem.replace('-review', '').replace('-', '-')
        return f'{base_url}/images/og-tools/{tool_name}.jpg'
    elif '/category/' in path_str or filepath.parent.name == 'category':
        category = filepath.stem.replace('-', '-')
        return f'{base_url}/images/og-categories/{category}.jpg'
    elif 'blog-' in filepath.name:
        blog_name = filepath.stem.replace('blog-', '').replace('-', '-')
        return f'{base_url}/images/og-blog/{blog_name}.jpg'
    elif '/compare/' in path_str:
        return f'{base_url}/images/og-compare.jpg'
    elif '/best/' in path_str:
        return f'{base_url}/images/og-best-of.jpg'
    elif '/guides/' in path_str:
        return f'{base_url}/images/og-guides.jpg'
    else:
        return f'{base_url}/images/og-default.jpg'

def fix_og_image_urls(content, filepath):
    """Fix OG image URLs in HTML content."""
    correct_url = get_correct_og_image_url(filepath)
    
    # Find and replace og:image URLs
    # Pattern: <meta property="og:image" content="...og-default.jpg" />
    pattern = r'(<meta\s+property=["\']og:image["\']\s+content=["\'])([^"\']+)(["\'])'
    
    def replace_url(match):
        current_url = match.group(2)
        # Only replace if it's pointing to default when it should be tool-specific
        if '/tools/' in str(filepath) or filepath.parent.name == 'tools':
            if 'og-default.jpg' in current_url:
                return f'{match.group(1)}{correct_url}{match.group(3)}'
        elif '/category/' in str(filepath) or filepath.parent.name == 'category':
            if 'og-default.jpg' in current_url:
                return f'{match.group(1)}{correct_url}{match.group(3)}'
        elif filepath.name == 'index.html':
            if 'og-default.jpg' in current_url:
                return f'{match.group(1)}{correct_url}{match.group(3)}'
        return match.group(0)  # Keep original if no change needed
    
    updated_content = re.sub(pattern, replace_url, content, flags=re.IGNORECASE)
    
    return updated_content

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        updated_content = fix_og_image_urls(content, filepath)
        
        if updated_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Fix OG image URLs in all HTML files."""
    root = Path('.')
    html_files = []
    
    for html_file in root.rglob('*.html'):
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if '.git' in html_file.parts:
            continue
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} HTML files")
    print("Fixing OG image URLs...\n")
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            if updated_count <= 20:
                print(f"[OK] Fixed OG image URL in {filepath}")
    
    print(f"\nCompleted! Fixed {updated_count} files.")

if __name__ == '__main__':
    main()
