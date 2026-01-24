#!/usr/bin/env python3
"""
Add Twitter Card meta tags (twitter:card, twitter:title, twitter:description, twitter:image)
to all pages. X/Twitter uses these for link previews; without them, previews can fail
on some pages (e.g. category pages) while working on others (e.g. tools).
Also escape & as &amp; in meta content to avoid parsing issues.
"""
import re
from pathlib import Path

def extract_page_info(content, filepath):
    """Extract title, description, og:image URL from content."""
    info = {'title': '', 'description': '', 'image': ''}
    m = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if m:
        info['title'] = re.sub(r'\s+', ' ', m.group(1).strip())
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', content, re.IGNORECASE)
    if m:
        info['description'] = m.group(1).strip()
    elif info['title']:
        info['description'] = info['title']
    m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', content, re.IGNORECASE)
    if m:
        info['image'] = m.group(1).strip()
    return info

def get_og_image_url(filepath):
    """OG image URL for page type."""
    base = "https://artificial.one"
    s = str(filepath).replace('\\', '/')
    if filepath.name == 'index.html':
        return f'{base}/images/og-homepage.jpg'
    if '/tools/' in s or filepath.parent.name == 'tools':
        name = filepath.stem.replace('-review', '').replace('-', '-')
        return f'{base}/images/og-tools/{name}.jpg'
    if '/category/' in s or filepath.parent.name == 'category':
        name = filepath.stem.replace('-', '-')
        return f'{base}/images/og-categories/{name}.jpg'
    if filepath.name.startswith('blog-'):
        name = filepath.stem.replace('blog-', '').replace('-', '-')
        return f'{base}/images/og-blog/{name}.jpg'
    if '/compare/' in s:
        return f'{base}/images/og-compare.jpg'
    if '/best/' in s:
        return f'{base}/images/og-best-of.jpg'
    if '/guides/' in s:
        return f'{base}/images/og-guides.jpg'
    return f'{base}/images/og-default.jpg'

def safe_content(text):
    """Escape & <> for use in HTML attribute; keep quotes as-is."""
    if not text:
        return ''
    return (
        text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
    )

def add_twitter_cards_and_fix_entities(content, filepath):
    """Add Twitter Card tags and fix & in OG/meta content."""
    info = extract_page_info(content, filepath)
    img = info['image'] or get_og_image_url(filepath)
    title = safe_content(info['title'])
    desc = safe_content(info['description'])

    twitter_tags = f'''    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{desc}">
    <meta name="twitter:image" content="{img}">'''

    # Fix & in existing og:title, og:description, og:image:alt
    def fix_og_attr(m):
        full, attr, val = m.group(0), m.group(1), m.group(2)
        fixed = safe_content(val)
        return fixed == val and full or f'<meta property="og:{attr}" content="{fixed}" />'
    content = re.sub(
        r'<meta\s+property=["\']og:(title|description|image:alt)["\']\s+content=["\']([^"\']*)["\']\s*/>',
        fix_og_attr,
        content,
        flags=re.IGNORECASE,
    )

    # Fix & in meta name="description" (match trailing > or /> so we don't leave extra >)
    def fix_desc(m):
        val, tail = m.group(1), m.group(2)
        fixed = safe_content(val)
        return f'<meta name="description" content="{fixed}"{tail}>'
    content = re.sub(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\'](\s*/?)>',
        fix_desc,
        content,
        flags=re.IGNORECASE,
    )

    # Already has twitter:card?
    if re.search(r'<meta\s+name=["\']twitter:card["\']', content, re.IGNORECASE):
        # Update existing twitter tags to include image if missing
        if not re.search(r'<meta\s+name=["\']twitter:image["\']', content, re.IGNORECASE):
            content = re.sub(
                r'(<meta\s+name=["\']twitter:description["\'][^>]+>)',
                rf'\1\n    <meta name="twitter:image" content="{img}">',
                content,
                flags=re.IGNORECASE,
                count=1,
            )
        return content

    # Insert Twitter tags after og:image:alt (last og:image:*)
    alt_match = list(re.finditer(r'<meta\s+property=["\']og:image:alt["\'][^>]+>', content, re.IGNORECASE))
    if alt_match:
        pos = alt_match[-1].end()
        content = content[:pos] + '\n' + twitter_tags + content[pos:]
        return content

    # Fallback: after og:image
    img_match = list(re.finditer(r'<meta\s+property=["\']og:image["\'][^>]+>', content, re.IGNORECASE))
    if img_match:
        pos = img_match[-1].end()
        content = content[:pos] + '\n' + twitter_tags + content[pos:]
        return content

    # No OG image; insert before </head>
    if '</head>' in content:
        content = content.replace('</head>', twitter_tags + '\n</head>')
    return content

def process(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read()
        out = add_twitter_cards_and_fix_entities(raw, path)
        if out != raw:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(out)
            return True
    except Exception as e:
        print(f"Error {path}: {e}")
    return False

def main():
    root = Path('.')
    files = [
        p for p in root.rglob('*.html')
        if not any(part.startswith('.') for part in p.parts) and '.git' not in p.parts
    ]
    files.sort()
    print(f"Found {len(files)} HTML files")
    n = 0
    for p in files:
        if process(p):
            n += 1
            if n <= 25:
                print(f"[OK] {p}")
    print(f"\nDone. Updated {n} files.")

if __name__ == '__main__':
    main()
