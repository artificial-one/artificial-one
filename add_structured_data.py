#!/usr/bin/env python3
"""
Add structured data (Schema.org JSON-LD) to HTML pages.
This helps Google understand content and enables rich snippets.
"""
import re
import json
from pathlib import Path

def extract_tool_info(content):
    """Extract tool information from HTML content."""
    info = {}
    
    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    if title_match:
        title = title_match.group(1)
        # Extract tool name (usually before "Review")
        tool_match = re.search(r'^([^R]+?)\s+Review', title, re.IGNORECASE)
        if tool_match:
            info['name'] = tool_match.group(1).strip()
        else:
            info['name'] = title.split('Review')[0].strip()
    
    # Extract rating
    rating_match = re.search(r'(\d+\.?\d*)/10|(\d+\.?\d*)/5', content)
    if rating_match:
        rating = rating_match.group(1) or rating_match.group(2)
        info['rating'] = float(rating)
        # Normalize to 5-point scale if needed
        if '/10' in content:
            info['rating'] = info['rating'] / 2
    
    # Extract description
    desc_match = re.search(r'<meta\s+name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', content, re.IGNORECASE)
    if desc_match:
        info['description'] = desc_match.group(1)
    
    # Extract URL
    canonical_match = re.search(r'<link\s+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', content, re.IGNORECASE)
    if canonical_match:
        info['url'] = canonical_match.group(1)
    
    return info

def create_review_schema(info):
    """Create Review schema for tool review pages."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Review",
        "itemReviewed": {
            "@type": "SoftwareApplication",
            "name": info.get('name', 'AI Tool'),
            "applicationCategory": "AI Tool"
        },
        "author": {
            "@type": "Organization",
            "name": "artificial.one",
            "url": "https://artificial.one"
        },
        "publisher": {
            "@type": "Organization",
            "name": "artificial.one",
            "url": "https://artificial.one"
        }
    }
    
    if 'rating' in info:
        schema["reviewRating"] = {
            "@type": "Rating",
            "ratingValue": str(info['rating']),
            "bestRating": "5",
            "worstRating": "1"
        }
    
    if 'description' in info:
        schema["reviewBody"] = info['description']
    
    if 'url' in info:
        schema["url"] = info['url']
    
    return schema

def create_article_schema(info, filepath):
    """Create Article schema for blog posts."""
    base_url = "https://artificial.one"
    url_path = str(filepath).replace('\\', '/')
    if url_path.startswith('./'):
        url_path = url_path[2:]
    if url_path == 'index.html':
        url = f'{base_url}/'
    else:
        url = f'{base_url}/{url_path}'
    
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": info.get('name', ''),
        "author": {
            "@type": "Organization",
            "name": "artificial.one"
        },
        "publisher": {
            "@type": "Organization",
            "name": "artificial.one",
            "logo": {
                "@type": "ImageObject",
                "url": "https://artificial.one/artificial-one-logo-large.svg"
            }
        },
        "url": url
    }
    
    if 'description' in info:
        schema["description"] = info['description']
    
    return schema

def create_breadcrumb_schema(filepath):
    """Create BreadcrumbList schema."""
    base_url = "https://artificial.one"
    
    # Build breadcrumb trail
    breadcrumbs = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Home",
            "item": f"{base_url}/"
        }
    ]
    
    parts = str(filepath).replace('\\', '/').split('/')
    parts = [p for p in parts if p and not p.endswith('.html')]
    
    position = 2
    current_path = ""
    
    for part in parts:
        if part == '.':
            continue
        current_path += f"/{part}"
        breadcrumbs.append({
            "@type": "ListItem",
            "position": position,
            "name": part.replace('-', ' ').title(),
            "item": f"{base_url}{current_path}.html"
        })
        position += 1
    
    # Add current page
    page_name = filepath.stem.replace('-', ' ').title()
    if page_name != 'Index':
        breadcrumbs.append({
            "@type": "ListItem",
            "position": position,
            "name": page_name,
            "item": f"{base_url}/{filepath}"
        })
    
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": breadcrumbs
    }

def add_structured_data(content, filepath):
    """Add structured data scripts to HTML head."""
    schemas = []
    
    # Determine page type
    is_tool_review = '/tools/' in str(filepath) and 'review' in str(filepath).lower()
    is_blog = 'blog-' in filepath.name or '/blog/' in str(filepath)
    is_category = '/category/' in str(filepath)
    
    # Add breadcrumb schema to all pages
    try:
        breadcrumb_schema = create_breadcrumb_schema(filepath)
        schemas.append(breadcrumb_schema)
    except:
        pass
    
    # Add review schema for tool reviews
    if is_tool_review:
        info = extract_tool_info(content)
        review_schema = create_review_schema(info)
        schemas.append(review_schema)
    
    # Add article schema for blog posts
    if is_blog:
        info = extract_tool_info(content)
        article_schema = create_article_schema(info, filepath)
        schemas.append(article_schema)
    
    # Add organization schema to homepage
    if filepath.name == 'index.html':
        org_schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "artificial.one",
            "url": "https://artificial.one",
            "logo": "https://artificial.one/artificial-one-logo-large.svg",
            "description": "Honest reviews of 220+ AI tools. Compare ChatGPT, Midjourney, Claude, and more."
        }
        schemas.append(org_schema)
    
    # Generate script tags
    script_tags = []
    for schema in schemas:
        script_content = json.dumps(schema, indent=2)
        script_tag = f'<script type="application/ld+json">\n{script_content}\n    </script>'
        script_tags.append(script_tag)
    
    if not script_tags:
        return content
    
    # Check if structured data already exists
    if '<script type="application/ld+json">' in content:
        # Replace existing or add additional
        # For simplicity, we'll add before closing </head>
        pass
    
    # Add before closing </head>
    all_scripts = '\n    '.join(script_tags)
    if '</head>' in content:
        content = content.replace('</head>', f'    {all_scripts}\n</head>')
    else:
        # Fallback: add before closing body
        content = content.replace('</body>', f'    {all_scripts}\n</body>')
    
    return content

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        updated_content = add_structured_data(content, filepath)
        
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
    print("Adding structured data...")
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            print(f"[OK] Added structured data to {filepath}")
    
    print(f"\nCompleted! Updated {updated_count} files with structured data.")
    print("\nNext steps:")
    print("1. Test structured data with Google Rich Results Test:")
    print("   https://search.google.com/test/rich-results")
    print("2. Submit updated sitemap to Google Search Console")

if __name__ == '__main__':
    main()
