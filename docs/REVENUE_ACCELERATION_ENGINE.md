# Revenue acceleration engine

This system automates the six revenue-growth loops for artificial.one. It runs in GitHub Actions, so the laptop does not need to remain online.

## 1. Contextual affiliate placement

`scripts/monetize_affiliate_links.py` scores eligible existing pages against every approved offer and inserts one relevant comparison block. It excludes legal, news, home, generated offer, and already managed pages, and uses `data/affiliate_placements.json` for limits and overrides.

## 2. Conversion optimization

`assets/affiliate-tracking.js` deterministically assigns each browser to sticky-call-to-action variant A or B. `scripts/optimize_conversion.py` uses anonymous aggregate events to select a winner only after both variants have at least 100 impressions and the uplift is statistically credible. A winning treatment retains a 10% holdout so regressions remain detectable.

## 3. Expected-earnings ranking

`scripts/optimize_revenue.py` ranks offers by observed commission per visitor and commission per click, with small-sample priors. Private PartnerStack terms can provide cold-start signals such as reward rate, cookie duration, trial, qualification, and deep-link support. Only the public ranked order is committed; account and customer data stay out of the repository.

## 4. Newsletter funnel

`scripts/publish_newsletter.py` creates a weekly, disclosed edition from current AI news and the highest-ranked relevant offers. It always refreshes the public archive at `newsletter/latest.html`. Beehiiv publishing is optional and requires repository secrets `BEEHIIV_API_KEY` and `BEEHIIV_PUBLICATION_ID`; `BEEHIIV_SEND_ENABLED=true` publishes a confirmed edition, otherwise it creates a draft.

## 5. Distribution engine

`scripts/distribute_content.py` refreshes `feed.xml` and `data/distribution_queue.json` with campaign-attributed links. Its self-renewing seven-day editorial calendar creates a fresh post every day from current site data: free tools, monitored AI news, partner use cases, buyer cautions, confirmed offer changes, workflow tips and a weekly roundup. It requires no model API or attended computer. The daily schedule can publish exactly one dated editorial item to Bluesky or a connected webhook; push-triggered builds never publish, and manual runs publish only when the `publish_social` input is selected. Deduplication state is retained privately in the workflow cache.

## 6. Controlled paid acquisition

`scripts/paid_acquisition.py` prepares a Google Ads search plan using high-intent phrases and negative brand keywords. Spending is disabled by default. Live creation requires every one of these conditions:

- `live_enabled` in `data/paid_acquisition_policy.json` and `PAID_ADS_LIVE=true`;
- Google Ads credentials and API version;
- an explicitly authorized target-country list;
- verified conversion measurement;
- `paid_search_allowed=true` for the specific affiliate program after checking its terms;
- positive daily budget, CPC limit, and stop-loss values.

Eligible campaigns are checked daily. A campaign with no conversion is automatically paused once both its minimum-click threshold and stop-loss are reached. The default policy cannot spend money.

## Cloud schedule and outputs

`.github/workflows/revenue-optimizer.yml` runs daily after the PartnerStack audit. It ranks offers, evaluates conversion tests, rebuilds commercial pages, refreshes AI news, creates the newsletter/RSS/distribution/ad plans, runs the complete test suite, and commits only public generated artifacts. Private publishing state is cached and no personal customer data is committed.

Public outputs include:

- `data/revenue_strategy.json`
- `data/conversion_strategy.json`
- `data/distribution_queue.json`
- `data/paid_campaign_plan.json`
- `newsletter/latest.html`
- `feed.xml`

## Activation checklist

The site-side automation and cloud generators work without additional services. Turning on outbound newsletter, social posting, or paid ads is a one-time account connection. Add the appropriate GitHub repository secrets, then enable only the matching repository variable. Paid ads also require editing the reviewed policy; never put credentials or private PartnerStack data in that file.
