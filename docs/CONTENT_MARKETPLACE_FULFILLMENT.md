# Sponsored-content order fulfilment

Artificial.One publishes five fixed-price PartnerStack Content Marketplace packages from `data/sponsorship_inventory.json`. The cloud worker in `scripts/partnerstack_content_marketplace.py` checks orders every two hours.

## Authority boundary

The worker never accepts, counters or declines an order. Those actions create a binding commercial commitment and stay with the owner. The daily executive report contains a direct PartnerStack action link for each pending or negotiating request.

After an order has been accepted, the worker is authorised to:

1. create a clearly labelled campaign record and public sponsor page;
2. add a time-limited sponsored spotlight when the purchased package includes one;
3. schedule the purchased disclosed social post or posts;
4. deploy those public assets through the normal repository-to-Vercel flow;
5. submit a live deliverable URL to PartnerStack on the following check;
6. keep an order in the daily report until it is completed.

Raw order details, submission receipts and owner-action state live only in the ignored `.content-marketplace/` directory and encrypted GitHub Actions cache. Public files contain only the sponsor name, supplied brief, public destination and disclosure needed to perform the order.

## Safety rules

- Every paid asset says it is sponsored.
- Sponsor copy is escaped before publication.
- Only HTTPS destinations become clickable.
- Payment never changes organic rankings or guarantees a positive review.
- A deliverable is submitted only after its public URL responds successfully.
- Submission receipts prevent duplicate delivery.
