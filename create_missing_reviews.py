import re
import os
from pathlib import Path

# Read reviews.html to extract all tool names
with open('reviews.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract tools array
tools_pattern = r'const tools = \[([\s\S]*?)\];'
match = re.search(tools_pattern, content)
if not match:
    print("Could not find tools array!")
    exit(1)

tools_array_content = match.group(1)

# Extract tool data - find all tool objects
tool_data = []
# Split by lines and extract tool objects
tool_objects = re.findall(r'\{[^}]*name:\s*"([^"]+)"[^}]*\}', tools_array_content)

for tool_obj_match in tool_objects:
    tool_name = tool_obj_match
    # Find the full object for this tool
    pattern = r'\{[^}]*name:\s*"' + re.escape(tool_name) + r'"[^}]*\}'
    full_obj_match = re.search(pattern, tools_array_content)
    if full_obj_match:
        obj_str = full_obj_match.group(0)
        tool_info = {'name': tool_name}
        # Extract link
        link_match = re.search(r'link:\s*"([^"]+)"', obj_str)
        if link_match:
            tool_info['link'] = link_match.group(1)
        # Extract rating
        rating_match = re.search(r'rating:\s*"([^"]+)"', obj_str)
        if rating_match:
            tool_info['rating'] = rating_match.group(1)
        tool_data.append(tool_info)

print(f"Found {len(tool_data)} tools")

# Function to convert tool name to review URL slug
def name_to_slug(name):
    """Convert tool name to review page slug"""
    slug = name.lower()
    # Remove special characters except spaces and hyphens
    slug = re.sub(r'[^\w\s-]', '', slug)
    # Replace spaces and multiple hyphens with single hyphen
    slug = re.sub(r'[\s_-]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug

# Check which review pages exist
tools_dir = Path('tools')
existing_reviews = set()
if tools_dir.exists():
    for file in tools_dir.glob('*-review.html'):
        slug = file.stem.replace('-review', '')
        existing_reviews.add(slug)

print(f"Found {len(existing_reviews)} existing review pages")

# Find missing reviews
missing_reviews = []
for tool in tool_data:
    tool_name = tool['name']
    slug = name_to_slug(tool_name)
    review_file = tools_dir / f"{slug}-review.html"
    if not review_file.exists():
        missing_reviews.append({
            'name': tool_name,
            'slug': slug,
            'file': review_file,
            'link': tool.get('link', ''),
            'rating': tool.get('rating', '4.5')
        })

print(f"\nFound {len(missing_reviews)} missing review pages")

# Read template
template_file = Path('tools/formrobin-review.html')
if not template_file.exists():
    print(f"Template file {template_file} not found!")
    exit(1)

with open(template_file, 'r', encoding='utf-8') as f:
    template = f.read()

# Create missing review pages
created_count = 0
for tool in missing_reviews:
    tool_name = tool['name']
    slug = tool['slug']
    review_file = tool['file']
    affiliate_link = tool['link']
    rating = tool['rating']
    
    print(f"Creating review for: {tool_name} -> {slug}-review.html")
    
    # Create review content from template
    review_content = template
    
    # Replace title
    review_content = re.sub(
        r'<title>.*?</title>',
        f'<title>{tool_name} Review 2026: Features, Pricing & AppSumo Deal | artificial.one</title>',
        review_content
    )
    
    # Replace meta description
    review_content = re.sub(
        r'<meta name="description" content="[^"]*"',
        f'<meta name="description" content="Complete {tool_name} review covering features, pricing, and exclusive AppSumo lifetime deal."',
        review_content
    )
    
    # Replace h1 in header
    review_content = re.sub(
        r'<h1>[^<]*</h1>',
        f'<h1>{tool_name} Review: Complete Guide</h1>',
        review_content,
        count=1
    )
    
    # Replace description paragraph
    review_content = re.sub(
        r'<p style="font-size: 1\.2em; margin: 15px 0;">[^<]*</p>',
        f'<p style="font-size: 1.2em; margin: 15px 0;">AI-powered tool that helps professionals and businesses achieve their goals efficiently</p>',
        review_content,
        count=1
    )
    
    # Replace rating score
    review_content = re.sub(
        r'<div class="score">[^<]*</div>',
        f'<div class="score">{rating}/5</div>',
        review_content
    )
    
    # Replace affiliate links
    if affiliate_link:
        review_content = re.sub(
            r'https://appsumo\.8odi\.net/[^\s"\'<>]+',
            affiliate_link,
            review_content
        )
    
    # Write the file
    with open(review_file, 'w', encoding='utf-8') as f:
        f.write(review_content)
    
    created_count += 1
    print(f"  Created {review_file}")

print(f"\nCreated {created_count} review pages out of {len(missing_reviews)} missing reviews")
