#!/usr/bin/env python3
"""
Add 50+ New AppSumo apps from tracker to the site:
- Extract New apps from appsumo-affiliate-links-tracker.xlsx
- Add to reviews.html, create detailed review pages, update guides, best-of, blogs, sitemap.
"""

import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCEL = ROOT / "appsumo-affiliate-links-tracker.xlsx"

# Category inference from name/slug keywords
CATEGORY_MAP = {
    "voice": "Voice & Audio",
    "audio": "Voice & Audio",
    "speak": "Voice & Audio",
    "trebble": "Voice & Audio",
    "email": "Marketing & Social",
    "tracker": "Marketing & Social",
    "goemail": "Marketing & Social",
    "proxiedmail": "Marketing & Social",
    "shell": "Coding & Development",
    "code": "Coding & Development",
    "codesmash": "Coding & Development",
    "nocode": "Coding & Development",
    "nativerest": "Coding & Development",
    "wp-login": "Coding & Development",
    "subpage": "Coding & Development",
    "capital": "Data & Analytics",
    "connector": "Data & Analytics",
    "sterling": "Data & Analytics",
    "sheet": "Data & Analytics",
    "spreadsheet": "Data & Analytics",
    "stackby": "Data & Analytics",
    "columns": "Data & Analytics",
    "measuremate": "Data & Analytics",
    "feedbeo": "Marketing & Social",
    "tabby": "Productivity & Business",
    "arvow": "Productivity & Business",
    "trainwel": "Productivity & Business",
    "approvethis": "Productivity & Business",
    "grain": "Productivity & Business",
    "flowyteam": "Productivity & Business",
    "lapsula": "Productivity & Business",
    "dodge": "Design & Images",
    "print": "Design & Images",
    "picbolt": "Design & Images",
    "graficto": "Design & Images",
    "imgupscaler": "Design & Images",
    "imgupscaler": "Design & Images",
    "social-media-canva": "Design & Images",
    "dijibot": "Productivity & Business",
    "editor": "Writing & Content",
    "editordo": "Writing & Content",
    "slidefill": "Design & Images",
    "slide": "Design & Images",
    "vibeo": "Video & Animation",
    "rendercut": "Video & Animation",
    "cutme": "Video & Animation",
    "vizologi": "Research & Data",
    "produktly": "Marketing & Social",
    "kiwilaunch": "Marketing & Social",
    "open-elms": "Productivity & Business",
    "elms": "Productivity & Business",
    "mystrika": "Marketing & Social",
    "spokk": "Marketing & Social",
    "support-board": "Marketing & Social",
    "pin-generator": "Marketing & Social",
    "rtila": "Marketing & Social",
    "nichesss": "Writing & Content",
    "wiz-write": "Writing & Content",
    "writecream": "Writing & Content",
    "wiz write": "Writing & Content",
    "local-rank": "Marketing & Social",
    "seo": "Marketing & Social",
    "more-good-reviews": "Marketing & Social",
    "reviews": "Marketing & Social",
    "updf": "Productivity & Business",
    "pdf": "Productivity & Business",
    "deftform": "Productivity & Business",
    "form": "Productivity & Business",
    "metasurvey": "Research & Data",
    "survey": "Research & Data",
    "cmaps": "Research & Data",
    "nodeland": "Research & Data",
    "anychat": "Marketing & Social",
    "chat": "Marketing & Social",
}

