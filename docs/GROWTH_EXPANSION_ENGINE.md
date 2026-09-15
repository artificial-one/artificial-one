# Growth expansion engine

This layer grows qualified traffic and adds direct revenue without requiring additional affiliate programs.

## Search discovery and indexing

`scripts/indexing_recovery.py` audits every commercial priority page for a canonical URL, indexability, sitemap membership and incoming internal links. It builds `buyers-guides.html`, publishes the privacy-safe summary in `data/indexing_recovery.json`, and submits changed URLs to IndexNow. Failed IndexNow batches remain in the private workflow cache for a later retry.

Google indexing verdicts continue to come from `scripts/search_revenue_engine.py` and remain private in the emailed Search Console report. IndexNow covers participating search engines; it is not represented as a Google indexing request.

## Decision tools

`scripts/build_decision_tools.py` generates:

- `ai-stack-builder.html`
- `decision-tools.html`
- AI software ROI calculator
- PDF workflow cost calculator
- AI voice production cost calculator
- landing-page ROI calculator

The calculators are browser-only, make no performance promises, and route visitors to relevant, tracked partner reviews. The stack builder scores reviewed registry descriptions and current revenue ranking; it does not invent product capabilities.

## Demand-gated content

The Search Console engine can activate a reviewed offer/use-case concept after at least 30 aggregate impressions match the product and use case. Public strategy contains only an opaque concept ID. Raw queries and counts stay in the private workflow cache and email. `scripts/build_search_revenue_pages.py` turns activated IDs into pages using only reviewed registry copy.

## Search-result experiments

The existing Search Console loop continues to test titles and descriptions only after adequate impressions, with minimum experiment duration and automatic reversion when click-through rate or average position crosses a safety threshold.

## Vendor change alerts

`scripts/monitor_offer_changes.py` monitors first-party product sources. A changed fingerprint must appear on two consecutive successful checks before a generic public alert is created. It never publishes an extracted price as fact. Confirmed alerts appear on `offer-updates.html` and in the generated weekly newsletter, always linking readers to the vendor source for verification.

## Direct sponsorship revenue

`scripts/build_sponsorship.py` generates a disclosed sponsorship storefront and a no-index post-payment intake page. The server endpoints create Stripe Checkout sessions, verify paid sessions, prevent duplicate submissions, store briefs privately in Upstash, and notify `hello@artificial.one` through Resend.

Checkout is disabled in `data/sponsorship_inventory.json` until all of the following are complete:

1. Approve the public packages and introductory prices.
2. Add `STRIPE_SECRET_KEY` to the production deployment environment.
3. Confirm `RESEND_API_KEY`, `UPSTASH_REDIS_REST_URL`, and `UPSTASH_REDIS_REST_TOKEN` are available to the production API endpoints.
4. Set `checkout_enabled` to `true` and deploy.

Payment never purchases an editorial verdict. Unsupported claims or prohibited submissions can be rejected under the published standards.

## Cloud execution

The revenue workflow rebuilds the tools and storefront, monitors vendor pages, refreshes alerts/newsletter/distribution output, audits discovery, submits IndexNow changes, runs the complete test suite and commits public-safe output daily. The Search Console workflow activates demand concepts and guarded snippet experiments, rebuilds affected pages, refreshes the buyer hub and submits those changes to IndexNow.

Beehiiv sending, social posting, Stripe checkout and paid ads remain independent gates. Missing credentials cannot silently activate any of them.
