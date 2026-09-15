#!/usr/bin/env python3
"""Build interactive decision tools that route high-intent visitors to offers."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from scripts.build_partner_offers import (
        apply_revenue_strategy,
        esc,
        load_registry,
        public_offers,
        shell,
        validate_registry,
    )
except ModuleNotFoundError:
    from build_partner_offers import (  # type: ignore
        apply_revenue_strategy,
        esc,
        load_registry,
        public_offers,
        shell,
        validate_registry,
    )


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "partner_offers.json"
SITEMAP_PATH = ROOT / "sitemap.xml"
SITEMAP_START = "  <!-- decision-tools:start -->"
SITEMAP_END = "  <!-- decision-tools:end -->"


CALCULATORS = (
    {
        "slug": "ai-software-roi-calculator",
        "title": "AI Software ROI Calculator",
        "description": "Estimate the monthly value, net return and break-even point of an AI software subscription.",
        "fields": (
            ("hours", "Hours spent on the workflow each week", 10, 0, 200, 1),
            ("rate", "Hourly cost ($)", 35, 0, 500, 1),
            ("saving", "Expected time saving (%)", 25, 0, 90, 1),
            ("cost", "Monthly software cost ($)", 49, 0, 5000, 1),
        ),
        "formula": "var gross=v.hours*4.33*v.rate*(v.saving/100),net=gross-v.cost,months=gross>0?v.cost/gross:0;return {primary:money(net),label:'Estimated net monthly value',detail:'Gross time value '+money(gross)+'; estimated payback '+(months||0).toFixed(1)+' months.'};",
        "offer_terms": ("productivity", "automation", "business", "marketing"),
    },
    {
        "slug": "pdf-workflow-cost-calculator",
        "title": "PDF Workflow Cost Calculator",
        "description": "Estimate what repetitive PDF editing, signing and document handling costs each month.",
        "fields": (
            ("documents", "Documents handled each month", 120, 0, 100000, 10),
            ("minutes", "Minutes spent per document", 8, 0, 240, 1),
            ("rate", "Hourly cost ($)", 35, 0, 500, 1),
            ("saving", "Potential time saving (%)", 35, 0, 90, 1),
        ),
        "formula": "var current=v.documents*v.minutes/60*v.rate,saved=current*(v.saving/100);return {primary:money(saved),label:'Potential monthly time value',detail:'Current estimated handling cost '+money(current)+'. Compare this value with the live subscription price.'};",
        "offer_terms": ("document", "pdf", "signature"),
    },
    {
        "slug": "voice-production-cost-calculator",
        "title": "AI Voice Production Cost Calculator",
        "description": "Compare an existing voice-production workflow with an estimated AI-assisted workflow.",
        "fields": (
            ("minutes", "Finished audio minutes each month", 180, 0, 100000, 10),
            ("manual", "Current cost per finished minute ($)", 8, 0, 1000, 0.5),
            ("ai", "Estimated AI cost per minute ($)", 1, 0, 1000, 0.1),
            ("review", "Editing and review overhead (%)", 20, 0, 200, 1),
        ),
        "formula": "var current=v.minutes*v.manual,assisted=v.minutes*v.ai*(1+v.review/100),saved=current-assisted;return {primary:money(saved),label:'Estimated monthly difference',detail:'Current '+money(current)+' versus AI-assisted '+money(assisted)+'. Verify quality and plan limits before deciding.'};",
        "offer_terms": ("audio", "voice", "video"),
    },
    {
        "slug": "landing-page-roi-calculator",
        "title": "Landing Page ROI Calculator",
        "description": "Estimate the revenue effect of a conversion-rate change before paying for another landing-page tool.",
        "fields": (
            ("visits", "Monthly landing-page visits", 5000, 0, 10000000, 100),
            ("current", "Current conversion rate (%)", 2, 0, 100, 0.1),
            ("target", "Target conversion rate (%)", 2.5, 0, 100, 0.1),
            ("value", "Value per conversion ($)", 80, 0, 1000000, 1),
            ("cost", "Additional monthly tool cost ($)", 99, 0, 100000, 1),
        ),
        "formula": "var extra=v.visits*Math.max(0,v.target-v.current)/100*v.value,net=extra-v.cost;return {primary:money(net),label:'Estimated net monthly upside',detail:'Additional gross value '+money(extra)+' after '+money(v.cost)+' tool cost. This is a scenario, not a performance promise.'};",
        "offer_terms": ("conversion", "marketing", "advert", "analytics"),
    },
)


def safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def offer_card(offer: dict[str, Any], placement: str, prefix: str = "") -> str:
    return f'''<article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p class="text-xs font-bold uppercase tracking-widest text-indigo-600">{esc(offer['category'])}</p>
      <h3 class="mt-2 text-xl font-black">{esc(offer['name'])}</h3>
      <p class="mt-2 text-sm text-slate-600">{esc(offer['best_for'])}</p>
      <div class="mt-4 flex flex-wrap gap-3"><a href="{prefix}partner-offers/{esc(offer['slug'])}.html" class="font-bold text-indigo-700">Review fit</a><a href="{esc(offer['tracking_url'])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer="" data-offer-id="{esc(offer['id'])}" data-placement="{esc(placement)}" class="font-bold text-purple-700">{esc(offer['cta_label'])} →</a></div>
    </article>'''


def cluster(category: str) -> str:
    value = category.casefold()
    if any(term in value for term in ("audio", "video", "voice", "design", "presentation", "website")):
        return "content"
    if any(term in value for term in ("marketing", "conversion", "sales", "seo")):
        return "growth"
    if any(term in value for term in ("document", "pdf", "signature")):
        return "documents"
    if any(term in value for term in ("data", "database", "developer", "research")):
        return "data"
    return "operations"


def render_stack_builder(offers: list[dict[str, Any]]) -> str:
    payload = [
        {
            "id": item["id"], "name": item["name"], "category": item["category"],
            "cluster": cluster(str(item["category"])), "summary": item["summary"],
            "best_for": item["best_for"], "use_cases": item["use_cases"],
            "slug": item["slug"], "tracking_url": item["tracking_url"],
            "cta_label": item["cta_label"], "rank": index,
        }
        for index, item in enumerate(offers)
    ]
    content = '''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16">
      <p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Free decision tool</p>
      <h1 class="mt-4 text-4xl font-black md:text-6xl">Build your AI software stack</h1>
      <p class="mt-5 max-w-3xl text-lg text-slate-600">Describe the job, team and buying priority. The tool scores our verified catalog and returns three practical options. No account is required.</p>
      <form id="stack-form" class="mt-9 grid gap-5 rounded-3xl border border-indigo-100 bg-indigo-50 p-6 md:grid-cols-2">
        <label class="font-bold">Primary goal<select id="goal" class="mt-2 w-full rounded-xl border border-slate-300 bg-white p-3"><option value="content">Create content</option><option value="growth">Grow traffic or sales</option><option value="documents">Handle documents</option><option value="data">Research or build with data</option><option value="operations">Run a team or operation</option></select></label>
        <label class="font-bold">Team context<select id="team" class="mt-2 w-full rounded-xl border border-slate-300 bg-white p-3"><option value="individual">Individual or creator</option><option value="team">Small team</option><option value="enterprise">Larger organization</option></select></label>
        <label class="font-bold md:col-span-2">What must the tool help you do?<input id="need" maxlength="120" class="mt-2 w-full rounded-xl border border-slate-300 bg-white p-3" placeholder="Example: turn podcast interviews into short videos"></label>
        <label class="font-bold">Buying priority<select id="priority" class="mt-2 w-full rounded-xl border border-slate-300 bg-white p-3"><option value="fit">Best workflow fit</option><option value="simple">Easy to evaluate</option><option value="scale">Built for repeat use</option></select></label>
        <button class="self-end rounded-xl bg-indigo-600 px-6 py-3 font-black text-white hover:bg-indigo-700" type="submit">Build my shortlist</button>
      </form>
      <p class="mt-4 text-xs text-slate-500">Recommendations are based on the selected workflow and reviewed product descriptions. We may earn a commission from marked links.</p>
    </div></section><section class="mx-auto max-w-5xl px-5 py-10"><div id="stack-results" aria-live="polite"><h2 class="text-3xl font-black">Your recommendations will appear here</h2></div></section>'''
    script = f'''<script id="offer-data" type="application/json">{safe_json(payload)}</script><script>
    (function(){{
      var offers=JSON.parse(document.getElementById('offer-data').textContent);
      var form=document.getElementById('stack-form'),results=document.getElementById('stack-results');
      function words(value){{return (value.toLowerCase().match(/[a-z0-9]+/g)||[]).filter(function(x){{return x.length>2;}});}}
      function escHtml(value){{var d=document.createElement('div');d.textContent=value;return d.innerHTML;}}
      function render(event){{if(event)event.preventDefault();var goal=document.getElementById('goal').value,team=document.getElementById('team').value,need=document.getElementById('need').value,query=words(need),priority=document.getElementById('priority').value;
        var ranked=offers.map(function(o){{var hay=words([o.name,o.category,o.summary,o.best_for,o.use_cases.join(' ')].join(' ')),score=o.cluster===goal?25:0;query.forEach(function(w){{if(hay.indexOf(w)>=0)score+=5;}});if(team==='enterprise'&&/team|business|enterprise|organization/i.test(o.best_for))score+=4;if(team==='individual'&&/creator|individual|freelancer|practitioner/i.test(o.best_for))score+=4;if(priority==='scale'&&/team|business|enterprise|repeat/i.test(o.best_for+' '+o.summary))score+=3;score-=o.rank/100;return {{offer:o,score:score}};}}).sort(function(a,b){{return b.score-a.score;}}).slice(0,3);
        var cards=ranked.map(function(x,i){{var o=x.offer,placement='stack-builder-'+(i+1);return '<article class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><p class="text-xs font-bold uppercase tracking-widest text-indigo-600">'+escHtml(o.category)+'</p><h3 class="mt-2 text-2xl font-black">'+escHtml(o.name)+'</h3><p class="mt-3 text-slate-600">'+escHtml(o.summary)+'</p><p class="mt-3 text-sm"><strong>Best for:</strong> '+escHtml(o.best_for)+'</p><div class="mt-5 flex flex-wrap gap-3"><a class="rounded-xl border border-indigo-200 px-5 py-3 font-bold text-indigo-700" href="partner-offers/'+encodeURIComponent(o.slug)+'.html">Read decision guide</a><a class="rounded-xl bg-indigo-600 px-5 py-3 font-bold text-white" href="'+escHtml(o.tracking_url)+'" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="'+escHtml(o.id)+'" data-placement="'+placement+'">'+escHtml(o.cta_label)+' →</a></div></article>';}}).join('');
        results.innerHTML='<h2 class="text-3xl font-black">Your three-tool shortlist</h2><p class="mt-2 text-slate-600">Compare fit and current pricing before subscribing.</p><div class="mt-6 grid gap-6 md:grid-cols-3">'+cards+'</div>';var shareParams=new URLSearchParams(location.search);shareParams.set('goal',goal);shareParams.set('team',team);history.replaceState(null,'',location.pathname+'?'+shareParams.toString());window.scrollTo({{top:results.offsetTop-90,behavior:'smooth'}});
      }}
      form.addEventListener('submit',render);var params=new URLSearchParams(location.search);if(params.get('goal')){{document.getElementById('goal').value=params.get('goal');document.getElementById('team').value=params.get('team')||'individual';render();}}
    }})();</script>'''
    return shell(
        title="AI Stack Builder: Find the Right AI Tools | artificial.one",
        description="Build a personalized three-tool AI software shortlist by workflow, team context and buying priority.",
        canonical_path="ai-stack-builder.html", content=content + script,
        social_image="https://artificial.one/images/social-cards/ai-stack-builder.jpg",
        social_image_alt="Build a personalized AI software shortlist — free decision tool from Artificial.One",
        structured_data={"@context": "https://schema.org", "@type": "WebApplication", "name": "artificial.one AI Stack Builder", "applicationCategory": "BusinessApplication", "operatingSystem": "Web", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    )


def matching_offers(offers: list[dict[str, Any]], terms: tuple[str, ...], limit: int = 4) -> list[dict[str, Any]]:
    matched = [item for item in offers if any(term in str(item["category"]).casefold() for term in terms)]
    return (matched or offers)[:limit]


def render_calculator(spec: dict[str, Any], offers: list[dict[str, Any]]) -> str:
    fields = "".join(
        f'<label class="font-bold">{esc(label)}<input class="calc-input mt-2 w-full rounded-xl border border-slate-300 p-3" id="{esc(key)}" type="number" value="{value}" min="{minimum}" max="{maximum}" step="{step}"></label>'
        for key, label, value, minimum, maximum, step in spec["fields"]
    )
    cards = "\n".join(offer_card(item, f"calculator-{spec['slug']}", "../") for item in matching_offers(offers, spec["offer_terms"]))
    keys = [item[0] for item in spec["fields"]]
    values = ",".join(f"{key}:num('{key}')" for key in keys)
    script = f'''<script>(function(){{function num(id){{var el=document.getElementById(id),n=Number(el.value);return Number.isFinite(n)?Math.max(Number(el.min)||0,Math.min(Number(el.max)||1e12,n)):0;}}function money(n){{return new Intl.NumberFormat('en-US',{{style:'currency',currency:'USD',maximumFractionDigits:0}}).format(n);}}function update(){{var v={{{values}}};var r=(function(v){{{spec['formula']}}})(v);document.getElementById('result-value').textContent=r.primary;document.getElementById('result-label').textContent=r.label;document.getElementById('result-detail').textContent=r.detail;}}document.querySelectorAll('.calc-input').forEach(function(x){{x.addEventListener('input',update);}});update();}})();</script>'''
    content = f'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Free calculator</p><h1 class="mt-4 text-4xl font-black md:text-6xl">{esc(spec['title'])}</h1><p class="mt-5 max-w-3xl text-lg text-slate-600">{esc(spec['description'])}</p><div class="mt-9 grid gap-5 rounded-3xl border border-indigo-100 bg-indigo-50 p-6 md:grid-cols-2">{fields}</div><div class="mt-6 rounded-3xl bg-slate-900 p-7 text-white"><p id="result-label" class="text-sm font-bold uppercase tracking-widest text-indigo-300"></p><p id="result-value" class="mt-2 text-5xl font-black"></p><p id="result-detail" class="mt-3 text-slate-300"></p></div><p class="mt-4 text-xs text-slate-500">Illustrative estimate only. Results depend entirely on your inputs and are not a performance promise.</p></div></section><section class="mx-auto max-w-5xl px-5 py-10"><h2 class="text-3xl font-black">Tools relevant to this calculation</h2><div class="mt-6 grid gap-5 md:grid-cols-2">{cards}</div></section>{script}'''
    return shell(
        title=f"{spec['title']} | Free Tool | artificial.one", description=spec["description"],
        canonical_path=f"calculators/{spec['slug']}.html", content=content, prefix="../",
        social_image=f"https://artificial.one/images/social-cards/{spec['slug'].replace('-calculator', '')}.jpg",
        social_image_alt=f"{spec['title']} — free decision tool from Artificial.One",
        structured_data={"@context": "https://schema.org", "@type": "WebApplication", "name": spec["title"], "applicationCategory": "BusinessApplication", "operatingSystem": "Web", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    )


def render_hub() -> str:
    cards = "".join(f'<a class="block rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:border-indigo-300" href="calculators/{esc(item["slug"])}.html"><h2 class="text-2xl font-black">{esc(item["title"])}</h2><p class="mt-2 text-slate-600">{esc(item["description"])}</p><span class="mt-4 inline-block font-bold text-indigo-700">Open calculator →</span></a>' for item in CALCULATORS)
    content = f'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Free buying tools</p><h1 class="mt-4 text-4xl font-black md:text-6xl">Make a better AI software decision</h1><p class="mt-5 max-w-3xl text-lg text-slate-600">Turn workflow requirements into a shortlist, then test whether the economics make sense.</p><a href="ai-stack-builder.html" class="mt-7 inline-block rounded-xl bg-indigo-600 px-6 py-3 font-black text-white">Build my AI stack →</a></div></section><section class="mx-auto grid max-w-5xl gap-6 px-5 py-10 md:grid-cols-2">{cards}</section>'''
    return shell(title="Free AI Tool Calculators and Stack Builder | artificial.one", description="Use free calculators and a guided AI stack builder to compare software fit and economics.", canonical_path="decision-tools.html", content=content, structured_data={"@context": "https://schema.org", "@type": "CollectionPage", "name": "artificial.one decision tools"})


def update_sitemap(source: str, paths: list[Path], lastmod: str) -> str:
    rows = [SITEMAP_START]
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        rows.append(f"  <url><loc>https://artificial.one/{relative}</loc><lastmod>{lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>")
    rows.append(SITEMAP_END)
    block = "\n".join(rows)
    if SITEMAP_START in source and SITEMAP_END in source:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), block, source, flags=re.S)
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + block + "\n</urlset>\n"


def planned_pages(offers: list[dict[str, Any]]) -> dict[Path, str]:
    pages = {ROOT / "ai-stack-builder.html": render_stack_builder(offers), ROOT / "decision-tools.html": render_hub()}
    pages.update({ROOT / "calculators" / f"{spec['slug']}.html": render_calculator(spec, offers) for spec in CALCULATORS})
    return pages


def build(check: bool = False) -> int:
    registry = load_registry(REGISTRY_PATH)
    offers = apply_revenue_strategy(public_offers(validate_registry(registry), date.today()))
    pages = planned_pages(offers)
    sitemap = SITEMAP_PATH.read_text(encoding="utf-8")
    expected_sitemap = update_sitemap(sitemap, list(pages), str(registry["updated_at"]))
    stale = [path for path, value in pages.items() if not path.exists() or path.read_text(encoding="utf-8") != value]
    if check:
        if stale or sitemap != expected_sitemap:
            print("Decision tools are stale.", file=sys.stderr)
            return 1
        print(f"Decision tools are current ({len(pages)} pages).")
        return 0
    for path, value in pages.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    SITEMAP_PATH.write_text(expected_sitemap, encoding="utf-8")
    print(f"Built {len(pages)} decision-tool pages.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return build(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
