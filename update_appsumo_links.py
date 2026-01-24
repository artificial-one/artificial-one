#!/usr/bin/env python3
"""
Script to update AppSumo affiliate links across the website based on 
the Excel file appsumo-affiliate-links-tracker.xlsx
"""

import os
import re
import pandas as pd
from pathlib import Path
from collections import defaultdict

# Configuration
EXCEL_FILE = "appsumo-affiliate-links-tracker.xlsx"
APPSUMO_DOMAIN = "appsumo.8odi.net"
APPSUMO_PATTERN = rf'https?://{re.escape(APPSUMO_DOMAIN)}/[^\s"\'<>)]+'

def read_excel_links(excel_file):
    """Read product names and affiliate links from Excel file."""
    print(f"Reading Excel file: {excel_file}")
    
    try:
        # Try multiple methods to read the Excel file
        df = None
        
        # Method 1: Try pandas with openpyxl, ignoring styles
        try:
            # Use a custom function to read without styles
            import zipfile
            import xml.etree.ElementTree as ET
            
            # Extract data directly from XML to avoid style parsing
            with zipfile.ZipFile(excel_file, 'r') as zip_ref:
                # Read the shared strings
                shared_strings = []
                try:
                    with zip_ref.open('xl/sharedStrings.xml') as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        for si in root.findall('.//main:si', ns):
                            text = ''
                            for t in si.findall('.//main:t', ns):
                                if t.text:
                                    text += t.text
                            shared_strings.append(text)
                except:
                    pass
                
                # Read the first worksheet
                sheet_files = [f for f in zip_ref.namelist() if f.startswith('xl/worksheets/sheet')]
                if sheet_files:
                    with zip_ref.open(sheet_files[0]) as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        
                        data = []
                        for row in root.findall('.//main:row', ns):
                            row_data = []
                            for cell in row.findall('.//main:c', ns):
                                value_elem = cell.find('.//main:v', ns)
                                if value_elem is not None and value_elem.text:
                                    val = value_elem.text
                                    # Check if it's a shared string reference
                                    t_attr = cell.get('t')
                                    if t_attr == 's' and shared_strings:
                                        try:
                                            idx = int(val)
                                            if idx < len(shared_strings):
                                                val = shared_strings[idx]
                                        except:
                                            pass
                                    row_data.append(val)
                                else:
                                    row_data.append(None)
                            if any(cell is not None for cell in row_data):
                                data.append(row_data)
                        
                        if data:
                            # First row as headers
                            headers = [str(cell) if cell else f"Column{i+1}" for i, cell in enumerate(data[0])]
                            df = pd.DataFrame(data[1:], columns=headers)
        except Exception as e1:
            print(f"XML extraction failed: {e1}, trying pandas...")
            # Method 2: Try pandas with different engines
            try:
                df = pd.read_excel(excel_file, engine='calamine')  # Rust-based, faster
            except:
                try:
                    df = pd.read_excel(excel_file, engine='xlrd')  # Older format support
                except:
                    # Last resort: try openpyxl with error suppression
                    import warnings
                    warnings.filterwarnings('ignore')
                    df = pd.read_excel(excel_file, engine='openpyxl')
        
        if df is None or df.empty:
            raise ValueError("Could not read Excel file with any method")
        
        print(f"Found {len(df)} rows in Excel file")
        print(f"Columns: {list(df.columns)}")
        
        # Create a mapping of product name to affiliate link
        # Try to find the right columns (case-insensitive)
        name_col = None
        link_col = None
        
        # Prefer "Your Generated Tracking Link" for affiliate links
        for col in df.columns:
            col_lower = str(col).lower()
            if ('name' in col_lower and 'product' in col_lower) or col == 'Product Name':
                name_col = col
            if 'tracking link' in col_lower or col == 'Your Generated Tracking Link':
                link_col = col
        
        # If not found, try broader search
        if not name_col:
            for col in df.columns:
                col_lower = str(col).lower()
                if 'name' in col_lower or 'product' in col_lower:
                    name_col = col
                    break
        
        if not link_col:
            for col in df.columns:
                col_lower = str(col).lower()
                if 'link' in col_lower or 'url' in col_lower or 'affiliate' in col_lower:
                    link_col = col
                    break
        
        if not name_col or not link_col:
            # If we can't find columns, try common patterns
            if len(df.columns) >= 2:
                name_col = df.columns[0]
                link_col = df.columns[1]
                print(f"Using first column as name: {name_col}")
                print(f"Using second column as link: {link_col}")
            else:
                raise ValueError("Could not identify name and link columns")
        
        print(f"Using name column: '{name_col}'")
        print(f"Using link column: '{link_col}'")
        
        product_links = {}
        for idx, row in df.iterrows():
            product_name = str(row[name_col]).strip()
            affiliate_link = str(row[link_col]).strip()
            
            # Skip empty rows
            if pd.isna(row[name_col]) or pd.isna(row[link_col]) or product_name == 'nan' or affiliate_link == 'nan':
                continue
            
            # Normalize product name for matching (lowercase, remove extra spaces)
            normalized_name = re.sub(r'\s+', ' ', product_name.lower().strip())
            product_links[normalized_name] = {
                'original_name': product_name,
                'link': affiliate_link
            }
        
        print(f"Loaded {len(product_links)} product links from Excel")
        # Show first 5 products as sample
        print("Sample products from Excel:")
        for i, (norm_name, data) in enumerate(list(product_links.items())[:5]):
            print(f"  {i+1}. '{data['original_name']}' -> {data['link'][:50]}...")
        return product_links
    
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        raise

