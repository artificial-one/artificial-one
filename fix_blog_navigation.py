#!/usr/bin/env python3
"""
Fix navigation width and styling in all blog pages.
Updates max-w-4xl to max-w-7xl and improves navigation menu styling.
"""

import os
import re
from pathlib import Path

def fix_blog_navigation(filepath):
    """Fix navigation in a blog HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix 1: Update navigation container width from max-w-4xl to max-w-7xl
        # Pattern: <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8"> (in nav)
        content = re.sub(
            r'(<nav[^>]*>.*?<div class=")max-w-4xl mx-auto px-4 sm:px-6 lg:px-8(">)',
            r'\1max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 xl:px-12\2',
            content,
            flags=re.DOTALL
        )
        
        # Fix 2: Update navigation menu styling to match blog.html
        # Change: gap-4 sm:gap-6 items-center text-sm sm:text-base
        # To: gap-6 lg:gap-8 items-center text-base lg:text-lg
        content = re.sub(
            r'(<div class="hidden md:flex )gap-4 sm:gap-6 items-center text-sm sm:text-base(">)',
            r'\1gap-6 lg:gap-8 items-center text-base lg:text-lg\2',
            content
        )
        
        # Fix 3: Add transition-colors to navigation links
        content = re.sub(
            r'(<span class="text-gray-600 hover:text-indigo-600 font-medium cursor-pointer">)',
            r'<span class="text-gray-600 hover:text-indigo-600 font-medium cursor-pointer transition-colors">',
            content
        )
        
        # Fix 4: Update Browse Tools button padding for better desktop appearance
        content = re.sub(
            r'(<a href="reviews\.html" class="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white )px-4 sm:px-6 py-2 rounded-lg font-semibold(">)',
            r'\1px-6 lg:px-8 py-2.5 rounded-lg font-semibold transition-all hover:shadow-lg\2',
            content
        )
        
        # Fix 5: Add transition-colors to Blog and About links
        content = re.sub(
            r'(<a href="(blog|about)\.html" class="text-gray-600 hover:text-indigo-600 font-medium">)',
            r'<a href="\2.html" class="text-gray-600 hover:text-indigo-600 font-medium transition-colors">',
            content
        )
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Process all blog HTML files."""
    blog_files = list(Path('.').glob('blog-*.html'))
    
    if not blog_files:
        print("No blog-*.html files found.")
        return
    
    print(f"Found {len(blog_files)} blog files to process...")
    
    fixed_count = 0
    for blog_file in sorted(blog_files):
        if fix_blog_navigation(blog_file):
            print(f"[FIXED] {blog_file.name}")
            fixed_count += 1
        else:
            print(f"  No changes needed: {blog_file.name}")
    
    print(f"\n[SUCCESS] Fixed {fixed_count} out of {len(blog_files)} blog files.")

if __name__ == '__main__':
    main()
