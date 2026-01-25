#!/usr/bin/env python3
"""
Add or improve Related Tools sections to review pages.
"""
import re
from pathlib import Path

# Mapping of tools to their related tools and categories
RELATED_TOOLS_MAP = {
    'triplo-ai': {
        'similar': [('cursor-review.html', 'Cursor - AI-powered code editor'), ('neuronwriter-review.html', 'NeuronWriter - SEO writing tool')],
        'lifetime': [('tidycal-review.html', 'TidyCal - Calendar scheduling ($29 lifetime)'), ('writesonic-review.html', 'Writesonic - AI writer')],
        'category': 'productivity-business',
        'comparison': 'triplo-ai-vs-cursor.html'
    },
    'neuronwriter': {
        'similar': [('frase-review.html', 'Frase - AI content research'), ('../compare/comparison-neuronwriter-vs-surfer.html', 'Surfer SEO - SEO optimization')],
        'lifetime': [('triplo-ai-review.html', 'Triplo AI - Universal AI assistant ($69 lifetime)'), ('tidycal-review.html', 'TidyCal - Calendar scheduling ($29 lifetime)')],
        'category': 'writing-content',
        'comparison': 'neuronwriter-vs-jasper.html'
    },
    'tidycal': {
        'similar': [('../compare/comparison-tidycal-vs-calendly.html', 'Calendly - Popular scheduling tool'), ('ace-meetings-review.html', 'Ace Meetings - Meeting scheduling')],
        'lifetime': [('triplo-ai-review.html', 'Triplo AI - Universal AI assistant ($69 lifetime)'), ('neuronwriter-review.html', 'NeuronWriter - SEO writing ($89 lifetime)')],
        'category': 'productivity-business',
        'comparison': 'comparison-tidycal-vs-calendly.html'
    },
    'frase': {
        'similar': [('neuronwriter-review.html', 'NeuronWriter - SEO writing tool'), ('../compare/comparison-neuronwriter-vs-surfer.html', 'Surfer SEO - SEO optimization')],
        'lifetime': [('triplo-ai-review.html', 'Triplo AI - Universal AI assistant'), ('tidycal-review.html', 'TidyCal - Calendar scheduling')],
        'category': 'writing-content',
        'comparison': None
    },
    'jasper': {
        'similar': [('neuronwriter-review.html', 'NeuronWriter - SEO writing alternative'), ('writesonic-review.html', 'Writesonic - AI writer')],
        'lifetime': [('triplo-ai-review.html', 'Triplo AI - Universal AI assistant'), ('tidycal-review.html', 'TidyCal - Calendar scheduling')],
        'category': 'writing-content',
        'comparison': 'neuronwriter-vs-jasper.html'
    },
    'grammarly': {
        'similar': [('prowritingaid-review.html', 'ProWritingAid - Writing coach'), ('wordtune-review.html', 'Wordtune - AI writing companion')],
        'lifetime': [('triplo-ai-review.html', 'Triplo AI - Universal AI assistant'), ('tidycal-review.html', 'TidyCal - Calendar scheduling')],
        'category': 'writing-content',
        'comparison': None
    }
}

RELATED_TOOLS_TEMPLATE = '''        <section style="margin-top: 60px; padding: 30px; background: #f8fafc; border-radius: 12px; border-left: 4px solid #667eea;">
            <h2 style="color: #667eea; margin-bottom: 20px;">Related AI Tools &amp; Alternatives</h2>
            <p style="margin-bottom: 25px; color: #555; font-size: 1.05em;">Compare {tool_name} with similar tools and explore other options:</p>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 25px;">
                <div style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e5e7eb;">
                    <h3 style="color: #333; margin-bottom: 10px; font-size: 1.1em;">Similar Tools</h3>
                    <ul style="list-style: none; margin: 0; padding: 0;">
{similar_tools}
                    </ul>
                </div>
                <div style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e5e7eb;">
                    <h3 style="color: #333; margin-bottom: 10px; font-size: 1.1em;">Other Lifetime Deals</h3>
                    <ul style="list-style: none; margin: 0; padding: 0;">
{lifetime_tools}
                    </ul>
                </div>
            </div>
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="margin-bottom: 15px; color: #555;"><strong>Explore More:</strong></p>
                <ul style="list-style: none; margin: 0; padding: 0;">
{explore_links}
                </ul>
            </div>
        </section>'''

