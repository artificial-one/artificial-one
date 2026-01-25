#!/usr/bin/env python3
"""Add filter system to blog.html"""

import re
from pathlib import Path

# Category mapping
category_map = {
    'SEO & CONTENT': 'seo-content',
    'PRODUCTIVITY': 'productivity',
    'BUSINESS': 'business',
    'COMPARISON': 'comparison',
    'DESIGN': 'design',
    'VOICE & AUDIO': 'voice',
    'FREE TOOLS': 'free-tools',
    'VIDEO': 'video',
    'WORTH IT': 'worth-it',
    'CODING': 'coding',
    'DEALS': 'deals',
    'DATA': 'data',
    'MARKETING': 'marketing',
    'SAVINGS': 'savings',
    'WRITING & CONTENT': 'writing',
    'VIDEO & ANIMATION': 'video',
    'DESIGN & IMAGES': 'design',
    'PRODUCTIVITY & BUSINESS': 'productivity',
    'E-COMMERCE & SUPPORT': 'ecommerce',
    'SOCIAL MEDIA & MARKETING': 'marketing',
    'MARKETING & PRODUCTIVITY': 'marketing',
    'DESIGN & E-COMMERCE': 'design',
    'MARKETING & ANALYTICS': 'marketing',
    'SALES & MARKETING': 'marketing',
    'MARKETING & CONVERSION': 'marketing',
    'EDUCATION & BUSINESS': 'education',
    'DATA & ANALYTICS': 'data',
    'SEO & RESEARCH': 'seo-research',
    'MARKETING & COPYWRITING': 'marketing',
    'DESIGN & BUSINESS': 'design',
}

content = Path('blog.html').read_text(encoding='utf-8')

# Add data-category attributes to articles
def add_category_attributes(match):
    article = match.group(0)
    # Extract category from the article
    cat_match = re.search(r'<div class="text-sm text-[a-z]+-600 font-semibold mb-2">([^<]+)</div>', article)
    if cat_match:
        category = cat_match.group(1)
        slug = category_map.get(category, category.lower().replace(' ', '-').replace('&', '').replace(' ', ''))
        # Add data-category attribute to article tag
        article = re.sub(r'(<article class="article-card)', f'\\1 data-category="{slug}"', article)
    return article

# Find all articles and add data-category
content = re.sub(r'<article class="article-card[^>]*>.*?</article>', add_category_attributes, content, flags=re.DOTALL)

# Add filter section before the blog grid
filter_section = '''    <!-- Filter Section -->
    <section class="py-6 sm:py-8 bg-white border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 xl:px-12">
            <div>
                <h3 class="text-sm font-semibold text-gray-700 mb-3">Filter by Category:</h3>
                <div class="flex flex-wrap gap-2 sm:gap-3">
                    <button onclick="filterByCategory('all')" class="cat-btn active px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">All</button>
                    <button onclick="filterByCategory('productivity')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">📊 Productivity</button>
                    <button onclick="filterByCategory('marketing')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">📱 Marketing</button>
                    <button onclick="filterByCategory('writing')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">✍️ Writing</button>
                    <button onclick="filterByCategory('design')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">🎨 Design</button>
                    <button onclick="filterByCategory('video')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">🎬 Video</button>
                    <button onclick="filterByCategory('coding')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">💻 Coding</button>
                    <button onclick="filterByCategory('data')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">📈 Data</button>
                    <button onclick="filterByCategory('voice')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">🎙️ Voice</button>
                    <button onclick="filterByCategory('seo-content')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">🔍 SEO</button>
                    <button onclick="filterByCategory('education')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">🎓 Education</button>
                    <button onclick="filterByCategory('ecommerce')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">🛒 E-commerce</button>
                    <button onclick="filterByCategory('deals')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">💰 Deals</button>
                    <button onclick="filterByCategory('comparison')" class="cat-btn px-3 sm:px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:border-blue-600 text-sm sm:text-base whitespace-nowrap">⚖️ Comparison</button>
                </div>
            </div>
        </div>
    </section>

'''

# Insert filter section before blog grid
content = content.replace('    <!-- Blog Grid -->', filter_section + '    <!-- Blog Grid -->')

# Add CSS for filter buttons
css_addition = '''        .cat-btn { transition: all 0.2s ease; }
        .cat-btn.active { background: #2563eb; color: white; border-color: #2563eb; }
'''
content = content.replace('        .cursor-pointer { cursor: pointer; }', css_addition + '        .cursor-pointer { cursor: pointer; }')

# Add JavaScript for filtering
js_code = '''
<script>
let currentCategoryFilter = 'all';

function filterByCategory(category) {
    currentCategoryFilter = category;
    document.querySelectorAll('.cat-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    const articles = document.querySelectorAll('.article-card');
    let visibleCount = 0;
    
    articles.forEach(article => {
        const articleCategory = article.getAttribute('data-category');
        if (category === 'all' || articleCategory === category) {
            article.style.display = '';
            visibleCount++;
        } else {
            article.style.display = 'none';
        }
    });
    
    updateCounts();
}

function updateCounts() {
    const articles = document.querySelectorAll('.article-card');
    const categoryCounts = {};
    
    articles.forEach(article => {
        const cat = article.getAttribute('data-category') || 'other';
        categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
    });
    
    // Update button labels with counts
    document.querySelectorAll('.cat-btn').forEach(btn => {
        const onclick = btn.getAttribute('onclick');
        const match = onclick.match(/filterByCategory\('([^']+)'\)/);
        if (match) {
            const cat = match[1];
            const text = btn.textContent.split('(')[0].trim();
            if (cat === 'all') {
                btn.textContent = `${text} (${articles.length})`;
            } else {
                const count = categoryCounts[cat] || 0;
                btn.textContent = `${text} (${count})`;
            }
        }
    });
}

window.addEventListener('DOMContentLoaded', function() {
    updateCounts();
});
</script>
'''

# Insert JavaScript before closing body tag
content = content.replace('</body>', js_code + '</body>')

Path('blog.html').write_text(content, encoding='utf-8')
print("Filter system added to blog.html!")
