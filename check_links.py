#!/usr/bin/env python3
"""
Script to check AppSumo affiliate links from Excel file.
Tests each link and reports which ones work and which are broken.
"""

import requests
import pandas as pd
from urllib.parse import urlparse
import sys
from datetime import datetime

# Configuration
EXCEL_FILE = 'appsumo-affiliate-links-tracker.xlsx'
OUTPUT_FILE = 'broken_links_report.txt'
TIMEOUT = 10  # seconds
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def is_valid_url(url):
    """Check if a string is a valid URL."""
    try:
        result = urlparse(str(url))
        return all([result.scheme, result.netloc])
    except:
        return False

def check_link(url):
    """Check if a link is accessible. Returns (status_code, error_message)."""
    if not url or pd.isna(url):
        return None, "Empty or NaN value"
    
    url = str(url).strip()
    
    if not is_valid_url(url):
        return None, "Invalid URL format"
    
    try:
        response = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return response.status_code, None
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.ConnectionError:
        return None, "Connection Error"
    except requests.exceptions.TooManyRedirects:
        return None, "Too Many Redirects"
    except requests.exceptions.RequestException as e:
        return None, f"Request Error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected Error: {str(e)}"

def main():
    """Main function to read Excel, check links, and generate report."""
    print(f"Reading links from {EXCEL_FILE}...")
    
    try:
        # Read Excel file
        df = pd.read_excel(EXCEL_FILE)
        print(f"Found {len(df)} rows in the Excel file.")
        
        # Try to find the column with links
        # Common column names: 'link', 'url', 'affiliate_link', 'Link', 'URL', etc.
        link_column = None
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['link', 'url', 'affiliate']):
                link_column = col
                break
        
        if link_column is None:
            print("\nAvailable columns:", list(df.columns))
            print("\nError: Could not find a column with links.")
            print("Please ensure your Excel file has a column named 'link', 'url', or 'affiliate_link'.")
            sys.exit(1)
        
        print(f"Using column '{link_column}' for links.\n")
        
        # Collect results
        working_links = []
        broken_links = []
        invalid_links = []
        
        total_links = len(df)
        print(f"Checking {total_links} links...\n")
        
        # Check each link
        for index, row in df.iterrows():
            url = row[link_column]
            status_code, error = check_link(url)
            
            # Get additional info if available (like product name, etc.)
            row_info = {}
            for col in df.columns:
                if col != link_column:
                    row_info[col] = row[col]
            
            if status_code is None:
                # Invalid or error
                invalid_links.append({
                    'url': url,
                    'error': error,
                    'row': index + 2,  # +2 because Excel rows start at 1 and header is row 1
                    'info': row_info
                })
                print(f"[{index + 1}/{total_links}] ❌ {url[:60]}... - {error}")
            elif status_code == 200:
                working_links.append({
                    'url': url,
                    'status': status_code,
                    'row': index + 2,
                    'info': row_info
                })
                print(f"[{index + 1}/{total_links}] ✅ {url[:60]}... - Status: {status_code}")
            else:
                broken_links.append({
                    'url': url,
                    'status': status_code,
                    'row': index + 2,
                    'info': row_info
                })
                print(f"[{index + 1}/{total_links}] ❌ {url[:60]}... - Status: {status_code}")
        
        # Generate report
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total links checked: {total_links}")
        print(f"✅ Working links (200): {len(working_links)}")
        print(f"❌ Broken links (non-200): {len(broken_links)}")
        print(f"⚠️  Invalid/Error links: {len(invalid_links)}")
        print("="*80 + "\n")
        
        # Write report to file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("AppSumo Affiliate Links Check Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"SUMMARY\n")
            f.write(f"Total links checked: {total_links}\n")
            f.write(f"Working links (200): {len(working_links)}\n")
            f.write(f"Broken links (non-200): {len(broken_links)}\n")
            f.write(f"Invalid/Error links: {len(invalid_links)}\n")
            f.write("\n" + "="*80 + "\n\n")
            
            # Broken links section
            if broken_links:
                f.write("BROKEN LINKS (Non-200 Status Codes)\n")
                f.write("="*80 + "\n")
                for item in broken_links:
                    f.write(f"\nRow {item['row']}: Status {item['status']}\n")
                    f.write(f"URL: {item['url']}\n")
                    if item['info']:
                        f.write(f"Additional Info: {item['info']}\n")
                f.write("\n" + "="*80 + "\n\n")
            
            # Invalid links section
            if invalid_links:
                f.write("INVALID/ERROR LINKS\n")
                f.write("="*80 + "\n")
                for item in invalid_links:
                    f.write(f"\nRow {item['row']}: {item['error']}\n")
                    f.write(f"URL: {item['url']}\n")
                    if item['info']:
                        f.write(f"Additional Info: {item['info']}\n")
                f.write("\n" + "="*80 + "\n\n")
            
            # Working links section (optional - can be commented out if too long)
            if working_links:
                f.write("WORKING LINKS (200 Status)\n")
                f.write("="*80 + "\n")
                for item in working_links:
                    f.write(f"Row {item['row']}: {item['url']}\n")
                f.write("\n" + "="*80 + "\n")
        
        print(f"Report saved to {OUTPUT_FILE}")
        
    except FileNotFoundError:
        print(f"Error: File '{EXCEL_FILE}' not found.")
        print("Please ensure the Excel file exists in the current directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
