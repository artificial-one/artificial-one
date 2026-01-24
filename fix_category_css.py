#!/usr/bin/env python3
"""Add missing mobile menu CSS to category pages."""
import re
from pathlib import Path

MOBILE_CSS = '''        #mobile-menu { border-top: 1px solid #e5e7eb; margin-top: 1rem; }
        .mobile-dropdown-btn svg { transition: transform 0.3s ease; }
        .mobile-dropdown-btn.active svg { transform: rotate(180deg); }'''

def fix_category_page(file_path):
    """Add mobile menu CSS if missing."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Check if already has mobile menu CSS
        if '#mobile-menu' in content and 'border-top' in content:
            return False
        
        # Find the closing </style> tag and insert CSS before it
        pattern = r'(\.dropdown-content a:hover.*?\})\s*(</style>)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            new_content = content[:match.end(1)] + '\n' + MOBILE_CSS + '\n    ' + content[match.start(2):]
            file_path.write_text(new_content, encoding='utf-8')
            return True
        
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    category_dir = Path('category')
    html_files = list(category_dir.glob('*.html'))
    
    fixed_count = 0
    for html_file in html_files:
        if fix_category_page(html_file):
            fixed_count += 1
            print(f"Fixed: {html_file}")
    
    print(f"\nFixed {fixed_count} category pages")

if __name__ == '__main__':
    main()
