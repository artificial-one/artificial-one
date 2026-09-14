# Search revenue engine

The daily GitHub Actions workflow in `.github/workflows/growth-engine.yml` turns aggregate Google Search Console data into guarded, revenue-focused site improvements.

## Daily loop

1. Inspect up to 40 priority URLs for indexing verdict, robots/indexing permission, fetch status, canonical selection, rich-result verdict and last crawl time.
2. Analyze final 28-day query/page performance and rank low-CTR opportunities. Commercial intent and pages attached to stronger affiliate conversion signals receive extra weight.
3. Email the private report to `hello@artificial.one` and resubmit the sitemap.
4. Build deterministic alternatives, comparison and use-case pages from approved partner copy. Review pages include pricing notes, structured data, internal links and tracked affiliate CTAs.
5. Commit only privacy-safe copy choices and generated static pages when they change.

## Experiment guardrails

- A page needs at least 80 impressions before an experiment can start or be judged.
- At most three new snippet experiments can start in one run.
- Experiments run at least 14 days and at most 28 days.
- Copy returns to the control when CTR falls below 80% of baseline or average position worsens by more than two places.
- A commercial variant wins early only after a 10% CTR improvement without a material ranking decline.
- Query-driven content priorities may change at most once every seven days.
- Generated pages use reviewed registry facts only; raw queries never become page copy automatically.

## Privacy and recovery

Raw queries, index findings and experiment baselines stay in the private workflow/email and the GitHub Actions cache. The public strategy contains offer IDs and copy variants only. Git records every published change, so an automated reversion is auditable and recoverable.
