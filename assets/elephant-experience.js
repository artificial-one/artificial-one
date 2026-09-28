(function () {
  "use strict";
  var DATA_URL = "/data/elephant_experience.json";
  var state = { data: null, question: "", shortlist: [], studio: [], studioCosts: {}, decisionId: "" };

  function h(value) { return String(value || "").replace(/[&<>"']/g, function (c) { return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }
  function safeUrl(value, fallback) { value = String(value || ""); return (/^https:\/\//i.test(value) || /^[a-z0-9][a-z0-9._\/-]*\.html(?:[?#].*)?$/i.test(value)) ? h(value) : fallback; }
  function load() { if (state.data) return Promise.resolve(state.data); return fetch(DATA_URL, { credentials: "same-origin" }).then(function (r) { if (!r.ok) throw new Error("Catalogue unavailable"); return r.json(); }).then(function (d) { state.data = d; return d; }); }
  function words(value) { var stop = {the:1,and:1,for:1,with:1,that:1,this:1,from:1,need:1,want:1,tool:1,software:1,help:1}; return (String(value || "").toLowerCase().match(/[a-z0-9]+/g) || []).filter(function (w) { return w.length > 2 && !stop[w]; }); }
  function source(tool) { return [tool.name, tool.category, tool.summary, tool.best_for].concat(tool.features || [], tool.platforms || []).join(" ").toLowerCase(); }
  function score(tool, query, options) {
    var hay = source(tool), tokens = words(query), value = 0, hits = [];
    tokens.forEach(function (token) { if (String(tool.name).toLowerCase().indexOf(token) >= 0) { value += 16; hits.push(token); } else if (String(tool.category).toLowerCase().indexOf(token) >= 0) { value += 11; hits.push(token); } else if (hay.indexOf(token) >= 0) { value += 5; hits.push(token); } });
    if (options.budget === "free" && tool.free) value += 18;
    if (options.budget === "value" && tool.free) value += 8;
    if (options.team === "solo" && /creator|individual|freelanc|solo|small/.test(hay)) value += 5;
    if (options.team === "small" && /team|business|collabor/.test(hay)) value += 5;
    if (options.team === "large" && /enterprise|organization|team|scale/.test(hay)) value += 7;
    if (tool.status === "reviewed") value += 5; else if (tool.status === "destination-checked") value += 2;
    if (tool.monetized) value += 1;
    [
      [/lead|outreach|prospect|sales|pipeline|crm/i, /lead|outreach|prospect|sales|pipeline|crm|email enrichment/i],
      [/webinar|podcast|recording|clip|video|audio/i, /webinar|podcast|recording|clip|video|audio|transcript/i],
      [/document|pdf|signature|approval/i, /document|pdf|signature|approval|contract/i],
      [/website|landing page|site builder/i, /website|landing page|site builder|web design/i],
      [/course|lesson|student|learning/i, /course|lesson|student|learning|education/i],
      [/support|customer service|help desk/i, /support|customer service|help desk|chatbot/i],
      [/search|retrieval|knowledge base|rag/i, /search|retrieval|knowledge base|vector|rag/i]
    ].forEach(function (intent) { if (intent[0].test(query) && intent[1].test(hay)) value += 28; });
    return { tool: tool, score: value, hits: hits.filter(function (x, i, a) { return a.indexOf(x) === i; }).slice(0, 4) };
  }
  function rank(query, options, limit) { return state.data.tools.map(function (tool) { return score(tool, query, options || {}); }).sort(function (a, b) { return b.score - a.score || a.tool.name.localeCompare(b.tool.name); }).slice(0, limit || 3); }
  function rankDiverse(query, options, limit) {
    var candidates = rank(query, options, 40), selected = [], categories = {};
    candidates.forEach(function (entry) { if (selected.length < limit && !categories[entry.tool.category]) { selected.push(entry); categories[entry.tool.category] = true; } });
    candidates.forEach(function (entry) { if (selected.length < limit && !selected.some(function (item) { return item.tool.id === entry.tool.id; })) selected.push(entry); });
    return selected.slice(0, limit);
  }
  function rationale(entry) { var bits = []; if (entry.hits.length) bits.push("matches " + entry.hits.join(", ")); if (entry.tool.status === "reviewed") bits.push("evidence-reviewed record"); if (entry.tool.free) bits.push("recorded free-plan signal"); return bits.slice(0, 3).join(" · ") || "closest recorded workflow fit"; }
  function track(name, meta) { if (window.ai1Track) window.ai1Track(name, meta || {}); }
  function encode(value) { return btoa(unescape(encodeURIComponent(JSON.stringify(value)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
  function decode(value) { try { var text = String(value || "").replace(/-/g, "+").replace(/_/g, "/"); while (text.length % 4) text += "="; return JSON.parse(decodeURIComponent(escape(atob(text)))); } catch (_) { return null; } }
  function hash(value) { var first = 2166136261, second = 2246822507, text = String(value); for (var i = 0; i < text.length; i += 1) { first = Math.imul(first ^ text.charCodeAt(i), 16777619); second = Math.imul(second ^ text.charCodeAt(i), 3266489909); } return (first >>> 0).toString(16).padStart(8,"0") + (second >>> 0).toString(16).padStart(8,"0"); }
  function anonymousId() {
    var key = "ao_outcome_id";
    try {
      var saved = localStorage.getItem(key); if (/^[a-f0-9]{32,64}$/i.test(saved || "")) return saved;
      var bytes = new Uint8Array(16); crypto.getRandomValues(bytes);
      var created = Array.prototype.map.call(bytes, function (value) { return value.toString(16).padStart(2, "0"); }).join("");
      localStorage.setItem(key, created); return created;
    } catch (_) { return hash(String(Date.now()) + Math.random()) + hash(Math.random()); }
  }
  function toolById(id) { return state.data.tools.find(function (item) { return item.id === id; }); }
  function entriesFromIds(ids, query, options) { return (ids || []).map(function (id) { var tool = toolById(id); return tool ? score(tool, query, options || {}) : null; }).filter(Boolean); }
  function copy(button, value, label) { if (navigator.clipboard) navigator.clipboard.writeText(value); button.textContent = label || "Link copied"; window.setTimeout(function () { button.textContent = button.dataset.originalLabel || "Copy link"; }, 2400); }
  function decisionPayload(query, team, budget, entries, created) { return { v: 1, q: query, t: team, b: budget, ids: entries.map(function (x) { return x.tool.id; }), at: created || (state.data && state.data.updated_at) || new Date().toISOString().slice(0, 10) }; }
  function decisionUrl(payload) { var url = new URL(location.origin + "/ask-elephant.html"); url.searchParams.set("decision", encode(payload)); return url.toString(); }

  function resultCard(entry, placement, index) {
    var t = entry.tool, affiliate = t.monetized && /^https:\/\//i.test(t.affiliate) ? '<a class="btn btn-small" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="' + h(t.offer_id) + '" data-placement="' + h(placement) + '" href="' + h(t.affiliate) + '">Check current offer →</a>' : '';
    return '<article class="tool-card elephant-result"><div class="card-top"><span class="winner-badge">' + (index === 0 ? "Best recorded fit" : "Alternative " + (index + 1)) + '</span><span class="fit-score"><span class="fit-number">' + Math.min(98, Math.max(58, 58 + entry.score)) + '%</span><small>signal fit</small></span></div><p class="category">' + h(t.category) + '</p><h3>' + h(t.name) + '</h3><p class="summary">' + h(t.summary) + '</p><p class="reason"><strong>Why:</strong> ' + h(rationale(entry)) + '</p><p class="limitation"><strong>Know first:</strong> ' + h(t.price) + '</p><div class="meta-row"><span class="tag">' + h(t.status) + '</span>' + (t.free ? '<span class="tag verified">Free-plan signal</span>' : '') + '</div><div class="card-actions"><a class="link-subtle" href="' + safeUrl(t.profile, "ai-tool-database.html") + '">Review record</a><button class="link-subtle outcome-choice" type="button" data-chosen-tool="' + h(t.id) + '">I chose this</button>' + affiliate + '</div></article>';
  }
  function workflowMarkup(entries) {
    var names = entries.map(function (entry) { return entry.tool.name; });
    var steps = [
      ["Day 1", "Define one measurable result for “" + state.question + "” and record today’s baseline."],
      ["Day 2", "Trial " + (names[0] || "the leading option") + " on one real task; do not migrate the whole workflow."],
      ["Days 3–4", "Test the handoff between " + (names.slice(0,2).join(" and ") || "the shortlisted tools") + "; note duplicate work and missing integrations."],
      ["Days 5–6", "Run the same task with the strongest alternative and compare time, output quality and actual cost."],
      ["Day 7", "Keep the smallest setup that improved the chosen result; cancel trials that did not earn a role."]
    ];
    return steps.map(function (step) { return '<li><span>' + h(step[0]) + '</span><p>' + h(step[1]) + '</p></li>'; }).join("");
  }
  function outcomeSummary(toolIds, target) {
    if (!target || !toolIds.length) return;
    fetch("/api/outcome-signals?tool_ids=" + encodeURIComponent(toolIds.join(",")), { credentials: "same-origin" }).then(function (r) { if (!r.ok) throw new Error(); return r.json(); }).then(function (body) {
      var visible = (body.signals || []).filter(function (item) { return item.responses >= 3; });
      target.innerHTML = visible.length ? '<p class="signal-note">Community signal: ' + visible.map(function (item) { var tool = toolById(item.tool_id); return h(tool ? tool.name : item.tool_id) + " · " + item.chosen + " chose it · " + item.worked + " reported a successful outcome"; }).join("<br>") + '</p>' : '<p class="signal-note">Outcome totals will appear after at least three anonymous responses.</p>';
    }).catch(function () { target.innerHTML = '<p class="signal-note">Outcome totals are temporarily unavailable.</p>'; });
  }
  function postOutcome(signal, toolId, button) {
    if (!state.decisionId || !toolId) return;
    fetch("/api/outcome-signals", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ signal: signal, tool_id: toolId, decision_id: state.decisionId, anonymous_id: anonymousId() }) }).then(function (r) { if (!r.ok) throw new Error(); button.textContent = "Recorded ✓"; button.disabled = true; track(signal.indexOf("helpful") === 0 ? "outcome_helpful" : signal === "chosen" ? "outcome_chosen" : "outcome_result", {offer_id:toolId, placement:"elephant-outcome"}); }).catch(function () { button.textContent = "Try again"; });
  }

  function initAsk() {
    var form = document.querySelector("[data-elephant-form]"); if (!form) return;
    var answer = document.querySelector("[data-elephant-answer]"), results = document.querySelector("[data-elephant-results]"), summary = document.querySelector("[data-elephant-summary]"), currentPayload = null;
    function run(query, team, budget, fixedIds, created) {
      state.question = query;
      state.shortlist = fixedIds && fixedIds.length ? entriesFromIds(fixedIds, query, {team:team,budget:budget}) : rank(query, {team:team,budget:budget}, 3);
      currentPayload = decisionPayload(query, team, budget, state.shortlist, created);
      state.decisionId = hash(JSON.stringify(currentPayload));
      results.innerHTML = state.shortlist.map(function (entry, i) { return resultCard(entry, "ask-elephant", i); }).join("");
      summary.textContent = "Three recorded fits for “" + query + "”";
      document.querySelector("[data-decision-stamp]").textContent = "Saved decision · " + currentPayload.at + " · reference " + state.decisionId.slice(0,8).toUpperCase();
      document.querySelector("[data-elephant-workflow]").innerHTML = workflowMarkup(state.shortlist);
      document.querySelector("[data-open-comparison]").href = "comparison-lab.html?tools=" + encodeURIComponent(currentPayload.ids.join(","));
      answer.hidden = false;
      history.replaceState(null, "", decisionUrl(currentPayload));
      Array.prototype.forEach.call(results.querySelectorAll("[data-chosen-tool]"), function (button) { button.addEventListener("click", function () { postOutcome("chosen", button.dataset.chosenTool, button); }); });
      Array.prototype.forEach.call(document.querySelectorAll("[data-outcome]"), function (button) { button.onclick = function () { postOutcome(button.dataset.outcome, state.shortlist[0].tool.id, button); }; });
      outcomeSummary(currentPayload.ids, document.querySelector("[data-outcome-signals]"));
      track("matcher_complete", {placement:"ask-elephant", result_ids:currentPayload.ids.join(",")});
    }
    form.addEventListener("submit", function (event) { event.preventDefault(); run(document.getElementById("elephant-question").value.trim(), form.querySelector("[data-elephant-team]").value, form.querySelector("[data-elephant-budget]").value); answer.scrollIntoView({behavior:"smooth", block:"start"}); });
    var params = new URLSearchParams(location.search), shared = decode(params.get("decision"));
    if (shared && shared.v === 1 && shared.q && Array.isArray(shared.ids)) { document.getElementById("elephant-question").value = shared.q; form.querySelector("[data-elephant-team]").value = shared.t || "solo"; form.querySelector("[data-elephant-budget]").value = shared.b || "flexible"; run(shared.q, shared.t || "solo", shared.b || "flexible", shared.ids.slice(0,3), shared.at); }
    else if (params.get("task")) { document.getElementById("elephant-question").value = params.get("task"); run(params.get("task"), params.get("team") || "solo", params.get("budget") || "flexible"); }
    var share = document.querySelector("[data-share-elephant]"); share.dataset.originalLabel = share.textContent; share.addEventListener("click", function () { if (currentPayload) { copy(share, decisionUrl(currentPayload), "Permanent link copied ✓"); track("stack_share", {placement:"ask-elephant-link"}); } });
    document.querySelector("[data-download-elephant]").addEventListener("click", function () { if (state.shortlist.length) window.ElephantShare.download("The Elephant's shortlist", state.shortlist.map(function (x) { return x.tool.name; }), "ASK THE ELEPHANT"); });
  }

  function initStudio() {
    var form = document.querySelector("[data-studio-form]"); if (!form) return;
    var workspace = document.querySelector("[data-studio-workspace]"), target = document.querySelector("[data-studio-items]");
    function ids() { return state.studio.map(function (x) { return x.tool.id; }); }
    function money(value) { return new Intl.NumberFormat("en-US", {style:"currency",currency:"USD",maximumFractionDigits:0}).format(value); }
    function plan() { return {v:1,q:state.question,ids:ids(),costs:state.studioCosts}; }
    function planUrl() { var url = new URL(location.origin + "/ai-stack-studio.html"); url.searchParams.set("plan", encode(plan())); return url.toString(); }
    function updateTotals() {
      var total = 0, cats = {}, overlaps = 0;
      Array.prototype.forEach.call(target.querySelectorAll("[data-studio-id]"), function (card) { var value = Math.max(0, Number(card.querySelector("[data-studio-cost]").value) || 0); state.studioCosts[card.dataset.studioId] = value; total += value; var entry = state.studio.find(function (x) { return x.tool.id === card.dataset.studioId; }); if (entry) cats[entry.tool.category] = (cats[entry.tool.category] || 0) + 1; });
      Object.keys(cats).forEach(function (cat) { if (cats[cat] > 1) overlaps += cats[cat] - 1; });
      document.querySelector("[data-studio-total]").textContent = money(total); document.querySelector("[data-studio-annual]").textContent = money(total * 12); document.querySelector("[data-studio-overlaps]").textContent = String(overlaps);
      document.querySelector("[data-studio-notes]").innerHTML = overlaps ? '<h3>Overlap worth testing</h3><p>' + overlaps + ' stack role' + (overlaps === 1 ? '' : 's') + ' share a category. Remove one if the real workflow does not justify both.</p>' : '<h3>Lean three-tool setup</h3><p>No category overlap detected. Enter the current prices you see so the monthly and annual totals travel with the shared link.</p>';
    }
    function render() {
      target.innerHTML = state.studio.map(function (entry, index) { var t = entry.tool, cost = Number(state.studioCosts[t.id] || 0); return '<article class="studio-item" data-studio-id="' + h(t.id) + '"><span class="studio-index">' + (index + 1) + '</span><p class="category">' + h(t.category) + '</p><h3>' + h(t.name) + '</h3><p>' + h(t.summary) + '</p><p class="reason">' + h(rationale(entry)) + '</p><label>Current monthly price you found<input type="number" min="0" max="100000" step="0.01" value="' + h(cost) + '" data-studio-cost></label><small class="price-source">Recorded note: ' + h(t.price) + '</small><div class="button-row"><a class="link-subtle" href="' + safeUrl(t.profile, "ai-tool-database.html") + '">Review record</a></div></article>'; }).join("");
      workspace.hidden = false; updateTotals();
      try { localStorage.setItem("ai1_studio_stack", JSON.stringify(plan())); } catch (_) {}
      Array.prototype.forEach.call(target.querySelectorAll("[data-studio-cost]"), function (input) { input.addEventListener("input", updateTotals); });
    }
    function compose(query) { state.question = query; state.studioCosts = {}; state.studio = rankDiverse(query, {team:"small",budget:"value"}, 3); render(); history.replaceState(null, "", planUrl()); workspace.scrollIntoView({behavior:"smooth",block:"start"}); track("stack_save", {placement:"stack-studio",offer_id:ids().join(",")}); }
    form.addEventListener("submit", function (event) { event.preventDefault(); compose(form.querySelector("[data-studio-query]").value.trim()); });
    var share = document.querySelector("[data-studio-share]"); share.dataset.originalLabel = share.textContent; share.addEventListener("click", function () { copy(share, planUrl(), "Permanent stack link copied ✓"); track("stack_share", {placement:"stack-studio-link"}); });
    document.querySelector("[data-studio-card]").addEventListener("click", function () { window.ElephantShare.download("My costed AI stack", state.studio.map(function (x) { return x.tool.name + " · " + money(state.studioCosts[x.tool.id] || 0) + "/mo"; }), "AI STACK STUDIO"); });
    document.querySelector("[data-studio-export]").addEventListener("click", function () { var blob = new Blob([JSON.stringify(plan(), null, 2)], {type:"application/json"}), link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "artificial-one-ai-stack.json"; link.click(); URL.revokeObjectURL(link.href); });
    var watch = document.querySelector("[data-stack-watch-form]"), watchStatus = document.querySelector("[data-stack-watch-status]");
    watch.addEventListener("submit", function (event) { event.preventDefault(); watchStatus.textContent = "Sending confirmation…"; fetch("/api/watchlist-subscribe", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:watch.email.value,tool_ids:ids(),consent:watch.consent.checked,website:watch.website.value})}).then(function (r) { return r.json().then(function (body) { if (!r.ok) throw new Error(body.error || "Subscription unavailable"); return body; }); }).then(function () { watchStatus.textContent = "Check your inbox to confirm this stack watchlist."; watch.reset(); ids().forEach(function (id) { track("watchlist_add", {offer_id:id,placement:"stack-studio"}); }); }).catch(function (error) { watchStatus.textContent = error.message; }); });
    var params = new URLSearchParams(location.search), saved = decode(params.get("plan"));
    if (saved && saved.v === 1 && Array.isArray(saved.ids)) { state.question = String(saved.q || "Shared AI stack"); form.querySelector("[data-studio-query]").value = state.question; state.studioCosts = saved.costs || {}; state.studio = entriesFromIds(saved.ids.slice(0,3), state.question, {team:"small",budget:"value"}); if (state.studio.length) render(); }
  }

  function initComparison() {
    var form = document.querySelector("[data-comparison-form]"); if (!form) return;
    var selects = Array.prototype.slice.call(form.querySelectorAll("[data-comparison-select]")), workspace = document.querySelector("[data-comparison-workspace]"), target = document.querySelector("[data-comparison-results]"), current = [];
    var ordered = state.data.tools.slice().sort(function (a,b) { return a.name.localeCompare(b.name); });
    selects.forEach(function (select, index) { select.innerHTML = (index === 2 ? '<option value="">No third tool</option>' : '<option value="">Choose a tool</option>') + ordered.map(function (tool) { return '<option value="' + h(tool.id) + '">' + h(tool.name) + '</option>'; }).join(""); });
    function labCard(tool) { var affiliate = tool.monetized && /^https:\/\//i.test(tool.affiliate) ? '<a class="btn btn-small" href="' + h(tool.affiliate) + '" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="' + h(tool.offer_id) + '" data-placement="comparison-lab">Check current offer →</a>' : ''; return '<article class="lab-card"><p class="category">' + h(tool.category) + '</p><h3>' + h(tool.name) + '</h3><dl><dt>Best for</dt><dd>' + h(tool.best_for || "Confirm against your workflow") + '</dd><dt>Recorded pricing signal</dt><dd>' + h(tool.price) + '</dd><dt>Evidence status</dt><dd>' + h(tool.status) + (tool.checked ? " · checked " + h(tool.checked) : "") + '</dd><dt>Capabilities recorded</dt><dd>' + h((tool.features || []).slice(0,4).join(" · ") || tool.summary) + '</dd></dl><div data-lab-signal="' + h(tool.id) + '"></div><div class="button-row"><a class="link-subtle" href="' + safeUrl(tool.profile, "ai-tool-database.html") + '">Open full record</a><button class="link-subtle outcome-choice" type="button" data-lab-chosen="' + h(tool.id) + '">I chose this</button>' + affiliate + '</div></article>'; }
    function render(ids) { current = Array.from(new Set(ids)).map(toolById).filter(Boolean).slice(0,3); if (current.length < 2) return; target.innerHTML = current.map(labCard).join(""); document.querySelector("[data-comparison-title]").textContent = current.map(function (t) { return t.name; }).join(" vs "); workspace.hidden = false; var decision = hash(current.map(function (t) { return t.id; }).join("|")); Array.prototype.forEach.call(target.querySelectorAll("[data-lab-chosen]"), function (button) { button.addEventListener("click", function () { state.decisionId = decision; postOutcome("chosen", button.dataset.labChosen, button); }); }); current.forEach(function (tool) { outcomeSummary([tool.id], target.querySelector('[data-lab-signal="' + tool.id + '"]')); }); var url = new URL(location.href); url.searchParams.set("tools", current.map(function (t) { return t.id; }).join(",")); history.replaceState(null,"",url); track("compare_open", {offer_ids:current.map(function (t) { return t.id; }).join(","),placement:"comparison-lab"}); }
    form.addEventListener("submit", function (event) { event.preventDefault(); var ids = selects.map(function (select) { return select.value; }).filter(Boolean); if (ids.length >= 2) render(ids); });
    var share = document.querySelector("[data-comparison-share]"); share.dataset.originalLabel = share.textContent; share.addEventListener("click", function () { copy(share, location.href, "Comparison link copied ✓"); track("compare_share", {offer_ids:current.map(function (t) { return t.id; }).join(","),placement:"comparison-lab"}); });
    var ids = String(new URLSearchParams(location.search).get("tools") || "").split(",").filter(Boolean).slice(0,3); if (ids.length >= 2) { ids.forEach(function (id,index) { selects[index].value = id; }); render(ids); }
  }

  function initRecipes() { var input = document.querySelector("[data-recipe-search-input]"); if (input) input.addEventListener("input", function () { var query = input.value.trim().toLowerCase(), shown = 0; Array.prototype.forEach.call(document.querySelectorAll("[data-recipe-search]"), function (card) { card.hidden = query && card.dataset.recipeSearch.indexOf(query) < 0; if (!card.hidden) shown += 1; }); document.querySelector("[data-recipe-empty]").hidden = shown !== 0; }); var card = document.querySelector("[data-recipe-card]"); if (card) card.addEventListener("click", function () { window.ElephantShare.download(card.dataset.shareTitle, ["Practical steps", "Fit-based tools", "Buying checks"], "AI WORKFLOW RECIPE"); }); }
  function readWatch() { try { return JSON.parse(localStorage.getItem("ai1_observatory_watch") || "[]"); } catch (_) { return []; } }
  function writeWatch(ids) { try { localStorage.setItem("ai1_observatory_watch", JSON.stringify(ids)); } catch (_) {} }
  function initObservatory() {
    var filter = document.querySelector("[data-change-filter]"); if (!filter) return;
    filter.addEventListener("change", function () { Array.prototype.forEach.call(document.querySelectorAll("[data-change-kind]"), function (card) { card.hidden = filter.value !== "all" && card.dataset.changeKind !== filter.value; }); });
    var watch = readWatch(), target = document.querySelector("[data-observatory-watchlist]");
    function renderWatch() { target.innerHTML = watch.length ? watch.map(function (item) { return '<span class="watch-pill">' + h(item.name) + '<button type="button" data-watch-remove="' + h(item.id) + '" aria-label="Remove ' + h(item.name) + '">×</button></span>'; }).join("") : '<p class="empty compact">No watched tools yet.</p>'; Array.prototype.forEach.call(target.querySelectorAll("[data-watch-remove]"), function (button) { button.addEventListener("click", function () { watch = watch.filter(function (x) { return x.id !== button.dataset.watchRemove; }); writeWatch(watch); renderWatch(); }); }); }
    Array.prototype.forEach.call(document.querySelectorAll("[data-observatory-watch]"), function (button) { button.addEventListener("click", function () { if (!watch.some(function (x) { return x.id === button.dataset.observatoryWatch; })) watch.push({id:button.dataset.observatoryWatch,name:button.dataset.toolName}); writeWatch(watch); renderWatch(); button.textContent = "Watching ✓"; track("watchlist_add", {offer_id:button.dataset.observatoryWatch,placement:"observatory"}); }); }); renderWatch();
    var form = document.querySelector("[data-watch-email-form]"), status = document.querySelector("[data-watch-status]"); form.addEventListener("submit", function (event) { event.preventDefault(); if (!watch.length) { status.textContent = "Watch at least one tool first."; return; } status.textContent = "Sending confirmation…"; fetch("/api/watchlist-subscribe", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:form.email.value,tool_ids:watch.map(function (x) { return x.id; }),consent:form.consent.checked,website:form.website.value})}).then(function (r) { return r.json().then(function (body) { if (!r.ok) throw new Error(body.error || "Subscription unavailable"); return body; }); }).then(function () { status.textContent = "Check your inbox to confirm the watchlist."; form.reset(); track("email_opt_in", {placement:"observatory"}); }).catch(function (error) { status.textContent = error.message; }); });
  }
  function boot() { load().then(function () { initAsk(); initStudio(); initComparison(); initRecipes(); initObservatory(); }).catch(function () { initRecipes(); var status = document.querySelector("[data-watch-status]"); if (status) status.textContent = "The live catalogue is temporarily unavailable."; }); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
}());
