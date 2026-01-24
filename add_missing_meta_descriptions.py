#!/usr/bin/env python3
"""
Add missing meta descriptions to HTML pages.
Generates SEO-friendly descriptions based on page content.
"""
import re
from pathlib import Path

def extract_page_info(content, filepath):
    """Extract information from page to generate meta description."""
    info = {}
    
    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if title_match:
        info['title'] = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    
    # Extract H1
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
    if h1_match:
        info['h1'] = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
    
    # Extract first paragraph
    p_match = re.search(r'<p[^>]*>(.*?)</p>', content, re.IGNORECASE | re.DOTALL)
    if p_match:
        info['first_para'] = re.sub(r'<[^>]+>', '', p_match.group(1)).strip()[:200]
    
    # Determine page type
    path_str = str(filepath).replace('\\', '/')
    if '/compare/' in path_str:
        info['type'] = 'comparison'
    elif '/guides/' in path_str:
        info['type'] = 'guide'
    elif '/tools/' in path_str:
        info['type'] = 'tool'
    elif '/best/' in path_str:
        info['type'] = 'best_of'
    elif '/category/' in path_str:
        info['type'] = 'category'
    elif 'blog-' in filepath.name:
        info['type'] = 'blog'
    else:
        info['type'] = 'page'
    
    return info

def generate_meta_description(info, filepath):
    """Generate SEO-friendly meta description."""
    title = info.get('title', '')
    h1 = info.get('h1', '')
    first_para = info.get('first_para', '')
    page_type = info.get('type', 'page')
    
    # Use H1 or title as base
    base_text = h1 or title or filepath.stem.replace('-', ' ').title()
    
    # Clean up base text
    base_text = re.sub(r'\s+', ' ', base_text).strip()
    
    # Generate description based on page type
    if page_type == 'comparison':
        # Comparison pages: "Compare X vs Y. See pricing, features, pros & cons. Find the best tool for your needs."
        if ' vs ' in base_text.lower() or ' vs ' in title.lower():
            tools = base_text.split(' vs ')[:2] if ' vs ' in base_text else [base_text]
            desc = f"Compare {tools[0] if len(tools) > 0 else 'AI tools'}. See pricing, features, pros & cons. Find the best tool for your needs in 2026."
        else:
            desc = f"{base_text}. Compare features, pricing, and reviews. Find the best AI tool for your needs."
    
    elif page_type == 'guide':
        # Guide pages: "Complete guide to X. Learn how to choose, use cases, and best tools. Updated 2026."
        desc = f"Complete guide to {base_text}. Learn how to choose, use cases, pricing, and best tools. Updated 2026."
    
    elif page_type == 'tool':
        # Tool pages: "X review 2026. Rating, pricing, features, pros & cons. See if it's worth it."
        tool_name = base_text.replace(' Review', '').replace(' review', '').strip()
        desc = f"{tool_name} review 2026. Rating, pricing, features, pros & cons. See if it's worth it for your business."
    
    elif page_type == 'best_of':
        # Best of pages: "Best X tools in 2026. Compare top-rated options, pricing, and features. Find the perfect match."
        desc = f"Best {base_text.replace('Best ', '').replace('best ', '')} in 2026. Compare top-rated options, pricing, and features. Find the perfect match."
    
    elif page_type == 'category':
        # Category pages: "Browse X AI tools. Compare reviews, ratings, and pricing. Find the best tool for your needs."
        category = base_text.replace(' AI Tools', '').replace(' Tools', '').strip()
        desc = f"Browse {category} AI tools. Compare reviews, ratings, and pricing. Find the best tool for your needs in 2026."
    
    elif page_type == 'blog':
        # Blog posts: Use first paragraph or generate from title
        if first_para and len(first_para) > 50:
            desc = first_para[:150] + '...'
        else:
            desc = f"{base_text}. Learn about AI tools, comparisons, and reviews. Updated 2026."
    
    else:
        # Generic pages
        if first_para and len(first_para) > 50:
            desc = first_para[:150] + '...'
        else:
            desc = f"{base_text}. Find the best AI tools, reviews, and comparisons. Updated 2026."
    
    # Clean up description
    desc = re.sub(r'\s+', ' ', desc).strip()
    
    # Ensure it's between 120-160 characters (optimal length)
    if len(desc) > 160:
        desc = desc[:157] + '...'
    elif len(desc) < 120:
        # Pad with relevant text
        if '2026' not in desc:
            desc += " Updated 2026."
        if len(desc) < 120:
            desc += " Find the best AI tools and reviews."
    
    # Final length check
    if len(desc) > 160:
        desc = desc[:157] + '...'
    
    return desc

def add_meta_description(content, filepath):
    """Add meta description to HTML head."""
    # Check if meta description already exists
    if re.search(r'<meta\s+name=["\']description["\'][^>]*>', content, re.IGNORECASE):
        return content
    
    # Extract page info
    info = extract_page_info(content, filepath)
    
    # Generate description
    description = generate_meta_description(info, filepath)
    
    meta_tag = f'<meta name="description" content="{description}" />'
    
    # Add after viewport or title, before closing </head>
    if '<meta name="viewport"' in content:
        # Add after viewport
        content = re.sub(
            r'(<meta\s+name=["\']viewport["\'][^>]*>)',
            rf'\1\n    {meta_tag}',
            content,
            flags=re.IGNORECASE
        )
    elif '<title>' in content:
        # Add after title
        content = re.sub(
            r'(<title>.*?</title>)',
            rf'\1\n    {meta_tag}',
            content,
            flags=re.IGNORECASE | re.DOTALL
        )
    elif '</head>' in content:
        # Add before closing head
        content = content.replace('</head>', f'    {meta_tag}\n</head>')
    else:
        # Fallback: add before closing body
        content = content.replace('</body>', f'    {meta_tag}\n</body>')
    
    return content

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Skip if already has meta description
        if re.search(r'<meta\s+name=["\']description["\'][^>]*>', content, re.IGNORECASE):
            return False
        
        updated_content = add_meta_description(content, filepath)
        
        if updated_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Process all HTML files missing meta descriptions."""
    root = Path('.')
    html_files = []
    
    # Find all HTML files
    for html_file in root.rglob('*.html'):
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if '.git' in html_file.parts:
            continue
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} HTML files")
    print("Checking for missing meta descriptions...\n")
    
    # First pass: identify files missing descriptions
    files_to_update = []
    for filepath in sorted(html_files):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if not re.search(r'<meta\s+name=["\']description["\'][^>]*>', content, re.IGNORECASE):
                files_to_update.append(filepath)
        except:
            pass
    
    print(f"Found {len(files_to_update)} files missing meta descriptions\n")
    print("Adding meta descriptions...\n")
    
    updated_count = 0
    for filepath in sorted(files_to_update):
        if process_file(filepath):
            updated_count += 1
            print(f"[OK] Added meta description to {filepath}")
    
    print(f"\nCompleted! Updated {updated_count} files with meta descriptions.")
    print(f"\nRemaining files without descriptions: {len(files_to_update) - updated_count}")

if __name__ == '__main__':
    main()
