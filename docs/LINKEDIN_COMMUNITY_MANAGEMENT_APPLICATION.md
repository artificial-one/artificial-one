# LinkedIn Community Management access preparation

This document is the application packet and implementation boundary for Artificial.One. It reflects LinkedIn’s official requirements as reviewed on September 23, 2026.

## Intended commercial use case

Artificial.One is an AI-software discovery and comparison publisher. Its integration will manage content and inbound engagement for the official Artificial.One LinkedIn Company Page. It will:

- publish original Artificial.One posts and visual buying guides;
- retrieve comments, reactions and aggregate engagement on the Page’s own posts;
- let the operator review conversations and respond through LinkedIn’s official APIs;
- use aggregate results to improve the relevance of future Artificial.One content;
- retain only the minimum LinkedIn data required for conversation management and evidence of completed publishing.

The integration will not scrape the general feed, automate connection invitations or direct messages, manufacture engagement, or mass-comment on unrelated member posts.

## Requested organization permissions

- `rw_organization_admin` — verify and manage the authorized Artificial.One Page context.
- `w_organization_social` — publish as the Company Page.
- `r_organization_social_feed` — retrieve Page posts, comments, reactions and social metadata.
- `w_organization_social_feed` — reply and react as the Company Page.

Member-feed read access is deliberately excluded from the initial request because `r_member_social_feed` is restricted to selected developers and is not required for the Page-management use case.

## Assets already prepared

- Registered legal organization: `mareke solutions s.r.o.`
- Czech company number (IČO): `29415675`
- Registered address: `Korunní 2569/108b, Vinohrady, 101 00 Praha 10, Czech Republic`
- Public product website: <https://artificial.one/>
- Public privacy policy: <https://artificial.one/privacy.html>
- Business contact address: `hello@artificial.one`
- Official LinkedIn Company Page: <https://www.linkedin.com/company/artificial-one/> (organization ID `145231312`)
- Existing official-API visual publishing implementation and confirmed delivery receipts.
- A twelve-post weekly editorial system using original Artificial.One content.
- Encrypted token storage in GitHub Actions and public-safe delivery receipts containing no access tokens.
- A data-minimization rule: no general-feed scraping, automated connections, unsolicited messages, or sale of LinkedIn member data.

## Remaining prerequisites that require the account owner

LinkedIn makes Community Management available only to registered legal organizations for commercial use. Before an application can credibly pass Development-tier review, the owner must provide or complete:

1. Add the applying Artificial One member as a super admin of the new official Company Page; the established Marek Eckhaus account currently administers it and mareke solutions s.r.o. is the legal operator.
2. Verify the Company Page against a new, dedicated developer application.
3. Verify `hello@artificial.one` as the business email and `artificial.one` as the organization’s domain.

The current standalone publishing application should remain untouched. LinkedIn’s guidance says the Community Management request should use a new application without other API products, so the new Page-management app must be separate.

## Development-tier application answers

**Legal organization:** mareke solutions s.r.o., IČO 29415675, Korunní 2569/108b, Vinohrady, 101 00 Praha 10, Czech Republic.

**Product description:** Artificial.One Community Desk is the private management interface operated by mareke solutions s.r.o. to publish original Artificial.One Page content, review inbound engagement on its own posts and respond to those conversations through LinkedIn’s official APIs.

**Customers/users:** Initially the internal Artificial.One operator only. It is not offered as a multi-tenant social-media automation product.

**Why LinkedIn data is needed:** Post, comment, reaction and aggregate engagement data are required to show the operator conversations occurring on Artificial.One Page content and to publish an appropriate response from that Page.

**Storage and retention:** OAuth credentials are encrypted deployment secrets. Public delivery receipts contain only the post identifier, URL, title and timestamp. If comment data is stored during the approved integration, it will be minimized and removed when no longer needed for the management purpose or upon a valid deletion request.

**Safeguards:** Access is limited to the Artificial.One Page and authorized administrators. The integration does not scrape LinkedIn pages, automate network growth, send direct messages, or interact with unrelated content.

## Standard-tier demonstration plan

After Development access is granted, record a downloadable video under five minutes showing:

1. OAuth authorization and selection of the Artificial.One Page.
2. An original image post published through the application.
3. The application displaying aggregate engagement and comments for that post.
4. A reply created through the official comments endpoint.
5. The privacy policy, deletion contact and visible data fields.
6. Token storage, access controls and the absence of unrelated member-feed collection.

Do not apply for Standard tier until each demonstrated function works against Development access. A rejected application cannot simply be resubmitted with the same app.

## Official references

- Community Management review: <https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review>
- Access tiers and scopes: <https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access>
- Comments API: <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/comments-api>
- Reactions API: <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/reactions-api>
