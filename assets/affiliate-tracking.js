(function () {
  "use strict";

  var SESSION_KEY = "artificial_one_affiliate_session";

  function safeSessionId() {
    try {
      var existing = window.sessionStorage.getItem(SESSION_KEY);
      if (existing) return existing;
      var value = window.crypto && window.crypto.randomUUID
        ? window.crypto.randomUUID()
        : "s-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
      window.sessionStorage.setItem(SESSION_KEY, value);
      return value;
    } catch (_) {
      return "anonymous";
    }
  }

  var sessionId = safeSessionId();

  function campaignContext() {
    try {
      var params = new URLSearchParams(window.location.search);
      return {
        source: compactSubId(params.get("utm_source"), "direct"),
        campaign: compactSubId(params.get("utm_campaign"), "organic")
      };
    } catch (_) {
      return { source: "direct", campaign: "organic" };
    }
  }

  function eventPayload(link, eventName) {
    var context = campaignContext();
    return {
      event: eventName || "affiliate_click",
      offer_id: link.dataset.offerId || "unknown",
      placement: link.dataset.placement || "unknown",
      page_path: window.location.pathname,
      source: context.source,
      campaign: context.campaign,
      session_id: sessionId,
      occurred_at: new Date().toISOString()
    };
  }

  function compactSubId(value, fallback) {
    var cleaned = String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80);
    return cleaned || fallback;
  }

  function addPartnerStackAttribution(link) {
    try {
      var url = new URL(link.href, window.location.href);
      if (!url.searchParams.has("sid1")) {
        url.searchParams.set("sid1", compactSubId(link.dataset.offerId, "offer"));
      }
      if (!url.searchParams.has("sid2")) {
        url.searchParams.set("sid2", compactSubId(link.dataset.placement, "placement"));
      }
      if (!url.searchParams.has("sid3")) {
        var context = campaignContext();
        url.searchParams.set("sid3", context.campaign !== "organic" ? context.campaign : compactSubId(window.location.pathname, "home"));
      }
      link.href = url.toString();
    } catch (_) {
      // The original verified destination remains usable if URL parsing fails.
    }
  }

  var impressionSeen = Object.create(null);
  var affiliateObserver = null;

  function trackVisibleRecommendations() {
    if (!("IntersectionObserver" in window)) return;
    if (!affiliateObserver) {
      affiliateObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting || entry.intersectionRatio < 0.5) return;
          var link = entry.target;
          var key = [link.dataset.offerId, link.dataset.placement, window.location.pathname].join(":");
          if (!impressionSeen[key]) {
            impressionSeen[key] = true;
            sendToConfiguredEndpoint(eventPayload(link, "affiliate_impression"));
          }
          affiliateObserver.unobserve(link);
        });
      }, { threshold: [0.5] });
    }
    document.querySelectorAll("a[data-affiliate-offer]").forEach(function (link) {
      if (link.dataset.affiliateObserved) return;
      link.dataset.affiliateObserved = "1";
      affiliateObserver.observe(link);
    });
  }

  function observeDynamicRecommendations() {
    if (!("MutationObserver" in window)) return;
    new MutationObserver(trackVisibleRecommendations).observe(document.body, { childList: true, subtree: true });
  }

  function sendToConfiguredEndpoint(payload) {
    var meta = document.querySelector('meta[name="affiliate-event-endpoint"]');
    var endpoint = meta && meta.content ? meta.content.trim() : "";
    if (!endpoint) return;

    try {
      var body = JSON.stringify(payload);
      if (window.navigator.sendBeacon) {
        var accepted = window.navigator.sendBeacon(
          endpoint,
          new Blob([body], { type: "application/json" })
        );
        if (accepted) return;
      }
      window.fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body,
        keepalive: true,
        credentials: "same-origin"
      }).catch(function () {});
    } catch (_) {
      // Tracking must never prevent the visitor from reaching the partner.
    }
  }

  function hashBucket(value) {
    var hash = 2166136261;
    for (var index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0) % 100;
  }

  function selectVariant(strategy) {
    var sticky = strategy && strategy.sticky ? strategy.sticky : {};
    var variants = sticky.variants || {};
    var bucket = hashBucket(sessionId + ":" + window.location.pathname);
    var winner = sticky.mode === "winner" && (sticky.winner === "a" || sticky.winner === "b") ? sticky.winner : null;
    var key = winner ? (bucket < 90 ? winner : (winner === "a" ? "b" : "a")) : (bucket < 50 ? "a" : "b");
    return {
      key: key,
      message: variants[key] && variants[key].message ? variants[key].message : "Considering this tool? Check the current partner offer.",
      cta: variants[key] && variants[key].cta ? variants[key].cta : "View partner offer"
    };
  }

  function loadConversionStrategy() {
    if (!window.fetch) return Promise.resolve({});
    return window.fetch("/data/conversion_strategy.json", { credentials: "same-origin", cache: "no-cache" })
      .then(function (response) { return response.ok ? response.json() : {}; })
      .catch(function () { return {}; });
  }

  function installStickyRecommendation(strategy) {
    var source = document.querySelector("a[data-affiliate-offer]");
    if (!source || document.getElementById("affiliate-sticky-recommendation")) return;

    var dismissalKey = "affiliate_sticky_dismissed:" + window.location.pathname;
    try {
      if (window.sessionStorage.getItem(dismissalKey)) return;
    } catch (_) {}

    var bar = document.createElement("aside");
    bar.id = "affiliate-sticky-recommendation";
    bar.setAttribute("aria-label", "Partner recommendation");
    bar.style.cssText = "position:fixed;left:12px;right:12px;bottom:12px;z-index:9999;display:none;align-items:center;justify-content:center;gap:14px;padding:12px 46px 12px 16px;border:1px solid #c7d2fe;border-radius:14px;background:rgba(255,255,255,.97);box-shadow:0 14px 40px rgba(15,23,42,.2);backdrop-filter:blur(10px);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif";

    var label = document.createElement("span");
    var variant = selectVariant(strategy);
    label.textContent = variant.message;
    label.style.cssText = "color:#334155;font-size:14px;font-weight:600";

    var link = source.cloneNode(true);
    link.textContent = variant.cta;
    link.dataset.placement = (source.dataset.placement || "affiliate") + "-sticky-cro-" + variant.key;
    link.style.cssText = "display:inline-block;flex:0 0 auto;padding:10px 16px;border-radius:9px;background:#4f46e5;color:#fff;font-size:14px;font-weight:700;text-decoration:none";

    var close = document.createElement("button");
    close.type = "button";
    close.setAttribute("aria-label", "Dismiss partner recommendation");
    close.textContent = "×";
    close.style.cssText = "position:absolute;right:12px;top:50%;transform:translateY(-50%);border:0;background:transparent;color:#64748b;font-size:26px;line-height:1;cursor:pointer";
    close.addEventListener("click", function () {
      bar.remove();
      try { window.sessionStorage.setItem(dismissalKey, "1"); } catch (_) {}
    });

    bar.appendChild(label);
    bar.appendChild(link);
    bar.appendChild(close);
    document.body.appendChild(bar);

    function maybeShow() {
      var scrollable = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      if (window.scrollY / scrollable >= 0.35) {
        bar.style.display = "flex";
        window.removeEventListener("scroll", maybeShow);
      }
    }

    window.addEventListener("scroll", maybeShow, { passive: true });
    maybeShow();
  }

  document.addEventListener("click", function (event) {
    var link = event.target.closest("a[data-affiliate-offer]");
    if (!link) return;

    addPartnerStackAttribution(link);
    var payload = eventPayload(link, "affiliate_click");

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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      loadConversionStrategy().then(function (strategy) {
        installStickyRecommendation(strategy);
        trackVisibleRecommendations();
        observeDynamicRecommendations();
      });
    });
  } else {
    loadConversionStrategy().then(function (strategy) {
      installStickyRecommendation(strategy);
      trackVisibleRecommendations();
      observeDynamicRecommendations();
    });
  }
})();
