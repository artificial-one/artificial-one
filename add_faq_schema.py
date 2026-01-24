#!/usr/bin/env python3
"""
Add FAQPage schema to pages with FAQs.
This enables FAQ rich snippets in search results.
"""
import re
import json
from pathlib import Path

def extract_faqs(content):
    """Extract FAQ questions and answers from HTML."""
    faqs = []
    
    # Look for FAQ patterns
    # Pattern 1: <h3>Question</h3><p>Answer</p>
    faq_pattern1 = r'<h[23][^>]*>(.*?)</h[23]>\s*<p[^>]*>(.*?)</p>'
    matches = re.findall(faq_pattern1, content, re.DOTALL | re.IGNORECASE)
    
    for question, answer in matches:
        # Clean up HTML tags
        question = re.sub(r'<[^>]+>', '', question).strip()
        answer = re.sub(r'<[^>]+>', '', answer).strip()
        
        # Check if it looks like a FAQ (question mark, common FAQ words)
        if '?' in question or any(word in question.lower() for word in ['what', 'how', 'why', 'when', 'where', 'is', 'are', 'can', 'does', 'do']):
            if len(question) > 10 and len(answer) > 20:
                faqs.append({
                    'question': question[:200],  # Limit length
                    'answer': answer[:500]  # Limit length
                })
    
    # Pattern 2: FAQ section with specific markers
    if 'FAQ' in content or 'Frequently Asked' in content:
        # Look for sections between FAQ markers
        faq_section = re.search(r'(?:FAQ|Frequently Asked Questions).*?(?=<h[12]|</article|</section|$)', content, re.DOTALL | re.IGNORECASE)
        if faq_section:
            section_content = faq_section.group(0)
            # Extract Q&A pairs
            qa_pairs = re.findall(r'<h[23][^>]*>(.*?)\?</h[23]>\s*<p[^>]*>(.*?)</p>', section_content, re.DOTALL | re.IGNORECASE)
            for question, answer in qa_pairs:
                question = re.sub(r'<[^>]+>', '', question).strip() + '?'
                answer = re.sub(r'<[^>]+>', '', answer).strip()
                if len(question) > 10 and len(answer) > 20:
                    faqs.append({
                        'question': question[:200],
                        'answer': answer[:500]
                    })
    
    return faqs[:10]  # Limit to 10 FAQs

def create_faq_schema(faqs):
    """Create FAQPage schema from FAQs."""
    if not faqs:
        return None
    
    main_entity = []
    for faq in faqs:
        main_entity.append({
            "@type": "Question",
            "name": faq['question'],
            "acceptedAnswer": {
                "@type": "Answer",
                "text": faq['answer']
            }
        })
    
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": main_entity
    }

def add_faq_schema(content, filepath):
    """Add FAQ schema to HTML if FAQs are present."""
    # Check if already has FAQ schema
    if '"@type": "FAQPage"' in content:
        return content
    
    faqs = extract_faqs(content)
    if not faqs:
        return content
    
    schema = create_faq_schema(faqs)
    if not schema:
        return content
    
    # Generate script tag
    script_content = json.dumps(schema, indent=2)
    script_tag = f'<script type="application/ld+json">\n{script_content}\n    </script>'
    
    # Add before closing </head>
    if '</head>' in content:
        content = content.replace('</head>', f'    {script_tag}\n</head>')
    else:
        content = content.replace('</body>', f'    {script_tag}\n</body>')
    
    return content

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        updated_content = add_faq_schema(content, filepath)
        
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
    print("Adding FAQ schema to pages with FAQs...")
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            print(f"[OK] Added FAQ schema to {filepath}")
    
    print(f"\nCompleted! Updated {updated_count} files with FAQ schema.")

if __name__ == '__main__':
    main()
