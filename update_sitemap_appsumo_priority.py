"""
Update sitemap.xml: set priority=0.9 and changefreq=weekly for all tool review
pages that contain AppSumo affiliate links (appsumo.8odi.net).
"""
import os
import re

TOOLS_DIR = "tools"
SITEMAP = "sitemap.xml"

def get_appsumo_tool_slugs():
    slugs = set()
    for name in os.listdir(TOOLS_DIR):
        if not name.endswith("-review.html"):
            continue
        path = os.path.join(TOOLS_DIR, name)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                if "appsumo.8odi.net" in f.read():
                    slug = name.replace("-review.html", "")
                    slugs.add(slug)
        except Exception:
            pass
    return slugs

def main():
    slugs = get_appsumo_tool_slugs()
    print(f"Found {len(slugs)} AppSumo tool review pages")

    with open(SITEMAP, "r", encoding="utf-8") as f:
        content = f.read()

    # For each AppSumo tool URL, replace changefreq and priority (any current values)
    count = 0
    for slug in sorted(slugs):
        pattern = (
            f"(<loc>https://artificial\\.one/tools/{re.escape(slug)}\\-review\\.html</loc>\\s*"
            "<lastmod>[^<]+</lastmod>\\s*"
            ")<changefreq>[^<]+</changefreq>\\s*<priority>[^<]+</priority>"
        )
        replacement = r"\1<changefreq>weekly</changefreq>\n    <priority>0.9</priority>"
        new_content, n = re.subn(pattern, replacement, content)
        if n:
            content = new_content
            count += n

    with open(SITEMAP, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Updated {count} URL blocks in sitemap.xml")

if __name__ == "__main__":
    main()
