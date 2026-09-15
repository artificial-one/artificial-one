#!/usr/bin/env python3
"""Build the self-service sponsorship storefront and paid-customer intake."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from scripts.build_partner_offers import esc, shell
except ModuleNotFoundError:
    from build_partner_offers import esc, shell  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "data" / "sponsorship_inventory.json"
SITEMAP_PATH = ROOT / "sitemap.xml"
SITEMAP_START = "  <!-- sponsorship:start -->"
SITEMAP_END = "  <!-- sponsorship:end -->"


def load_inventory() -> dict[str, Any]:
    value = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    if value.get("version") != 1 or not isinstance(value.get("packages"), list):
        raise ValueError("Sponsorship inventory must be version 1 with packages")
    ids: set[str] = set()
    for item in value["packages"]:
        if not isinstance(item, dict) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(item.get("id") or "")):
            raise ValueError("Every sponsorship package requires a safe id")
        if item["id"] in ids or int(item.get("price_cents") or 0) <= 0:
            raise ValueError("Sponsorship package ids must be unique and prices positive")
        ids.add(item["id"])
    return value


def render_store(inventory: dict[str, Any]) -> str:
    enabled = bool(inventory.get("checkout_enabled"))
    cards: list[str] = []
    for item in inventory["packages"]:
        price = f"${int(item['price_cents']) / 100:,.0f}"
        button = f'<button type="button" data-package="{esc(item["id"])}" class="checkout mt-6 w-full rounded-xl bg-indigo-600 px-5 py-3 font-black text-white">Book securely — {price}</button>' if enabled else '<a href="mailto:hello@artificial.one?subject=Sponsorship%20availability" class="mt-6 block rounded-xl border border-indigo-200 px-5 py-3 text-center font-black text-indigo-700">Ask about availability</a>'
        cards.append(f'''<article class="flex flex-col rounded-3xl border border-slate-200 bg-white p-7 shadow-sm"><p class="text-xs font-bold uppercase tracking-widest text-indigo-600">Clearly labelled sponsorship</p><h2 class="mt-3 text-2xl font-black">{esc(item['name'])}</h2><p class="mt-3 text-slate-600">{esc(item['description'])}</p><p class="mt-4 text-sm text-slate-500">{esc(item['fulfillment'])}</p><p class="mt-auto pt-6 text-3xl font-black">{price}</p>{button}</article>''')
    content = f'''<section class="bg-white"><div class="mx-auto max-w-6xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-indigo-600">For AI companies</p><h1 class="mt-4 text-4xl font-black md:text-6xl">Sponsor a useful software decision</h1><p class="mt-5 max-w-3xl text-lg text-slate-600">Reach readers comparing AI and business software through placements that are disclosed, relevant and kept separate from editorial rankings.</p></div></section><section class="mx-auto grid max-w-6xl gap-6 px-5 py-10 md:grid-cols-3">{''.join(cards)}</section><section class="mx-auto max-w-4xl px-5 py-12"><h2 class="text-3xl font-black">Standards</h2><ul class="mt-5 list-disc space-y-3 pl-6 text-slate-700"><li>Every placement is labelled sponsored.</li><li>Payment does not buy a positive review or ranking.</li><li>Unsupported claims, impersonation and prohibited products are rejected and refunded.</li><li>Audience and delivery reporting uses aggregate data only.</li></ul><p id="checkout-status" class="mt-6 font-semibold text-rose-700" role="status"></p></section><script>document.querySelectorAll('.checkout').forEach(function(button){{button.addEventListener('click',async function(){{button.disabled=true;document.getElementById('checkout-status').textContent='Opening secure checkout…';try{{var response=await fetch('/api/sponsor-checkout',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{package_id:button.dataset.package}})}}),data=await response.json();if(!response.ok||!data.url)throw new Error(data.error||'Checkout unavailable');location.href=data.url;}}catch(error){{document.getElementById('checkout-status').textContent=error.message;button.disabled=false;}}}});}});</script>'''
    return shell(title="Sponsor artificial.one | AI Software Audience", description="Book a clearly labelled artificial.one newsletter, category or launch sponsorship.", canonical_path="sponsor.html", content=content, structured_data={"@context": "https://schema.org", "@type": "WebPage", "name": "Sponsor artificial.one"})


def render_success() -> str:
    content = '''<section class="bg-white"><div class="mx-auto max-w-3xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-emerald-600">Payment received</p><h1 class="mt-4 text-4xl font-black">Submit your sponsorship details</h1><p class="mt-4 text-slate-600">This form verifies the paid Stripe session before accepting your brief.</p><form id="intake" class="mt-8 grid gap-5 rounded-3xl border border-slate-200 p-7"><label class="font-bold">Your name<input name="name" maxlength="80" required class="mt-2 w-full rounded-xl border border-slate-300 p-3"></label><label class="font-bold">Company<input name="company" maxlength="100" required class="mt-2 w-full rounded-xl border border-slate-300 p-3"></label><label class="font-bold">Email<input name="email" type="email" maxlength="180" required class="mt-2 w-full rounded-xl border border-slate-300 p-3"></label><label class="font-bold">Product URL<input name="product_url" type="url" maxlength="500" required class="mt-2 w-full rounded-xl border border-slate-300 p-3"></label><label class="font-bold">Factual brief and source links<textarea name="brief" maxlength="3000" required rows="7" class="mt-2 w-full rounded-xl border border-slate-300 p-3"></textarea></label><button class="rounded-xl bg-indigo-600 px-6 py-3 font-black text-white">Submit paid brief</button><p id="status" role="status"></p></form></div></section><script>(function(){var form=document.getElementById('intake'),status=document.getElementById('status'),session=new URLSearchParams(location.search).get('session_id')||'';form.addEventListener('submit',async function(event){event.preventDefault();status.textContent='Verifying payment…';var data=Object.fromEntries(new FormData(form).entries());data.session_id=session;try{var response=await fetch('/api/sponsor-intake',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),body=await response.json();if(!response.ok)throw new Error(body.error||'Submission failed');form.innerHTML='<h2 class="text-2xl font-black">Brief received</h2><p class="mt-3 text-slate-600">We sent the submission to the artificial.one publishing queue.</p>';}catch(error){status.textContent=error.message;}});})();</script>'''
    return shell(title="Sponsorship intake | artificial.one", description="Secure post-payment sponsorship intake.", canonical_path="sponsor-success.html", content=content).replace("</head>", '  <meta name="robots" content="noindex,nofollow">\n</head>')


def update_sitemap(source: str, lastmod: str) -> str:
    row = f"{SITEMAP_START}\n  <url><loc>https://artificial.one/sponsor.html</loc><lastmod>{lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>\n{SITEMAP_END}"
    if SITEMAP_START in source and SITEMAP_END in source:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), row, source, flags=re.S)
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + row + "\n</urlset>\n"


def build(check: bool = False) -> int:
    inventory = load_inventory()
    outputs = {ROOT / "sponsor.html": render_store(inventory), ROOT / "sponsor-success.html": render_success()}
    sitemap = SITEMAP_PATH.read_text(encoding="utf-8")
    expected_sitemap = update_sitemap(sitemap, str(inventory.get("updated_at") or date.today().isoformat()))
    stale = [path for path, text in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    if check:
        if stale or sitemap != expected_sitemap:
            print("Sponsorship storefront is stale.", file=sys.stderr)
            return 1
        print("Sponsorship storefront is current.")
        return 0
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
    SITEMAP_PATH.write_text(expected_sitemap, encoding="utf-8")
    print(f"Built sponsorship storefront; checkout {'enabled' if inventory.get('checkout_enabled') else 'safely disabled'}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return build(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
