(function () {
  "use strict";

  var SESSION_KEY = "artificial_one_affiliate_session";
  var ACQUISITION_KEY = "artificial_one_acquisition";

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
      var suppliedSource = params.get("utm_source");
      var suppliedMedium = params.get("utm_medium");
      var suppliedCampaign = params.get("utm_campaign");
      var saved = JSON.parse(window.sessionStorage.getItem(ACQUISITION_KEY) || "null");
      if (suppliedSource || suppliedCampaign) {
        var supplied = {
          source: compactSubId(suppliedSource, "direct"),
          medium: compactSubId(suppliedMedium, "unknown"),
          campaign: compactSubId(suppliedCampaign, "organic"),
          landing_path: window.location.pathname
        };
        // Preserve the first external acquisition source when a visitor follows
        // one of our own UTM-tagged internal routes.
        if (saved && saved.source && supplied.source === "onsite") return saved;
        window.sessionStorage.setItem(ACQUISITION_KEY, JSON.stringify(supplied));
        return supplied;
      }
      if (saved && saved.source && saved.campaign) return saved;
      var referrerSource = "direct";
      var referrerMedium = "none";
      if (document.referrer) {
        var referrer = new URL(document.referrer);
        if (referrer.hostname && referrer.hostname !== window.location.hostname) {
          referrerSource = compactSubId(referrer.hostname.replace(/^www\./, ""), "referral");
          referrerMedium = "referral";
        }
      }
      var discovered = {
        source: referrerSource,
        medium: referrerMedium,
        campaign: "organic",
        landing_path: window.location.pathname
      };
      window.sessionStorage.setItem(ACQUISITION_KEY, JSON.stringify(discovered));
      return discovered;
    } catch (_) {
      return { source: "direct", medium: "none", campaign: "organic", landing_path: window.location.pathname };
    }
  }

  function eventPayload(link, eventName) {
    var context = campaignContext();
    return {
      event: eventName || "affiliate_click",
      offer_id: (link && (link.dataset.offerId || link.dataset.relatedOfferId)) || "content",
      placement: (link && link.dataset.placement) || "page",
      page_path: window.location.pathname,
      source: context.source,
      medium: context.medium || "unknown",
      campaign: context.campaign,
      landing_path: context.landing_path || window.location.pathname,
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

  function addAffiliateAttribution(link) {
    try {
      var url = new URL(link.href, window.location.href);
      var context = campaignContext();
      var third = context.campaign !== "organic" ? context.campaign : compactSubId(window.location.pathname, "home");
      var isImpact = link.dataset.affiliateNetwork === "impact" || /(^|\.)8odi\.net$/i.test(url.hostname);
      if (isImpact) {
        if (!url.searchParams.has("subId1")) url.searchParams.set("subId1", compactSubId(window.location.pathname, "home"));
        if (!url.searchParams.has("subId2")) url.searchParams.set("subId2", compactSubId(link.dataset.placement, "placement"));
        if (!url.searchParams.has("subId3")) url.searchParams.set("subId3", third);
        if (!url.searchParams.has("sharedId")) url.searchParams.set("sharedId", "artificial-one");
      } else {
        if (!url.searchParams.has("sid1")) url.searchParams.set("sid1", compactSubId(link.dataset.offerId, "offer"));
        if (!url.searchParams.has("sid2")) url.searchParams.set("sid2", compactSubId(link.dataset.placement, "placement"));
        if (!url.searchParams.has("sid3")) url.searchParams.set("sid3", third);
      }
      link.href = url.toString();
    } catch (_) {
      // The original verified destination remains usable if URL parsing fails.
    }
  }

  function applyAppSumoAvailability() {
    if (!window.fetch) return Promise.resolve();
    return window.fetch("/data/appsumo_offers.json", { credentials: "same-origin" })
      .then(function (response) { return response.ok ? response.json() : { offers: [] }; })
      .then(function (registry) {
        var statusByDestination = Object.create(null);
        (registry.offers || []).forEach(function (offer) {
          try {
            var parsed = new URL(offer.tracking_url);
            statusByDestination[parsed.origin + parsed.pathname] = offer;
          } catch (_) {}
        });
        document.querySelectorAll('a[data-affiliate-network="impact"]').forEach(function (link) {
          try {
            var parsed = new URL(link.href, window.location.href);
            var offer = statusByDestination[parsed.origin + parsed.pathname];
            if (!offer || offer.availability !== "expired") return;
            link.href = "/appsumo-ai-tools.html?unavailable=" + encodeURIComponent(offer.slug || "offer");
            link.removeAttribute("target");
            link.dataset.affiliateUnavailable = "1";
            link.setAttribute("aria-label", (link.textContent || "Offer") + " — current offer unavailable");
          } catch (_) {}
        });
      }).catch(function () {});
  }

  var impressionSeen = Object.create(null);
  var affiliateObserver = null;
  var routeImpressionSeen = Object.create(null);
  var routeObserver = null;

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

  function trackVisibleRoutes() {
    if (!("IntersectionObserver" in window)) return;
    if (!routeObserver) {
      routeObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting || entry.intersectionRatio < 0.5) return;
          var link = entry.target;
          var key = [link.dataset.relatedOfferId, link.dataset.placement, window.location.pathname].join(":");
          if (!routeImpressionSeen[key]) {
            routeImpressionSeen[key] = true;
            sendToConfiguredEndpoint(eventPayload(link, "content_route_impression"));
          }
          routeObserver.unobserve(link);
        });
      }, { threshold: [0.5] });
    }
    document.querySelectorAll("a[data-content-route]").forEach(function (link) {
      if (link.dataset.routeObserved) return;
      link.dataset.routeObserved = "1";
      routeObserver.observe(link);
    });
  }

  function observeDynamicRecommendations() {
    if (!("MutationObserver" in window)) return;
    new MutationObserver(function () {
      trackVisibleRecommendations();
      trackVisibleRoutes();
    }).observe(document.body, { childList: true, subtree: true });
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

  function installUnifiedShell() {
    if (document.querySelector(".site-header")) return;
    var stylesheet = Array.prototype.find.call(document.styleSheets || [], function (sheet) { return /decision-engine\.css/.test(sheet.href || ""); });
    if (!stylesheet) {
      var link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = "/assets/decision-engine.css";
      document.head.appendChild(link);
    }
    var legacy = document.querySelector("body > header, body > nav");
    var header = document.createElement("header");
    header.className = "site-header";
    header.innerHTML = '<div class="nav-wrap"><a class="brand" href="/"><img src="/images/social/artificial-one-logo.png" alt="Artificial.One elephant" width="43" height="43"><span>artificial<span class="brand-dot">.</span>one</span></a><button class="nav-toggle" type="button" aria-expanded="false" aria-label="Open navigation">☰</button><nav class="primary-nav" aria-label="Primary navigation"><a href="/ask-elephant.html">Ask Elephant</a><a href="/ai-tool-finder.html">Find Tools</a><a href="/workflow-recipes.html">Recipes</a><a href="/partner-offers.html">Deals</a><a href="/news.html">What’s New</a><a class="stack-trigger" href="/ai-stack-studio.html">My Stack</a><details class="more-menu"><summary>Explore ▾</summary><div class="more-links"><a href="/ai-stack-studio.html">Stack Studio</a><a href="/ai-tool-observatory.html">Tool Observatory</a><a href="/ai-tool-finder.html?compare=">Compare</a><a href="/reviews.html">All reviews</a><a href="/decision-tools.html">Free tools</a><a href="/buyers-guides.html">Buyer guides</a><a href="/developers.html">Public API</a><a href="/about.html">How we evaluate</a></div></details></nav></div>';
    if (legacy) legacy.replaceWith(header); else document.body.insertBefore(header, document.body.firstChild);
    var toggle = header.querySelector(".nav-toggle");
    var nav = header.querySelector(".primary-nav");
    toggle.addEventListener("click", function () { var open = nav.classList.toggle("is-open"); toggle.setAttribute("aria-expanded", String(open)); });
  }

  function trackWebVitals() {
    if (!("PerformanceObserver" in window)) return;
    var lcp = 0;
    try {
      new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (entry) { lcp = Math.max(lcp, entry.startTime || 0); });
      }).observe({ type: "largest-contentful-paint", buffered: true });
      var cls = 0;
      new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (entry) { if (!entry.hadRecentInput) cls += entry.value || 0; });
      }).observe({ type: "layout-shift", buffered: true });
      window.addEventListener("pagehide", function () {
        sendToConfiguredEndpoint(Object.assign(eventPayload(null, "web_vital"), { metric: "lcp", value: Math.round(lcp) }));
        sendToConfiguredEndpoint(Object.assign(eventPayload(null, "web_vital"), { metric: "cls", value: Math.round(cls * 1000) }));
      }, { once: true });
    } catch (_) {}
  }

  function trackReturningVisitor() {
    try {
      if (window.localStorage.getItem("ai1_seen_before")) sendToConfiguredEndpoint(eventPayload(null, "returning_visit"));
      window.localStorage.setItem("ai1_seen_before", new Date().toISOString());
    } catch (_) {}
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

  function loadContentRoutes() {
    if (!window.fetch) return Promise.resolve({ routes: [] });
    return window.fetch("/data/content_routes.json", { credentials: "same-origin", cache: "no-cache" })
      .then(function (response) { return response.ok ? response.json() : { routes: [] }; })
      .catch(function () { return { routes: [] }; });
  }

  function installContextualRevenueRoute(catalog) {
    if (document.getElementById("contextual-revenue-route")) return;
    if (/^\/(partner-offers|search-intent|calculators)\//.test(window.location.pathname)) return;
    var text = String(document.body && document.body.innerText || "").toLowerCase();
    var best = null;
    var bestScore = 0;
    (catalog.routes || []).forEach(function (route) {
      var score = 0;
      (route.strong_keywords || []).forEach(function (keyword) {
        if (keyword && text.indexOf(String(keyword).toLowerCase()) !== -1) score += 5;
      });
      (route.keywords || []).forEach(function (keyword) {
        if (keyword && text.indexOf(String(keyword).toLowerCase()) !== -1) score += 1;
      });
      if (score > bestScore) {
        best = route;
        bestScore = score;
      }
    });
    if (!best || bestScore < 3) return;

    var card = document.createElement("aside");
    card.id = "contextual-revenue-route";
    card.setAttribute("aria-label", "Relevant independent tool guide");
    card.style.cssText = "max-width:980px;margin:36px auto;padding:24px;border:1px solid #c7d2fe;border-radius:18px;background:#eef2ff;color:#172554;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif";

    var eyebrow = document.createElement("p");
    eyebrow.textContent = "Relevant decision guide";
    eyebrow.style.cssText = "margin:0 0 8px;color:#4f46e5;font-size:12px;font-weight:800;letter-spacing:.09em;text-transform:uppercase";
    var title = document.createElement("h2");
    title.textContent = "Would " + best.name + " fit this workflow?";
    title.style.cssText = "margin:0;font-size:26px;line-height:1.2";
    var summary = document.createElement("p");
    summary.textContent = best.summary;
    summary.style.cssText = "margin:12px 0 18px;line-height:1.6;color:#334155";
    var guide = document.createElement("a");
    guide.href = best.url + "?utm_source=onsite&utm_medium=content-route&utm_campaign=smart-routing";
    guide.textContent = "Check fit, limitations and pricing →";
    guide.dataset.contentRoute = "";
    guide.dataset.relatedOfferId = best.offer_id;
    guide.dataset.placement = "contextual-revenue-router";
    guide.style.cssText = "display:inline-block;margin-right:16px;padding:11px 16px;border-radius:9px;background:#4f46e5;color:#fff;font-weight:750;text-decoration:none";
    var calculator = document.createElement("a");
    calculator.href = best.calculator_url + "?utm_source=onsite&utm_medium=content-route&utm_campaign=value-calculator";
    calculator.textContent = "Estimate value first";
    calculator.dataset.contentRoute = "";
    calculator.dataset.relatedOfferId = best.offer_id;
    calculator.dataset.placement = "contextual-value-calculator";
    calculator.style.cssText = "display:inline-block;padding:10px 0;color:#4338ca;font-weight:750;text-decoration:none";
    card.appendChild(eyebrow);
    card.appendChild(title);
    card.appendChild(summary);
    card.appendChild(guide);
    card.appendChild(calculator);
    var footer = document.querySelector("footer");
    (footer && footer.parentNode ? footer.parentNode : document.body).insertBefore(card, footer || null);
    trackVisibleRoutes();
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
    var route = event.target.closest("a[data-content-route]");
    if (route) {
      sendToConfiguredEndpoint(eventPayload(route, "content_route_click"));
    }
    var link = event.target.closest("a[data-affiliate-offer]");
    if (!link) return;

    if (link.dataset.affiliateUnavailable === "1") return;

    addAffiliateAttribution(link);
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
      installUnifiedShell();
      trackReturningVisitor();
      trackWebVitals();
      loadConversionStrategy().then(function (strategy) {
        sendToConfiguredEndpoint(eventPayload(null, "site_visit"));
        applyAppSumoAvailability();
        loadContentRoutes().then(installContextualRevenueRoute);
        installStickyRecommendation(strategy);
        trackVisibleRecommendations();
        trackVisibleRoutes();
        observeDynamicRecommendations();
      });
    });
  } else {
    installUnifiedShell();
    trackReturningVisitor();
    trackWebVitals();
    loadConversionStrategy().then(function (strategy) {
      sendToConfiguredEndpoint(eventPayload(null, "site_visit"));
      applyAppSumoAvailability();
      loadContentRoutes().then(installContextualRevenueRoute);
      installStickyRecommendation(strategy);
      trackVisibleRecommendations();
      trackVisibleRoutes();
      observeDynamicRecommendations();
    });
  }
})();
