#!/usr/bin/env python3
"""Add mobile menu CSS to category pages."""
import re
from pathlib import Path

def add_mobile_css(file_path):
    """Add mobile menu CSS styles if missing."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Check if already has mobile menu CSS
        if '#mobile-menu { border-top' in content:
            return False
        
        # Find </style> and add CSS before it
        if '</style>' in content:
            css_to_add = '''        #mobile-menu { border-top: 1px solid #e5e7eb; margin-top: 1rem; }
        .mobile-dropdown-btn svg { transition: transform 0.3s ease; }
        .mobile-dropdown-btn.active svg { transform: rotate(180deg); }
    '''
            new_content = content.replace('</style>', css_to_add + '</style>')
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
        if add_mobile_css(html_file):
            fixed_count += 1
            print(f"Added CSS: {html_file}")
    
    print(f"\nAdded mobile CSS to {fixed_count} category pages")

if __name__ == '__main__':
    main()
