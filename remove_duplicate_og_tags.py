#!/usr/bin/env python3
"""
Remove duplicate OG image meta tags from HTML files.
Keeps only the first occurrence of each OG tag type.
"""
import re
from pathlib import Path
from collections import OrderedDict

def remove_duplicate_og_tags(content):
    """Remove duplicate OG meta tags, keeping only the first occurrence."""
    # Find all OG tags
    og_pattern = r'<meta\s+property=["\'](og:[^"\']+)["\'][^>]*>'
    matches = list(re.finditer(og_pattern, content, re.IGNORECASE))
    
    if not matches:
        return content
    
    # Track which OG properties we've seen
    seen_properties = OrderedDict()
    tags_to_remove = []
    
    for match in matches:
        tag = match.group(0)
        # Extract property name (e.g., "og:image", "og:image:width")
        prop_match = re.search(r'property=["\'](og:[^"\']+)["\']', tag, re.IGNORECASE)
        if prop_match:
            prop_name = prop_match.group(1).lower()
            
            # For og:image and related tags, we want to keep the first set together
            if prop_name.startswith('og:image'):
                # Group by base property (og:image)
                base_prop = 'og:image'
            else:
                base_prop = prop_name
            
            if base_prop not in seen_properties:
                seen_properties[base_prop] = []
            seen_properties[base_prop].append((match.start(), match.end(), tag))
    
    # For each property, keep only the first occurrence
    # For og:image, keep the first set (og:image, og:image:width, og:image:height, og:image:alt)
    tags_to_keep = set()
    
    # Find the first og:image set
    first_image_set = None
    for match in matches:
        tag = match.group(0)
        if 'og:image"' in tag.lower() and not 'og:image:' in tag.lower():
            # This is the base og:image tag
            first_image_set = match.start()
            break
    
    if first_image_set is not None:
        # Keep og:image and its related tags (width, height, alt) that come right after
        for i, match in enumerate(matches):
            tag_start = match.start()
            tag = match.group(0)
            prop_match = re.search(r'property=["\'](og:[^"\']+)["\']', tag, re.IGNORECASE)
            if prop_match:
                prop_name = prop_match.group(1).lower()
                
                # Keep the first og:image and its immediate siblings
                if prop_name == 'og:image':
                    if tag_start == first_image_set:
                        tags_to_keep.add(tag_start)
                        # Keep the next few tags that are likely og:image:width, og:image:height, og:image:alt
                        for j in range(i+1, min(i+4, len(matches))):
                            next_tag = matches[j].group(0)
                            if 'og:image:' in next_tag.lower():
                                tags_to_keep.add(matches[j].start())
                            else:
                                break
                elif prop_name.startswith('og:image:'):
                    # Only keep if it's part of the first set
                    if any(abs(tag_start - kept) < 200 for kept in tags_to_keep):
                        tags_to_keep.add(tag_start)
    
    # Keep all other OG tags (first occurrence only)
    for prop_name, occurrences in seen_properties.items():
        if not prop_name.startswith('og:image'):
            if occurrences:
                tags_to_keep.add(occurrences[0][0])
    
    # Build new content, removing duplicates
    result_parts = []
    last_end = 0
    
    for match in matches:
        if match.start() in tags_to_keep:
            # Keep this tag, add content before it
            result_parts.append(content[last_end:match.end()])
            last_end = match.end()
        else:
            # Skip this duplicate tag, add content before it
            result_parts.append(content[last_end:match.start()])
            last_end = match.end()
    
    result_parts.append(content[last_end:])
    return ''.join(result_parts)

def process_file(filepath):
    """Process a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        updated_content = remove_duplicate_og_tags(content)
        
        if updated_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Remove duplicate OG tags from all HTML files."""
    root = Path('.')
    html_files = []
    
    for html_file in root.rglob('*.html'):
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if '.git' in html_file.parts:
            continue
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} HTML files")
    print("Removing duplicate OG tags...\n")
    
    updated_count = 0
    for filepath in sorted(html_files):
        if process_file(filepath):
            updated_count += 1
            if updated_count <= 20:
                print(f"[OK] Removed duplicates in {filepath}")
    
    print(f"\nCompleted! Fixed {updated_count} files.")

if __name__ == '__main__':
    main()
