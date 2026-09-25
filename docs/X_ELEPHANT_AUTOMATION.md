# Artificial.One X elephant

Artificial.One's X presence is designed as a clearly disclosed automated elephant: useful, skeptical, playful, and commercially transparent.

## What runs automatically

- Three original visual posts every day at deliberately uneven times.
- Morning discovery, midday discussion, and evening decision-guide formats.
- Existing reviewed Artificial.One inventory supplies every subject and image.
- A checksum-verified local Qwen model drafts the playful hook and question. The reviewed topic, image, attribution and optional route are inserted deterministically.
- Generated copy is length-, claim-, safety- and repetition-checked; the existing reviewed templates are the automatic fallback.
- Only the evening post carries a website or affiliate route, keeping two-thirds of the feed conversational rather than promotional.
- Confirmed publications enter `data/distribution_receipts.json`, so the business-activity diary can include them.
- Durable private state prevents duplicate posts and duplicate replies across workflow runs.
- The model runs inside GitHub Actions from the shared private cache, without a laptop or hosted-model API.

## Persona

Display name: `Artificial.One 🐘`

Bio:

> 🐘 Automated AI-tool scout. I remember every feature and forget every marketing claim. Human-owned; bot-posted. Independent decisions at artificial.one

The voice uses recurring formats including Trunk Test, SaaS Smell Test, Elephant Court, and Keep / Trial / Delete. It challenges vague vendor claims without fabricating personal experience or insulting people.

## Safety and platform-policy controls

- No automated likes.
- No automated follows or unfollows.
- No automated DMs.
- No replies discovered from keyword searches.
- Replies contain no affiliate links.
- A user receives at most one automated reply per day.
- Opt-outs are recognized and remembered.
- AI replies run only when `X_AI_REPLY_APPROVED=true`, which must not be set until X grants written approval.
- Original posting runs only when the account is visibly labeled automated and `X_AUTOMATED_LABEL_CONFIRMED=true`.
- `X_ELEPHANT_ENABLED=false` is the immediate stop control.
- Manual workflow runs do not publish unless their explicit `publish` checkbox is enabled.
- Mention replies retain the separate written-approval gate and are not changed by original-post generation.

## Required GitHub configuration

Repository secrets:

- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

Repository variables:

- `X_ACCOUNT_USERNAME`
- `X_ELEPHANT_ENABLED` — keep `false` until credentials and the account label are ready
- `X_AUTOMATED_LABEL_CONFIRMED` — set `true` only after applying the automated-account label
- `X_AI_REPLY_APPROVED` — keep `false` until X explicitly approves AI-powered automated replies

The X developer app needs read-and-write user authentication. Website scripting, browser automation, password storage, automatic likes, and automatic following are intentionally not used.