def normalize_product_name(name):
    """Normalize product name for matching."""
    # Remove extra spaces, convert to lowercase
    normalized = re.sub(r'\s+', ' ', str(name).strip().lower())
    return normalized

def find_product_in_content(content, product_name, product_links):
    """Find product references in content and return matches."""
    matches = []
    
    # Try exact normalized match first
    normalized = normalize_product_name(product_name)
    if normalized in product_links:
        return [(normalized, product_links[normalized])]
    
    # Try partial matches (product name contains or is contained in)
    for norm_name, link_data in product_links.items():
        if normalized in norm_name or norm_name in normalized:
            matches.append((norm_name, link_data))
    
    return matches

def update_links_in_file(file_path, product_links):
    """Update AppSumo links in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        updates_made = []
        
        # Find all AppSumo links in the file
        appsumo_links = re.findall(APPSUMO_PATTERN, content)
        
        # Also find product names near links (for reviews.html structure)
        # Pattern: name: "Product Name" ... link: "https://appsumo..."
        # This pattern matches JavaScript object structure: {name: "...", ..., link: "..."}
        product_link_pattern = r'name:\s*"([^"]+)"[^}]*?link:\s*"(https?://' + re.escape(APPSUMO_DOMAIN) + r'/[^"]+)"'
        product_matches = list(re.finditer(product_link_pattern, content, re.DOTALL))
        
        for match in product_matches:
            product_name = match.group(1)
            old_link = match.group(2)
            
            # Find matching product in Excel
            normalized = normalize_product_name(product_name)
            if normalized in product_links:
                new_link = product_links[normalized]['link']
                if old_link != new_link:
                    # Replace just the URL part (group 2) with the new link
                    # match.start(2) and match.end(2) point to the URL without quotes
                    link_start = match.start(2)
                    link_end = match.end(2)
                    content = content[:link_start] + new_link + content[link_end:]
                    updates_made.append({
                        'product': product_name,
                        'old_link': old_link,
                        'new_link': new_link
                    })
            else:
                # Debug: show products that weren't matched
                if file_path.endswith('reviews.html'):
                    # Try fuzzy matching
                    best_match = None
                    best_score = 0
                    for norm_name, link_data in product_links.items():
                        # Check if names are similar (one contains the other or vice versa)
                        if normalized in norm_name or norm_name in normalized:
                            score = min(len(normalized), len(norm_name)) / max(len(normalized), len(norm_name))
                            if score > best_score:
                                best_score = score
                                best_match = (norm_name, link_data)
                    
                    if best_match and best_score > 0.7:  # 70% similarity threshold
                        new_link = best_match[1]['link']
                        if old_link != new_link:
                            link_start = match.start(2)
                            link_end = match.end(2)
                            content = content[:link_start] + f'"{new_link}"' + content[link_end:]
                            updates_made.append({
                                'product': product_name,
                                'old_link': old_link,
                                'new_link': new_link,
                                'matched_via': 'fuzzy'
                            })
        
        # Also check for standalone links that might be near product names
        # Look for patterns like: link: "https://appsumo..." and try to find nearby product name
        standalone_link_pattern = r'link:\s*"(https?://' + re.escape(APPSUMO_DOMAIN) + r'/[^"]+)"'
        standalone_matches = list(re.finditer(standalone_link_pattern, content))
        
        # For each standalone link, look backwards for a product name
        for match in standalone_matches:
            old_link = match.group(1)
            # Look backwards up to 500 chars for a name: "Product" pattern
            start_pos = max(0, match.start() - 500)
            context = content[start_pos:match.start()]
            
            # Find the closest name: "Product" before this link
            name_match = re.search(r'name:\s*"([^"]+)"', context)
            if name_match:
                product_name = name_match.group(1)
                normalized = normalize_product_name(product_name)
                
                if normalized in product_links:
                    new_link = product_links[normalized]['link']
                    if old_link != new_link:
                        # Replace this specific occurrence
                        content = content[:match.start()] + f'link: "{new_link}"' + content[match.end():]
                        updates_made.append({
                            'product': product_name,
                            'old_link': old_link,
                            'new_link': new_link
                        })
        
        # Also handle links in anchor tags: <a href="https://appsumo...">
        anchor_pattern = r'(<a[^>]*href=["\'])(https?://' + re.escape(APPSUMO_DOMAIN) + r'/[^"\']+)(["\'][^>]*>)'
        anchor_matches = list(re.finditer(anchor_pattern, content))
        
        # For anchor tags, try to find product name in nearby text
        for match in anchor_matches:
            old_link = match.group(2)
            # Look in a wider context around the link
            start_pos = max(0, match.start() - 1000)
            end_pos = min(len(content), match.end() + 1000)
            context = content[start_pos:end_pos]
            
            # Try to find product name in the context
            # Look for common patterns
            name_patterns = [
                r'name:\s*"([^"]+)"',
                r'product[:\s]+"?([^"]+)"?',
                r'([A-Z][a-zA-Z0-9\s&]+)\s+(?:is|tool|software|platform)',
            ]
            
            product_name = None
            for pattern in name_patterns:
                name_match = re.search(pattern, context, re.IGNORECASE)
                if name_match:
                    potential_name = name_match.group(1).strip()
                    normalized = normalize_product_name(potential_name)
                    if normalized in product_links:
                        product_name = potential_name
                        break
            
            if product_name:
                normalized = normalize_product_name(product_name)
                new_link = product_links[normalized]['link']
                if old_link != new_link:
                    # Replace the link
                    new_anchor = match.group(1) + new_link + match.group(3)
                    content = content[:match.start()] + new_anchor + content[match.end():]
                    updates_made.append({
                        'product': product_name,
                        'old_link': old_link,
                        'new_link': new_link
                    })
        
        # Write the file if changes were made
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return updates_made
        
        return []
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return []

def find_html_files():
    """Find all HTML files in the project."""
    html_files = []
    for root, dirs, files in os.walk('.'):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    
    return html_files

def main():
    print("=" * 70)
    print("AppSumo Affiliate Link Updater")
    print("=" * 70)
    print()
    
    # Step 1: Read Excel file
    if not os.path.exists(EXCEL_FILE):
        print(f"Error: Excel file '{EXCEL_FILE}' not found!")
        return
    
    product_links = read_excel_links(EXCEL_FILE)
    
    if not product_links:
        print("No product links found in Excel file!")
        return
    
    print()
    
    # Step 2: Find all HTML files
    print("Finding HTML files...")
    html_files = find_html_files()
    print(f"Found {len(html_files)} HTML files")
    print()
    
    # Step 3: Update links in each file
    print("Updating links...")
    print("-" * 70)
    
    total_updates = 0
    files_updated = 0
    all_updates = defaultdict(list)
    
    for file_path in html_files:
        updates = update_links_in_file(file_path, product_links)
        if updates:
            files_updated += 1
            total_updates += len(updates)
            all_updates[file_path] = updates
            print(f"[{files_updated}] {file_path}: {len(updates)} link(s) updated")
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Files updated: {files_updated}")
    print(f"Total links updated: {total_updates}")
    print()
    
    if all_updates:
        print("=" * 70)
        print("DETAILED CHANGES")
        print("=" * 70)
        for file_path, updates in sorted(all_updates.items()):
            print(f"\n{file_path}:")
            for update in updates:
                print(f"  {update['product']}")
                print(f"    Old: {update['old_link']}")
                print(f"    New: {update['new_link']}")
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

if __name__ == "__main__":
    main()
