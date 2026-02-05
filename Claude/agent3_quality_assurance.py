#!/usr/bin/env python3
"""
Agent 3: Quality Assurance System (artificial.one)
Tests generated content for quality, SEO, and conversion.
Adapted to match actual site: /tools/, /compare/, /best/, /guides/, blog; Tailwind classes; appsumo.8odi.net.
"""

import os
import sys
import json
import argparse
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import anthropic

load_dotenv()

# artificial.one conventions (match config.js)
SITE_URL = os.getenv('SITE_URL', 'https://artificial.one')
AFFILIATE_DOMAIN = 'appsumo.8odi.net'
TEMP_CONTENT_DIR = os.getenv('TEMP_CONTENT', '/temp-content')
QA_RESULTS_FILE = os.getenv('QA_RESULTS_PATH', os.path.join(os.getenv('SCRIPTS_DIR', '/scripts'), 'qa_results.json'))


class QualityAssurance:
    def __init__(self):
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        self.gptzero_key = os.getenv('GPTZERO_API_KEY', '')
        self.client = anthropic.Anthropic(api_key=self.anthropic_key) if self.anthropic_key else None

    def test_page(self, html_file_path: str) -> Dict:
        """Run comprehensive QA tests on a single page (artificial.one structure)."""
        results = {
            'file': html_file_path,
            'status': 'PASS',
            'issues': [],
            'suggestions': [],
            'scores': {},
        }
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        path_str = str(html_file_path)

        # Test 1: Technical (title, description, H1, schema, canonical)
        tech_issues = self._test_technical(soup, html_content, path_str)
        if tech_issues:
            results['issues'].extend(tech_issues)
            results['status'] = 'FAIL'

        # Test 2: SEO
        seo_score, seo_issues = self._test_seo(soup)
        results['scores']['seo'] = seo_score
        if seo_issues:
            results['issues'].extend(seo_issues)
            if seo_score < 7:
                results['status'] = 'FAIL'

        # Test 3: Content quality (AI) – only if passing so far
        if results['status'] != 'FAIL' and self.client:
            quality_score, quality_issues, suggestions = self._test_content_quality(html_content)
            results['scores']['quality'] = quality_score
            results['suggestions'].extend(suggestions)
            if quality_issues:
                results['issues'].extend(quality_issues)
            if quality_score < 8:
                results['status'] = 'FAIL'

        # Test 4: AI detection (optional)
        if self.gptzero_key and results['status'] != 'FAIL':
            ai_score = self._test_ai_detection(soup.get_text())
            results['scores']['ai_detection'] = ai_score
            if ai_score > 0.35:
                results['issues'].append(f"High AI detection score: {ai_score:.2%}")
                results['status'] = 'FAIL'

        # Test 5: Conversion (artificial.one: gradient CTAs, optional email, affiliate when deal)
        conversion_suggestions = self._test_conversion(soup, path_str)
        results['suggestions'].extend(conversion_suggestions)

        scores = [v for v in results['scores'].values() if isinstance(v, (int, float)) and v <= 10]
        if scores:
            results['scores']['overall'] = round(sum(scores) / len(scores), 1)
        return results

    def _test_technical(self, soup: BeautifulSoup, html: str, path_str: str) -> List[str]:
        """Technical HTML validity – match our meta and schema conventions."""
        issues = []
        title = soup.find('title')
        if not title:
            issues.append("Missing <title> tag")
        else:
            t = title.get_text(strip=True)
            if len(t) > 60:
                issues.append(f"Title too long: {len(t)} chars (max 60)")
            elif len(t) < 30:
                issues.append(f"Title too short: {len(t)} chars (min 30)")
            if 'artificial.one' not in t and '|' not in t:
                issues.append("Title should end with '| artificial.one'")

        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc or not meta_desc.get('content'):
            issues.append("Missing meta description")
        else:
            d = meta_desc['content']
            if len(d) > 160:
                issues.append(f"Meta description too long: {len(d)} chars (max 160)")
            elif len(d) < 120:
                issues.append(f"Meta description too short: {len(d)} chars (min 120)")

        h1 = soup.find('h1')
        if not h1:
            issues.append("Missing H1 tag")
        elif len(soup.find_all('h1')) > 1:
            issues.append("Multiple H1 tags (should be one)")

        if not soup.find('script', type='application/ld+json'):
            issues.append("Missing schema markup (JSON-LD)")

        canonical = soup.find('link', rel='canonical')
        if not canonical or not canonical.get('href'):
            issues.append("Missing canonical URL")
        elif canonical.get('href') and not canonical['href'].startswith(SITE_URL):
            issues.append("Canonical should use " + SITE_URL)

        # Affiliate: require appsumo.8odi.net only when page is about lifetime/AppSumo deals
        affiliate_links = soup.find_all('a', href=lambda x: x and AFFILIATE_DOMAIN in x)
        path_normalized = path_str.replace('\\', '/')
        is_tool_page = '/tools/' in path_normalized
        is_deal_content = 'lifetime' in html.lower() or 'appsumo' in html.lower()
        if is_deal_content and len(affiliate_links) == 0:
            if is_tool_page:
                issues.append("Lifetime-deal / AppSumo tool page should include at least one " + AFFILIATE_DOMAIN + " link")
            else:
                issues.append("Deal-focused page should include " + AFFILIATE_DOMAIN + " where relevant")
        return issues

    def _test_seo(self, soup: BeautifulSoup) -> Tuple[float, List[str]]:
        """SEO: word count, internal links, images alt, H2 structure."""
        score = 10.0
        issues = []
        text = soup.get_text()
        word_count = len(text.split())
        if word_count < 800:
            issues.append(f"Low word count: {word_count} (minimum 800)")
            score -= 2
        internal_links = soup.find_all('a', href=lambda x: x and (x.startswith('/') or '.html' in x or 'index.html' in x))
        if len(internal_links) < 3:
            issues.append(f"Few internal links: {len(internal_links)} (minimum 3)")
            score -= 1
        images = soup.find_all('img')
        no_alt = [i for i in images if not i.get('alt')]
        if no_alt:
            issues.append(f"{len(no_alt)} images missing alt text")
            score -= 1
        h2_count = len(soup.find_all('h2'))
        if h2_count < 2:
            issues.append(f"Few H2 headings: {h2_count} (minimum 2)")
            score -= 1
        return max(score, 0), issues

    def _test_content_quality(self, html_content: str) -> Tuple[float, List[str], List[str]]:
        """AI-powered content quality check."""
        prompt = f"""You are a senior content editor. Review this HTML for artificial.one ("AI Tools Reviewed BY AI").
Score 1-10: content_depth, readability, helpfulness, natural_language, uniqueness.
Output JSON only:
{{"content_depth":8,"readability":9,"helpfulness":7,"natural_language":8,"uniqueness":6,"overall_quality":7.6,"issues":[],"improvements":[]}}
Do not mention specific AI product names in feedback. HTML (excerpt):
{html_content[:8000]}
"""
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            data = json.loads(response_text.strip())
            overall = float(data.get("overall_quality", 7))
            issues = list(data.get("issues", []))
            improvements = list(data.get("improvements", []))
            return overall, issues, improvements
        except Exception as e:
            print(f"Content quality test error: {e}")
            return 7.0, [], ["Could not complete AI quality check"]

    def _test_ai_detection(self, text_content: str) -> float:
        if not self.gptzero_key:
            return 0.0
        try:
            r = requests.post(
                "https://api.gptzero.me/v2/predict/text",
                headers={"Authorization": f"Bearer {self.gptzero_key}", "Content-Type": "application/json"},
                json={"document": text_content[:5000]},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                return float(data.get("documents", [{}])[0].get("completely_generated_prob", 0.0))
        except Exception as e:
            print(f"AI detection error: {e}")
        return 0.0

    def _test_conversion(self, soup: BeautifulSoup, path_str: str) -> List[str]:
        """Conversion: artificial.one uses gradient buttons (no class='cta'); email optional."""
        suggestions = []
        # CTAs: our site uses bg-gradient-to-r, from-purple-600, from-indigo-600, .btn
        cta_candidates = soup.find_all(
            'a',
            class_=lambda x: x
            and (
                'bg-gradient-to-r' in str(x)
                or 'from-purple-600' in str(x)
                or 'from-indigo-600' in str(x)
                or 'btn' in str(x).lower()
            ),
        )
        if len(cta_candidates) < 2:
            suggestions.append(f"Add more primary CTAs (gradient buttons); found {len(cta_candidates)}")

        affiliate_links = soup.find_all('a', href=lambda x: x and AFFILIATE_DOMAIN in x)
        if len(affiliate_links) < 1 and ('tools' in path_str or 'compare' in path_str or 'guide' in path_str.lower()):
            suggestions.append("Consider adding affiliate CTA(s) using " + AFFILIATE_DOMAIN)

        email_inputs = soup.find_all('input', type='email')
        if len(email_inputs) == 0:
            suggestions.append("Consider adding email capture (e.g. Beehiiv) for conversions")

        faq = soup.find(class_=lambda x: x and 'faq' in str(x).lower()) or soup.find('h2', string=lambda s: s and 'FAQ' in (s or ''))
        if not faq:
            suggestions.append("Consider adding FAQ section for SEO and conversions")

        return suggestions


def main():
    parser = argparse.ArgumentParser(description="Agent 3: QA for artificial.one content")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Test only this file (path relative to TEMP_CONTENT, e.g. tools/tool-name.html)",
    )
    args = parser.parse_args()

    temp_dir = Path(TEMP_CONTENT_DIR)
    if not temp_dir.exists():
        print("No temp-content directory found at", TEMP_CONTENT_DIR, file=sys.stderr)
        sys.exit(1)

    qa = QualityAssurance()
    results = []

    if args.file:
        # Single file: path relative to TEMP_CONTENT
        full_path = temp_dir / args.file.replace("\\", "/").lstrip("/")
        if not full_path.exists():
            print(f"File not found: {full_path}", file=sys.stderr)
            sys.exit(1)
        if not full_path.suffix.lower() == ".html":
            print("Only .html files are tested.", file=sys.stderr)
            sys.exit(1)
        print("Testing (single file):", full_path)
        result = qa.test_page(str(full_path))
        # Store relative path for n8n consistency (e.g. tools/tool-name.html)
        result["file"] = args.file.replace("\\", "/").strip("/")
        results = [result]
    else:
        # All files in temp-content
        for html_file in sorted(temp_dir.rglob("*.html")):
            print("Testing:", html_file)
            result = qa.test_page(str(html_file))
            # Store path relative to TEMP_CONTENT when possible
            try:
                result["file"] = str(html_file.relative_to(temp_dir)).replace("\\", "/")
            except ValueError:
                result["file"] = str(html_file)
            results.append(result)

    scripts_dir = Path(QA_RESULTS_FILE).parent
    scripts_dir.mkdir(parents=True, exist_ok=True)
    with open(QA_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total = len(results)
    pct = (passed / total * 100) if total else 0
    print("\n=== QA Results (artificial.one) ===")
    print("Total:", total, "| Passed:", passed, "| Failed:", failed, "| Pass rate:", f"{pct:.1f}%")
    print("Results saved to:", QA_RESULTS_FILE)


if __name__ == "__main__":
    main()
