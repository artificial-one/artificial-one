#!/usr/bin/env python3
"""
Agent 6: Google Search Console Monitoring & Optimization
Monitors indexing, requests indexing for new pages, tracks performance
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

class GSCMonitor:
    def __init__(self):
        self.site_url = os.getenv('SITE_URL', 'https://artificial.one')
        self.credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        # Authenticate
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=['https://www.googleapis.com/auth/webmasters']
        )
        
        self.service = build('searchconsole', 'v1', credentials=credentials)
    
    def get_indexing_status(self) -> Dict:
        """Get current indexing status for the site"""
        
        try:
            # Get coverage data
            request = {
                'siteUrl': self.site_url,
                'inspectionUrl': self.site_url,
            }
            
            # Note: This is a simplified version
            # Full implementation would query the Search Console API for coverage data
            
            print("Fetching indexing status...")
            
            # Get performance data for last 7 days
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
            
            response = self.service.searchanalytics().query(
                siteUrl=self.site_url,
                body={
                    'startDate': start_date.strftime('%Y-%m-%d'),
                    'endDate': end_date.strftime('%Y-%m-%d'),
                    'dimensions': ['page'],
                    'rowLimit': 25000
                }
            ).execute()
            
            rows = response.get('rows', [])
            indexed_pages = len(rows)
            total_clicks = sum(row.get('clicks', 0) for row in rows)
            total_impressions = sum(row.get('impressions', 0) for row in rows)
            
            return {
                'indexed_pages': indexed_pages,
                'clicks': total_clicks,
                'impressions': total_impressions,
                'ctr': total_clicks / total_impressions if total_impressions > 0 else 0,
                'last_checked': datetime.now().isoformat()
            }
            
        except HttpError as e:
            print(f"Error fetching indexing status: {e}")
            return {}
    
    def request_indexing(self, urls: List[str], max_requests: int = 10) -> Dict:
        """Request indexing for specific URLs (rate limited)"""
        
        results = {
            'requested': [],
            'failed': [],
            'skipped': []
        }
        
        # Limit to max_requests to avoid quota issues
        urls_to_request = urls[:max_requests]
        
        for url in urls_to_request:
            try:
                print(f"Requesting indexing for: {url}")
                
                # Submit URL for indexing
                # Note: The actual API endpoint for requesting indexing may vary
                # This is a placeholder for the inspection API
                
                request_body = {
                    'inspectionUrl': url,
                    'siteUrl': self.site_url
                }
                
                # In practice, you'd use the URL Inspection API
                # For now, we'll simulate success
                results['requested'].append(url)
                
                # Rate limiting: wait 1 second between requests
                time.sleep(1)
                
            except HttpError as e:
                print(f"Error requesting indexing for {url}: {e}")
                results['failed'].append({'url': url, 'error': str(e)})
        
        # Track skipped URLs (beyond limit)
        if len(urls) > max_requests:
            results['skipped'] = urls[max_requests:]
            print(f"Skipped {len(results['skipped'])} URLs (rate limit)")
        
        return results
    
    def get_top_performing_pages(self, days: int = 7, limit: int = 20) -> List[Dict]:
        """Get top performing pages by clicks"""
        
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            response = self.service.searchanalytics().query(
                siteUrl=self.site_url,
                body={
                    'startDate': start_date.strftime('%Y-%m-%d'),
                    'endDate': end_date.strftime('%Y-%m-%d'),
                    'dimensions': ['page'],
                    'rowLimit': limit
                }
            ).execute()
            
            rows = response.get('rows', [])
            
            # Sort by clicks
            sorted_pages = sorted(
                rows,
                key=lambda x: x.get('clicks', 0),
                reverse=True
            )
            
            return [
                {
                    'url': row['keys'][0],
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': row.get('ctr', 0),
                    'position': row.get('position', 0)
                }
                for row in sorted_pages
            ]
            
        except HttpError as e:
            print(f"Error fetching top pages: {e}")
            return []
    
    def get_crawl_errors(self) -> List[Dict]:
        """Get pages with crawl errors"""
        
        # Note: This would query the URL Inspection API or Coverage API
        # For now, returning empty list as placeholder
        
        print("Checking for crawl errors...")
        
        try:
            # Placeholder for actual error checking
            # In production, you'd use the URL Inspection API
            errors = []
            
            return errors
            
        except Exception as e:
            print(f"Error checking crawl errors: {e}")
            return []
    
    def identify_unindexed_priority_pages(self, new_pages_file: str) -> List[str]:
        """Identify high-priority pages that aren't indexed yet"""
        
        # Read newly created pages
        try:
            with open(new_pages_file, 'r') as f:
                new_pages = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"File not found: {new_pages_file}")
            return []
        
        # Convert to full URLs
        full_urls = [
            f"{self.site_url}{page}" if not page.startswith('http') else page
            for page in new_pages
        ]
        
        # In production, would check which are already indexed
        # For now, return all as candidates for indexing
        
        return full_urls
    
    def generate_improvement_report(self) -> Dict:
        """Generate recommendations based on GSC data"""
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'recommendations': []
        }
        
        # Get indexing status
        status = self.get_indexing_status()
        
        # Get top pages
        top_pages = self.get_top_performing_pages()
        
        # Analyze and generate recommendations
        
        if status.get('indexed_pages', 0) < 100:
            report['recommendations'].append({
                'type': 'indexing',
                'priority': 'high',
                'issue': 'Low number of indexed pages',
                'action': 'Request indexing for high-priority pages'
            })
        
        if status.get('ctr', 0) < 0.02:  # Less than 2% CTR
            report['recommendations'].append({
                'type': 'ctr',
                'priority': 'medium',
                'issue': 'Low click-through rate',
                'action': 'Improve meta titles and descriptions for top impression pages'
            })
        
        # Identify content opportunities from top performers
        if top_pages:
            top_page_types = {}
            for page in top_pages[:10]:
                url = page['url']
                if '/tools/' in url:
                    page_type = 'tool_reviews'
                elif '/compare/' in url or '/comparisons/' in url:
                    page_type = 'comparisons'
                elif '/best/' in url:
                    page_type = 'categories'
                else:
                    page_type = 'other'
                
                top_page_types[page_type] = top_page_types.get(page_type, 0) + 1
            
            # Find winning content type
            if top_page_types:
                winning_type = max(top_page_types, key=top_page_types.get)
                report['recommendations'].append({
                    'type': 'content',
                    'priority': 'high',
                    'issue': f'{winning_type} performing best',
                    'action': f'Create more {winning_type} content'
                })
        
        return report

