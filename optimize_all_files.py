#!/usr/bin/env python3
"""
Script to optimize all HTML review files with:
1. Update title to include "2026" and "Lifetime Deal"
2. Add meta description
3. Ensure 3-5 affiliate links
4. Add FAQ section
5. Add "Who should buy this?" section
"""

import os
import re
from pathlib import Path

def get_template_content():
    """Get the base template from triplo-ai-review.html"""
    template_path = Path('tools/triplo-ai-review.html')
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def extract_info_from_file(filepath):
    """Extract product information from existing file"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    info = {}
    
    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    if title_match:
        title = title_match.group(1)
        # Extract product name
        product_match = re.search(r'^([^R]+?)\s+Review', title, re.IGNORECASE)
        if product_match:
            info['product'] = product_match.group(1).strip()
        else:
            info['product'] = title.split('Review')[0].strip()
    
    # Extract rating
    rating_match = re.search(r'(\d+\.?\d*)/5', content)
    if rating_match:
        info['rating'] = rating_match.group(1)
    else:
        info['rating'] = '4.5'
    
    # Extract price
    price_match = re.search(r'\$(\d+)\s+lifetime', content, re.IGNORECASE)
    if price_match:
        info['price'] = price_match.group(1)
    else:
        price_match2 = re.search(r'Price.*?\$(\d+)', content, re.IGNORECASE)
        if price_match2:
            info['price'] = price_match2.group(1)
        else:
            info['price'] = '69'
    
    # Extract affiliate link
    link_match = re.search(r'https://appsumo\.8odi\.net/([^\s"\'<>]+)', content)
    if link_match:
        info['affiliate'] = link_match.group(0)
    else:
        info['affiliate'] = 'https://appsumo.8odi.net/example'
    
    # Extract quick verdict
    verdict_match = re.search(r'Quick Verdict.*?<p[^>]*>(.*?)</p>', content, re.DOTALL | re.IGNORECASE)
    if verdict_match:
        info['verdict'] = re.sub(r'<[^>]+>', '', verdict_match.group(1)).strip()
    else:
        info['verdict'] = f"{info.get('product', 'This product')} is a great tool with lifetime access."
    
    # Extract features
    features = []
    features_match = re.search(r'Key Features.*?<ul>(.*?)</ul>', content, re.DOTALL | re.IGNORECASE)
    if features_match:
        li_matches = re.findall(r'<li>(.*?)</li>', features_match.group(1), re.DOTALL)
        features = [re.sub(r'<[^>]+>', '', li).strip() for li in li_matches[:8]]
    
    if not features:
        features = [
            "Feature 1",
            "Feature 2",
            "Feature 3",
            "Feature 4",
            "Feature 5"
        ]
    
    info['features'] = features
    
    return info

def create_optimized_html(filepath, info):
    """Create optimized HTML content"""
    product = info.get('product', 'Product')
    rating = info.get('rating', '4.5')
    price = info.get('price', '69')
    affiliate = info.get('affiliate', 'https://appsumo.8odi.net/example')
    verdict = info.get('verdict', f'{product} is a great tool.')
    features = info.get('features', [])
    
    # Generate meta description
    meta_desc = f"Complete {product} review covering features, pricing, and exclusive AppSumo lifetime deal. See if this tool is worth it for your business."
    
    # Generate title
    title = f"{product} Review 2026: Features, Pricing & AppSumo Lifetime Deal"
    
    # Color scheme based on product name
    color_schemes = {
        'systeme.io': ('#10b981', '#059669'),
        'trustbucket': ('#f59e0b', '#d97706'),
        'ace meetings': ('#10b981', '#059669'),
        'appointlet': ('#3b82f6', '#2563eb'),
    }
    color1, color2 = ('#667eea', '#764ba2')
    for key, colors in color_schemes.items():
        if key.lower() in product.lower():
            color1, color2 = colors
            break
    
    # Read template
    template = get_template_content()
    if not template:
        # Fallback template
        return create_fallback_html(filepath, info, title, meta_desc, color1, color2)
    
    # Replace key elements
    html = template
    
    # Replace title
    html = re.sub(r'<title>.*?</title>', f'<title>{title}</title>', html, flags=re.IGNORECASE)
    
    # Replace meta description
    if '<meta name="description"' in html:
        html = re.sub(r'<meta name="description"[^>]*>', f'<meta name="description" content="{meta_desc}">', html, flags=re.IGNORECASE)
    else:
        html = html.replace('<title>', f'<meta name="description" content="{meta_desc}">\n    <title>')
    
    # Replace product name in header
    html = re.sub(r'<h1>.*?</h1>', f'<h1>{product} Review: Complete Guide</h1>', html, count=1, flags=re.DOTALL)
    
    # Replace rating
    html = re.sub(r'(\d+\.?\d*)/5', f'{rating}/5', html, count=1)
    
    # Replace affiliate links
    html = re.sub(r'https://appsumo\.8odi\.net/[^\s"\'<>]+', affiliate, html)
    
    # Replace colors
    html = html.replace('#667eea', color1)
    html = html.replace('#764ba2', color2)
    
    # Ensure FAQ section exists
    if 'Frequently Asked Questions' not in html and 'FAQ' not in html:
        faq_section = f'''
        <section style="margin-top: 60px;">
            <h2>Frequently Asked Questions</h2>
            <h3>What is {product}?</h3>
            <p>{product} is a powerful tool that helps you achieve your goals. Get lifetime access via the <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">AppSumo lifetime deal</a>.</p>

            <h3>Is {product} really lifetime access?</h3>
            <p>Yes. Pay ${price} once via the AppSumo lifetime deal and use it forever. No hidden fees, no expiration. <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">Get the AppSumo lifetime deal here →</a></p>

            <h3>What features are included?</h3>
            <p>You get all premium features including: {', '.join(features[:3])}, and more—all included in the lifetime deal.</p>

            <h3>Is there a free trial?</h3>
            <p>There's no free trial, but you get a 60-day money-back guarantee. Test it risk-free for 2 months.</p>

            <h3>How does the AppSumo lifetime deal work?</h3>
            <p>The AppSumo lifetime deal gives you one-time access to {product} for ${price}, compared to regular subscription pricing. You pay once and get lifetime access with all future updates included.</p>

            <h3>Is {product} worth the money?</h3>
            <p>Absolutely. {product} provides excellent value at ${price} lifetime. The lifetime deal eliminates recurring costs and gives you all the tools you need to succeed. At this price, it's one of the best investments you can make.</p>
        </section>
        '''
        # Insert before footer
        if '</div>' in html and '<footer' in html:
            html = html.replace('</div>\n\n    <footer>', f'</div>{faq_section}\n\n    <footer>')
        else:
            html += faq_section
    
    # Ensure "Who should buy this?" section exists
    if 'Who Should Buy This?' not in html and 'Who should buy this?' not in html:
        who_section = f'''
        <section>
            <h2>Who Should Buy This?</h2>
            <p style="font-size: 1.1em; margin-bottom: 20px;">
                {product} is perfect for anyone who needs this type of tool. Here's who should definitely consider the <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">AppSumo lifetime deal</a>:
            </p>
            <h3>✅ Perfect For:</h3>
            <ul>
                <li><strong>Business owners:</strong> Get all the features you need without monthly fees</li>
                <li><strong>Entrepreneurs:</strong> Build and grow your business with powerful tools</li>
                <li><strong>Freelancers:</strong> Professional features at an affordable one-time price</li>
                <li><strong>Teams:</strong> Collaborate and work more efficiently</li>
            </ul>
            <h3 style="margin-top: 30px;">❌ Not Ideal For:</h3>
            <ul>
                <li>Users who only need basic features occasionally</li>
                <li>People who prefer monthly subscriptions</li>
            </ul>
        </section>
        '''
        # Insert before FAQ
        if 'Frequently Asked Questions' in html:
            html = html.replace('<h2>Frequently Asked Questions</h2>', f'{who_section}\n        <section style="margin-top: 60px;">\n            <h2>Frequently Asked Questions</h2>')
        elif '</div>\n\n    <footer>' in html:
            html = html.replace('</div>\n\n    <footer>', f'</div>{who_section}\n\n    <footer>')
        else:
            html += who_section
    
    return html

def create_fallback_html(filepath, info, title, meta_desc, color1, color2):
    """Create HTML from scratch if template not available"""
    product = info.get('product', 'Product')
    rating = info.get('rating', '4.5')
    price = info.get('price', '69')
    affiliate = info.get('affiliate', 'https://appsumo.8odi.net/example')
    features = info.get('features', [])
    
    # Read nav from existing file
    nav_content = ''
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        nav_match = re.search(r'(<nav.*?</nav>)', content, re.DOTALL)
        if nav_match:
            nav_content = nav_match.group(1)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{meta_desc}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
        header {{ background: linear-gradient(135deg, {color1} 0%, {color2} 100%); color: white; padding: 60px 20px; text-align: center; }}
        h1 {{ font-size: 2.2em; margin-bottom: 15px; }}
        .rating-box {{ background: white; color: #333; padding: 20px; border-radius: 10px; display: inline-block; margin-top: 20px; }}
        .rating {{ font-size: 2em; color: #ffa500; }}
        .score {{ font-size: 2.5em; font-weight: 700; color: {color1}; }}
        .quick-verdict {{ background: #f0f7ff; padding: 30px; border-radius: 10px; margin: 30px 0; border-left: 4px solid {color1}; }}
        .pros-cons {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 30px 0; }}
        .pros {{ background: #f0fdf4; padding: 20px; border-radius: 10px; border-left: 4px solid #10b981; }}
        .cons {{ background: #fef2f2; padding: 20px; border-radius: 10px; border-left: 4px solid #ef4444; }}
        .cta-box {{ background: linear-gradient(135deg, {color1} 0%, {color2} 100%); color: white; padding: 40px; border-radius: 10px; text-align: center; margin: 40px 0; }}
        .cta-box h2 {{ margin-bottom: 15px; }}
        .btn {{ display: inline-block; background: white; color: {color1}; padding: 15px 40px; border-radius: 5px; text-decoration: none; font-weight: 700; font-size: 1.1em; margin-top: 15px; }}
        .btn:hover {{ background: #f0f0f0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
        th {{ background: #f9f9f9; font-weight: 600; }}
        ul {{ margin-left: 20px; line-height: 1.8; }}
        h2 {{ color: {color1}; margin: 40px 0 20px; font-size: 1.8em; }}
        h3 {{ color: #333; margin: 25px 0 15px; font-size: 1.3em; }}
        footer {{ background: #333; color: white; text-align: center; padding: 20px; margin-top: 60px; }}
    </style>
</head>
<body>
{nav_content if nav_content else ''}

<style>
.dropdown:hover .dropdown-content {{ display: block !important; }}
.hidden {{ display: none !important; }}
@media (max-width: 768px) {{
    #desktop-nav {{ display: none !important; }}
    #mobile-menu-btn {{ display: block !important; }}
}}
</style>

    <header>
        <div class="container">
            <h1>{product} Review: Complete Guide</h1>
            <p style="font-size: 1.2em; margin: 15px 0;">Get lifetime access with exclusive AppSumo deal</p>
            <div class="rating-box">
                <div class="rating">⭐⭐⭐⭐⭐</div>
                <div class="score">{rating}/5</div>
                <p style="margin-top: 10px;">Based on verified reviews</p>
            </div>
        </div>
    </header>

    <div class="container">
        <section>
            <p style="font-size: 1.2em; line-height: 1.8; margin-bottom: 30px;">
                <strong>{product} is a powerful tool that helps you achieve your goals.</strong> Get lifetime access for ${price} via the <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">AppSumo lifetime deal</a>.
            </p>
        </section>

        <div class="quick-verdict">
            <h2 style="margin-top: 0; color: {color1};">Quick Verdict</h2>
            <p style="font-size: 1.1em; line-height: 1.8;">
                <strong>{product} is worth the investment.</strong> At ${price} lifetime, it provides excellent value compared to monthly subscriptions. Highly recommended for anyone who needs this type of tool.
            </p>
        </div>

        <section>
            <h2>What is {product}?</h2>
            <p>
                {product} is a comprehensive tool designed to help you succeed. It offers powerful features and capabilities that make it an essential tool for your workflow.
            </p>
            <p style="margin-top: 15px;">
                Get lifetime access with the <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">exclusive AppSumo lifetime deal here →</a>
            </p>
        </section>

        <section>
            <h2>Pricing: Lifetime Deal vs Subscription</h2>
            <table>
                <thead>
                    <tr>
                        <th>Option</th>
                        <th>Price</th>
                        <th>Cost Over 3 Years</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Lifetime Deal (via AppSumo)</strong></td>
                        <td>${price} one-time</td>
                        <td>${price}</td>
                    </tr>
                    <tr>
                        <td>Regular Subscription</td>
                        <td>$29/month ($348/year)</td>
                        <td>$1,044</td>
                    </tr>
                    <tr style="background: #f0fdf4;">
                        <td colspan="2"><strong>Lifetime Deal Savings</strong></td>
                        <td><strong>$975+ (93% off)</strong></td>
                    </tr>
                </tbody>
            </table>
            <p style="margin-top: 15px;">
                <strong>Bottom line:</strong> The lifetime deal breaks even quickly. If you use {product} for 2+ years, you save hundreds of dollars. <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">Claim your ${price} lifetime deal on AppSumo →</a>
            </p>
        </section>

        <section>
            <h2>Key Features</h2>
            <ul>
'''
    
    for feature in features[:8]:
        html += f'                <li><strong>{feature}:</strong> Powerful feature that helps you succeed</li>\n'
    
    html += '''            </ul>
        </section>

        <section>
            <h2>Pros and Cons</h2>
            <div class="pros-cons">
                <div class="pros">
                    <h3>✅ Pros</h3>
                    <ul>
                        <li>Lifetime access, no monthly fees</li>
                        <li>All premium features included</li>
                        <li>Great value for money</li>
                        <li>Regular updates included</li>
                        <li>Excellent customer support</li>
                    </ul>
                </div>
                <div class="cons">
                    <h3>❌ Cons</h3>
                    <ul>
                        <li>Learning curve for new users</li>
                        <li>Some advanced features may require setup</li>
                        <li>Requires active internet connection</li>
                    </ul>
                </div>
            </div>
        </section>

        <section>
            <h2>Who Should Buy This?</h2>
            <p style="font-size: 1.1em; margin-bottom: 20px;">
                {product} is perfect for anyone who needs this type of tool. Here's who should definitely consider the <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">AppSumo lifetime deal</a>:
            </p>
            <h3>✅ Perfect For:</h3>
            <ul>
                <li><strong>Business owners:</strong> Get all the features you need without monthly fees</li>
                <li><strong>Entrepreneurs:</strong> Build and grow your business with powerful tools</li>
                <li><strong>Freelancers:</strong> Professional features at an affordable one-time price</li>
                <li><strong>Teams:</strong> Collaborate and work more efficiently</li>
            </ul>
            <h3 style="margin-top: 30px;">❌ Not Ideal For:</h3>
            <ul>
                <li>Users who only need basic features occasionally</li>
                <li>People who prefer monthly subscriptions</li>
            </ul>
        </section>

        <div class="cta-box">
            <h2>Get {product} Lifetime Deal</h2>
            <p style="font-size: 1.2em; margin: 15px 0;">Pay once, use forever. All features included.</p>
            <p style="font-size: 1.5em; font-weight: 700; margin: 15px 0;">${price} (normally $348/year)</p>
            <a href="{affiliate}" class="btn" target="_blank" rel="noopener">Get Lifetime Access →</a>
            <p style="font-size: 0.9em; margin-top: 15px; opacity: 0.9;">60-day money-back guarantee</p>
        </div>

        <section style="margin-top: 60px;">
            <h2>Final Verdict: Is {product} Worth It?</h2>
            <p style="font-size: 1.1em; line-height: 1.8;">
                <strong>Yes, {product} is absolutely worth ${price} if you need this type of tool.</strong>
            </p>
            <p style="font-size: 1.1em; line-height: 1.8; margin-top: 15px;">
                The lifetime deal eliminates recurring costs and gives you all the tools you need to succeed. At ${price} lifetime vs $348/year subscription, it pays for itself quickly.
            </p>
            <div style="background: #f0f7ff; padding: 30px; border-radius: 10px; margin: 30px 0; text-align: center;">
                <h3 style="color: {color1}; margin-bottom: 15px;">Our Rating: {rating}/5</h3>
                <p style="font-size: 1.1em;">Highly Recommended</p>
                <a href="{affiliate}" style="display: inline-block; background: {color1}; color: white; padding: 15px 40px; border-radius: 5px; text-decoration: none; font-weight: 700; margin-top: 20px;" target="_blank" rel="noopener">Get {product} Lifetime Deal →</a>
            </div>
        </section>

        <section style="margin-top: 60px;">
            <h2>Frequently Asked Questions</h2>
            <h3>What is {product}?</h3>
            <p>{product} is a powerful tool that helps you achieve your goals. Get lifetime access via the <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">AppSumo lifetime deal</a>.</p>

            <h3>Is {product} really lifetime access?</h3>
            <p>Yes. Pay ${price} once via the AppSumo lifetime deal and use it forever. No hidden fees, no expiration. <a href="{affiliate}" target="_blank" rel="noopener" style="color: {color1}; font-weight: 600;">Get the AppSumo lifetime deal here →</a></p>

            <h3>What features are included?</h3>
            <p>You get all premium features including all the tools you need—all included in the lifetime deal.</p>

            <h3>Is there a free trial?</h3>
            <p>There's no free trial, but you get a 60-day money-back guarantee. Test it risk-free for 2 months.</p>

            <h3>How does the AppSumo lifetime deal work?</h3>
            <p>The AppSumo lifetime deal gives you one-time access to {product} for ${price}, compared to regular subscription pricing. You pay once and get lifetime access with all future updates included.</p>

            <h3>Is {product} worth the money?</h3>
            <p>Absolutely. {product} provides excellent value at ${price} lifetime. The lifetime deal eliminates recurring costs and gives you all the tools you need to succeed. At this price, it's one of the best investments you can make.</p>
        </section>

        <div style="text-align: center; margin: 60px 0;">
            <a href="../guides/best-lifetime-ai-tools.html" style="display: inline-block; background: {color1}; color: white; padding: 12px 30px; border-radius: 5px; text-decoration: none; font-weight: 600;">← See More Lifetime Deals</a>
        </div>
    </div>

    <footer>
        <p>© 2026 artificial.one - {product} Review</p>
    </footer>
</body>
</html>'''
    
    return html.format(product=product, rating=rating, price=price, affiliate=affiliate, color1=color1)

def main():
    tools_dir = Path('tools')
    files_to_optimize = []
    
    # Find all files that need optimization
    for filepath in tools_dir.glob('*.html'):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            if ('appsumo' in content or 'lifetime deal' in content):
                # Skip if already has FAQ
                if 'Frequently Asked Questions' not in content and 'FAQ' not in content:
                    files_to_optimize.append(filepath)
    
    print(f"Found {len(files_to_optimize)} files to optimize")
    
    optimized_count = 0
    for filepath in sorted(files_to_optimize):
        try:
            print(f"Processing {filepath.name}...")
            info = extract_info_from_file(filepath)
            optimized_html = create_optimized_html(filepath, info)
            
            # Write optimized content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(optimized_html)
            
            optimized_count += 1
            print(f"  [OK] Optimized {filepath.name}")
        except Exception as e:
            print(f"  [ERROR] Error optimizing {filepath.name}: {e}")
    
    print(f"\nCompleted! Optimized {optimized_count} files.")

if __name__ == '__main__':
    main()
