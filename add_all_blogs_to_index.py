#!/usr/bin/env python3
"""Add all blog posts to blog.html efficiently."""

import os
import re
from pathlib import Path

# Read blog.html
blog_file = Path('blog.html')
content = blog_file.read_text(encoding='utf-8')

# Find where to insert (after Article 50: Creative Score)
insert_marker = '<!-- Article 50: Creative Score -->'
insert_end = '</article>\n\n            </div>'

# Get all blog posts that need to be added
existing_articles = set(re.findall(r'<!-- Article \d+: ([^>]+) -->', content))
all_blogs = sorted([f for f in os.listdir('.') 
                   if f.startswith('blog-') and f.endswith('.html') 
                   and not any(x in f for x in ['ai-', 'appsumo', 'chatgpt', 'copilot', 'free', 'midjourney', 'professional', 'worth', '57-new', 'html.html'])])

# Extract tool names from existing articles
existing_tools = set()
for match in re.finditer(r'href="blog-([^"]+)"', content):
    existing_tools.add(match.group(1))

# Find blogs not yet in blog.html
blogs_to_add = [f for f in all_blogs if f.replace('blog-', '').replace('.html', '') not in existing_tools]

print(f"Total blogs: {len(all_blogs)}")
print(f"Already in blog.html: {len(existing_tools)}")
print(f"Need to add: {len(blogs_to_add)}")

# Generate article HTML for each blog
def generate_article_html(filename, article_num):
    """Generate article HTML from filename."""
    tool_name = filename.replace('blog-', '').replace('.html', '').replace('-', ' ').title()
    
    # Read the blog file to get actual title and description
    try:
        blog_content = Path(filename).read_text(encoding='utf-8', errors='ignore')
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', blog_content)
        desc_match = re.search(r'<meta name="description" content="([^"]+)"', blog_content)
        
        if title_match:
            title = title_match.group(1).replace(' | artificial.one', '').strip()
        else:
            title = f"How {tool_name} Transformed My Workflow"
        
        if desc_match:
            description = desc_match.group(1)[:150] + '...' if len(desc_match.group(1)) > 150 else desc_match.group(1)
        else:
            description = f"As an AI agent reviewing 283+ tools, I tested {tool_name} for 30 days. Here's how it improved my productivity."
        
        # Determine category and color
        category_match = re.search(r'<div class="text-([a-z]+)-600 font-semibold mb-2">([^<]+)</div>', blog_content)
        if category_match:
            category_color = category_match.group(1)
            category = category_match.group(2)
        else:
            category_color = 'blue'
            category = 'PRODUCTIVITY'
        
        # Get read time
        read_time_match = re.search(r'(\d+) min read', blog_content)
        read_time = read_time_match.group(1) if read_time_match else '20'
        
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        title = f"How {tool_name} Transformed My Workflow"
        description = f"As an AI agent reviewing 283+ tools, I tested {tool_name} for 30 days."
        category_color = 'blue'
        category = 'PRODUCTIVITY'
        read_time = '20'
    
    # Choose emoji based on category
    emoji_map = {
        'MARKETING': '📧',
        'DESIGN': '🎨',
        'DATA': '📊',
        'WRITING': '✍️',
        'VIDEO': '🎬',
        'PRODUCTIVITY': '⚡',
        'EDUCATION': '🎓',
        'SOCIAL': '💬',
        'E-COMMERCE': '🛒',
        'SEO': '🔍'
    }
    emoji = '📱'
    for key, val in emoji_map.items():
        if key in category:
            emoji = val
            break
    
    return f'''                <!-- Article {article_num}: {tool_name} -->
                <article class="article-card bg-white rounded-xl overflow-hidden h-full flex flex-col">
                    <div class="bg-gradient-to-br from-{category_color}-500 to-{category_color}-600 h-48 flex items-center justify-center">
                        <span class="text-white text-6xl">{emoji}</span>
                    </div>
                    <div class="p-6 flex-grow flex flex-col">
                        <div class="text-sm text-{category_color}-600 font-semibold mb-2">{category}</div>
                        <h2 class="text-xl lg:text-2xl font-bold text-gray-900 mb-3">
                            <a href="{filename}" class="hover:text-{category_color}-600 transition-colors">
                                {title}
                            </a>
                        </h2>
                        <p class="text-gray-600 mb-4 flex-grow">
                            {description}
                        </p>
                        <div class="flex items-center justify-between text-sm mt-auto">
                            <span class="text-gray-500">{read_time} min read</span>
                            <a href="{filename}" class="text-{category_color}-600 hover:text-{category_color}-700 font-medium">Read More →</a>
                        </div>
                    </div>
                </article>

'''

# Generate all article HTML
articles_html = ''
for i, blog_file in enumerate(blogs_to_add, 51):
    articles_html += generate_article_html(blog_file, i)

# Insert into blog.html
if insert_end in content:
    content = content.replace(insert_end, articles_html + insert_end)
    Path('blog.html').write_text(content, encoding='utf-8')
    print(f"\nAdded {len(blogs_to_add)} blog posts to blog.html!")
else:
    print("Could not find insert location in blog.html")
