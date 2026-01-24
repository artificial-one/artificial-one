#!/usr/bin/env python3
"""Add mobile dropdown JavaScript to category pages."""
import re
from pathlib import Path

def add_mobile_dropdown_js(file_path):
    """Add mobile dropdown JavaScript if missing."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Check if already has mobile dropdown JavaScript
        if 'mobile-dropdown-btn' in content and 'forEach' in content:
            return False
        
        # Find the mobile-menu-btn addEventListener and add dropdown JS after it
        pattern = r"(document\.getElementById\('mobile-menu-btn'\)\.addEventListener\('click', function\(\) \{[^}]+\}\);)\s*(</script>)"
        
        replacement = r'''\1
document.querySelectorAll('.mobile-dropdown-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        this.classList.toggle('active');
        this.nextElementSibling.classList.toggle('hidden');
    });
});
\2'''
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
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
        if add_mobile_dropdown_js(html_file):
            fixed_count += 1
            print(f"Added JS: {html_file}")
    
    print(f"\nAdded mobile dropdown JS to {fixed_count} category pages")

if __name__ == '__main__':
    main()
