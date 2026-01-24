#!/usr/bin/env python3
"""
Add Open Graph image meta tags to pages.
This improves social media sharing appearance.
"""
import re
from pathlib import Path

def get_og_image_url(filepath):
    """Generate OG image URL based on page type."""
    base_url = "https://artificial.one"
    
    # Determine image based on page type
    path_str = str(filepath).replace('\\', '/')
    
    if filepath.name == 'index.html':
        return f'{base_url}/images/og-homepage.jpg'
    elif '/tools/' in path_str or filepath.parent.name == 'tools':
        # Tool review pages
        tool_name = filepath.stem.replace('-review', '').replace('-', '-')
        return f'{base_url}/images/og-tools/{tool_name}.jpg'
    elif '/category/' in path_str:
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

def add_og_image_tags(content, filepath):
    """Add OG image meta tags to HTML head."""
    # Check if OG image already exists
    if re.search(r'<meta\s+property=["\']og:image["\']', content, re.IGNORECASE):
        return content
    
    og_image_url = get_og_image_url(filepath)
    
    og_tags = f'''    <meta property="og:image" content="{og_image_url}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="{filepath.stem.replace('-', ' ').title()}" />'''
    
    # Add after existing OG tags or before closing </head>
    if '<meta property="og:' in content:
        # Add after last OG tag
        content = re.sub(
            r'(<meta\s+property=["\']og:[^>]*>)',
            rf'\1\n{og_tags}',
            content,
            flags=re.IGNORECASE
        )
        # But we want it after the last one, so let's do it differently
        last_og = list(re.finditer(r'<meta\s+property=["\']og:[^>]*>', content, re.IGNORECASE))
        if last_og:
            last_pos = last_og[-1].end()
            content = content[:last_pos] + '\n' + og_tags + content[last_pos:]
    elif '</head>' in content:
        content = content.replace('</head>', f'{og_tags}\n</head>')
    else:
        content = content.replace('</body>', f'{og_tags}\n</body>')
    
    return content

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        updated_content = add_og_image_tags(content, filepath)
        
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
    
    for html_file in root.rglob('*.html'):
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if '.git' in html_file.parts:
            continue
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} HTML files")
    print("Adding OG image meta tags...")
    print("Note: You'll need to create the actual image files later.")
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            if updated_count <= 10:  # Show first 10
                print(f"[OK] Added OG image tags to {filepath}")
    
    print(f"\nCompleted! Updated {updated_count} files with OG image tags.")
    print("\nNext step: Create OG images (1200x630px) for:")
    print("  - Homepage: /images/og-homepage.jpg")
    print("  - Tool reviews: /images/og-tools/*.jpg")
    print("  - Categories: /images/og-categories/*.jpg")
    print("  - Blog posts: /images/og-blog/*.jpg")

if __name__ == '__main__':
    main()
