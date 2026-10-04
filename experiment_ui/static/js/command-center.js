/* Command Center, productions list and shell health (UI Patch 1, D-115).
   Reads only the /api/status payload that app.js already polls; app.js calls
   window.CommandCenter.render(data) on every refresh. */
(function () {
  "use strict";

  const STATUS_TONE = {
    HUMAN_REVIEW: "human",
    BLOCKED: "blocked",
    READY: "ready",
    COMPLETE: "complete",
    RUNNING: "running"
  };
  const PRODUCTION_FILTERS = [
    ["active", "Active"],
    ["review", "Review Queue"],
    ["completed", "Completed"]
  ];
  const PRODUCTION_EMPTY = {
    active: "No active productions. Accept a concept at the Concept Gate and it appears here.",
    review: "Nothing waiting on you: no production or opportunity needs a decision.",
    completed: "No production has a current final render yet."
  };
  // The scheduled task wakes every 2 hours by default; three missed wakes
  // means it is probably not installed or not running.
  const SCHEDULER_STALE_HOURS = 6;
  const MAX_VIRAL_CARDS = 3;

  let productionFilter = "active";
  let latest = null;

  function $(id) { return document.getElementById(id); }

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function plural(count, word) {
    return count + " " + word + (count === 1 ? "" : "s");
  }

  function hoursSince(iso, now) {
    const time = Date.parse(iso || "");
    if (!Number.isFinite(time)) return null;
    return (now - time) / 3600000;
  }

  function relativeTime(iso, now) {
    const time = Date.parse(iso || "");
    if (!Number.isFinite(time)) return "unknown";
    const minutes = Math.round((time - now) / 60000);
    const format = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
    if (Math.abs(minutes) < 60) return format.format(minutes, "minute");
    const hours = Math.round(minutes / 60);
    if (Math.abs(hours) < 48) return format.format(hours, "hour");
    return format.format(Math.round(hours / 24), "day");
  }

  function badge(status, label) {
    const tone = STATUS_TONE[status] || "ready";
    return '<span class="status-badge status-' + tone + '">' + esc(label) + "</span>";
  }

  function stageTrack(production) {
    const stages = production.stages || [];
    const index = stages.findIndex(function (stage) { return stage.state === "current"; });
    const label = production.stage === "DONE"
      ? "All stages done"
      : "Stage " + (index + 1) + " of " + stages.length + ": " + production.stage_label;
    return '<ol class="stage-track" role="img" aria-label="' + esc(label) + '">' +
      stages.map(function (stage) {
        return '<li class="stage-step ' + esc(stage.state) + '" title="' +
          esc(stage.label) + '"></li>';
      }).join("") + "</ol>";
  }

  function jobRunning(data) {
    const job = (data || {}).automation_job;
    return Boolean(job && (job.status === "RUNNING" || job.status === "STOPPING"));
  }

  // One Continue per production (D-163): the row says what stopped the last
  // run at its stage and starts the automatic runner from the row itself.
  function continueButton(production, running) {
    if (!production.can_continue) return "";
    return '<button type="button" class="primary-cta compact production-continue" data-continue="' +
      esc(production.concept_id) + '"' + (running ? ' disabled aria-disabled="true"' : "") +
      ' aria-label="Continue ' + esc(production.title) + '">' +
      (running ? "Running…" : "Continue →") + "</button>";
  }

  function productionRow(production) {
    const running = jobRunning(latest);
    return '<article class="production-row">' +
      '<div class="production-main">' +
        '<h3 class="production-title">' + esc(production.title) + "</h3>" +
        '<p class="production-detail">' + esc(production.detail) +
          (production.updated_at ? ' <span class="production-updated">· updated ' + esc(relativeTime(production.updated_at, Date.now())) + "</span>" : "") +
        "</p>" +
        (production.blocker ? '<p class="production-blocker">' + esc(production.blocker) + "</p>" : "") +
      "</div>" +
      '<div class="production-stage">' +
        '<span class="production-stage-label">' + esc(production.stage_label) + "</span>" +
        stageTrack(production) +
      "</div>" +
      '<div class="production-status">' + badge(production.status, production.status_label) + "</div>" +
      '<div class="production-actions">' + continueButton(production, running) +
      '<a href="/production#' +
        esc(encodeURIComponent(production.concept_id)) + '" class="button-link ghost compact" data-route="/production" data-subroute="' +
        esc(encodeURIComponent(production.concept_id)) + '" aria-label="Open ' +
        esc(production.title) + '">Open →</a></div>' +
    "</article>";
  }

  function inboxItems(data) {
    const inbox = data.opportunity_inbox || {};
    return (inbox.items || []).filter(function (item) {
      return item && item.status === "NEEDS_REVIEW";
    });
  }

  function viralDetail(item) {
    const viral = item.viral || {};
    const parts = [];
    if (viral.breadth) parts.push(String(viral.breadth).toLowerCase().replaceAll("_", " "));
    const ratio = Number(viral.lifetime_ratio);
    if (Number.isFinite(ratio) && ratio > 0) {
      parts.push(ratio.toFixed(1) + "× channel normal");
    }
    if (viral.strength) parts.push(String(viral.strength).toLowerCase().replaceAll("_", " "));
    return parts.join(" · ") || "New breakout from the radar";
  }

  // Gates that come before a production exists (D-118). Research claims are
  // already counted per production, so only Analysis and Concept are listed.
  function gateWaiting(data) {
    const pending = function (rows) {
      return (rows || []).filter(function (row) { return row && String(row.decision || "PENDING").toUpperCase() === "PENDING"; }).length;
    };
    const gates = [
      {
        id: "analysis",
        label: "Analysis",
        noun: "finding",
        count: pending((data.human_analysis_review || {}).items),
        detail: "Accept or reject what Experiment 02 found in the study videos."
      },
      {
        id: "concept",
        label: "Concept",
        noun: "concept",
        count: (data.concept_gate || {}).complete ? 0 : pending((data.concept_gate || {}).concepts),
        detail: "Accepted concepts become productions."
      }
    ];
    // The free narration preview is decided per format but is not part of the
    // production status (D-115), so it is listed here once it can be heard.
    gates.push({
      id: "preview",
      label: "Narration Preview",
      noun: "preview",
      count: ((data.narration_preview_gate || {}).items || []).filter(function (row) {
        return row && row.audio_ready && String(row.decision || "PENDING").toUpperCase() === "PENDING";
      }).length,
      detail: "Listen to the free prototype before any paid narration."
    });
    // Production gates (D-122) live on the Produce page; count them together.
    if (window.Produce) {
      const produceTabs = ["budget", "rights", "export", "publish", "plan", "audio", "visuals", "roughcut", "edit"];
      const counts = produceTabs.map(function (tab) { return window.Produce.pending(tab); });
      const first = counts.findIndex(function (count) { return count > 0; });
      gates.push({
        id: first === -1 ? "budget" : produceTabs[first],
        route: "/produce",
        label: "Production",
        noun: "production decision",
        count: counts.reduce(function (sum, count) { return sum + count; }, 0),
        detail: "Budget, footage rights, final export or publish, plus anything the gate policy held for you."
      });
    }
    return gates.filter(function (gate) { return gate.count > 0; });
  }

  function attentionItems(data) {
    const productions = ((data.productions || {}).productions || []);
    const cards = [];
    productions.forEach(function (production) {
      if (production.status === "HUMAN_REVIEW") {
        cards.push({
          tone: "human",
          kicker: "Human review · " + production.stage_label,
          title: production.title,
          detail: production.detail,
          action: "Continue review",
          route: "/production",
          subroute: encodeURIComponent(production.concept_id)
        });
      } else if (production.status === "BLOCKED") {
        cards.push({
          tone: "blocked",
          kicker: "Blocked · " + production.stage_label,
          title: production.title,
          detail: production.detail,
          action: "Open production",
          route: "/production",
          subroute: encodeURIComponent(production.concept_id)
        });
      }
    });

    gateWaiting(data).forEach(function (gate) {
      cards.push({
        tone: "human",
        kicker: gate.label + " Gate",
        title: plural(gate.count, gate.noun) + " to review",
        detail: gate.detail,
        action: "Review " + gate.noun + "s",
        route: gate.route || "/review",
        subroute: gate.id
      });
    });

    const waiting = inboxItems(data);
    const viral = waiting.filter(function (item) { return item.source_type === "VIRAL_RADAR"; });
    viral.slice(0, MAX_VIRAL_CARDS).forEach(function (item) {
      cards.push({
        tone: "running",
        kicker: "Viral breakout",
        title: item.title || "Untitled breakout",
        detail: viralDetail(item),
        action: "Review opportunity",
        route: "/opportunity/review",
        subroute: encodeURIComponent(item.opportunity_id || "")
      });
    });
    const otherCount = waiting.length - Math.min(viral.length, MAX_VIRAL_CARDS);
    if (otherCount > 0) {
      cards.push({
        tone: "human",
        kicker: "Opportunities",
        title: plural(otherCount, "idea") + " to review",
        detail: viral.length > MAX_VIRAL_CARDS
          ? "Includes " + plural(viral.length - MAX_VIRAL_CARDS, "more breakout") + "."
          : "Approve, watch, save or reject each one in the inbox.",
        action: "Review ideas",
        route: "/opportunity/review"
      });
    }

    const job = data.job || {};
    if (job.status === "FAILED") {
      cards.push({
        tone: "blocked",
        kicker: "Last job failed",
        title: job.label || job.action_id || "Job",
        detail: "Exit code " + (job.return_code == null ? "unknown" : job.return_code) +
          ". Open the log to see why.",
        action: "Open log",
        drawer: true
      });
    }
    const productionCount = productions.filter(function (production) {
      return production.status === "HUMAN_REVIEW" || production.status === "BLOCKED";
    }).length;
    const gateCount = gateWaiting(data).reduce(function (sum, gate) { return sum + gate.count; }, 0);
    const total = productionCount + gateCount + waiting.length + (job.status === "FAILED" ? 1 : 0);
    return { cards: cards, total: total };
  }

  function attentionCard(card) {
    const button = card.drawer
      ? '<button type="button" class="ghost compact" data-job-drawer>' + esc(card.action) + "</button>"
      : '<a class="button-link ghost compact" href="' + esc(card.route + (card.subroute ? "#" + card.subroute : "")) +
        '" data-route="' + esc(card.route) + '"' +
        (card.subroute ? ' data-subroute="' + esc(card.subroute) + '"' : "") + ">" +
        esc(card.action) + " →</a>";
    return '<article class="attention-card tone-' + esc(card.tone) + '">' +
      '<p class="attention-kicker">' + esc(card.kicker) + "</p>" +
      '<h3 class="attention-title">' + esc(card.title) + "</h3>" +
      '<p class="attention-detail">' + esc(card.detail) + "</p>" +
      button +
    "</article>";
  }

  function schedulerState(data, now) {
    const schedule = (data.viral_radar || {}).schedule;
    if (!schedule || !schedule.checked_at) {
      return {
        tone: "ready",
        short: "Scheduler: not run yet",
        text: "The radar scheduler has not run yet. Install automation from Tools to run it every 2 hours.",
        problem: null
      };
    }
    const age = hoursSince(schedule.checked_at, now);
    const result = schedule.result || {};
    if (age !== null && age > SCHEDULER_STALE_HOURS) {
      return {
        tone: "blocked",
        short: "Scheduler: stale",
        text: "Last scheduler tick " + relativeTime(schedule.checked_at, now) +
          ". The scheduled task may have stopped.",
        problem: "Radar scheduler has not run for " + Math.round(age) + " hours"
      };
    }
    if (result.status && result.status !== "COMPLETE" && result.status !== "PARTIAL") {
      return {
        tone: "blocked",
        short: "Scheduler: last run failed",
        text: "Last radar run " + relativeTime(schedule.checked_at, now) + " ended " +
          String(result.status).toLowerCase() + ".",
        problem: "Last radar run ended " + String(result.status).toLowerCase()
      };
    }
    return {
      tone: "complete",
      short: "Scheduler OK",
      text: "Last tick " + relativeTime(schedule.checked_at, now) + " (" +
        String(schedule.action || "").toLowerCase().replaceAll("_", " ") + ").",
      problem: null
    };
  }

  function runningItems(data, scheduler, now) {
    const items = [];
    const job = data.job || {};
    if (job.status === "RUNNING" || job.status === "STOPPING") {
      items.push({
        tone: "running",
        title: "Running now: " + (job.label || job.action_id),
        detail: "Started " + relativeTime(job.started_at, now) + ".",
        drawer: true
      });
    }
    items.push({ tone: scheduler.tone, title: "Viral radar scheduler", detail: scheduler.text });
    const schedule = (data.viral_radar || {}).schedule || {};
    const radar = data.viral_radar || {};
    if (schedule.next_snapshot_due || schedule.next_discovery_due) {
      const parts = [];
      if (schedule.next_snapshot_due) parts.push("snapshots " + relativeTime(schedule.next_snapshot_due, now));
      if (schedule.next_discovery_due) parts.push("discovery " + relativeTime(schedule.next_discovery_due, now));
      items.push({
        tone: "ready",
        title: "Next radar work",
        detail: parts.join(", ") + "; " + plural(Number(radar.tracked_count || 0), "video") + " tracked."
      });
    }
    const workflow = data.workflow || {};
    if (workflow.next_title) {
      items.push({
        tone: workflow.state === "RUNNING_AUTOMATIC" ? "running" : "ready",
        title: "Next pipeline step",
        detail: workflow.next_title +
          (workflow.next_due_at ? " (due " + relativeTime(workflow.next_due_at, now) + ")" : "")
      });
    }
    return items;
  }

  // Status polls arrive every few seconds; only touch the DOM when the markup
  // changed, so keyboard focus and hover survive a poll (UI-19).
  const lastHtml = new WeakMap();
  function paint(element, html) {
    if (lastHtml.get(element) === html) return;
    lastHtml.set(element, html);
    element.innerHTML = html;
  }

  function renderRunning(items) {
    const list = $("runningAutomatically");
    if (!list) return;
    paint(list, items.map(function (item) {
      return '<li class="running-item">' +
        '<span class="status-dot tone-' + esc(item.tone) + '" aria-hidden="true"></span>' +
        "<div><strong>" + esc(item.title) + "</strong>" +
        '<p class="muted">' + esc(item.detail) + "</p></div>" +
        (item.drawer ? '<button type="button" class="ghost compact" data-job-drawer>Log</button>' : "") +
      "</li>";
    }).join(""));
  }

  function setCount(id, count) {
    const node = $(id);
    if (!node) return;
    node.hidden = !count;
    node.textContent = count ? String(count) : "";
  }

  function renderHealth(data, scheduler) {
    const problems = [];
    const job = data.job || {};
    if (job.status === "FAILED") problems.push("Last job failed: " + (job.label || job.action_id));
    if (scheduler.problem) problems.push(scheduler.problem);
    const pill = $("healthPill");
    const dot = $("healthDot");
    const label = $("healthLabel");
    if (!pill || !dot || !label) return;
    const running = job.status === "RUNNING" || job.status === "STOPPING";
    const tone = problems.length ? "blocked" : running ? "running" : "complete";
    pill.className = "health-pill tone-" + tone;
    dot.className = "status-dot tone-" + tone;
    // The pill never claims more than the scheduler state supports: a
    // scheduler that has not run yet is not "on time".
    const schedulerOk = scheduler.tone === "complete";
    label.textContent = problems.length
      ? plural(problems.length, "issue") + " need attention"
      : running ? "Working" : schedulerOk ? "System healthy" : "Healthy · " + scheduler.short.replace(/^Scheduler: /, "scheduler ");
    pill.title = problems.length ? problems.join("\n") : "No failed jobs. " + scheduler.text;

    const schedulerDot = $("schedulerStatusDot");
    const schedulerText = $("schedulerStatus");
    if (schedulerDot) schedulerDot.className = "status-dot tone-" + scheduler.tone;
    if (schedulerText) {
      schedulerText.textContent = scheduler.short;
      schedulerText.title = scheduler.text;
    }
  }

  function filterProductions(productions, filter) {
    return productions.filter(function (production) {
      if (filter === "review") {
        return production.status === "HUMAN_REVIEW" || production.status === "BLOCKED";
      }
      if (filter === "completed") return production.status === "COMPLETE";
      return production.status !== "COMPLETE";
    });
  }

  // Section 14 of the redesign: every decision waiting, in one list.
  function reviewQueue(data) {
    const queue = [];
    ((data.productions || {}).productions || []).forEach(function (production) {
      if (production.status !== "HUMAN_REVIEW" && production.status !== "BLOCKED") return;
      queue.push({
        title: production.title,
        kind: production.stage_label + (production.status === "BLOCKED" ? " · blocked" : ""),
        detail: production.detail,
        tone: STATUS_TONE[production.status],
        route: "/production",
        subroute: encodeURIComponent(production.concept_id)
      });
    });
    gateWaiting(data).forEach(function (gate) {
      queue.push({
        title: plural(gate.count, gate.noun) + " waiting",
        kind: gate.label + " Gate",
        detail: gate.detail,
        tone: "human",
        route: gate.route || "/review",
        subroute: gate.id,
        count: gate.count
      });
    });
    inboxItems(data).forEach(function (item) {
      queue.push({
        title: item.title || item.opportunity_id,
        kind: "Opportunity · " + (item.source_label || "idea").toLowerCase(),
        detail: item.viral ? viralDetail(item) : (item.summary || ""),
        tone: "running",
        route: "/opportunity/review",
        subroute: encodeURIComponent(item.opportunity_id)
      });
    });
    return queue;
  }

  function reviewQueueHtml(queue) {
    if (!queue.length) return '<p class="empty-state">' + esc(PRODUCTION_EMPTY.review) + "</p>";
    const total = queue.reduce(function (sum, entry) { return sum + (entry.count || 1); }, 0);
    return '<div class="queue-head"><p><strong>' + plural(total, "decision") + "</strong> waiting</p>" +
      '<a href="' + esc(queue[0].route) + '#' +
        esc(queue[0].subroute) + '" class="button-link primary-cta" data-route="' + esc(queue[0].route) + '" data-subroute="' +
        esc(queue[0].subroute) + '">Start review queue →</a></div>' +
      '<ol class="review-queue">' + queue.map(function (entry) {
        return '<li class="queue-row tone-' + esc(entry.tone) + '">' +
          '<div class="queue-main"><strong>' + esc(entry.title) + "</strong>" +
            '<span class="muted">' + esc(entry.detail) + "</span></div>" +
          '<span class="queue-kind">' + esc(entry.kind) + "</span>" +
          '<a href="' + esc(entry.route) + '#' +
            esc(entry.subroute) + '" class="button-link ghost compact" data-route="' + esc(entry.route) + '" data-subroute="' +
            esc(entry.subroute) + '">Review →</a>' +
        "</li>";
      }).join("") + "</ol>";
  }

  function renderProductionsView() {
    const tabs = $("productionTabs");
    const list = $("productionsList");
    if (!tabs || !list || !latest) return;
    const productions = ((latest.productions || {}).productions || []);
    const queue = reviewQueue(latest);
    paint(tabs, PRODUCTION_FILTERS.map(function (tab) {
      const count = tab[0] === "review"
        ? queue.reduce(function (sum, entry) { return sum + (entry.count || 1); }, 0)
        : filterProductions(productions, tab[0]).length;
      const active = tab[0] === productionFilter;
      return '<button type="button" role="tab" class="inbox-tab' + (active ? " active" : "") +
        '" aria-selected="' + active + '" data-production-filter="' + tab[0] + '">' +
        esc(tab[1]) + ' <span class="tab-count">' + count + "</span></button>";
    }).join(""));
    if (productionFilter === "review") {
      paint(list, reviewQueueHtml(queue));
      return;
    }
    const shown = filterProductions(productions, productionFilter);
    paint(list, shown.length
      ? shown.map(productionRow).join("")
      : '<p class="empty-state">' + esc(PRODUCTION_EMPTY[productionFilter]) + "</p>");
  }

  function render(data) {
    latest = data;
    const now = Date.now();
    const attention = attentionItems(data);
    const queue = $("attentionQueue");
    if (queue) {
      paint(queue, attention.cards.length
        ? attention.cards.map(attentionCard).join("")
        : '<p class="empty-state">Nothing is waiting on you. New breakouts and review steps will appear here.</p>');
    }
    const count = $("attentionCount");
    if (count) count.textContent = attention.total ? "· " + attention.total + " remaining" : "· all clear";

    const productions = data.productions || {};
    const active = $("activeProductions");
    if (active) {
      const rows = filterProductions(productions.productions || [], "active");
      paint(active, rows.length
        ? rows.map(productionRow).join("")
        : '<p class="empty-state">' + esc(PRODUCTION_EMPTY.active) + "</p>");
    }

    const scheduler = schedulerState(data, now);
    renderRunning(runningItems(data, scheduler, now));
    renderHealth(data, scheduler);
    setCount("navAttentionCount", attention.total);
    setCount("navOpportunityCount", inboxItems(data).length);
    setCount("navProductionCount", Number(productions.active_count || 0));
    renderProductionsView();
  }

  function setProductionFilter(filter) {
    productionFilter = PRODUCTION_FILTERS.some(function (tab) { return tab[0] === filter; })
      ? filter
      : "active";
    renderProductionsView();
  }

  document.addEventListener("click", function (event) {
    const go = event.target.closest("[data-continue]");
    if (go) {
      if (go.disabled || typeof window.runAction !== "function") return;
      go.disabled = true;
      go.textContent = "Starting…";
      window.runAction("auto_continue");
      return;
    }
    const tab = event.target.closest("[data-production-filter]");
    if (!tab) return;
    setProductionFilter(tab.dataset.productionFilter);
    history.replaceState({}, "", "/productions#" + productionFilter);
    document.querySelectorAll(".nav-subitem").forEach(function (item) {
      const on = item.dataset.route === "/productions" && item.dataset.subroute === productionFilter;
      item.classList.toggle("active", on);
    });
  });

  if (window.location.pathname === "/productions") {
    setProductionFilter(window.location.hash.replace(/^#/, ""));
  }

  window.CommandCenter = {
    render: render,
    setProductionFilter: setProductionFilter,
    _test: { attentionItems: attentionItems, schedulerState: schedulerState, filterProductions: filterProductions, productionRow: productionRow }
  };
})();
