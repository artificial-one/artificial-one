(function () {
  "use strict";

  function eventPayload(link) {
    return {
      event: "affiliate_click",
      offer_id: link.dataset.offerId || "unknown",
      placement: link.dataset.placement || "unknown",
      page_path: window.location.pathname,
      occurred_at: new Date().toISOString()
    };
  }

  function sendToConfiguredEndpoint(payload) {
    var meta = document.querySelector('meta[name="affiliate-event-endpoint"]');
    var endpoint = meta && meta.content ? meta.content.trim() : "";
    if (!endpoint || !window.navigator.sendBeacon) return;

    try {
      var body = new Blob([JSON.stringify(payload)], { type: "application/json" });
      window.navigator.sendBeacon(endpoint, body);
    } catch (_) {
      // Tracking must never prevent the visitor from reaching the partner.
    }
  }

  document.addEventListener("click", function (event) {
    var link = event.target.closest("a[data-affiliate-offer]");
    if (!link) return;

    var payload = eventPayload(link);

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(payload);

    if (typeof window.gtag === "function") {
      window.gtag("event", "affiliate_click", {
        offer_id: payload.offer_id,
        placement: payload.placement,
        page_path: payload.page_path,
        transport_type: "beacon"
      });
    }

    if (typeof window.plausible === "function") {
      window.plausible("Affiliate Click", {
        props: {
          offer_id: payload.offer_id,
          placement: payload.placement
        }
      });
    }

    sendToConfiguredEndpoint(payload);
  });
})();