def generate_related_tools_section(tool_key, tool_name):
    """Generate Related Tools section HTML."""
    if tool_key not in RELATED_TOOLS_MAP:
        return None
    
    data = RELATED_TOOLS_MAP[tool_key]
    
    # Build similar tools list
    similar_items = []
    for link, desc in data.get('similar', []):
        similar_items.append(f'                        <li style="margin-bottom: 12px;"><a href="{link}" style="color: #667eea; font-weight: 600; text-decoration: none;">{desc}</a></li>')
    similar_tools = '\n'.join(similar_items) if similar_items else '                        <li style="margin-bottom: 12px;">No similar tools listed yet.</li>'
    
    # Build lifetime deals list
    lifetime_items = []
    for link, desc in data.get('lifetime', []):
        lifetime_items.append(f'                        <li style="margin-bottom: 12px;"><a href="{link}" style="color: #667eea; font-weight: 600; text-decoration: none;">{desc}</a></li>')
    lifetime_tools = '\n'.join(lifetime_items) if lifetime_items else '                        <li style="margin-bottom: 12px;">No lifetime deals listed yet.</li>'
    
    # Build explore links
    explore_items = []
    if data.get('comparison'):
        explore_items.append(f'                    <li style="margin-bottom: 10px;"><a href="../compare/{data["comparison"]}" style="color: #667eea; font-weight: 600; text-decoration: none;">→ Compare {tool_name} vs Alternatives</a> — Detailed head-to-head comparison</li>')
    explore_items.append(f'                    <li style="margin-bottom: 10px;"><a href="../category/{data["category"]}.html" style="color: #667eea; font-weight: 600; text-decoration: none;">→ {data["category"].replace("-", " ").title()} Tools</a> — Browse all tools in this category</li>')
    explore_items.append('                    <li style="margin-bottom: 10px;"><a href="../guides/best-lifetime-ai-tools.html" style="color: #667eea; font-weight: 600; text-decoration: none;">→ Browse All 75+ Lifetime Deals</a> — Complete list of AI tool deals</li>')
    explore_links = '\n'.join(explore_items)
    
    return RELATED_TOOLS_TEMPLATE.format(
        tool_name=tool_name,
        similar_tools=similar_tools,
        lifetime_tools=lifetime_tools,
        explore_links=explore_links
    )

def has_related_tools_section(content):
    """Check if page already has a Related Tools section."""
    patterns = [
        r'Related Tools.*Alternatives',
        r'Related AI Tools',
        r'Similar Tools'
    ]
    for pattern in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False

def add_related_tools_section(filepath, tool_key, tool_name):
    """Add or replace Related Tools section in a review page."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Check if section already exists
        if has_related_tools_section(content):
            # Find and replace existing section
            pattern = r'<section[^>]*>.*?Related.*?Tools.*?</section>'
            new_section = generate_related_tools_section(tool_key, tool_name)
            if new_section:
                content = re.sub(pattern, new_section, content, flags=re.DOTALL | re.IGNORECASE)
        else:
            # Find insertion point (before footer or before closing </div> of container)
            # Look for FAQ section or Final Verdict section end
            insertion_patterns = [
                r'(</section>\s*<div[^>]*text-align: center[^>]*margin: 60px)',
                r'(</section>\s*</div>\s*<div[^>]*sticky-cta-bar)',
                r'(</section>\s*</div>\s*<footer)',
                r'(Frequently Asked Questions.*?</section>)',
            ]
            
            new_section = generate_related_tools_section(tool_key, tool_name)
            if not new_section:
                return False
            
            inserted = False
            for pattern in insertion_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    content = content[:match.end()] + '\n\n' + new_section + '\n' + content[match.end():]
                    inserted = True
                    break
            
            if not inserted:
                # Fallback: insert before footer
                footer_match = re.search(r'(<footer)', content, re.IGNORECASE)
                if footer_match:
                    content = content[:footer_match.start()] + '\n\n' + new_section + '\n\n' + content[footer_match.start():]
                else:
                    return False
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Process review pages."""
    # Top priority pages to update
    pages_to_update = [
        ('tools/frase-review.html', 'frase', 'Frase'),
        ('tools/jasper-alternative-review.html', 'jasper', 'Jasper'),
        ('tools/grammarly-alternative-review.html', 'grammarly', 'Grammarly'),
    ]
    
    print("Adding/improving Related Tools sections...")
    updated = 0
    for filepath_str, tool_key, tool_name in pages_to_update:
        filepath = Path(filepath_str)
        if filepath.exists():
            if add_related_tools_section(filepath, tool_key, tool_name):
                updated += 1
                print(f"[OK] Updated {filepath}")
        else:
            print(f"[SKIP] {filepath} not found")
    
    print(f"\nCompleted! Updated {updated} files.")

if __name__ == '__main__':
    main()
