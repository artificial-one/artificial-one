# Elephant decision engine

The Elephant experience turns Artificial.One's normalized catalogue into a useful, repeatable product rather than another directory.

## Public experiences

- `ask-elephant.html` performs catalogue-grounded workflow matching in the visitor's browser. Questions are not sent to a hosted model.
- `ai-stack-studio.html` builds shareable stacks, accepts visitor-owned cost assumptions, identifies category overlap and exports JSON.
- `workflow-recipes.html` and `workflow-recipes/` map eight common business outcomes to practical steps and relevant tools.
- `ai-tool-observatory.html` exposes confirmed vendor-source changes and keeps a private local watchlist.
- `developers.html` documents the privacy-safe catalogue and change API.
- `data/elephant_experience.json` is the versioned client dataset generated from the normalized tool catalogue.

## Ranking rules

Recommendations use the recorded name, category, summary, best-for description, features, platforms, free-plan signal and verification state. Matching words and workflow fit dominate the score. Monetization contributes one point only, so an affiliate relationship cannot override a materially stronger workflow match.

The system never generates product capabilities, price claims or hands-on-testing claims. Visitors are directed to vendor sources for current details.

## Watchlist privacy

Local watchlists stay in browser storage. Email alerts require a second confirmation link. Pending confirmation records expire after 24 hours, requests are rate-limited, and alert messages include an immediate unsubscribe link. The daily cloud sender delivers only changes already published by the two-consecutive-observation monitor.

Required deployment values are the existing `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` and `RESEND_API_KEY`, plus an optional `WATCHLIST_EMAIL_FROM` repository variable when the default `updates@artificial.one` sender is not used.

## Automatic refresh

`scripts/build_elephant_experience.py` runs from the revenue optimizer and tool-intelligence workflows. New catalogue records, partner destinations and confirmed vendor changes therefore flow into the assistant, recipes, observatory and public API without attended editing.

Run locally with the configured Python runtime:

```powershell
python scripts/build_elephant_experience.py
python scripts/build_elephant_experience.py --check
python -m unittest tests.test_elephant_experience -v
```
