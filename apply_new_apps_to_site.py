#!/usr/bin/env python3
"""
Apply 57 New AppSumo apps to the site:
- Create detailed review pages
- Add to reviews.html, guides, best-of, blogs, sitemap
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "new_apps_data.json"
TOOLS_DIR = ROOT / "tools"
GUIDES_DIR = ROOT / "guides"
BEST_DIR = ROOT / "best"

REVIEW_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta property="og:title" content="{name} Review 2026: Features, Pricing &amp; AppSumo Lifetime Deal" />
    <meta property="og:description" content="{meta_desc}" />
    <meta property="og:type" content="article" />
    <meta property="og:url" content="https://artificial.one/tools/{slug}-review.html" />
    <meta property="og:image" content="https://artificial.one/images/og-default.jpg" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <link rel="canonical" href="https://artificial.one/tools/{slug}-review.html" />
    <title>{name} Review 2026: Features, Pricing & AppSumo Lifetime Deal</title>
    <meta name="description" content="{meta_desc}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
        header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 60px 20px; text-align: center; }}
        h1 {{ font-size: 2.2em; margin-bottom: 15px; }}
        .rating-box {{ background: white; color: #333; padding: 20px; border-radius: 10px; display: inline-block; margin-top: 20px; }}
        .score {{ font-size: 2.5em; font-weight: 700; color: #667eea; }}
        .quick-verdict {{ background: #f0f7ff; padding: 30px; border-radius: 10px; margin: 30px 0; border-left: 4px solid #667eea; }}
        .pros-cons {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 30px 0; }}
        .pros {{ background: #f0fdf4; padding: 20px; border-radius: 10px; border-left: 4px solid #10b981; }}
        .cons {{ background: #fef2f2; padding: 20px; border-radius: 10px; border-left: 4px solid #ef4444; }}
        .cta-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 10px; text-align: center; margin: 40px 0; }}
        .btn {{ display: inline-block; background: white; color: #667eea; padding: 15px 40px; border-radius: 5px; text-decoration: none; font-weight: 700; font-size: 1.1em; margin-top: 15px; }}
        .btn:hover {{ background: #f0f0f0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
        th {{ background: #f9f9f9; font-weight: 600; }}
        ul {{ margin-left: 20px; line-height: 1.8; }}
        h2 {{ color: #667eea; margin: 40px 0 20px; font-size: 1.8em; }}
        footer {{ background: #333; color: white; text-align: center; padding: 20px; margin-top: 60px; }}
    </style>
</head>
<body>
    <nav style="background: white; border-bottom: 1px solid #e5e7eb; padding: 16px 24px;">
        <div style="max-width: 1000px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center;">
            <a href="../index.html"><img src="../artificial-one-logo-large.svg" alt="artificial.one" style="height: 48px;"></a>
            <div style="display: flex; gap: 20px;">
                <a href="../reviews.html" style="color: #4b5563; text-decoration: none; font-weight: 500;">Reviews</a>
                <a href="../guides/best-lifetime-ai-tools.html" style="color: #4b5563; text-decoration: none; font-weight: 500;">Lifetime Deals</a>
                <a href="../blog.html" style="color: #4b5563; text-decoration: none; font-weight: 500;">Blog</a>
            </div>
        </div>
    </nav>
    <header>
        <div class="container">
            <h1>{name} Review: Complete Guide</h1>
            <div class="rating-box">
                <div class="score">4.5/5</div>
                <p style="margin-top: 10px;">AppSumo lifetime deal</p>
            </div>
        </div>
    </header>
    <div class="container">
        <section>
            <p style="font-size: 1.2em; line-height: 1.8; margin-bottom: 30px;">{desc}</p>
        </section>
        <div class="quick-verdict">
            <h2 style="margin-top: 0; color: #667eea;">Quick Verdict</h2>
            <p style="font-size: 1.1em;">{name} is a solid pick for {bestFor} who want a one-time payment. The AppSumo lifetime deal removes recurring costs and locks in value.</p>
        </div>
        <section>
            <h2>What is {name}?</h2>
            <p>{desc} Get lifetime access via the AppSumo deal—pay once, use forever.</p>
        </section>
        <section>
            <h2>Pricing: Lifetime Deal</h2>
            <p>Get lifetime access to {name} via AppSumo. Pay once, use forever. No monthly fees.</p>
            <div class="cta-box">
                <h2>Get {name} Lifetime Deal</h2>
                <a href="{link}" class="btn" target="_blank" rel="noopener">Get Lifetime Access →</a>
            </div>
        </section>
        <section>
            <h2>Key Features</h2>
            <ul>
                <li>Lifetime access with one-time payment</li>
                <li>No recurring subscription</li>
                <li>{pros_0}</li>
                <li>{pros_1}</li>
            </ul>
        </section>
        <section>
            <h2>Pros and Cons</h2>
            <div class="pros-cons">
                <div class="pros">
                    <h3>✅ Pros</h3>
                    <ul>{pros_ul}</ul>
                </div>
                <div class="cons">
                    <h3>❌ Cons</h3>
                    <ul>{cons_ul}</ul>
                </div>
            </div>
        </section>
        <section>
            <h2>Who is {name} For?</h2>
            <p>{name} is best for <strong>{bestFor}</strong>. If you need {cat_lower} tools without monthly fees, the AppSumo lifetime deal is worth considering.</p>
        </section>
        <div style="text-align: center; margin: 60px 0;">
            <a href="../guides/best-lifetime-ai-tools.html" style="display: inline-block; background: #667eea; color: white; padding: 12px 30px; border-radius: 5px; text-decoration: none; font-weight: 600;">← More AI Lifetime Deals</a>
        </div>
    </div>
    <footer><p>© 2026 artificial.one - {name} Review</p></footer>
</body>
</html>
'''


def escape_js(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def format_review_html(app: dict) -> str:
    name = app["name"].replace("&", "&amp;")
    slug = app["slug"]
    link = app["link"]
    desc = app["desc"]
    best_for = app["bestFor"]
    cat = app["cat"]
    pros = app["pros"]
    cons = app["cons"]
    meta_desc = f"Complete {name} review covering features, pricing, and exclusive AppSumo lifetime deal. {desc[:80]}..."
    pros_0 = pros[0] if len(pros) > 0 else "Lifetime access"
    pros_1 = pros[1] if len(pros) > 1 else "One-time payment"
    pros_ul = "".join(f"<li>{p}</li>" for p in pros)
    cons_ul = "".join(f"<li>{c}</li>" for c in cons)
    cat_lower = cat.lower()
    return REVIEW_TEMPLATE.format(
        name=name,
        slug=slug,
        link=link,
        meta_desc=meta_desc,
        desc=desc,
        bestFor=best_for,
        pros_0=pros_0,
        pros_1=pros_1,
        pros_ul=pros_ul,
        cons_ul=cons_ul,
        cat_lower=cat_lower,
    )


def js_entry(app: dict) -> str:
    name = app["name"].replace('"', '\\"')
    cat = app["cat"]
    desc = escape_js(app["desc"])
    pros = "[" + ", ".join(f'"{escape_js(p)}"' for p in app["pros"]) + "]"
    cons = "[" + ", ".join(f'"{escape_js(c)}"' for c in app["cons"]) + "]"
    best = app["bestFor"].replace('"', '\\"')
    link = app["link"]
    return f'    {{name: "{name}", cat: "{cat}", type: "deal", rating: "4.5", desc: "{desc}", pros: {pros}, cons: {cons}, bestFor: "{best}", pricing: "Lifetime deal", link: "{link}"}}'


def run():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    TOOLS_DIR.mkdir(exist_ok=True)

    # 1. Create review pages
    for app in data:
        html = format_review_html(app)
        path = TOOLS_DIR / f"{app['slug']}-review.html"
        path.write_text(html, encoding="utf-8")
    print(f"Created {len(data)} review pages in tools/")

    # 2. Update reviews.html
    reviews_path = ROOT / "reviews.html"
    content = reviews_path.read_text(encoding="utf-8")
    # Insert new deal entries before "];" that closes tools array.
    # Match ",\n];\nfunction getCategorySlug" so we replace the comma before ]; with ",\n<entries>\n"; avoids double comma.
    new_entries = ",\n" + ",\n".join(js_entry(a) for a in data)
    pat = r',\s*\]\s*;\s*\nfunction getCategorySlug'
    m = re.search(pat, content)
    if m:
        content = content[: m.start()] + new_entries + "\n];\nfunction getCategorySlug" + content[m.end() :]
    reviews_path.write_text(content, encoding="utf-8")
    print("Updated reviews.html")

    # 3. Update best-lifetime-ai-tools: add "57 New Deals" section
    blt = ROOT / "guides" / "best-lifetime-ai-tools.html"
    blt_content = blt.read_text(encoding="utf-8")
    sample = data[:15]
    rows_html = "".join(
        f'                    <tr><td><strong><a href="../tools/{a["slug"]}-review.html">{a["name"]}</a></strong></td><td>{a["bestFor"]}</td><td>Lifetime</td><td>—</td><td>⭐ 4.5/5</td></tr>\n'
        for a in sample
    )
    new_section = (
        '\n        <section style="margin: 40px 0;"><h2 style="margin-bottom: 20px;">57 New AppSumo Deals (2026)</h2>'
        '<p style="margin-bottom: 20px;">Recently added. <a href="../blog-57-new-appsumo-deals-2026.html">Full roundup →</a></p>'
        '<table><thead><tr><th>AI Tool</th><th>Best For</th><th>Lifetime Price</th><th>Rating</th></tr></thead><tbody>\n'
        + rows_html
        + "                </tbody></table></section>"
    )
    # Insert after first </table></section> (Quick Comparison table), before "Detailed Reviews"
    blt_content = re.sub(
        r'(</tbody>\s*</table>\s*</section>\s*)(\s*<section>\s*<h2[^>]*>Detailed Reviews)',
        r"\1" + new_section + r"\2",
        blt_content,
        count=1,
    )
    blt.write_text(blt_content, encoding="utf-8")
    print("Updated best-lifetime-ai-tools.html")

    # 4. Update best-appsumo-ai-deals: add "New" section
    baa = ROOT / "guides" / "best-appsumo-ai-deals.html"
    baa_content = baa.read_text(encoding="utf-8")
    new_list = "".join(
        f'<li><strong><a href="../tools/{a["slug"]}-review.html">{a["name"]}</a></strong> - {a["bestFor"]}</li>\n'
        for a in data[:20]
    )
    new_section = f'<h2>57 New AppSumo Deals (2026)</h2><p>Recently added lifetime deals. <a href="../blog-57-new-appsumo-deals-2026.html">Full roundup →</a></p><ol>{new_list}</ol>'
    baa_content = baa_content.replace(
        "<h2>Top AI Lifetime Deals</h2>",
        new_section + "\n\n<h2>Top AI Lifetime Deals</h2>",
        1,
    )
    baa.write_text(baa_content, encoding="utf-8")
    print("Updated best-appsumo-ai-deals.html")

    # 5. Create guide: best-new-appsumo-deals-2026.html
    guide = ROOT / "guides" / "best-new-appsumo-deals-2026.html"
    by_cat = {}
    for a in data:
        c = a["cat"]
        by_cat.setdefault(c, []).append(a)
    body_parts = ["<h1>57 New AppSumo Deals 2026</h1><p style='font-size:1.1em'>Recently added lifetime deals. Pay once, use forever.</p>"]
    for cat, apps in sorted(by_cat.items()):
        body_parts.append(f"<h2>{cat}</h2><ul>")
        for a in apps:
            s, n, d = a["slug"], a["name"], a["desc"]
            body_parts.append(f'<li><strong><a href="../tools/{s}-review.html">{n}</a></strong> — {d}</li>')
        body_parts.append("</ul>")
    body_parts.append('<div style="text-align:center;margin:40px 0"><a href="best-lifetime-ai-tools.html" style="background:#667eea;color:white;padding:12px 24px;border-radius:8px;text-decoration:none">← All AI Lifetime Deals</a></div>')
    body = "".join(body_parts)
    nav = (ROOT / "guides" / "best-appsumo-ai-deals.html").read_text(encoding="utf-8")
    nav_m = re.search(r"<nav[^>]*>[\s\S]*?</nav>", nav)
    nav_html = nav_m.group(0) if nav_m else ""
    guide.write_text(
        f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>57 New AppSumo Deals 2026 | artificial.one</title><meta name="description" content="57 new AppSumo lifetime deals 2026. AI tools, productivity, design, marketing."><link rel="canonical" href="https://artificial.one/guides/best-new-appsumo-deals-2026.html"></head><body style="font-family:sans-serif;max-width:900px;margin:0 auto;padding:20px">{nav_html}{body}</body></html>',
        encoding="utf-8",
    )
    print("Created guides/best-new-appsumo-deals-2026.html")

    # 6. Create blog: 57 New AppSumo Deals 2026
    blog_path = ROOT / "blog-57-new-appsumo-deals-2026.html"
    blog_nav = open(ROOT / "blog-appsumo-deals.html", "r", encoding="utf-8").read()
    blog_nav = re.search(r"<nav[^>]*>[\s\S]*?</nav>", blog_nav)
    blog_nav = blog_nav.group(0) if blog_nav else ""
    blog_body = """
    <article style="max-width: 720px; margin: 0 auto; padding: 40px 20px;">
        <h1>57 New AppSumo Deals 2026: Best Picks</h1>
        <p style="font-size: 1.1em; color: #666; margin: 20px 0;">AppSumo just added 50+ new lifetime deals. We rounded up the best picks by category—voice, writing, design, data, marketing, and more.</p>
        <h2>Why lifetime deals?</h2>
        <p>Pay once, use forever. No monthly subscriptions. These tools normally charge $20–100/month; with a lifetime deal you lock in access.</p>
        <h2>Top picks by category</h2>
        <ul>
            <li><strong>Voice &amp; Audio:</strong> EasySpeak, Trebble, Clawdia</li>
            <li><strong>Writing:</strong> Editor.do, Wiz Write, Writecream, nichesss</li>
            <li><strong>Design &amp; Images:</strong> DodgePrint, SlideFill, Picbolt, Graficto, Img.Upscaler, Social Media Canva</li>
            <li><strong>Video:</strong> Vibeo, RenderCut, CutMe Short</li>
            <li><strong>Data &amp; Spreadsheets:</strong> Better Sheets, Smart Spreadsheets, Sheetany, Stackby, Columns</li>
            <li><strong>Marketing &amp; Social:</strong> GoEmailTracker, Feedbeo, Pin Generator, Produktly, kiwilaunch, Support Board, More Good Reviews</li>
            <li><strong>Coding &amp; Dev:</strong> Interactive Shell, CodeSmash, NoCodeBackend, NativeRest, Subpage, WP Login Lockdown</li>
            <li><strong>Productivity:</strong> Grain, Trainwel, ApproveThis, UPDF, FlowyTeam, Deftform</li>
        </ul>
        <p>See the <a href="guides/best-new-appsumo-deals-2026.html">full list of 57 new AppSumo deals</a> with links to detailed reviews.</p>
        <p><a href="guides/best-lifetime-ai-tools.html" style="display:inline-block;background:#667eea;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;margin-top:20px;">Browse all AI lifetime deals →</a></p>
    </article>
    """
    blog_full = f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>57 New AppSumo Deals 2026 | artificial.one</title><meta name="description" content="57 new AppSumo lifetime deals in 2026. Best picks for voice, writing, design, data, marketing."></head><body>{blog_nav}{blog_body}<footer style="text-align:center;padding:40px;color:#666;">© 2026 artificial.one</footer></body></html>'
    blog_path.write_text(blog_full, encoding="utf-8")
    print("Created blog-57-new-appsumo-deals-2026.html")

    # 7. Update sitemap
    sitemap = ROOT / "sitemap.xml"
    sm = sitemap.read_text(encoding="utf-8")
    entry_tpl = """  <url>
    <loc>https://artificial.one/tools/{slug}-review.html</loc>
    <lastmod>2026-01-24</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
"""
    new_urls = "".join(entry_tpl.format(slug=a["slug"]) for a in data)
    new_urls += """  <url>
    <loc>https://artificial.one/guides/best-new-appsumo-deals-2026.html</loc>
    <lastmod>2026-01-24</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://artificial.one/blog-57-new-appsumo-deals-2026.html</loc>
    <lastmod>2026-01-24</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
"""
    sm = sm.replace("</urlset>", new_urls + "\n</urlset>")
    sitemap.write_text(sm, encoding="utf-8")
    print("Updated sitemap.xml")

    print("Done.")


if __name__ == "__main__":
    run()
