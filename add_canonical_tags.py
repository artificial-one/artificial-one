#!/usr/bin/env python3
"""
Add canonical tags to all HTML pages.
Canonical tags prevent duplicate content issues and consolidate link equity.
"""
import re
from pathlib import Path

def get_canonical_url(filepath):
    """Generate canonical URL from file path."""
    base_url = "https://artificial.one"
    
    # Convert Windows path to URL path
    url_path = str(filepath).replace('\\', '/')
    
    # Remove leading './' if present
    if url_path.startswith('./'):
        url_path = url_path[2:]
    
    # Handle index.html at root
    if url_path == 'index.html':
        return f'{base_url}/'
    
    return f'{base_url}/{url_path}'

def add_canonical_tag(content, canonical_url):
    """Add or update canonical tag in HTML head."""
    canonical_tag = f'<link rel="canonical" href="{canonical_url}" />'
    
    # Check if canonical already exists
    if re.search(r'<link\s+rel=["\']canonical["\']', content, re.IGNORECASE):
        # Replace existing canonical
        content = re.sub(
            r'<link\s+rel=["\']canonical["\'][^>]*>',
            canonical_tag,
            content,
            flags=re.IGNORECASE
        )
    else:
        # Add canonical tag after viewport meta tag or before closing </head>
        if '<meta name="viewport"' in content:
            content = re.sub(
                r'(<meta\s+name=["\']viewport["\'][^>]*>)',
                rf'\1\n    {canonical_tag}',
                content,
                flags=re.IGNORECASE
            )
        elif '</head>' in content:
            content = content.replace('</head>', f'    {canonical_tag}\n</head>')
        else:
            # Fallback: add before closing body tag
            content = content.replace('</body>', f'    {canonical_tag}\n</body>')
    
    return content

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        canonical_url = get_canonical_url(filepath)
        updated_content = add_canonical_tag(content, canonical_url)
        
        # Only write if content changed
        if updated_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_content)
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
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            print(f"[OK] Added canonical to {filepath}")
    
    print(f"\nCompleted! Updated {updated_count} files with canonical tags.")

if __name__ == '__main__':
    main()
