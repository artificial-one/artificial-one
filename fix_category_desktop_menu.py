#!/usr/bin/env python3
"""Fix desktop menu in category pages to hide on mobile."""
import re
from pathlib import Path

def fix_desktop_menu(file_path):
    """Add hidden md:flex to desktop menu if missing."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Pattern to find desktop menu div without hidden md:flex
        pattern = r'<div class="flex gap-4 sm:gap-6 items-center text-sm sm:text-base">'
        replacement = '<div class="hidden md:flex gap-4 sm:gap-6 items-center text-sm sm:text-base">'
        
        if pattern in content:
            new_content = content.replace(pattern, replacement)
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
        if fix_desktop_menu(html_file):
            fixed_count += 1
            print(f"Fixed: {html_file}")
    
    print(f"\nFixed {fixed_count} category pages")

if __name__ == '__main__':
    main()
