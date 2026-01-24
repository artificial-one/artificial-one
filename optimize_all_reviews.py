#!/usr/bin/env python3
import os
import re
from pathlib import Path

def get_nav_template():
    return '''<nav style="background: white; border-bottom: 1px solid #e5e7eb; position: sticky; top: 0; z-index: 50;">
    <div style="max-width: 1200px; margin: 0 auto; padding: 0 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; height: 80px;">
            <a href="../index.html"><img src="../artificial-one-logo-large.svg" alt="artificial.one" style="height: 80px;"></a>
            
            <button id="mobile-menu-btn" style="display: none; background: none; border: none; cursor: pointer;" onclick="document.getElementById('mobile-menu').classList.toggle('hidden')">
                <svg style="width: 24px; height: 24px;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </button>
            
            <div id="desktop-nav" style="display: flex; gap: 24px; align-items: center; font-size: 15px;">
                <a href="../reviews.html" style="color: #4b5563; text-decoration: none; font-weight: 500;">Reviews</a>
                
                <div class="dropdown" style="position: relative;">
                    <span style="color: #4b5563; cursor: pointer; font-weight: 500;">Categories ▾</span>
                    <div class="dropdown-content" style="display: none; position: absolute; background: white; min-width: 240px; box-shadow: 0 8px 16px rgba(0,0,0,0.15); border-radius: 8px; top: calc(100% + 5px); left: -15px; padding: 12px 0;">
                        <a href="../category/writing-content.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">✍️ Writing & Content</a>
                        <a href="../category/design-images.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">🎨 Design & Images</a>
                        <a href="../category/video-animation.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">🎬 Video & Animation</a>
                        <a href="../category/coding-development.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">💻 Coding & Development</a>
                        <a href="../category/productivity-business.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">📊 Productivity & Business</a>
                    </div>
                </div>
                
                <div class="dropdown" style="position: relative;">
                    <span style="color: #4b5563; cursor: pointer; font-weight: 500;">💰 Lifetime Deals ▾</span>
                    <div class="dropdown-content" style="display: none; position: absolute; background: white; min-width: 240px; box-shadow: 0 8px 16px rgba(0,0,0,0.15); border-radius: 8px; top: calc(100% + 5px); left: -15px; padding: 12px 0;">
                        <a href="../guides/best-lifetime-deal-software-2026.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">🎯 Browse All Deals</a>
                        <a href="../guides/use-case-startups.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">🚀 Best for Startups</a>
                        <a href="../guides/use-case-freelancers.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">💼 Best for Freelancers</a>
                        <a href="../guides/best-lifetime-ai-tools.html" style="display: block; padding: 14px 20px; color: #4b5563; text-decoration: none;">🤖 AI Tools</a>
                    </div>
                </div>
                
                <a href="../blog.html" style="color: #4b5563; text-decoration: none; font-weight: 500;">Blog</a>
                <a href="../about.html" style="color: #4b5563; text-decoration: none; font-weight: 500;">About</a>
                <a href="../index.html" style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 10px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">Home</a>
            </div>
        </div>
        
        <div id="mobile-menu" class="hidden" style="display: none; padding-bottom: 16px; border-top: 1px solid #e5e7eb; margin-top: 16px;">
            <div style="display: flex; flex-direction: column; gap: 12px;">
                <a href="../index.html" style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; text-align: center;">Home</a>
                <a href="../reviews.html" style="background: linear-gradient(135deg, #8b5cf6, #a855f7); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; text-align: center;">Reviews</a>
                <a href="../guides/best-lifetime-deal-software-2026.html" style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; text-align: center;">💰 Lifetime Deals</a>
                <a href="../blog.html" style="background: linear-gradient(135deg, #f59e0b, #d97706); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; text-align: center;">Blog</a>
                <a href="../about.html" style="background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; text-align: center;">About</a>
            </div>
        </div>
    </div>
</nav>

<style>
.dropdown:hover .dropdown-content { display: block !important; }
.hidden { display: none !important; }
@media (max-width: 768px) {
    #desktop-nav { display: none !important; }
    #mobile-menu-btn { display: block !important; }
}
</style>'''

def extract_info(content):
    info = {}
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    if title_match:
        title = title_match.group(1)
        product_match = re.search(r'^([^R]+?)\s+Review', title, re.IGNORECASE)
        if product_match:
            info['product'] = product_match.group(1).strip()
        else:
            info['product'] = title.split('Review')[0].strip()
    
    rating_match = re.search(r'(\d+\.?\d*)/5', content)
    if rating_match:
        info['rating'] = rating_match.group(1)
    
    price_match = re.search(r'\$(\d+)\s+lifetime', content, re.IGNORECASE)
    if price_match:
        info['price'] = price_match.group(1)
    
    link_match = re.search(r'https://appsumo\.8odi\.net/([^\s"\'<>]+)', content)
    if link_match:
        info['affiliate'] = link_match.group(0)
    
    verdict_match = re.search(r'Quick Verdict.*?<p[^>]*>(.*?)</p>', content, re.DOTALL | re.IGNORECASE)
    if verdict_match:
        info['verdict'] = re.sub(r'<[^>]+>', '', verdict_match.group(1)).strip()
    
    features_match = re.search(r'Key Features.*?<ul>(.*?)</ul>', content, re.DOTALL | re.IGNORECASE)
    if features_match:
        info['features'] = features_match.group(1)
    
    return info

def get_color_scheme(product_name):
    schemes = {
        'systeme.io': ('#10b981', '#059669'),
        'trustbucket': ('#f59e0b', '#d97706'),
        'ace meetings': ('#10b981', '#059669'),
        'appointlet': ('#3b82f6', '#2563eb'),
    }
    for key, colors in schemes.items():
        if key in product_name.lower():
            return colors
    return ('#667eea', '#764ba2')

tools_dir = Path('tools')
files_to_optimize = []
for filepath in tools_dir.glob('*.html'):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read().lower()
        if ('appsumo' in content or 'lifetime deal' in content) and 'Frequently Asked Questions' not in content:
            files_to_optimize.append(filepath)

print(f"Found {len(files_to_optimize)} files to optimize")
for f in sorted(files_to_optimize)[:10]:
    print(f"  {f.name}")
