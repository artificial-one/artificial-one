#!/usr/bin/env python3
"""
Add complete Open Graph meta tags (title, description, type, url, image) to all pages.
This ensures all pages have proper OG tags for social media sharing.
"""
import re
from pathlib import Path

def extract_page_info(content, filepath):
    """Extract page information for OG tags."""
    info = {
        'title': '',
        'description': '',
        'url': '',
        'type': 'website'
    }
    
    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if title_match:
        info['title'] = re.sub(r'\s+', ' ', title_match.group(1).strip())
    
    # Extract meta description
    desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', content, re.IGNORECASE)
    if desc_match:
        info['description'] = desc_match.group(1).strip()
    elif title_match:
        # Fallback: use title as description
        info['description'] = info['title']
    
    # Generate URL
    base_url = "https://artificial.one"
    path_str = str(filepath).replace('\\', '/')
    
    if filepath.name == 'index.html':
        info['url'] = base_url
    else:
        # Remove leading ./
        if path_str.startswith('./'):
            path_str = path_str[2:]
        info['url'] = f'{base_url}/{path_str}'
    
    # Determine type
    if '/tools/' in path_str or filepath.parent.name == 'tools':
        info['type'] = 'article'
    elif 'blog-' in filepath.name:
        info['type'] = 'article'
    else:
        info['type'] = 'website'
    
    return info

def get_og_image_url(filepath):
    """Get OG image URL for the page."""
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

def add_complete_og_tags(content, filepath):
    """Add or update complete OG tags to HTML content."""
    info = extract_page_info(content, filepath)
    og_image_url = get_og_image_url(filepath)
    
    # Create complete OG tags
    og_tags = f'''    <meta property="og:title" content="{info['title']}" />
    <meta property="og:description" content="{info['description']}" />
    <meta property="og:type" content="{info['type']}" />
    <meta property="og:url" content="{info['url']}" />
    <meta property="og:image" content="{og_image_url}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="{info['title']}" />'''
    
    # Check if any OG tags exist
    has_og_tags = re.search(r'<meta\s+property=["\']og:', content, re.IGNORECASE)
    
    if has_og_tags:
        # Remove all existing OG tags
        content = re.sub(
            r'<meta\s+property=["\']og:[^>]*>',
            '',
            content,
            flags=re.IGNORECASE
        )
        # Clean up extra blank lines
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # Find where to insert (after viewport or before closing head)
        if '<meta name="viewport"' in content:
            content = re.sub(
                r'(<meta\s+name=["\']viewport["\'][^>]*>)',
                rf'\1\n{og_tags}',
                content,
                flags=re.IGNORECASE,
                count=1
            )
        elif '</head>' in content:
            content = content.replace('</head>', f'{og_tags}\n</head>')
        else:
            # Insert after title
            if '<title>' in content:
                content = re.sub(
                    r'(</title>)',
                    rf'\1\n{og_tags}',
                    content,
                    flags=re.IGNORECASE,
                    count=1
                )
    else:
        # No OG tags exist, add them after viewport or title
        if '<meta name="viewport"' in content:
            content = re.sub(
                r'(<meta\s+name=["\']viewport["\'][^>]*>)',
                rf'\1\n{og_tags}',
                content,
                flags=re.IGNORECASE,
                count=1
            )
        elif '</title>' in content:
            content = re.sub(
                r'(</title>)',
                rf'\1\n{og_tags}',
                content,
                flags=re.IGNORECASE,
                count=1
            )
        elif '</head>' in content:
            content = content.replace('</head>', f'{og_tags}\n</head>')
    
    return content

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        updated_content = add_complete_og_tags(content, filepath)
        
        if updated_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Add complete OG tags to all HTML files."""
    root = Path('.')
    html_files = []
    
    for html_file in root.rglob('*.html'):
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if '.git' in html_file.parts:
            continue
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} HTML files")
    print("Adding complete OG tags (title, description, type, url, image)...\n")
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            if updated_count <= 20:
                print(f"[OK] Updated OG tags in {filepath}")
    
    print(f"\nCompleted! Updated {updated_count} files with complete OG tags.")

if __name__ == '__main__':
    main()
