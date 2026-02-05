# artificial.one – Automation Implementation Summary

This document summarizes what was created and modified in `/Claude` to adapt the ideal automation system to the **existing** artificial.one site structure.

---

## What Was Created

### 1. `/Claude/config.js`
- **Purpose:** Single source of truth for the automation system.
- **Contents:**
  - **Site:** URL, tagline (“AI Tools Reviewed BY AI”), branding rules (no specific AI product names).
  - **Directories:** `tools/`, `best/`, `compare/`, `guides/`, `tutorials/`, `category/`, blog at root (`blog-*.html`), `images/`.
  - **Affiliate:** Pattern `appsumo.8odi.net`; when to use (lifetime/AppSumo); disclosure text.
  - **Meta:** Title/description length, OG/Twitter patterns, canonical.
  - **Navigation:** Desktop/mobile nav, dropdowns, CTA button, relative paths from `/tools/` (`../`).
  - **Styling:** Tailwind classes used on site (e.g. `bg-gradient-to-r`, score/price badges, CTA box, footer).
  - **QA:** Selectors for CTAs (gradient buttons, `.btn`), email capture, FAQ; schema types; back link.
  - **Sitemap:** Namespace, element names, priorities/changefreq by section (tools 0.9, best/compare 0.9, guides 0.8, blog 0.7, etc.).
  - **Paths:** `REPO_DIR`, `TEMP_CONTENT`, `APPROVED_CONTENT`, `SCRIPTS_DIR`, `APPROVED_PAGES.txt`.
  - **Sheets:** `MASTER_TOOLS_DB`, `QA_REPORT`, `NEEDS_FIXING`, `REVENUE_DASHBOARD`, `GSC_IMPROVEMENTS`.

### 2. `/Claude/templates/` (4 HTML templates)
- **tool_review_template.html**  
  Matches existing tool pages: nav (../), breadcrumb, “Back to All Reviews”, AI transparency badge, optional `{{EMAIL_CAPTURE_BLOCK}}`, header (category, H1, score/price badges, short description), `{{CONTENT_BODY}}`, main CTA box (gradient button + affiliate disclosure), “Explore More AI Tools” box, footer. Placeholders: `{{PAGE_TITLE}}`, `{{META_DESCRIPTION}}`, `{{CANONICAL_URL}}`, `{{OG_IMAGE}}`, `{{KEYWORDS}}`, `{{BREADCRUMB_SCHEMA}}`, `{{FAQ_SCHEMA}}`, `{{CATEGORY_LABEL}}`, `{{TOOL_NAME}}`, `{{SCORE}}`, `{{PRICE}}`, `{{SHORT_DESCRIPTION}}`, `{{AFFILIATE_OR_OFFICIAL_URL}}`, `{{CTA_LABEL}}`.

- **comparison_template.html**  
  Matches compare pages: same nav/dropdowns, breadcrumb “Compare”, AI badge, `{{TOOL_A}}` / `{{TOOL_B}}`, Quick Verdict, two cards, `{{DETAILED_COMPARISON}}`, Explore More. Placeholders: `{{PAGE_TITLE}}`, `{{META_DESCRIPTION}}`, `{{CANONICAL_URL}}`, `{{CATEGORY_LABEL}}`, `{{SHORT_DESCRIPTION}}`, `{{QUICK_VERDICT}}`, `{{TOOL_A_CARD}}`, `{{TOOL_B_CARD}}`, `{{BREADCRUMB_SCHEMA}}`, `{{FAQ_SCHEMA}}`.

- **blog_post_template.html**  
  Simpler blog layout: nav (root-relative), AI badge, optional `{{EMAIL_CAPTURE_BLOCK}}`, H1, lead, `{{CONTENT_BODY}}`, affiliate note (appsumo.8odi.net), footer. Placeholders: `{{PAGE_TITLE}}`, `{{META_DESCRIPTION}}`, `{{CANONICAL_URL}}`, `{{LEAD_PARAGRAPH}}`.

- **category_page_template.html**  
  Matches best/category pages: nav with dropdowns, breadcrumb “Best Of”, AI badge, H1, description, `{{TOOL_CARDS_SECTION}}`, Explore More. Placeholders: `{{PAGE_TITLE}}`, `{{META_DESCRIPTION}}`, `{{CANONICAL_URL}}`, `{{BREADCRUMB_SCHEMA}}`, `{{FAQ_SCHEMA}}`.

All templates use the same styling and “AI Tools Reviewed BY AI” positioning; no specific AI product names in copy.

### 3. `/Claude/n8n_workflow.json`
- **Purpose:** One n8n workflow that can be imported and then extended.
- **Flow (simplified):**  
  Schedule (daily 8 AM) → Read Google Sheets `MASTER_TOOLS_DB` (pending tools) → SplitInBatches (for each tool) → HTTP Request (Claude API tool review) → Write file to `/temp-content/tools/{{slug}}.html` → loop back → when batch done → Execute Command `agent3_quality_assurance.py` → Read `qa_results.json` → If “All Pass?” → Deploy (deploy.sh) / else handle failures.
- **Paths used:** `/root/n8n/scripts/` for QA and deploy; `/temp-content/`, `/approved-content/`. Replace with your VPS paths and set env (e.g. `GOOGLE_SHEET_ID`, Anthropic header auth).
- **Note:** After import, configure credentials (Google Sheets, Anthropic API key), fix any node types/versions for your n8n release, and connect the “All Pass? = false” branch to your Fix workflow or NEEDS_FIXING sheet.

---

## What Was Modified

