#!/usr/bin/env python3
"""
List all OG images that need to be created.
Generates a CSV file and organized list for image creation.
"""
import csv
from pathlib import Path
from collections import defaultdict

def get_og_image_path(filepath):
    """Get the OG image path for a file."""
    base_url = "https://artificial.one"
    path_str = str(filepath).replace('\\', '/')
    
    if filepath.name == 'index.html':
        return f'{base_url}/images/og-homepage.jpg', 'homepage'
    elif '/tools/' in path_str:
        tool_name = filepath.stem.replace('-review', '').replace('-', '')
        return f'{base_url}/images/og-tools/{tool_name}.jpg', 'tool'
    elif filepath.parent.name == 'tools':
        tool_name = filepath.stem.replace('-review', '').replace('-', '')
        return f'{base_url}/images/og-tools/{tool_name}.jpg', 'tool'
    elif '/category/' in path_str:
        category = filepath.stem.replace('-', '-')
        return f'{base_url}/images/og-categories/{category}.jpg', 'category'
    elif 'blog-' in filepath.name:
        blog_name = filepath.stem.replace('blog-', '').replace('-', '-')
        return f'{base_url}/images/og-blog/{blog_name}.jpg', 'blog'
    elif '/compare/' in path_str:
        return f'{base_url}/images/og-compare.jpg', 'compare'
    elif '/best/' in path_str:
        return f'{base_url}/images/og-best-of.jpg', 'best_of'
    elif '/guides/' in path_str:
        return f'{base_url}/images/og-guides.jpg', 'guide'
    else:
        return f'{base_url}/images/og-default.jpg', 'default'

def extract_page_info(content, filepath):
    """Extract info for image creation."""
    info = {}
    
    # Extract title
    import re
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if title_match:
        info['title'] = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    
    # Extract rating
    rating_match = re.search(r'(\d+\.?\d*)/10|(\d+\.?\d*)/5', content)
    if rating_match:
        rating = rating_match.group(1) or rating_match.group(2)
        info['rating'] = rating
    
    # Extract category
    cat_match = re.search(r'category["\']:\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
    if cat_match:
        info['category'] = cat_match.group(1)
    
    return info

def main():
    """Generate list of needed OG images."""
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
    print("Analyzing OG image requirements...\n")
    
    # Organize by type
    images_by_type = defaultdict(list)
    all_images = []
    
    for filepath in sorted(html_files):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            og_url, img_type = get_og_image_path(filepath)
            page_info = extract_page_info(content, filepath)
            
            image_data = {
                'file': str(filepath),
                'type': img_type,
                'url': og_url,
                'title': page_info.get('title', filepath.stem.replace('-', ' ').title()),
                'rating': page_info.get('rating', ''),
                'category': page_info.get('category', ''),
                'priority': 'high' if img_type in ['homepage', 'category', 'tool'] or '/tools/' in str(filepath) or filepath.parent.name == 'tools' else 'medium'
            }
            
            images_by_type[img_type].append(image_data)
            all_images.append(image_data)
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
    
    # Generate CSV
    csv_file = 'og_images_needed.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['priority', 'type', 'file', 'url', 'title', 'rating', 'category'])
        writer.writeheader()
        # Sort by priority
        sorted_images = sorted(all_images, key=lambda x: (x['priority'] == 'high', x['type'], x['title']))
        writer.writerows(sorted_images)
    
    print(f"Generated {csv_file} with {len(all_images)} images needed\n")
    
    # Print summary by type
    print("=" * 60)
    print("OG IMAGES SUMMARY BY TYPE")
    print("=" * 60)
    
    for img_type in sorted(images_by_type.keys()):
        count = len(images_by_type[img_type])
        print(f"\n{img_type.upper().replace('_', ' ')}: {count} images")
        
        # Show first 5 examples
        for img in images_by_type[img_type][:5]:
            print(f"  - {img['url'].split('/')[-1]}")
        if count > 5:
            print(f"  ... and {count - 5} more")
    
    # Priority breakdown
    print("\n" + "=" * 60)
    print("PRIORITY BREAKDOWN")
    print("=" * 60)
    
    high_priority = [img for img in all_images if img['priority'] == 'high']
    medium_priority = [img for img in all_images if img['priority'] == 'medium']
    
    print(f"\nHIGH PRIORITY: {len(high_priority)} images")
    print("  - Homepage")
    print("  - Category pages")
    print("  - Tool review pages")
    print(f"\nMEDIUM PRIORITY: {len(medium_priority)} images")
    print("  - Blog posts")
    print("  - Guide pages")
    print("  - Comparison pages")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("\n1. START WITH HIGH PRIORITY:")
    print(f"   - Create {len(high_priority)} images first")
    print("   - Focus on homepage + categories + top 20 tools")
    print("\n2. USE CANVA TEMPLATE:")
    print("   - Create one template (1200×630px)")
    print("   - Duplicate for each image")
    print("   - Update tool name, rating, category")
    print("\n3. TIME ESTIMATE:")
    print(f"   - High priority ({len(high_priority)} images): ~{len(high_priority) * 3} minutes")
    print(f"   - All images ({len(all_images)} images): ~{len(all_images) * 3} minutes ({len(all_images) * 3 / 60:.1f} hours)")
    print("\n4. BATCH CREATION:")
    print("   - Create 10-20 images per session")
    print("   - Spread over 2-4 weeks")
    print("   - Focus on pages getting traffic first")
    
    print(f"\n[OK] CSV file created: {csv_file}")
    print("   Open in Excel/Google Sheets to track progress!")

if __name__ == '__main__':
    main()