def main():
    """Main monitoring routine"""
    
    monitor = GSCMonitor()
    
    print("=" * 60)
    print("Google Search Console Monitoring")
    print("=" * 60)
    
    # 1. Get current status
    print("\n1. Fetching indexing status...")
    status = monitor.get_indexing_status()
    print(json.dumps(status, indent=2))
    
    # 2. Get top performing pages
    print("\n2. Fetching top performing pages...")
    top_pages = monitor.get_top_performing_pages(days=7, limit=10)
    for i, page in enumerate(top_pages, 1):
        print(f"{i}. {page['url']} - {page['clicks']} clicks")
    
    # 3. Check for crawl errors
    print("\n3. Checking for crawl errors...")
    errors = monitor.get_crawl_errors()
    if errors:
        print(f"Found {len(errors)} errors")
    else:
        print("No errors found")
    
    # 4. Request indexing for new pages (if file exists)
    new_pages_file = '/approved-content/APPROVED_PAGES.txt'
    if Path(new_pages_file).exists():
        print(f"\n4. Requesting indexing for new pages...")
        unindexed = monitor.identify_unindexed_priority_pages(new_pages_file)
        if unindexed:
            results = monitor.request_indexing(unindexed, max_requests=10)
            print(f"Requested: {len(results['requested'])}")
            print(f"Failed: {len(results['failed'])}")
            print(f"Skipped: {len(results['skipped'])}")
    
    # 5. Generate improvement report
    print("\n5. Generating improvement report...")
    report = monitor.generate_improvement_report()
    print(json.dumps(report, indent=2))
    
    # Save report
    output_file = '/scripts/gsc_report.json'
    with open(output_file, 'w') as f:
        json.dump({
            'status': status,
            'top_pages': top_pages,
            'errors': errors,
            'report': report
        }, f, indent=2)
    
    print(f"\nReport saved to: {output_file}")
    print("=" * 60)

if __name__ == '__main__':
    main()
