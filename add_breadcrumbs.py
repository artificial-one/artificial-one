#!/usr/bin/env python3
"""
Add breadcrumb navigation to HTML pages.
Breadcrumbs improve UX and enable breadcrumb rich snippets.
"""
import re
from pathlib import Path

def get_breadcrumbs(filepath):
    """Generate breadcrumb trail from file path."""
    base_url = "https://artificial.one"
    
    breadcrumbs = [
        ('Home', f'{base_url}/')
    ]
    
    # Parse path
    parts = str(filepath).replace('\\', '/').split('/')
    parts = [p for p in parts if p and p != '.' and not p.endswith('.html')]
    
    current_path = ""
    for part in parts:
        current_path += f"/{part}"
        # Format name
        name = part.replace('-', ' ').title()
        # Special formatting for categories
        if part == 'category':
            continue
        elif 'category' in current_path:
            # Category pages
            category_name = part.replace('-', ' & ').title()
            breadcrumbs.append((category_name, f'{base_url}{current_path}.html'))
        elif part == 'tools':
            breadcrumbs.append(('Tools', f'{base_url}{current_path}/'))
        elif part == 'compare':
            breadcrumbs.append(('Compare', f'{base_url}{current_path}/'))
        elif part == 'best':
            breadcrumbs.append(('Best Of', f'{base_url}{current_path}/'))
        elif part == 'guides':
            breadcrumbs.append(('Guides', f'{base_url}{current_path}/'))
        elif part == 'tutorials':
            breadcrumbs.append(('Tutorials', f'{base_url}{current_path}/'))
        else:
            breadcrumbs.append((name, f'{base_url}{current_path}.html'))
    
    return breadcrumbs

def create_breadcrumb_html(breadcrumbs):
    """Create breadcrumb HTML with schema markup."""
    if len(breadcrumbs) <= 1:
        return ""
    
    items = []
    for i, (name, url) in enumerate(breadcrumbs, 1):
        if i == len(breadcrumbs):
            # Last item (current page)
            items.append(f'''        <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem">
          <span itemprop="name">{name}</span>
          <meta itemprop="position" content="{i}" />
        </li>''')
        else:
            items.append(f'''        <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem">
          <a href="{url}" itemprop="item"><span itemprop="name">{name}</span></a>
          <meta itemprop="position" content="{i}" />
        </li>''')
    
    breadcrumb_html = f'''    <nav aria-label="Breadcrumb" style="margin: 20px 0; padding: 10px 0; border-bottom: 1px solid #e5e7eb;">
      <ol itemscope itemtype="https://schema.org/BreadcrumbList" style="list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 8px; font-size: 14px; color: #6b7280;">
{chr(10).join(items)}
      </ol>
    </nav>'''
    
    return breadcrumb_html

def add_breadcrumbs(content, filepath):
    """Add breadcrumb navigation to HTML content."""
    # Skip if already has breadcrumbs
    if 'itemscope itemtype="https://schema.org/BreadcrumbList"' in content:
        return content
    
    breadcrumbs = get_breadcrumbs(filepath)
    if len(breadcrumbs) <= 1:
        return content  # Skip homepage
    
    breadcrumb_html = create_breadcrumb_html(breadcrumbs)
    
    # Find insertion point - after nav/header, before main content
    # Try to insert after header/nav
    if '<article' in content:
        content = re.sub(r'(<article[^>]*>)', rf'\1\n{breadcrumb_html}', content, count=1)
    elif '<main' in content:
        content = re.sub(r'(<main[^>]*>)', rf'\1\n{breadcrumb_html}', content, count=1)
    elif '<section' in content:
        content = re.sub(r'(<section[^>]*class=["\'][^"\']*py-[^"\']*["\'][^>]*>)', rf'\1\n{breadcrumb_html}', content, count=1)
    elif '</nav>' in content:
        content = content.replace('</nav>', f'</nav>\n{breadcrumb_html}')
    elif '</header>' in content:
        content = content.replace('</header>', f'</header>\n{breadcrumb_html}')
    else:
        # Fallback: add at start of body content
        if '<body' in content:
            content = re.sub(r'(<body[^>]*>)', rf'\1\n{breadcrumb_html}', content, count=1)
    
    return content

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        updated_content = add_breadcrumbs(content, filepath)
        
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
    print("Adding breadcrumb navigation...")
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            print(f"[OK] Added breadcrumbs to {filepath}")
    
    print(f"\nCompleted! Updated {updated_count} files with breadcrumbs.")

if __name__ == '__main__':
    main()
