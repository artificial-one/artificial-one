# Partner Offer System

This is the commercial publishing loop for artificial.one. It converts an approved partner proposal into transparent, measurable static pages without allowing unreviewed submissions to publish themselves.

## The loop

1. A partner submits a structured brief through `partners.html`.
2. The offer, claims, dates, tracking link and evidence are checked outside the public repository.
3. An editor adds the approved public fields to `data/partner_offers.json` with `status: "published"`.
4. `scripts/build_partner_offers.py` validates the record and builds the offer hub, individual offer pages and the managed sitemap block.
5. CTA clicks emit an `affiliate_click` event with `offer_id`, `placement`, `page_path` and timestamp.
6. Conversion reports are matched to the partner's tracking URL outside the public repository. Winning placements can then be expanded; expired or weak offers can be paused.

On `main`, `.github/workflows/partner-offers.yml` reruns the safety tests, rebuilds approved pages and commits generated output whenever the public registry or builder changes. It also runs daily so expired offers are automatically retired. Pull requests must contain current generated output before they can pass.

The public registry must never contain commission percentages, account contacts, contracts, API keys, conversion exports or payment data. Store private partner data in `data/partner_offers.private.json`, which is ignored by Git, or in a proper CRM.

## Publishing an offer

Copy the example object from `data/partner_offers.example.json` into the `offers` array in `data/partner_offers.json`. A published offer requires:

- unique lowercase `id` and `slug`;
- `status` set to `published`;
- factual name, category, summary and audience fit;
- public offer and pricing language;
- an evidence-based reason to consider the product, a material caution and two to five concrete use cases;
- the exact partner-provided HTTPS tracking URL;
- editorial approval and terms-verification dates;
- at least one HTTPS evidence URL;
- an optional site-relative review URL;
- an optional expiry date.

Then run:

```powershell
python scripts/build_partner_offers.py
python scripts/build_partner_offers.py --check
```

The builder refuses incomplete published records, does not publish drafts, excludes expired offers, HTML-escapes registry content, adds `rel="nofollow sponsored noopener"` to commercial links and removes stale generated offer pages when an offer is paused.

## Click measurement

`assets/affiliate-tracking.js` automatically emits events for links with `data-affiliate-offer`. It supports:

- Google Analytics through `gtag`;
- Google Tag Manager through `dataLayer`;
- Plausible custom events;
- an optional first-party collection endpoint.

To use a first-party endpoint, set the page metadata to a real HTTPS collector:

```html
<meta name="affiliate-event-endpoint" content="https://analytics.example.com/events">
```

The event intentionally excludes email address, referrer, IP address and browser fingerprint data. The server receiving a beacon remains responsible for its own privacy and retention policy.

## Editorial guardrails

- A partner can buy access or a clearly labelled placement, never a rating or positive verdict.
- Claims must be attributable to evidence and rechecked when terms change.
- Pages must state the commercial relationship beside the primary CTA.
- Expiry dates should be used whenever supplied.
- Do not infer conversions from clicks. Reconcile clicks with the affiliate platform's actual conversion report.
- Start with three to five offers and prove clicks and conversions before increasing publishing volume.

## PartnerStack monitoring

The recurring account monitor keeps its latest private baseline in `.partner-metrics/partnerstack-baseline.json`, which is ignored by Git. It compares account-wide and program-level clicks, signups, revenue, commissions, invitations, terms gates and payout readiness. Routine runs stay quiet when nothing material changes.

Monitoring is read-only. It must not accept invitations or terms, create referral links, download resources, send messages or change account settings. Any newly interesting program is reviewed for audience fit, economics and promotion restrictions before it is added to the public registry.