### 1. `/Claude/agent3_quality_assurance.py`
- **Technical:** Title must include “artificial.one” or “|”; canonical must start with `SITE_URL`; schema and H1 checks kept.
- **Affiliate:** Require `appsumo.8odi.net` only when content is “deal” (lifetime/AppSumo) and path is tool or deal-focused; no hard require on every page.
- **SEO:** Internal links accept relative (e.g. `.html`, `index.html`); minimum internal links 3; H2 minimum 2.
- **Conversion:** CTAs detected by our classes: `bg-gradient-to-r`, `from-purple-600`, `from-indigo-600`, `.btn` (no generic “cta”/“button”). Email capture and FAQ are suggestions only. Affiliate suggestion only for tools/compare/guides when no appsumo link.
- **Paths:** `TEMP_CONTENT_DIR`, `QA_RESULTS_FILE` from env (`TEMP_CONTENT`, `QA_RESULTS_PATH`, `SCRIPTS_DIR`) with defaults `/temp-content` and `/scripts/qa_results.json`.
- **Output:** Same JSON shape; summary line says “artificial.one”.

### 2. `/Claude/update_sitemap.py`
- **Directories:** Uses `tools/`, `best/`, `compare/` (not `comparisons/`), `guides/`, `tutorials/`, `category/`; blog as root-level `blog-*.html`; no `alternatives/`.
- **Skip:** Excludes `Claude/`, `temp-content`, `node_modules`, `.git` when scanning HTML.
- **Priorities/changefreq:** Aligned with existing bands: homepage 1.0/daily; tools, best, compare 0.9/weekly; category, guides 0.8; tutorials, blog 0.7; sitemap.html 0.8; about 0.5; rest 0.5/monthly.
- **Sitemap format:** Same namespace and structure as current `sitemap.xml`: `urlset`, `url`, `loc`, `lastmod`, `changefreq`, `priority`.
- **Site root:** Default `SITE_ROOT` is `os.getcwd()` so it works when run from repo root; override with env for VPS.

---

## What Was Not Changed

- No files outside `/Claude/` were modified (no existing site pages, index, sitemap, or assets).
- `agent6_gsc_monitor.py`, `deploy.sh`, `content_generation_prompts.md`, `initial_tools_list.md`, `01_SETUP_GUIDE.md`, `n8n_workflow_architecture.md`, `README.md` are unchanged except where referenced by config/templates/workflow.

---

## Issues / Inconsistencies Found in Existing Site

1. **Breadcrumb JSON-LD:** Some pages use a backslash in the URL in schema (e.g. `tools\\chatgpt.html`). Templates use correct forward slashes; consider fixing existing pages for consistency.
2. **Email capture:** Current tool and compare pages do not include an email form; templates have optional `{{EMAIL_CAPTURE_BLOCK}}` so you can add Beehiiv (or other) when ready.
3. **Affiliate links:** Many tool reviews link to the product’s official site (e.g. chat.openai.com) rather than appsumo.8odi.net; config and QA only require appsumo for lifetime/AppSumo-focused content.
4. **Compare folder name:** Spec said “comparisons” but the live site uses `compare/`; config and sitemap use `compare/`.
5. **Blog nav:** Some blog pages use a simpler nav (e.g. blog-best-appsumo-deals-2026); blog template matches that style (root-relative links).

---

## Recommendations

1. **Credentials:** In n8n, set `GOOGLE_SHEET_ID`, Anthropic API key (header auth), and optionally GPTZero for AI detection. Point script paths (`/root/n8n/scripts/` or your actual path) in the workflow and in `deploy.sh`.
2. **Content prompts:** Keep using `content_generation_prompts.md`; ensure the tool review prompt instructs the model to output full HTML that fits `tool_review_template.html` (same nav, sections, CTA, appsumo.8odi.net where applicable).
3. **Deploy paths:** In `deploy.sh`, `REPO_DIR` should be the artificial.one repo root; `APPROVED_PAGES.txt` should list paths like `tools/slug.html`, `compare/a-vs-b.html` so files are copied into the correct folders.
4. **Sitemap:** Run `update_sitemap.py` from the repo root (or set `SITE_ROOT`) after adding new pages so `sitemap.xml` stays in sync.
5. **QA pass/fail branch:** In the imported n8n workflow, connect the “All Pass?” false branch to a Google Sheets node (e.g. append to NEEDS_FIXING) or to your Fix workflow; “Append Approved” in the JSON is intended for the pass branch (or move approved logic into deploy).
6. **Fix workflow:** Implement Workflow 3 (Fix & Enhance) as a separate workflow triggered by QA failures, using the same scripts and NEEDS_FIXING sheet as in the architecture doc.

---

## File Checklist

| Item                         | Location                          | Status   |
|-----------------------------|-----------------------------------|----------|
| Config                      | `Claude/config.js`                | Created  |
| QA script (adapted)         | `Claude/agent3_quality_assurance.py` | Modified |
| Sitemap script (adapted)    | `Claude/update_sitemap.py`        | Modified |
| Tool review template        | `Claude/templates/tool_review_template.html` | Created  |
| Comparison template         | `Claude/templates/comparison_template.html`  | Created  |
| Blog template               | `Claude/templates/blog_post_template.html`   | Created  |
| Category template           | `Claude/templates/category_page_template.html`| Created  |
| n8n workflow                | `Claude/n8n_workflow.json`       | Created  |
| This summary                | `Claude/IMPLEMENTATION_SUMMARY.md`| Created  |

All of the above are under `/Claude/` and do not overwrite existing site content.
