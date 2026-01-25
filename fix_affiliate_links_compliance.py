#!/usr/bin/env python3
"""
Fix affiliate link compliance issues:
1. Remove duplicate rel="nofollow sponsored" attributes
2. Ensure all AppSumo links have rel="nofollow sponsored"
3. Normalize rel attribute format
"""
import re
from pathlib import Path

def normalize_rel_attribute(rel_value):
    """Normalize and clean rel attribute value."""
    if not rel_value:
        return "nofollow sponsored"
    
    # Split by spaces and normalize
    parts = [p.strip().lower() for p in rel_value.split() if p.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_parts = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            unique_parts.append(part)
    
    # Ensure we have nofollow and sponsored
    if 'nofollow' not in unique_parts:
        unique_parts.append('nofollow')
    if 'sponsored' not in unique_parts:
        unique_parts.append('sponsored')
    
    # Keep noopener if present
    if 'noopener' not in unique_parts and 'noopener' in rel_value.lower():
        unique_parts.insert(0, 'noopener')
    
    return ' '.join(unique_parts)

def fix_affiliate_link(match):
    """Fix affiliate link with proper rel attributes."""
    full_tag = match.group(0)
    
    # Check if it's an AppSumo affiliate link
    is_appsumo = 'appsumo.8odi.net' in full_tag.lower() or 'appsumo' in full_tag.lower()
    
    if not is_appsumo:
        return full_tag
    
    # Extract existing rel attribute
    rel_match = re.search(r'rel\s*=\s*["\']([^"\']*)["\']', full_tag, re.IGNORECASE)
    
    if rel_match:
        # Normalize existing rel attribute
        rel_value = rel_match.group(1)
        normalized_rel = normalize_rel_attribute(rel_value)
        
        # Replace the rel attribute
        fixed_tag = re.sub(
            r'rel\s*=\s*["\'][^"\']*["\']',
            f'rel="{normalized_rel}"',
            full_tag,
            flags=re.IGNORECASE
        )
        return fixed_tag
    else:
        # Add rel attribute before closing >
        fixed_tag = re.sub(
            r'(>)',
            r' rel="nofollow sponsored"\1',
            full_tag
        )
        return fixed_tag

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        
        # Pattern to match anchor tags with AppSumo links
        appsumo_pattern = r'<a\s+[^>]*href\s*=\s*["\']https?://[^"\']*appsumo[^"\']*["\'][^>]*>'
        
        # Fix all AppSumo affiliate links
        content = re.sub(appsumo_pattern, fix_affiliate_link, content, flags=re.IGNORECASE)
        
        # Also check for links with "appsumo.8odi.net" specifically
        specific_pattern = r'<a\s+[^>]*href\s*=\s*["\']https?://appsumo\.8odi\.net[^"\']*["\'][^>]*>'
        content = re.sub(specific_pattern, fix_affiliate_link, content, flags=re.IGNORECASE)
        
        # Only write if content changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Process all HTML files."""
    root = Path('.')
    html_files = []
    
    # Find all HTML files
    for html_file in root.rglob('*.html'):
        # Skip hidden directories and .git
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if '.git' in html_file.parts:
            continue
        
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} HTML files")
    print("Fixing affiliate link compliance issues...")
    print("- Removing duplicate rel attributes")
    print("- Ensuring all AppSumo links have rel='nofollow sponsored'")
    print()
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            print(f"[OK] Fixed affiliate links in {filepath}")
    
    print(f"\n[SUCCESS] Completed! Fixed {updated_count} files.")
    print("\nNext steps:")
    print("1. Manually verify a few affiliate links")
    print("2. Check that rel='nofollow sponsored' is present")
    print("3. Ensure no duplicate rel attributes remain")

if __name__ == '__main__':
    main()
