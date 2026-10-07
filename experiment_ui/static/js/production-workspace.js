/* Production Workspace (UI-08, D-117).
   One accepted concept at /production#<concept_id>, with eight real
   sections (Evidence … Produce) read from GET /api/production. Review
   decisions still happen in the existing panels (Workspace, /analysis)
   until each gate moves onto the shared review workspace (UI-09 onward). */
(function () {
  "use strict";

  const REFRESH_MS = 10000;
  const STATE_ICON = { done: "✓", current: "●", todo: "○" };
  const STATE_TEXT = { done: "done", current: "current stage", todo: "not started" };

  let conceptId = "";
  let payload = null;
  let error = "";
  let loading = false;
  let fetchedAt = 0;
  let statusMarker = "";
  let selected = Object.create(null);
  let painted = "";

  function $(id) { return document.getElementById(id); }
  function yp() { return window.YP; }
  function esc(value) { return yp().escapeHtml(value); }

  function ago(iso) {
    const time = Date.parse(iso || "");
    if (!Number.isFinite(time)) return "";
    const minutes = Math.round((Date.now() - time) / 60000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return minutes + " min ago";
    const hours = Math.round(minutes / 60);
    if (hours < 48) return hours + "h ago";
    return Math.round(hours / 24) + "d ago";
  }

  function tone(status) {
    return { HUMAN_REVIEW: "human", BLOCKED: "blocked", READY: "ready", COMPLETE: "complete" }[status] || "ready";
  }

  function currentSectionId(sections) {
    const current = sections.find(function (s) { return s.state === "current"; });
    return current ? current.id : sections[sections.length - 1].id;
  }

  function currentStep(production) {
    const status = production.status;
    let action = "";
    if (status === "HUMAN_REVIEW" && production.stage === "RESEARCH") {
      // Research claims have moved to the shared review workspace (D-118).
      const claims = (((yp().status() || {}).research_gate || {}).claims || []).filter(function (claim) {
        return claim.concept_id === production.concept_id && String(claim.decision || "PENDING").toUpperCase() === "PENDING";
      });
      const target = "research" + (claims.length ? "/" + encodeURIComponent(claims[0].concept_id + "::" + claims[0].claim_id) : "");
      action = '<a href="/review#' + esc(target) + '" class="button-link primary-cta" data-route="/review" data-subroute="' + esc(target) + '">Continue review →</a>';
    } else if (status === "HUMAN_REVIEW" && production.stage === "PACKAGE") {
      action = '<a href="/packaging#titles" class="button-link primary-cta" data-route="/packaging" data-subroute="titles">Continue review →</a>';
    } else if (status === "HUMAN_REVIEW" && (production.stage === "FORMAT" || production.stage === "PRODUCE")) {
      // Format plans and voice performances are on the shared review workspace (D-121).
      const gate = production.stage === "FORMAT" ? "format" : "voice";
      action = '<a class="button-link primary-cta" href="/review#' + gate + '" data-route="/review" data-subroute="' +
        gate + '">Continue review →</a>';
    } else if (status === "HUMAN_REVIEW" && production.stage === "SCRIPT") {
      // The Script Gate is on the shared review workspace too (D-119).
      action = '<a href="/review#script" class="button-link primary-cta" data-route="/review" data-subroute="script">Continue review →</a>';
    } else if (status === "HUMAN_REVIEW" || status === "BLOCKED") {
      action = '<a href="/analysis" class="button-link primary-cta" data-route="/analysis">' +
        (status === "BLOCKED" ? "Open in workspace →" : "Continue review →") + "</a>";
    } else if (status === "READY") {
      // This production's own Continue (D-163): the automatic runner moves
      // it on and stops at the next gate; the blocker line says what stopped
      // the last run here.
      const job = (yp().status() || {}).automation_job;
      const running = Boolean(job && (job.status === "RUNNING" || job.status === "STOPPING"));
      action = '<button type="button" class="primary-cta production-continue" data-continue="' +
        esc(production.concept_id) + '"' + (running ? ' disabled aria-disabled="true"' : "") + ">" +
        (running ? "Running…" : "Continue →") + "</button>" +
        '<p class="muted">Runs every ready step for this stage and stops at the next decision.</p>';
    }
    return '<section class="pw-current tone-' + tone(status) + '" aria-label="Current step">' +
      '<p class="section-kicker">CURRENT STEP</p>' +
      "<h3>" + esc(production.stage_label) + " · " + esc(production.status_label) + "</h3>" +
      '<p class="pw-current-detail">' + esc(production.detail) + "</p>" +
      (production.blocker ? '<p class="production-blocker">' + esc(production.blocker) + "</p>" : "") +
      action +
    "</section>";
  }

  function sectionBody(section, production) {
    const isCurrent = section.state === "current" ||
      (production.stage === "DONE" && section.id === "PRODUCE");
    const progress = (section.progress || []).length
      ? '<ul class="pw-checklist">' + section.progress.map(function (step) {
        return '<li class="' + (step.status === "done" ? "done" : "") + '"><span aria-hidden="true">' +
          (step.status === "done" ? "✓" : "○") + "</span>" + esc(step.label) +
          '<span class="visually-hidden"> — ' + esc(step.status) + "</span></li>";
      }).join("") + "</ul>"
      : "";
    const facts = (section.facts || []).length
      ? '<dl class="pw-facts">' + section.facts.map(function (fact) {
        return "<div><dt>" + esc(fact.label) + "</dt><dd>" + esc(fact.value) + "</dd></div>";
      }).join("") + "</dl>"
      : "";
    const rows = (section.rows || []).length
      ? '<table class="pw-rows"><thead><tr><th scope="col">Item</th><th scope="col">Status</th><th scope="col">Detail</th></tr></thead><tbody>' +
        section.rows.map(function (row) {
          return "<tr><th scope=\"row\">" + esc(row.label) + '</th><td><span class="status-badge status-' + esc(row.tone) + '">' +
            esc(row.status) + "</span></td><td>" + esc(row.detail) + "</td></tr>";
        }).join("") + "</tbody></table>"
      : "";
    const empty = !progress && !facts && !rows && section.empty
      ? '<p class="empty-state">' + esc(section.empty) + "</p>"
      : "";
    return (isCurrent ? currentStep(production) : "") +
      '<p class="pw-summary">' + esc(section.summary || "") + "</p>" +
      progress + facts + rows + empty;
  }

  function render() {
    const root = $("productionWorkspace");
    if (!root || !yp()) return;
    let html;
    if (!conceptId) {
      html = '<div class="rw-empty"><h2>No production selected</h2><p class="muted">Open one from the Productions list.</p>' +
        '<div class="rw-empty-actions"><a href="/productions" class="button-link ghost compact" data-route="/productions">Productions</a></div></div>';
    } else if (!payload) {
      html = error
        ? '<div class="rw-empty"><p>' + esc(error) + '</p><div class="rw-empty-actions">' +
          '<a href="/productions" class="button-link ghost compact" data-route="/productions">Productions</a></div></div>'
        : '<p class="empty-state">Loading production…</p>';
    } else {
      const production = payload.production;
      const sections = payload.sections || [];
      const active = selected[conceptId] || currentSectionId(sections);
      const section = sections.find(function (s) { return s.id === active; }) || sections[0];
      html =
        '<a href="/productions" class="button-link ghost compact pw-back" data-route="/productions">← Productions</a>' +
        '<header class="pw-head">' +
          '<div class="pw-head-copy"><h2 class="pw-title">' + esc(production.title) + "</h2>" +
            (production.premise ? '<p class="muted pw-premise">' + esc(production.premise) + "</p>" : "") + "</div>" +
          '<div class="pw-head-status"><span class="status-badge status-' + tone(production.status) + '">' +
            esc(production.stage_label + " · " + production.status_label) + "</span>" +
            (production.updated_at ? '<span class="muted">Updated ' + esc(ago(production.updated_at)) + "</span>" : "") +
          "</div>" +
        "</header>" +
        (error ? '<p class="radar-error">' + esc(error) + "</p>" : "") +
        '<div class="pw-tabs" role="tablist" aria-label="Production sections">' +
          sections.map(function (s) {
            const on = s.id === section.id;
            return '<button type="button" role="tab" id="pw-tab-' + esc(s.id) + '" class="pw-tab state-' + esc(s.state) + (on ? " active" : "") +
              '" aria-selected="' + on + '" aria-controls="pw-panel" tabindex="' + (on ? "0" : "-1") +
              '" data-pw-tab="' + esc(s.id) + '"><span class="pw-tab-state" aria-hidden="true">' + STATE_ICON[s.state] + "</span>" +
              esc(s.label) + '<span class="visually-hidden"> (' + STATE_TEXT[s.state] + ")</span></button>";
          }).join("") +
        "</div>" +
        '<section class="pw-panel" id="pw-panel" role="tabpanel" aria-labelledby="pw-tab-' + esc(section.id) + '">' +
          sectionBody(section, production) +
        "</section>";
    }
    if (html === painted && root.innerHTML) return;
    painted = html;
    const focusedTab = document.activeElement && document.activeElement.dataset
      ? document.activeElement.dataset.pwTab : null;
    root.innerHTML = html;
    const activeTab = root.querySelector(".pw-tab.active");
    if (activeTab && activeTab.parentElement) {
      // Keep the selected tab visible in the scrolling strip on narrow screens.
      const strip = activeTab.parentElement;
      const left = activeTab.offsetLeft; // the strip is the offset parent (position: relative)
      if (left < strip.scrollLeft || left + activeTab.offsetWidth > strip.scrollLeft + strip.clientWidth) {
        strip.scrollLeft = Math.max(0, left - 16);
      }
    }
    if (focusedTab) {
      const tab = root.querySelector('[data-pw-tab="' + focusedTab + '"]');
      if (tab) tab.focus();
    }
  }

  async function load() {
    if (loading || !conceptId || !yp()) return;
    loading = true;
    const requested = conceptId;
    try {
      const data = await yp().api("/api/production?concept_id=" + encodeURIComponent(requested));
      if (requested === conceptId) {
        payload = data;
        error = "";
      }
    } catch (err) {
      if (requested === conceptId) {
        error = /unknown production/i.test(err.message)
          ? "This production no longer exists: the concept is not accepted at the Concept Gate any more."
          : "The production could not be loaded: " + err.message;
        if (/unknown production/i.test(err.message)) payload = null;
      }
    } finally {
      loading = false;
      fetchedAt = Date.now();
      render();
    }
  }

  function open(id) {
    const next = String(id || "");
    if (next !== conceptId) {
      conceptId = next;
      payload = null;
      error = "";
    }
    render();
    load();
  }

  function selectTab(id, focus) {
    selected[conceptId] = id;
    render();
    if (focus) {
      const tab = document.querySelector('[data-pw-tab="' + id + '"]');
      if (tab) tab.focus();
    }
  }

  document.addEventListener("click", function (event) {
    const tab = event.target.closest("[data-pw-tab]");
    if (tab) selectTab(tab.dataset.pwTab, false);
  });

  // WAI-ARIA tabs: arrows move, Home/End jump, focus follows selection.
  document.addEventListener("keydown", function (event) {
    const tab = event.target.closest && event.target.closest("[data-pw-tab]");
    if (!tab) return;
    const tabs = Array.from(document.querySelectorAll("[data-pw-tab]"));
    const index = tabs.indexOf(tab);
    let next = -1;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next === -1) return;
    event.preventDefault();
    selectTab(tabs[next].dataset.pwTab, true);
  });

  window.ProductionWorkspace = {
    open: open,
    show: function () {
      if (window.location.pathname === "/production") open(window.YPUtil.decode(window.location.hash.slice(1)));
    },
    // Called on every status poll; refetch when the pipeline moved or data is old.
    refresh: function (data) {
      if (window.location.pathname !== "/production" || !conceptId) return;
      const marker = JSON.stringify(((data.productions || {}).productions || []).find(function (p) {
        return p.concept_id === conceptId;
      }) || null);
      if (marker !== statusMarker || Date.now() - fetchedAt > REFRESH_MS) {
        statusMarker = marker;
        load();
      }
    }
  };
})();
