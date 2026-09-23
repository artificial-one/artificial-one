(function () {
  "use strict";

  var STORE = {
    stack: "ai1_stack",
    compare: "ai1_compare",
    watch: "ai1_watchlist",
    history: "ai1_history",
    visit: "ai1_last_visit"
  };
  var catalog = [];
  var compareItems = [];

  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; }
    catch (_) { return fallback; }
  }

  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); }
    catch (_) { /* storage is optional */ }
  }

  function anonymousSession() {
    try {
      var existing = sessionStorage.getItem("artificial_one_affiliate_session");
      if (existing) return existing;
      var value = "s-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2,10);
      sessionStorage.setItem("artificial_one_affiliate_session", value);
      return value;
    } catch (_) { return "anonymous"; }
  }

  function text(value) {
    return String(value || "").replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
    });
  }

  function parseCatalog() {
    var source = document.getElementById("ai1-offer-data");
    if (source) {
      try { catalog = JSON.parse(source.textContent || "[]"); }
      catch (_) { catalog = []; }
    }
    if (!catalog.length) {
      catalog = Array.prototype.map.call(document.querySelectorAll("[data-tool-card]"), function (card) {
        return Object.assign({}, card.dataset);
      });
    }
    return catalog;
  }

  function send(eventName, meta) {
    var payload = Object.assign({
      event: eventName,
      page_path: location.pathname,
      page_url: location.href,
      placement: "decision-engine",
      session_id: anonymousSession(),
      timestamp: new Date().toISOString()
    }, meta || {});
    if (window.dataLayer && Array.isArray(window.dataLayer)) {
      window.dataLayer.push(Object.assign({ event: eventName }, payload));
    }
    var endpoint = document.querySelector('meta[name="affiliate-event-endpoint"]');
    if (!endpoint) return;
    try {
      var body = JSON.stringify(payload);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(endpoint.content, new Blob([body], { type: "application/json" }));
      } else {
        fetch(endpoint.content, { method: "POST", headers: { "Content-Type": "application/json" }, body: body, keepalive: true }).catch(function () {});
      }
    } catch (_) { /* analytics never blocks the interface */ }
  }
  window.ai1Track = send;

  function itemById(id) {
    return catalog.find(function (item) { return String(item.id) === String(id); });
  }

  function words(value) {
    var stop = { a:1, an:1, and:1, for:1, from:1, i:1, in:1, my:1, of:1, the:1, to:1, tool:1, use:1, want:1, with:1 };
    return String(value || "").toLowerCase().split(/[^a-z0-9]+/).filter(function (word) { return word.length > 2 && !stop[word]; });
  }

  var missionTerms = {
    create: ["audio","content","create","design","image","podcast","presentation","video","voice","write","writing"],
    sell: ["advertising","conversion","email","lead","marketing","research","sales","seo","trade"],
    automate: ["automation","business","productivity","workflow","operations","tracking"],
    research: ["analysis","data","database","document","pdf","research","search","trade"],
    build: ["code","developer","development","hosting","website","web","database"]
  };

  function haystack(item) {
    return [item.name,item.category,item.summary,item.best,item.why,item.limit,item.offer,(item.useCases || []).join(" ")].join(" ").toLowerCase();
  }

  function score(item, query, mission, index) {
    var source = haystack(item);
    var tokens = words(query);
    var scoreValue = Math.max(12, 61 - Math.min(index, 22));
    tokens.forEach(function (token) {
      if (String(item.name || "").toLowerCase().indexOf(token) >= 0) scoreValue += 22;
      if (String(item.category || "").toLowerCase().indexOf(token) >= 0) scoreValue += 16;
      if (source.indexOf(token) >= 0) scoreValue += 9;
    });
    (missionTerms[mission] || []).forEach(function (token) {
      if (source.indexOf(token) >= 0) scoreValue += 5;
    });
    if (item.featured) scoreValue += 3;
    return Math.min(98, Math.max(tokens.length || mission ? 54 : 71, scoreValue));
  }

  function initials(name) {
    return String(name || "AI").split(/\s+/).slice(0,2).map(function (part) { return part.charAt(0); }).join("");
  }

  function cardMarkup(item, fit, placement) {
    var verified = item.verified ? "Verified " + text(item.verified) : "Partner verified";
    var brand = item.color || "#8b5cf6";
    return '<article class="tool-card" data-tool-card data-id="' + text(item.id) + '" style="--brand:' + text(brand) + '">' +
      '<div class="card-top"><span class="tool-mark" aria-hidden="true">' + text(initials(item.name)) + '</span><span class="fit-score">' + fit + '%<small>fit score</small></span></div>' +
      '<p class="category">' + text(item.category) + '</p><h3>' + text(item.name) + '</h3>' +
      '<p class="summary">' + text(item.summary) + '</p>' +
      '<p class="reason"><strong>Why it fits:</strong> ' + text(item.why || item.best) + '</p>' +
      '<p class="limitation"><strong>Know first:</strong> ' + text(item.limit || item.offer) + '</p>' +
      '<div class="meta-row"><span class="tag">' + text(item.offer) + '</span><span class="tag verified">' + verified + '</span></div>' +
      '<div class="card-actions"><a class="btn btn-small" href="' + text(item.affiliateUrl) + '" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="' + text(item.id) + '" data-placement="' + text(placement) + '">' + text(item.cta || ("Check " + item.name)) + ' →</a>' +
      '<button class="icon-btn compare-add" type="button" data-id="' + text(item.id) + '" aria-label="Compare ' + text(item.name) + '">⇄</button>' +
      '<button class="icon-btn stack-add" type="button" data-id="' + text(item.id) + '" aria-label="Save ' + text(item.name) + '">＋</button>' +
      '<a class="details link-subtle" href="' + text(item.url) + '">Full verdict</a></div></article>';
  }

  function showMatches(query, mission) {
    var ranked = catalog.map(function (item, index) {
      return { item: item, score: score(item, query, mission, index) };
    }).sort(function (a,b) { return b.score - a.score; }).slice(0,3);
    var grid = document.querySelector("[data-matcher-results-grid]");
    var area = document.querySelector("[data-matcher-results]");
    if (!grid || !area) return;
    grid.innerHTML = ranked.map(function (entry) { return cardMarkup(entry.item, entry.score, "matcher-result"); }).join("");
    area.classList.add("is-visible");
    area.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
    bindDynamic(area);
    ranked.forEach(function (entry, position) {
      send("recommendation_impression", { offer_id: entry.item.id, position: position + 1, score: entry.score, mission: mission, query: query });
    });
    send("matcher_complete", { query: query, mission: mission, result_ids: ranked.map(function (entry) { return entry.item.id; }).join(",") });
    var history = read(STORE.history, []);
    history.unshift({ at: new Date().toISOString(), query: query, mission: mission, ids: ranked.map(function (entry) { return entry.item.id; }) });
    write(STORE.history, history.slice(0,12));
  }

  function initMatcher() {
    var form = document.querySelector("[data-matcher-form]");
    if (!form) return;
    var input = form.querySelector("input");
    var mission = "";
    Array.prototype.forEach.call(document.querySelectorAll("[data-mission]"), function (button) {
      button.addEventListener("click", function () {
        mission = button.dataset.mission;
        Array.prototype.forEach.call(document.querySelectorAll("[data-mission]"), function (item) { item.classList.toggle("is-active", item === button); });
        if (button.dataset.prompt && input) input.value = button.dataset.prompt;
        send("matcher_start", { mission: mission, source: button.closest(".mission-grid") ? "mission-card" : "chip" });
        if (button.closest(".mission-grid")) showMatches(input ? input.value : "", mission);
      });
    });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      send("matcher_start", { mission: mission, source: "query" });
      showMatches(input ? input.value.trim() : "", mission);
    });
    var params = new URLSearchParams(location.search);
    if (params.get("task") && input) { input.value = params.get("task"); showMatches(input.value, params.get("mission") || ""); }
  }

  function updateSavedButtons() {
    var saved = read(STORE.stack, []);
    Array.prototype.forEach.call(document.querySelectorAll(".stack-add"), function (button) {
      var active = saved.indexOf(button.dataset.id) >= 0;
      button.classList.toggle("is-saved", active);
      button.textContent = active ? "✓" : "＋";
    });
  }

  function renderStack() {
    var panel = document.querySelector("[data-stack-panel]");
    if (!panel) return;
    var target = panel.querySelector("[data-stack-list]");
    var ids = read(STORE.stack, []);
    if (!ids.length) {
      target.innerHTML = '<p class="empty">Your stack is empty. Save useful tools as you browse.</p>';
      return;
    }
    target.innerHTML = ids.map(function (id) {
      var item = itemById(id);
      if (!item) return "";
      return '<div class="saved-item"><div><a href="' + text(item.url) + '">' + text(item.name) + '</a><small>' + text(item.category) + '</small></div><button class="icon-btn stack-remove" data-id="' + text(item.id) + '" aria-label="Remove ' + text(item.name) + '">×</button></div>';
    }).join("");
    Array.prototype.forEach.call(target.querySelectorAll(".stack-remove"), function (button) {
      button.addEventListener("click", function () { toggleStackItem(button.dataset.id, false); });
    });
  }

  function toggleStackItem(id, announce) {
    var ids = read(STORE.stack, []);
    var exists = ids.indexOf(id) >= 0;
    ids = exists ? ids.filter(function (item) { return item !== id; }) : ids.concat(id);
    write(STORE.stack, ids);
    updateSavedButtons();
    renderStack();
    if (announce !== false) send(exists ? "stack_remove" : "stack_save", { offer_id: id });
  }

  function renderCompareDrawer() {
    compareItems = read(STORE.compare, []).slice(0,2);
    var drawer = document.querySelector("[data-compare-drawer]");
    if (!drawer) return;
    var target = drawer.querySelector("[data-compare-items]");
    target.innerHTML = compareItems.map(function (id) {
      var item = itemById(id);
      return item ? '<span class="compare-chip">' + text(item.name) + '</span>' : "";
    }).join("");
    drawer.classList.toggle("is-open", compareItems.length > 0);
  }

  function toggleCompare(id) {
    compareItems = read(STORE.compare, []).slice(0,2);
    var index = compareItems.indexOf(id);
    if (index >= 0) compareItems.splice(index,1);
    else if (compareItems.length < 2) compareItems.push(id);
    else compareItems[1] = id;
    write(STORE.compare, compareItems);
    renderCompareDrawer();
    send(index >= 0 ? "compare_remove" : "compare_add", { offer_id: id, compare_count: compareItems.length });
  }

  function openComparison() {
    var modal = document.querySelector("[data-compare-modal]");
    if (!modal || compareItems.length < 2) return;
    var target = modal.querySelector("[data-comparison-grid]");
    target.innerHTML = compareItems.map(function (id) {
      var item = itemById(id);
      if (!item) return "";
      return '<article class="comparison-column"><span class="tool-mark">' + text(initials(item.name)) + '</span><h3>' + text(item.name) + '</h3><dl><dt>Best for</dt><dd>' + text(item.best) + '</dd><dt>Current pricing note</dt><dd>' + text(item.offer) + '</dd><dt>Why consider it</dt><dd>' + text(item.why) + '</dd><dt>Limitation</dt><dd>' + text(item.limit) + '</dd><dt>Verified</dt><dd>' + text(item.verified) + '</dd></dl><a class="btn" href="' + text(item.affiliateUrl) + '" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="' + text(item.id) + '" data-placement="compare-modal">' + text(item.cta) + ' →</a></article>';
    }).join("");
    modal.classList.add("is-open");
    modal.querySelector(".close-btn").focus();
    send("compare_open", { offer_ids: compareItems.join(",") });
  }

  function bindDynamic(root) {
    Array.prototype.forEach.call((root || document).querySelectorAll(".stack-add"), function (button) {
      if (button.dataset.bound) return;
      button.dataset.bound = "1";
      button.addEventListener("click", function () { toggleStackItem(button.dataset.id); });
    });
    Array.prototype.forEach.call((root || document).querySelectorAll(".compare-add"), function (button) {
      if (button.dataset.bound) return;
      button.dataset.bound = "1";
      button.addEventListener("click", function () { toggleCompare(button.dataset.id); });
    });
    updateSavedButtons();
  }

  function initPanels() {
    var panel = document.querySelector("[data-stack-panel]");
    Array.prototype.forEach.call(document.querySelectorAll("[data-open-stack]"), function (button) {
      button.addEventListener("click", function () { if (panel) { panel.classList.add("is-open"); renderStack(); panel.querySelector(".close-btn").focus(); } });
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-close-panel]"), function (button) {
      button.addEventListener("click", function () { button.closest(".stack-panel,.modal-backdrop").classList.remove("is-open"); });
    });
    var compareOpen = document.querySelector("[data-open-compare]");
    if (compareOpen) compareOpen.addEventListener("click", openComparison);
    var share = document.querySelector("[data-share-compare]");
    if (share) share.addEventListener("click", function () {
      var url = new URL(location.origin + "/ai-tool-finder.html");
      url.searchParams.set("compare", compareItems.join(","));
      navigator.clipboard && navigator.clipboard.writeText(url.toString());
      share.textContent = "Link copied";
      send("compare_share", { offer_ids: compareItems.join(",") });
    });
    var clear = document.querySelector("[data-clear-compare]");
    if (clear) clear.addEventListener("click", function () { write(STORE.compare, []); renderCompareDrawer(); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") Array.prototype.forEach.call(document.querySelectorAll(".is-open"), function (item) { item.classList.remove("is-open"); });
    });
  }

  function initCatalogFilters() {
    var search = document.getElementById("tool-search");
    var cards = Array.prototype.slice.call(document.querySelectorAll("#tool-grid [data-tool-card]"));
    var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-filter]"));
    var count = document.getElementById("finder-count");
    var empty = document.getElementById("no-tools");
    if (!search || !cards.length) return;
    var filter = "all";
    function update() {
      var tokens = words(search.value);
      var shown = 0;
      cards.forEach(function (card) {
        var matchCategory = filter === "all" || card.dataset.category === filter;
        var source = card.dataset.search || card.textContent.toLowerCase();
        var matchText = !tokens.length || tokens.every(function (token) { return source.indexOf(token) >= 0; });
        card.hidden = !(matchCategory && matchText);
        if (!card.hidden) shown += 1;
      });
      if (count) count.textContent = shown + " matching verified partner tool" + (shown === 1 ? "" : "s");
      if (empty) empty.hidden = shown !== 0;
    }
    buttons.forEach(function (button) {
      button.addEventListener("click", function () { filter = button.dataset.filter; buttons.forEach(function (item) { item.classList.toggle("active", item === button); }); update(); });
    });
    search.addEventListener("input", update);
    update();
  }

  function initNews() {
    var target = document.querySelector("[data-news-radar]");
    if (!target || !Array.isArray(window.AI1_NEWS_ITEMS)) return;
    target.innerHTML = window.AI1_NEWS_ITEMS.slice(0,4).map(function (item) {
      return '<a class="news-item" href="' + text(item.related && item.related.url ? item.related.url : "news.html") + '" data-content-route data-placement="home-news-radar"><time>' + text(item.display_date || "New") + '</time><strong>' + text(item.title) + '</strong><small>' + text(item.category || item.source) + ' →</small></a>';
    }).join("");
  }

  function initCalculator() {
    var form = document.querySelector("[data-value-calculator]");
    if (!form) return;
    var output = form.querySelector("[data-calc-output]");
    function calculate() {
      var monthly = Number(form.querySelector("[name=monthly]").value || 0);
      var hours = Number(form.querySelector("[name=hours]").value || 0);
      var value = Number(form.querySelector("[name=value]").value || 0);
      var difference = hours * value - monthly;
      output.textContent = difference > 0 ? "Illustrative monthly value after cost: " + difference.toLocaleString(undefined,{style:"currency",currency:"USD",maximumFractionDigits:0}) : "Enter your expected time saving and hourly value to model the trade-off.";
    }
    form.addEventListener("input", calculate);
    calculate();
  }

  function initTabs() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-tabs]"), function (tabs) {
      var buttons = tabs.querySelectorAll("[data-tab]");
      var panel = tabs.querySelector("[data-tab-panel]");
      Array.prototype.forEach.call(buttons, function (button) {
        button.addEventListener("click", function () {
          Array.prototype.forEach.call(buttons, function (item) { item.classList.toggle("is-active", item === button); });
          panel.textContent = button.dataset.content;
          send("use_case_tab", { offer_id: tabs.dataset.offerId, tab: button.textContent });
        });
      });
    });
  }

  function initNav() {
    var toggle = document.querySelector(".nav-toggle");
    var nav = document.querySelector(".primary-nav");
    if (toggle && nav) toggle.addEventListener("click", function () { var open = nav.classList.toggle("is-open"); toggle.setAttribute("aria-expanded", String(open)); });
  }

  function initWatch() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-watch-offer]"), function (button) {
      var id = button.dataset.watchOffer;
      var ids = read(STORE.watch, []);
      if (ids.indexOf(id) >= 0) { button.classList.add("is-saved"); button.textContent = "Watching this deal ✓"; }
      button.addEventListener("click", function () {
        var list = read(STORE.watch, []);
        if (list.indexOf(id) < 0) list.push(id);
        write(STORE.watch, list);
        button.classList.add("is-saved"); button.textContent = "Watching this deal ✓";
        send("watchlist_add", { offer_id: id });
      });
    });
  }

  function initNewVisit() {
    var previous = read(STORE.visit, "");
    var badges = document.querySelectorAll("[data-new-date]");
    if (previous) Array.prototype.forEach.call(badges, function (badge) { if (badge.dataset.newDate > previous.slice(0,10)) badge.hidden = false; });
    write(STORE.visit, new Date().toISOString());
  }

  document.addEventListener("DOMContentLoaded", function () {
    parseCatalog();
    var queryCompare = new URLSearchParams(location.search).get("compare");
    if (queryCompare) write(STORE.compare, queryCompare.split(",").filter(Boolean).slice(0,2));
    initNav(); initMatcher(); initCatalogFilters(); initPanels(); initNews(); initCalculator(); initTabs(); initWatch(); initNewVisit();
    bindDynamic(document); renderStack(); renderCompareDrawer();
  });
})();