def extract_new_apps():
    """Read Excel and return list of {name, slug, link} for Status=New."""
    with zipfile.ZipFile(EXCEL, "r") as z:
        shared = []
        try:
            with z.open("xl/sharedStrings.xml") as x:
                r = ET.parse(x).getroot()
                ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in r.findall(".//m:si", ns):
                    t = "".join(e.text or "" for e in si.findall(".//m:t", ns))
                    shared.append(t)
        except Exception:
            pass
        sheets = sorted([s for s in z.namelist() if s.startswith("xl/worksheets/sheet")])
        with z.open(sheets[0]) as x:
            r = ET.parse(x).getroot()
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            rows = []
            for row in r.findall(".//m:row", ns):
                rdata = []
                for c in row.findall(".//m:c", ns):
                    v = c.find(".//m:v", ns)
                    val = v.text if v is not None and v.text else None
                    if c.get("t") == "s" and val and shared:
                        try:
                            val = shared[int(val)]
                        except Exception:
                            pass
                    rdata.append(val)
                if any(x is not None for x in rdata):
                    rows.append(rdata)
    headers = [str(h) if h else f"Col{i}" for i, h in enumerate(rows[0])]
    name_col = headers[0]
    slug_col = "Product Slug"
    link_col = "Your Generated Tracking Link"
    status_col = "Status"
    out = []
    for r in rows[1:]:
        row = {}
        for i, h in enumerate(headers):
            row[h] = r[i] if i < len(r) else None
        if not row.get(status_col) or str(row.get(status_col)).strip().lower() != "new":
            continue
        name = (row.get(name_col) or "").strip()
        slug = (row.get(slug_col) or "").strip()
        link = (row.get(link_col) or "").strip()
        if not name or not link:
            continue
        # slug filename: use last part if path-like
        if "/" in slug:
            slug = slug.split("/")[-1]
        slug = re.sub(r"[^\w\-]", "", slug.replace(" ", "-").lower())
        if not slug:
            slug = re.sub(r"[^\w]", "", name.lower())[:30]
        out.append({"name": name, "slug": slug, "link": link})
    return out


def infer_category(name: str, slug: str) -> str:
    n = name.lower()
    s = slug.lower().replace("-", "").replace("_", "")
    combined = n + " " + s
    for k, cat in CATEGORY_MAP.items():
        if k in combined or k in n or k in s:
            return cat
    return "Productivity & Business"


def metadata(name: str, slug: str, cat: str) -> dict:
    """Generate desc, pros, cons, bestFor for a tool."""
    c = cat.lower()
    base = {
        "desc": f"{name} helps teams and solopreneurs with a one-time AppSumo deal.",
        "pros": ["Lifetime access", "One-time payment", "No recurring fees"],
        "cons": ["Newer product", "Check deal terms"],
        "bestFor": "Teams and solo users",
    }
    if "voice" in c or "audio" in c:
        base["desc"] = f"{name} offers voice or audio features with lifetime access via AppSumo."
        base["pros"] = ["Lifetime deal", "Voice/audio features", "Pay once"]
        base["bestFor"] = "Content creators, podcasters"
    elif "writing" in c:
        base["desc"] = f"{name} supports writing and content creation. Get lifetime access on AppSumo."
        base["pros"] = ["Lifetime access", "Writing tools", "No subscription"]
        base["bestFor"] = "Writers, content creators"
    elif "design" in c or "image" in c:
        base["desc"] = f"{name} provides design or image tools. Lifetime deal on AppSumo."
        base["pros"] = ["Lifetime deal", "Design features", "One-time price"]
        base["bestFor"] = "Designers, marketers"
    elif "video" in c:
        base["desc"] = f"{name} helps with video creation or editing. AppSumo lifetime deal available."
        base["pros"] = ["Lifetime access", "Video tools", "Pay once"]
        base["bestFor"] = "Video creators, editors"
    elif "coding" in c:
        base["desc"] = f"{name} supports developers with lifetime access via AppSumo."
        base["pros"] = ["Lifetime deal", "Dev tools", "No monthly fee"]
        base["bestFor"] = "Developers, technical users"
    elif "marketing" in c or "social" in c:
        base["desc"] = f"{name} helps with marketing or social media. Lifetime deal on AppSumo."
        base["pros"] = ["Lifetime access", "Marketing features", "One-time payment"]
        base["bestFor"] = "Marketers, social managers"
    elif "data" in c or "analytics" in c:
        base["desc"] = f"{name} offers data or analytics. Get lifetime access on AppSumo."
        base["pros"] = ["Lifetime deal", "Data features", "No subscription"]
        base["bestFor"] = "Analysts, data-driven teams"
    elif "research" in c:
        base["desc"] = f"{name} supports research and surveys. AppSumo lifetime deal."
        base["pros"] = ["Lifetime access", "Research tools", "Pay once"]
        base["bestFor"] = "Researchers, survey creators"
    return base


def main():
    os.chdir(ROOT)
    apps = extract_new_apps()
    print(f"Found {len(apps)} New apps")
    data = []
    for a in apps:
        cat = infer_category(a["name"], a["slug"])
        m = metadata(a["name"], a["slug"], cat)
        data.append({
            "name": a["name"],
            "slug": a["slug"],
            "link": a["link"],
            "cat": cat,
            **m,
        })
    out_path = ROOT / "new_apps_data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {out_path}")
    return data


if __name__ == "__main__":
    main()
