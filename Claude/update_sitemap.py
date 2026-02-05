#!/usr/bin/env python3
"""
Sitemap Generator and Updater (artificial.one)
Updates sitemap.xml with new pages. Matches existing format: urlset, loc, lastmod, changefreq, priority.
Directories: tools/, best/, compare/, guides/, tutorials/, category/; blog at root (blog-*.html).
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

SITEMAP_NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'


class SitemapUpdater:
    def __init__(self, site_url: str, site_root: str):
        self.site_url = site_url.rstrip('/')
        self.site_root = Path(site_root)
        self.sitemap_path = self.site_root / 'sitemap.xml'
        self.namespace = SITEMAP_NS
        ET.register_namespace('', self.namespace)

    def find_all_html_pages(self) -> List[Path]:
        """Find all HTML pages; skip temp, node_modules, .git, Claude (automation)."""
        html_files = []
        for html_file in self.site_root.rglob('*.html'):
            path_str = str(html_file).replace('\\', '/')
            if any(skip in path_str for skip in ['temp-content', 'node_modules', '.git', '/Claude/', '\\Claude\\']):
                continue
            html_files.append(html_file)
        return html_files

    def get_url_priority(self, file_path: Path) -> Tuple[float, str]:
        """Priority and changefreq for artificial.one structure (match existing 0.5–0.8 bands)."""
        path_str = str(file_path.relative_to(self.site_root)).replace('\\', '/')
        # Homepage
        if path_str == 'index.html':
            return (1.0, 'daily')
        # Tool reviews (high)
        if '/tools/' in path_str:
            return (0.9, 'weekly')
        # Compare pages (folder is "compare" not "comparisons")
        if '/compare/' in path_str:
            return (0.9, 'weekly')
        # Best / category lists
        if '/best/' in path_str:
            return (0.9, 'weekly')
        # Category landing pages
        if '/category/' in path_str:
            return (0.8, 'weekly')
        # Guides
        if '/guides/' in path_str:
            return (0.8, 'weekly')
        # Tutorials
        if '/tutorials/' in path_str:
            return (0.7, 'weekly')
        # Blog at root (blog-*.html)
        if path_str.startswith('blog-') and path_str.endswith('.html'):
            return (0.7, 'weekly')
        # Sitemap, about, other root
        if path_str in ('sitemap.html', 'about.html'):
            return (0.8 if path_str == 'sitemap.html' else 0.5, 'monthly')
        return (0.5, 'monthly')
    
    def create_sitemap(self) -> ET.ElementTree:
        """Create a new sitemap from scratch"""
        
        root = ET.Element('urlset')
        root.set('xmlns', self.namespace)
        
        html_files = self.find_all_html_pages()
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for html_file in html_files:
            # Create URL from file path
            relative_path = html_file.relative_to(self.site_root)
            
            # Convert path to URL
            url_path = str(relative_path).replace('\\', '/')
            if url_path == 'index.html':
                url_path = ''
            elif url_path.endswith('/index.html'):
                url_path = url_path[:-11]  # Remove 'index.html'
            
            full_url = f"{self.site_url}/{url_path}"
            
            # Get priority and changefreq
            priority, changefreq = self.get_url_priority(html_file)
            
            # Create URL element
            url_elem = ET.SubElement(root, 'url')
            
            loc = ET.SubElement(url_elem, 'loc')
            loc.text = full_url
            
            lastmod = ET.SubElement(url_elem, 'lastmod')
            lastmod.text = current_date
            
            changefreq_elem = ET.SubElement(url_elem, 'changefreq')
            changefreq_elem.text = changefreq
            
            priority_elem = ET.SubElement(url_elem, 'priority')
            priority_elem.text = str(priority)
        
        return ET.ElementTree(root)
    
    def update_existing_sitemap(self) -> ET.ElementTree:
        """Update existing sitemap with new pages"""
        
        if not self.sitemap_path.exists():
            print("No existing sitemap found. Creating new one...")
            return self.create_sitemap()
        
        # Parse existing sitemap
        tree = ET.parse(self.sitemap_path)
        root = tree.getroot()
        
        # Get existing URLs
        existing_urls = set()
        for url_elem in root.findall(f'.//{{{self.namespace}}}url'):
            loc = url_elem.find(f'{{{self.namespace}}}loc')
            if loc is not None and loc.text:
                existing_urls.add(loc.text)
        
        # Find all current HTML pages
        html_files = self.find_all_html_pages()
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Add new pages
        added_count = 0
        for html_file in html_files:
            # Create URL from file path
            relative_path = html_file.relative_to(self.site_root)
            url_path = str(relative_path).replace('\\', '/')
            
            if url_path == 'index.html':
                url_path = ''
            elif url_path.endswith('/index.html'):
                url_path = url_path[:-11]
            
            full_url = f"{self.site_url}/{url_path}"
            
            # If URL not in sitemap, add it
            if full_url not in existing_urls:
                priority, changefreq = self.get_url_priority(html_file)
                
                url_elem = ET.SubElement(root, 'url')
                
                loc = ET.SubElement(url_elem, 'loc')
                loc.text = full_url
                
                lastmod = ET.SubElement(url_elem, 'lastmod')
                lastmod.text = current_date
                
                changefreq_elem = ET.SubElement(url_elem, 'changefreq')
                changefreq_elem.text = changefreq
                
                priority_elem = ET.SubElement(url_elem, 'priority')
                priority_elem.text = str(priority)
                
                added_count += 1
        
        print(f"Added {added_count} new URLs to sitemap")
        
        return tree
    
    def save_sitemap(self, tree: ET.ElementTree):
        """Save sitemap to file"""
        
        # Format XML with indentation
        self._indent(tree.getroot())
        
        tree.write(
            self.sitemap_path,
            encoding='utf-8',
            xml_declaration=True
        )
        
        print(f"Sitemap saved to: {self.sitemap_path}")
    
    def _indent(self, elem, level=0):
        """Add indentation to XML for readability"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self._indent(child, level+1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

def main():
    """Main: update sitemap for artificial.one (run from repo root or set SITE_ROOT)."""
    site_url = os.getenv('SITE_URL', 'https://artificial.one')
    site_root = os.getenv('SITE_ROOT', os.getcwd())
    print("=" * 60)
    print("Sitemap Updater (artificial.one)")
    print("=" * 60)
    print("Site URL:", site_url)
    print("Site Root:", site_root)
    print()
    updater = SitemapUpdater(site_url, site_root)
    tree = updater.update_existing_sitemap()
    root = tree.getroot()
    url_count = len(root.findall(f'.//{{{SITEMAP_NS}}}url'))
    print("Total URLs in sitemap:", url_count)
    updater.save_sitemap(tree)
    print("=" * 60)
    print("Sitemap update complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()
