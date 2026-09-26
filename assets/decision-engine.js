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
  var previousVisit = "";

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
    var stop = { a:1, an:1, and:1, for:1, from:1, get:1, i:1, in:1, into:1, me:1, my:1, need:1, of:1, one:1, our:1, run:1, the:1, to:1, tool:1, turn:1, use:1, want:1, with:1, you:1, your:1 };
    return String(value || "").toLowerCase().split(/[^a-z0-9]+/).filter(function (word) { return word.length > 2 && !stop[word]; });
  }

  function hasWord(sourceWords, token) {
    return sourceWords.some(function (word) {
      return word === token || (token.length > 4 && word.indexOf(token) === 0) || (word.length > 4 && token.indexOf(word) === 0);
    });
  }

  var missionTerms = {
    create: ["audio","content","create","design","image","podcast","presentation","video","voice","write","writing"],
    sell: ["advertising","conversion","email","lead","marketing","research","sales","seo","trade"],
    automate: ["automation","business","productivity","workflow","operations","tracking"],
    research: ["analysis","data","database","document","pdf","research","search","trade"],
    build: ["code","developer","development","hosting","website","web","database"]
  };

  function inferMission(query) {
    var sourceWords = words(query);
    var winner = "";
    var winnerScore = 0;
    Object.keys(missionTerms).forEach(function (mission) {
      var value = missionTerms[mission].filter(function (term) { return hasWord(sourceWords, term); }).length;
      if (value > winnerScore) { winner = mission; winnerScore = value; }
    });
    return winner;
  }

  function haystack(item) {
    return [item.name,item.category,item.summary,item.best,item.why,item.limit,item.offer,(item.useCases || []).join(" ")].join(" ").toLowerCase();
  }

  function score(item, query, mission, index) {
    var source = haystack(item);
    var tokens = words(query);
    var sourceWords = words(source);
    var nameWords = words(item.name);
    var categoryWords = words(item.category);
    var scoreValue = Math.max(12, 61 - Math.min(index, 22));
    tokens.forEach(function (token) {
      if (hasWord(nameWords, token)) scoreValue += 22;
      if (hasWord(categoryWords, token)) scoreValue += 16;
      if (hasWord(sourceWords, token)) scoreValue += 9;
    });
    (missionTerms[mission] || []).forEach(function (token) {
      if (hasWord(sourceWords, token)) scoreValue += 5;
    });
    if (item.featured) scoreValue += 3;
    return Math.min(98, Math.max(tokens.length || mission ? 54 : 71, scoreValue));
  }

  function initials(name) {
    return String(name || "AI").split(/\s+/).slice(0,2).map(function (part) { return part.charAt(0); }).join("");
  }

  function imageMarkup(item, kind) {
    var screenshot = item.screenshotUrl ? '<img src="' + text(item.screenshotUrl) + '" alt="' + text(item.name) + ' product website preview" width="1000" height="563" loading="lazy" decoding="async">' : '';
    var logo = item.logoUrl ? '<img src="' + text(item.logoUrl) + '" alt="' + text(item.name) + ' logo" width="48" height="48" loading="lazy" decoding="async">' : '';
    return '<div class="product-visual product-visual-' + text(kind || "card") + '">' + screenshot + '<span class="product-logo">' + logo + '<b aria-hidden="true">' + text(initials(item.name)) + '</b></span></div>';
  }

  function cardMarkup(item, fit, placement, position) {
    var verified = item.verified ? "Verified " + text(item.verified) : "Partner verified";
    var brand = item.color || "#8b5cf6";
    var winner = position === 0 ? '<span class="winner-badge">Recommended winner</span>' : '';
    return '<article class="tool-card' + (position === 0 ? ' is-winner' : '') + '" data-tool-card data-id="' + text(item.id) + '" style="--brand:' + text(brand) + '">' + imageMarkup(item, "card") +
      '<div class="card-top">' + winner + '<span class="fit-score"><span class="fit-number" style="--fit:' + fit + '">' + fit + '%</span><small>fit score</small></span></div>' +
      '<p class="category">' + text(item.category) + '</p><h3>' + text(item.name) + '</h3>' +
      '<p class="summary">' + text(item.summary) + '</p>' +
      '<p class="reason"><strong>' + (position === 0 ? 'Why it wins:' : 'Why it fits:') + '</strong> ' + text(item.why || item.best) + '</p>' +
      '<p class="outcome"><strong>Outcome:</strong> ' + text((item.useCases || [])[0] || item.best) + '</p>' +
      '<p class="limitation"><strong>Know first:</strong> ' + text(item.limit || item.offer) + '</p>' +
      '<div class="meta-row"><span class="tag">' + text(item.price || item.offer) + '</span><span class="tag">' + text(item.trial || "Check trial status") + '</span><span class="tag verified">' + verified + '</span></div>' +
      '<div class="card-actions"><a class="btn btn-small" href="' + text(item.affiliateUrl) + '" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="' + text(item.id) + '" data-placement="' + text(placement) + '">' + text(item.cta || ("Check " + item.name)) + ' →</a>' +
      '<button class="icon-btn compare-add" type="button" data-id="' + text(item.id) + '" aria-label="Compare ' + text(item.name) + '">⇄</button>' +
      '<button class="icon-btn stack-add" type="button" data-id="' + text(item.id) + '" aria-label="Save ' + text(item.name) + '">＋</button>' +
      '<a class="details link-subtle" href="' + text(item.url) + '">Full verdict</a></div></article>';
  }

  function setupSelection(query, mission) {
    mission = mission || inferMission(query);
    var all = catalog.map(function (item, index) {
      return { item: item, score: score(item, query, mission, index) };
    }).sort(function (a,b) { return b.score - a.score; });
    var chosen = [];
    var categories = {};
    all.forEach(function (entry) {
      var category = String(entry.item.category || "other").toLowerCase();
      if (chosen.length < 3 && !categories[category]) {
        chosen.push(entry);
        categories[category] = true;
      }
    });
    all.forEach(function (entry) {
      if (chosen.length < 3 && chosen.indexOf(entry) < 0) chosen.push(entry);
    });
    return chosen.slice(0, 3);
  }

  function currentToolMatches(value) {
    var source = String(value || "").toLowerCase();
    if (!source) return [];
    return catalog.filter(function (item) {
      var name = String(item.name || "").toLowerCase();
      return name.length > 2 && source.indexOf(name) >= 0;
    });
  }

  function planDecision(item, position, currentTools) {
    var exact = currentTools.find(function (existing) { return String(existing.id) === String(item.id); });
    if (exact) return { label: "Keep", note: "You already use this. Keep it unless the limitation below blocks the job." };
    var overlap = currentTools.find(function (existing) {
      return String(existing.category || "").toLowerCase() === String(item.category || "").toLowerCase();
    });
    if (overlap) return { label: "Compare first", note: "Compare it with " + overlap.name + " before replacing anything." };
    if (position === 0) return { label: "Start here", note: "This is the strongest first move for the result you described." };
    if (position === 1) return { label: "Add if needed", note: "Add this only when the first tool cannot complete this part of the workflow." };
    return { label: "Consider later", note: "Keep this as the expansion step once the core workflow proves useful." };
  }

  function planCardMarkup(item, fit, position, currentTools) {
    var decision = planDecision(item, position, currentTools);
    var brand = item.color || "#8b5cf6";
    return '<article class="plan-card" style="--brand:' + text(brand) + '">' +
      '<div class="plan-card-top"><span class="plan-step">' + (position + 1) + '</span><span class="plan-action">' + text(decision.label) + '</span><span class="plan-fit">' + fit + '% fit</span></div>' +
      imageMarkup(item, "plan") +
      '<p class="category">' + text(item.category) + '</p><h3>' + text(item.name) + '</h3>' +
      '<p class="plan-role">' + text(decision.note) + '</p>' +
      '<p class="outcome"><strong>Its job:</strong> ' + text((item.useCases || [])[0] || item.best || item.summary) + '</p>' +
      '<p class="limitation"><strong>Check before paying:</strong> ' + text(item.limit || item.offer || "Confirm the current plan and limits.") + '</p>' +
      '<div class="plan-cost"><span>Current pricing signal</span><strong>' + text(item.price || item.offer || "Check current plans") + '</strong></div>' +
      '<div class="plan-actions"><a class="btn btn-small" href="' + text(item.affiliateUrl) + '" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="' + text(item.id) + '" data-placement="setup-plan">' + text(item.cta || ("Open " + item.name)) + ' →</a><a class="details link-subtle" href="' + text(item.url) + '">Read the evidence</a></div></article>';
  }

  function setupOptions(form) {
    var team = form.querySelector("[data-setup-team]");
    var budget = form.querySelector("[data-setup-budget]");
    var current = form.querySelector("[data-setup-current]");
    return {
      team: team ? team.value : "",
      budget: budget ? budget.value : "",
      current: current ? current.value.trim() : ""
    };
  }

  function showMatches(query, mission, options) {
    options = options || {};
    var grid = document.querySelector("[data-matcher-results-grid]");
    var area = document.querySelector("[data-matcher-results]");
    if (!grid || !area) return;
    var setupMode = area.hasAttribute("data-setup-plan");
    var ranked = setupMode ? setupSelection(query, mission) : catalog.map(function (item, index) {
      return { item: item, score: score(item, query, mission, index) };
    }).sort(function (a,b) { return b.score - a.score; }).slice(0,3);
    var currentTools = currentToolMatches(options.current);
    grid.innerHTML = setupMode ? ranked.map(function (entry, position) {
      return planCardMarkup(entry.item, entry.score, position, currentTools);
    }).join("") : ranked.map(function (entry, position) {
      return cardMarkup(entry.item, entry.score, "matcher-result", position);
    }).join("");
    if (setupMode) {
      var title = area.querySelector("[data-plan-title]");
      var meta = area.querySelector("[data-plan-meta]");
      var budget = area.querySelector("[data-plan-budget]");
      if (title) title.textContent = "Your setup for “" + query + "”";
      if (meta) {
        var teamLabels = { solo: "Built for one person", small: "Built for a 2–10 person team", growing: "Built for an 11–50 person team", large: "Built for a 51+ person team" };
        meta.textContent = (teamLabels[options.team] || "Built around the job") + ". " + (currentTools.length ? "Existing tools were checked for overlap." : "Each tool has one clear role.");
      }
      if (budget) budget.textContent = options.budget ? "$" + options.budget + "/month target — verify prices" : "Confirm current plans";
      var params = new URLSearchParams();
      params.set("task", query);
      if (options.team) params.set("team", options.team);
      if (options.budget) params.set("budget", options.budget);
      if (options.current) params.set("current", options.current);
      if (window.history && window.history.replaceState) window.history.replaceState(null, "", location.pathname + "?" + params.toString() + "#build");
    }
    area.classList.add("is-visible");
    area.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
    bindDynamic(area);
    initCardCtaExperiment();
    ranked.forEach(function (entry, position) {
      send("recommendation_impression", { offer_id: entry.item.id, position: position + 1, score: entry.score, mission: mission, query: query });
    });
    send(setupMode ? "setup_plan_complete" : "matcher_complete", { query: query, mission: mission, team: options.team || "", budget: options.budget || "", result_ids: ranked.map(function (entry) { return entry.item.id; }).join(",") });
    var history = read(STORE.history, []);
    history.unshift({ at: new Date().toISOString(), query: query, mission: mission, team: options.team || "", budget: options.budget || "", current: options.current || "", ids: ranked.map(function (entry) { return entry.item.id; }) });
    write(STORE.history, history.slice(0,12));
    renderHistory();
  }

  function initMatcher() {
    var form = document.querySelector("[data-matcher-form]");
    if (!form) return;
    var input = form.querySelector("[data-setup-goal], input[type='search'], input");
    var mission = "";
    Array.prototype.forEach.call(form.querySelectorAll("[data-example-prompt]"), function (button) {
      button.addEventListener("click", function () {
        if (!input) return;
        input.value = button.dataset.examplePrompt || "";
        input.focus();
      });
    });
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
      if (!input || !input.value.trim()) { if (input) input.focus(); return; }
      send("matcher_start", { mission: mission, source: "query" });
      showMatches(input.value.trim(), mission, setupOptions(form));
    });
    var params = new URLSearchParams(location.search);
    var team = form.querySelector("[data-setup-team]");
    var budget = form.querySelector("[data-setup-budget]");
    var current = form.querySelector("[data-setup-current]");
    if (team && params.get("team")) team.value = params.get("team");
    if (budget && params.get("budget")) budget.value = params.get("budget");
    if (current && params.get("current")) current.value = params.get("current");
    if (params.get("task") && input) { input.value = params.get("task"); showMatches(input.value, params.get("mission") || "", setupOptions(form)); }
    var share = document.querySelector("[data-share-plan]");
    if (share) share.addEventListener("click", function () {
      var url = location.href;
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).catch(function () {});
      share.textContent = "Plan link copied ✓";
      setTimeout(function () { share.textContent = "Copy this plan"; }, 1800);
      send("setup_plan_shared", { method: "copy_link" });
    });
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
      target.innerHTML = '<div class="empty-state"><span class="elephant-state" aria-hidden="true"></span><p>Your stack is empty. Save useful tools as you browse.</p></div>';
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

  function initHomePicks() {
    var target = document.querySelector("[data-home-picks]");
    if (!target || !catalog.length) return;
    var history = read(STORE.history, []);
    var latest = history[0] || {};
    var saved = read(STORE.stack, []);
    var watched = read(STORE.watch, []);
    var ranked = catalog.map(function (item, index) {
      var value = score(item, latest.query || "", latest.mission || "", index);
      if (saved.indexOf(item.id) >= 0) value += 5;
      if (watched.indexOf(item.id) >= 0) value += 3;
      var age = Math.max(0, (Date.now() - Date.parse(item.verified || "2000-01-01")) / 86400000);
      value += Math.max(0, 4 - Math.floor(age / 30));
      return { item: item, score: Math.min(98, value) };
    }).sort(function (a,b) { return b.score - a.score; }).slice(0,6);
    target.innerHTML = ranked.map(function (entry) { return cardMarkup(entry.item, entry.score, "homepage-pick"); }).join("");
    bindDynamic(target);
  }

  function renderHistory() {
    var target = document.querySelector("[data-comparison-history]");
    if (!target) return;
    var history = read(STORE.history, []).slice(0,4);
    if (!history.length) {
      target.innerHTML = '<p class="empty compact">Run a match to build your decision history.</p>';
      return;
    }
    target.innerHTML = history.map(function (entry, index) {
      var names = (entry.ids || []).map(function (id) { var item = itemById(id); return item && item.name; }).filter(Boolean);
      return '<button class="history-item" type="button" data-history-index="' + index + '"><strong>' + text(entry.query || entry.mission || "Tool shortlist") + '</strong><small>' + text(names.join(" · ")) + '</small></button>';
    }).join("");
    Array.prototype.forEach.call(target.querySelectorAll("[data-history-index]"), function (button) {
      button.addEventListener("click", function () {
        var entry = history[Number(button.dataset.historyIndex)];
        if (!entry) return;
        write(STORE.compare, (entry.ids || []).slice(0,2));
        renderCompareDrawer();
        openComparison();
      });
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
      return '<article class="comparison-column">' + imageMarkup(item, "compare") + '<h3>' + text(item.name) + '</h3><dl><dt>Best for</dt><dd>' + text(item.best) + '</dd><dt>Price / offer</dt><dd>' + text(item.price || item.offer) + '</dd><dt>Trial</dt><dd>' + text(item.trial || "Check current availability") + '</dd><dt>Why consider it</dt><dd>' + text(item.why) + '</dd><dt>Limitation</dt><dd>' + text(item.limit) + '</dd><dt>Verified</dt><dd>' + text(item.verified) + '</dd></dl><a class="btn" href="' + text(item.affiliateUrl) + '" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="' + text(item.id) + '" data-placement="compare-modal">' + text(item.cta) + ' →</a></article>';
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
    var shareStack = document.querySelector("[data-share-stack]");
    if (shareStack) shareStack.addEventListener("click", function () {
      var ids = read(STORE.stack, []);
      var url = new URL(location.origin + "/ai-tool-finder.html");
      url.searchParams.set("stack", ids.join(","));
      if (navigator.clipboard) navigator.clipboard.writeText(url.toString());
      shareStack.textContent = ids.length ? "Stack link copied" : "Empty stack link copied";
      send("stack_share", { offer_ids: ids.join(",") });
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

  function radarMarkup(item) {
    return '<a class="news-item" href="' + text(item.url || "news.html") + '" data-content-route data-placement="home-news-radar" data-new-date="' + text(item.date || "") + '"><time>' + text(item.label || "New") + '</time><strong>' + text(item.title) + '</strong><small>' + text(item.kind || "AI news") + ' →</small></a>';
  }

  function initNews() {
    var target = document.querySelector("[data-news-radar]");
    if (!target || !Array.isArray(window.AI1_NEWS_ITEMS)) return;
    var news = window.AI1_NEWS_ITEMS.slice(0,3).map(function (item) {
      return { title: item.title, url: item.related && item.related.url ? item.related.url : "news.html", label: item.display_date || "New", kind: item.category || item.source, date: String(item.published_at || "").slice(0,10) };
    });
    var newest = catalog.slice().sort(function (a,b) { return String(b.verified || "").localeCompare(String(a.verified || "")); }).slice(0,2).map(function (item) {
      return { title: item.name + " joined the verified decision engine", url: item.url, label: item.verified, kind: "New tool", date: item.verified };
    });
    fetch("/data/offer_change_alerts.json", { credentials: "same-origin", cache: "no-cache" }).then(function (response) { return response.ok ? response.json() : { alerts: [] }; }).then(function (payload) {
      var changes = (payload.alerts || []).slice(0,2).map(function (alert) {
        var item = itemById(alert.offer_id);
        return { title: (item ? item.name : "A tracked tool") + " pricing or availability changed", url: item ? item.url : "offer-updates.html", label: alert.detected_on, kind: "Price / plan change", date: alert.detected_on };
      });
      target.innerHTML = changes.concat(newest, news).slice(0,6).map(radarMarkup).join("");
      initNewVisit();
    }).catch(function () { target.innerHTML = newest.concat(news).slice(0,6).map(radarMarkup).join(""); });
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
    var watched = read(STORE.watch, []);
    var target = document.querySelector("[data-watch-alerts]");
    if (!target || !watched.length || !window.fetch) return;
    fetch("/data/offer_change_alerts.json", { credentials: "same-origin", cache: "no-cache" }).then(function (response) { return response.ok ? response.json() : { alerts: [] }; }).then(function (payload) {
      var seen = read("ai1_seen_alerts", []);
      var alerts = (payload.alerts || []).filter(function (alert) { return watched.indexOf(alert.offer_id) >= 0; }).filter(function (alert, index, all) { return all.findIndex(function (item) { return item.offer_id === alert.offer_id; }) === index; });
      if (!alerts.length) return;
      target.innerHTML = alerts.map(function (alert) {
        var item = itemById(alert.offer_id);
        var key = alert.offer_id + ":" + alert.detected_on;
        return '<a class="alert-item' + (seen.indexOf(key) < 0 ? ' is-new' : '') + '" href="' + text(item ? item.url : "offer-updates.html") + '"><span class="elephant-state" aria-hidden="true"></span><span><strong>' + text(item ? item.name : "Tracked tool") + ' changed</strong><small>' + text(alert.detected_on) + ' · Recheck price or availability</small></span></a>';
      }).join("");
      write("ai1_seen_alerts", alerts.map(function (alert) { return alert.offer_id + ":" + alert.detected_on; }));
    }).catch(function () {});
  }

  function initNewVisit() {
    var badges = document.querySelectorAll("[data-new-date]");
    var recent = [];
    if (previousVisit) Array.prototype.forEach.call(badges, function (badge) {
      if (badge.dataset.newDate > previousVisit.slice(0,10)) {
        badge.hidden = false;
        var card = badge.closest("[data-tool-card]");
        if (card && recent.indexOf(card.dataset.id) < 0) recent.push(card.dataset.id);
      }
    });
    var target = document.querySelector("[data-new-since-list]");
    if (target && recent.length) target.innerHTML = recent.slice(0,4).map(function (id) {
      var item = itemById(id);
      return item ? '<a class="new-since-item" href="' + text(item.url) + '"><strong>' + text(item.name) + '</strong><small>Verified ' + text(item.verified) + '</small></a>' : '';
    }).join("");
    write(STORE.visit, new Date().toISOString());
  }

  function initOptIns() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-email-opt-in]"), function (link) {
      link.addEventListener("click", function () { send("email_opt_in", { placement: "weekly-shortlist" }); });
    });
  }

  function initCardCtaExperiment() {
    if (!window.fetch) return;
    fetch("/data/conversion_strategy.json", { credentials: "same-origin", cache: "no-cache" }).then(function (response) { return response.ok ? response.json() : {}; }).then(function (strategy) {
      var cards = strategy.cards || {};
      var hash = 0;
      var source = anonymousSession() + ":" + location.pathname;
      for (var index = 0; index < source.length; index += 1) hash = ((hash << 5) - hash + source.charCodeAt(index)) | 0;
      var winner = cards.mode === "winner" && (cards.winner === "a" || cards.winner === "b") ? cards.winner : null;
      var key = winner ? (Math.abs(hash) % 10 ? winner : (winner === "a" ? "b" : "a")) : (Math.abs(hash) % 2 ? "a" : "b");
      var template = cards.variants && cards.variants[key] && cards.variants[key].cta;
      if (!template) return;
      Array.prototype.forEach.call(document.querySelectorAll(".tool-card a[data-affiliate-offer]"), function (link) {
        var item = itemById(link.dataset.offerId);
        if (!item) return;
        link.textContent = template.replace("{name}", item.name) + " →";
        link.dataset.placement = (link.dataset.placement || "card") + "-card-cro-" + key;
      });
    }).catch(function () {});
  }

  document.addEventListener("DOMContentLoaded", function () {
    parseCatalog();
    previousVisit = read(STORE.visit, "");
    var params = new URLSearchParams(location.search);
    var queryCompare = params.get("compare");
    if (queryCompare) write(STORE.compare, queryCompare.split(",").filter(Boolean).slice(0,2));
    var queryStack = params.get("stack");
    if (queryStack) write(STORE.stack, queryStack.split(",").filter(function (id) { return !!itemById(id); }).slice(0,20));
    initNav(); initMatcher(); initHomePicks(); initCatalogFilters(); initPanels(); initNews(); initCalculator(); initTabs(); initWatch(); initNewVisit(); initOptIns(); initCardCtaExperiment();
    bindDynamic(document); renderStack(); renderHistory(); renderCompareDrawer();
  });
})();
