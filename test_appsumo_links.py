#!/usr/bin/env python3
"""
Script to scan HTML files in tools/ folder, extract AppSumo affiliate links,
and test which ones are broken.
"""

import os
import re
import requests
from urllib.parse import urlparse
from collections import defaultdict
import time

# Configuration
TOOLS_FOLDER = "tools"
APPSUMO_DOMAIN = "appsumo.8odi.net"
TIMEOUT = 10  # seconds
DELAY_BETWEEN_REQUESTS = 0.5  # seconds to avoid rate limiting

def find_html_files(folder):
    """Find all HTML files in the specified folder."""
    html_files = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    return html_files

def extract_appsumo_links(file_path):
    """Extract all AppSumo affiliate links from an HTML file."""
    links = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Pattern to match AppSumo affiliate links
        # Matches both http and https, and various URL formats
        pattern = r'https?://' + re.escape(APPSUMO_DOMAIN) + r'/[^\s"\'<>)]+'
        
        matches = re.findall(pattern, content)
        
        for match in matches:
            # Clean up the URL (remove trailing punctuation that might have been captured)
            url = match.rstrip('.,;:!?)')
            links.add(url)
            
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return links

def test_link(url):
    """Test if a link is accessible."""
    try:
        # Follow redirects to check if the final destination is valid
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=True, 
                               headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        
        # Consider 2xx and 3xx status codes as valid
        if response.status_code < 400:
            return True, response.status_code, None
        else:
            return False, response.status_code, None
            
    except requests.exceptions.Timeout:
        return False, None, "Timeout"
    except requests.exceptions.ConnectionError:
        return False, None, "Connection Error"
    except requests.exceptions.TooManyRedirects:
        return False, None, "Too Many Redirects"
    except Exception as e:
        return False, None, str(e)

def main():
    print("=" * 70)
    print("AppSumo Link Checker")
    print("=" * 70)
    print()
    
    # Step 1: Find all HTML files
    print(f"Scanning HTML files in '{TOOLS_FOLDER}' folder...")
    html_files = find_html_files(TOOLS_FOLDER)
    print(f"Found {len(html_files)} HTML files")
    print()
    
    # Step 2: Extract all AppSumo links
    print("Extracting AppSumo affiliate links...")
    all_links = set()
    links_by_file = defaultdict(set)
    
    for file_path in html_files:
        links = extract_appsumo_links(file_path)
        if links:
            all_links.update(links)
            links_by_file[file_path].update(links)
    
    print(f"Found {len(all_links)} unique AppSumo links across {len(links_by_file)} files")
    print()
    
    if not all_links:
        print("No AppSumo links found!")
        return
    
    # Step 3: Test each unique link
    print("Testing links...")
    print("-" * 70)
    
    results = {}
    broken_links = []
    working_links = []
    
    for i, link in enumerate(sorted(all_links), 1):
        print(f"[{i}/{len(all_links)}] Testing: {link}")
        is_valid, status_code, error = test_link(link)
        
        if is_valid:
            results[link] = {'status': 'OK', 'status_code': status_code}
            working_links.append(link)
            print(f"  [OK] Working (Status: {status_code})")
        else:
            results[link] = {'status': 'BROKEN', 'status_code': status_code, 'error': error}
            broken_links.append(link)
            error_msg = f" - {error}" if error else f" (Status: {status_code})" if status_code else ""
            print(f"  [X] Broken{error_msg}")
        
        # Small delay to avoid rate limiting
        if i < len(all_links):
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total unique links tested: {len(all_links)}")
    print(f"Working links: {len(working_links)}")
    print(f"Broken links: {len(broken_links)}")
    print()
    
    # Step 4: Report broken links
    if broken_links:
        print("=" * 70)
        print("BROKEN LINKS")
        print("=" * 70)
        for link in sorted(broken_links):
            result = results[link]
            print(f"\n{link}")
            print(f"  Status Code: {result.get('status_code', 'N/A')}")
            if result.get('error'):
                print(f"  Error: {result['error']}")
            
            # Show which files contain this broken link
            files_with_link = [f for f, links in links_by_file.items() if link in links]
            print(f"  Found in {len(files_with_link)} file(s):")
            for file_path in files_with_link:
                print(f"    - {file_path}")
    else:
        print("[OK] All links are working!")
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

if __name__ == "__main__":
    main()
