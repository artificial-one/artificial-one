# artificial.one

artificial.one is a static AI software discovery and affiliate publishing site. It combines reviews, comparisons, guides and carefully disclosed partner offers.

The current commercial goal is to prove a small number of partner offers end to end—proposal, verification, publication, click attribution and confirmed conversion—before increasing publishing volume.

Current offer state (2026-09-14): Volza and Descript are published as verified partner pages. Runpod is recorded as a draft until its separate account requirement is verified. Private PartnerStack performance baselines live under `.partner-metrics/` and are never committed.

## Site structure

- `tools/` – individual tool reviews
- `compare/` – product comparisons
- `best/`, `guides/`, `tutorials/`, `category/` – discovery content
- `blog-*.html` – root-level articles
- `partners.html` – partner intake page
- `partner-offers.html` and `partner-offers/` – validated, generated commercial pages
- `data/partner_offers.json` – public offer registry
- `scripts/build_partner_offers.py` – offer validation and static page builder
- `assets/affiliate-tracking.js` – privacy-conscious click event adapter
- `Claude/` – experimental n8n content automation package

## Partner offer workflow

Only records explicitly marked `published` are rendered. Published records require editorial approval, recently verified terms, a partner-provided HTTPS tracking URL and source evidence.

```powershell
python scripts/build_partner_offers.py
python scripts/build_partner_offers.py --check
python -m unittest discover -s tests -v
```

See [PARTNER_OFFER_SYSTEM.md](PARTNER_OFFER_SYSTEM.md) for the registry fields, analytics integrations and editorial guardrails.

## Security

Never commit `.env`, `env`, private partner terms, API keys, payment data or raw conversion exports. Public offer data belongs in `data/partner_offers.json`; private commercial records belong in a CRM or the ignored `data/partner_offers.private.json` file.

## Deployment

The site contains plain HTML, JavaScript and image assets and can be deployed to any static host. Run the offer build and its check before deployment. `sitemap.xml` includes a managed partner-offer block updated by the builder.
