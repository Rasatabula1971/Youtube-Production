/* Analysis, Concept and Research gates on the shared review workspace
   (UI-09/UI-10, D-118). Same endpoints and payloads as the classic panels
   in Workspace (/analysis); only the review experience changes.
   Route: /review#<gate> or /review#<gate>/<item key>. */
(function () {
  "use strict";

  const GATES = ["analysis", "concept", "research"];
  let activeGate = "analysis";
  let showDecided = false;
  const workspaces = {};
  const pendingFocus = {};

  function yp() { return window.YP; }
  function esc(value) { return yp().escapeHtml(value); }
  function status() { return (yp() && yp().status()) || {}; }

  function words(value) { return String(value || "").replace(/_/g, " ").toLowerCase(); }

  function text(value) {
    if (value == null) return "";
    if (Array.isArray(value)) return value.map(text).filter(Boolean).join("; ");
    if (typeof value === "object") {
      return Object.keys(value)
        .filter(function (key) { return value[key] !== null && value[key] !== "" && typeof value[key] !== "object"; })
        .map(function (key) { return words(key) + ": " + value[key]; })
        .join(" · ");
    }
    return String(value);
  }

  function section(title, body) {
    return body ? '<h3 class="rw-section">' + esc(title) + "</h3>" + body : "";
  }

  function facts(pairs) {
    const rows = pairs.filter(function (pair) { return text(pair[1]); });
    if (!rows.length) return "";
    return '<dl class="pw-facts rw-facts">' + rows.map(function (pair) {
      return "<div><dt>" + esc(pair[0]) + "</dt><dd>" + esc(text(pair[1])) + "</dd></div>";
    }).join("") + "</dl>";
  }

  function list(items) {
    const kept = (items || []).map(text).filter(Boolean);
    return kept.length ? '<ul class="rw-list">' + kept.map(function (item) { return "<li>" + esc(item) + "</li>"; }).join("") + "</ul>" : "";
  }

  function decidedBadge(decision) {
    const value = String(decision || "PENDING").toUpperCase();
    if (value === "PENDING") return "";
    const tone = value === "ACCEPT" ? "complete" : value === "REWORK" || value === "REJECT" ? "blocked" : "human";
    return '<span class="status-badge status-' + tone + '">Decided: ' + esc(words(value)) + "</span>";
  }

  function safeLink(url, label) {
    try {
      const parsed = new URL(String(url || ""));
      if (parsed.protocol === "https:" || parsed.protocol === "http:") {
        return '<a href="' + esc(parsed.href) + '" target="_blank" rel="noopener noreferrer">' + esc(label || parsed.hostname) + "</a>";
      }
    } catch (_) {}
    return esc(label || "");
  }

  async function post(url, body, okMessage) {
    try {
      await yp().api(url, { method: "POST", body: JSON.stringify(body) });
      yp().showToast(okMessage, false);
      await yp().refresh();
    } catch (error) {
      yp().showToast(error.message, true);
    }
  }

  // ---------------------------------------------------------------- Analysis
  const analysis = {
    label: "Analysis",
    kicker: "ANALYSIS REVIEW",
    snapshot: function () { return status().human_analysis_review || {}; },
    all: function () { return this.snapshot().items || []; },
    key: function (item) { return item.video_id + "::" + item.item_id; },
    title: function (item) { return item.statement || item.item_id; },
    meta: function (item) {
      const packet = (this.snapshot().packets || []).find(function (p) { return p.video_id === item.video_id; }) || {};
      const source = packet.source || {};
      return '<span class="source-chip">' + esc(words(item.kind)) + "</span>" +
        '<span class="rw-meta-text">' + esc(words(item.dimension)) + " · " + esc(source.title || item.video_id) + "</span>" +
        decidedBadge(item.decision);
    },
    evidence: function (item) {
      const evidence = (item.supporting_evidence || []).map(function (e) {
        return "<li><strong>" + esc(words(e.type)) + "</strong>" + (e.locator ? ' <span class="muted">· ' + esc(text(e.locator)) + "</span>" : "") +
          "<br>" + esc(e.observation) + "</li>";
      }).join("");
      return facts([
        ["Dimension", words(item.dimension)],
        ["Confidence", item.confidence],
        ["Mechanisms", item.mechanism_ids]
      ]) +
        section("Supporting evidence", evidence ? '<ul class="rw-list rw-evidence-list">' + evidence + "</ul>" : '<p class="muted">No evidence references on this finding.</p>');
    },
    decisions: function () {
      return [
        { value: "ACCEPT", label: "Accept", hint: "This finding is supported by the evidence and goes into the reviewed profile.", tone: "complete" },
        { value: "REJECT", label: "Reject", hint: "Not supported, or not useful for this channel.", tone: "blocked" }
      ];
    },
    decide: function (item, decision, note) {
      return post("/api/human-analysis-review", {
        video_id: item.video_id,
        item_id: item.item_id,
        decision: decision,
        note: note
      }, decision === "ACCEPT" ? "Analysis finding accepted." : "Analysis finding rejected.");
    }
  };

  // ----------------------------------------------------------------- Concept
  const concept = {
    label: "Concept",
    kicker: "CONCEPT REVIEW",
    snapshot: function () { return status().concept_gate || {}; },
    all: function () { return this.snapshot().concepts || []; },
    key: function (item) { return item.concept_id; },
    title: function (item) { return item.working_title || item.concept_id; },
    meta: function (item) {
      return '<span class="source-chip">' + esc(item.mechanism_label || "concept") + "</span>" +
        (item.triage_default ? "" : '<span class="rw-meta-text">brought in by you (not shortlisted)</span>') +
        decidedBadge(item.decision);
    },
    evidence: function (item) {
      const need = item.viewer_need_evidence || {};
      const criteria = this.snapshot().criteria || {};
      const confirms = (item.required_accept_criteria || []).map(function (key) { return criteria[key] || words(key); });
      return facts([
        ["Premise", item.premise],
        ["Audience promise", item.audience_promise],
        ["Viewer problem", item.viewer_problem],
        ["Viewer moment", item.viewer_moment],
        ["Desired outcome", item.desired_outcome],
        ["Format intent", item.format_intent]
      ]) +
        section("Why viewers would watch", facts([
          ["Viewer need", (need.status ? need.status + " — " : "") + (need.rationale || "")],
          ["Basis", need.evidence_basis],
          ["Content gap", item.content_gap],
          ["Channel fit", item.channel_fit]
        ])) +
        section("Mechanism", facts([
          ["Mechanism", item.mechanism_label],
          ["How it is applied", item.mechanism_application],
          ["Transformation", item.transformation_method]
        ])) +
        section("Research questions", list(item.research_questions)) +
        section("Checks", facts([
          ["Title clarity test", item.title_clarity_test],
          ["Source dependency", item.source_dependency_test],
          ["Source overlap", item.source_overlap],
          ["Triage", item.llm_triage]
        ])) +
        section("Accepting confirms", list(confirms));
    },
    decisions: function () {
      return [
        { value: "ACCEPT", label: "Accept", hint: "Becomes a production; research starts automatically.", tone: "complete" },
        { value: "REWORK", label: "Rework", hint: "Regenerate it with your direction.", tone: "running", needsNote: true, notePlaceholder: "say what must change" },
        { value: "SAVE_IDEA", label: "Save idea", hint: "Park it in the saved ideas bank.", tone: "human" },
        { value: "REJECT", label: "Reject", hint: "Not for this channel.", tone: "blocked" }
      ];
    },
    decide: function (item, decision, note) {
      const messages = { ACCEPT: "Concept accepted.", REWORK: "Concept marked for rework.", SAVE_IDEA: "Concept saved for later.", REJECT: "Concept rejected." };
      return post("/api/concept-gate", {
        concept_id: item.concept_id,
        decision: decision,
        criteria: {},
        note: note
      }, messages[decision] || "Saved.");
    }
  };

  // ---------------------------------------------------------------- Research
  const research = {
    label: "Research",
    kicker: "RESEARCH REVIEW",
    snapshot: function () { return status().research_gate || {}; },
    all: function () { return this.snapshot().claims || []; },
    key: function (item) { return item.concept_id + "::" + item.claim_id; },
    // Waivers and other claims' decisions change this claim's question panel.
    extraSignature: function (item) {
      const row = (this.snapshot().question_coverage || []).find(function (r) { return r.concept_id === item.concept_id; });
      return JSON.stringify(row ? row.questions : []);
    },
    title: function (item) { return item.statement || item.claim_id; },
    meta: function (item) {
      const conflicted = ((item.coverage || {}).state || "") === "CONFLICTED";
      return '<span class="source-chip">' + esc(item.claim_id) + "</span>" +
        '<span class="rw-meta-text">' + esc((item.concept || {}).working_title || item.concept_id) +
        (item.role ? " · " + esc(words(item.role)) : "") + "</span>" +
        (conflicted ? '<span class="status-badge status-blocked">Conflicting sources</span>' : "") +
        decidedBadge(item.decision);
    },
    evidence: function (item) {
      const sources = (item.evidence || []).map(function (link) {
        const source = link.source || {};
        return "<li>" +
          '<span class="status-badge status-' + (link.stance === "SUPPORTS" ? "complete" : link.stance === "CONTRADICTS" ? "blocked" : "ready") + '">' +
            esc(words(link.stance || "cites")) + "</span> " +
          "<strong>" + safeLink(source.url, source.title || link.source_id) + "</strong>" +
          (source.publisher ? ' <span class="muted">· ' + esc(source.publisher) + "</span>" : "") +
          (link.locator ? ' <span class="muted">· ' + esc(text(link.locator)) + "</span>" : "") +
          (link.evidence_quote ? '<blockquote class="rw-quote">' + esc(link.evidence_quote) + "</blockquote>" : "") +
          (link.evidence_note ? '<p class="muted">' + esc(link.evidence_note) + "</p>" : "") +
        "</li>";
      }).join("");
      const coverage = (this.snapshot().question_coverage || []).find(function (row) { return row.concept_id === item.concept_id; }) || { questions: [] };
      const mine = new Set(item.question_ids || []);
      const questions = (coverage.questions || []).map(function (q) {
        const tone = q.status === "ANSWERED" ? "complete" : q.status === "WAIVED" ? "ready" : "human";
        const waivable = q.status !== "ANSWERED";
        return '<li class="rw-question' + (mine.has(q.question_id) ? " mine" : "") + '">' +
          '<span class="status-badge status-' + tone + '">' + esc(words(q.status)) + "</span> " + esc(q.question) +
          (mine.has(q.question_id) ? ' <span class="muted">(this claim answers it)</span>' : "") +
          (q.waiver && q.waiver.note ? '<p class="muted">Waived: ' + esc(q.waiver.note) + "</p>" : "") +
          (waivable
            ? ' <button type="button" class="ghost compact" data-waive="' + esc(q.status === "WAIVED" ? "UNWAIVE_QUESTION" : "WAIVE_QUESTION") +
              '" data-concept="' + esc(item.concept_id) + '" data-question="' + esc(q.question_id) + '">' +
              (q.status === "WAIVED" ? "Remove waiver" : "Waive…") + "</button>"
            : "") +
        "</li>";
      }).join("");
      return facts([
        ["Coverage", item.coverage],
        ["Carried from earlier review", item.carried_from_review]
      ]) +
        section("Sources", sources ? '<ul class="rw-list rw-evidence-list">' + sources + "</ul>" : '<p class="muted">No evidence links on this claim.</p>') +
        section("Research questions for this concept", questions ? '<ul class="rw-list rw-questions">' + questions + "</ul>" : "") +
        section("Accepting confirms", list(Object.values(item.criteria_descriptions || {})));
    },
    decisions: function (item) {
      const conflicted = ((item.coverage || {}).state || "") === "CONFLICTED";
      return [
        conflicted
          ? { value: "ACCEPT", label: "Accept", hint: "The sources conflict: say how you resolved it.", tone: "complete", needsNote: true, notePlaceholder: "say how the conflict is resolved" }
          : { value: "ACCEPT", label: "Accept", hint: "Safe to use in the script as worded.", tone: "complete" },
        { value: "REWORK", label: "Rework", hint: "Re-research it with your direction.", tone: "running", needsNote: true, notePlaceholder: "say what must change" },
        { value: "REJECT", label: "Reject", hint: "Not supported; keep it out of the script.", tone: "blocked" }
      ];
    },
    decide: function (item, decision, note) {
      const messages = { ACCEPT: "Research claim accepted.", REWORK: "Research claim sent for rework.", REJECT: "Research claim rejected." };
      return post("/api/research-gate", {
        concept_id: item.concept_id,
        claim_id: item.claim_id,
        decision: decision,
        criteria: {},
        note: note
      }, messages[decision] || "Saved.");
    }
  };

  const CONFIGS = { analysis: analysis, concept: concept, research: research };

  function items(gate) {
    const config = CONFIGS[gate];
    const all = config.all().filter(Boolean);
    return showDecided ? all : all.filter(function (item) { return String(item.decision || "PENDING").toUpperCase() === "PENDING"; });
  }

  function pendingCount(gate) {
    return CONFIGS[gate].all().filter(function (item) { return String((item || {}).decision || "PENDING").toUpperCase() === "PENDING"; }).length;
  }

  function emptyHtml(gate) {
    const config = CONFIGS[gate];
    const snap = config.snapshot();
    const total = config.all().length;
    const state = snap.status ? words(snap.status) : "not started";
    if (total && !showDecided) {
      return "<h2>Every " + esc(config.label.toLowerCase()) + " item is decided</h2>" +
        '<p class="muted">Gate status: ' + esc(state) + '. Switch to "All items" to revisit a decision.</p>';
    }
    return "<h2>Nothing to review at the " + esc(config.label) + " Gate</h2>" +
      '<p class="muted">Gate status: ' + esc(state) + ". Items appear here when the pipeline reaches this gate.</p>" +
      '<div class="rw-empty-actions"><button type="button" class="ghost compact" data-route="/">Command Center</button></div>';
  }

  function ensure(gate) {
    if (workspaces[gate]) return workspaces[gate];
    const root = document.getElementById("gateReview-" + gate);
    if (!root || !window.ReviewWorkspace || !yp()) return null;
    const config = CONFIGS[gate];
    workspaces[gate] = window.ReviewWorkspace.create({
      root: root,
      kicker: config.kicker,
      items: function () { return items(gate); },
      key: function (item) { return config.key(item); },
      signature: function (item) {
        return config.key(item) + ":" + (item.decision || "") + ":" + (item.note || "") +
          (config.extraSignature ? ":" + config.extraSignature(item) : "");
      },
      title: function (item) { return config.title(item); },
      meta: function (item) { return config.meta(item); },
      renderEvidence: function (item) { return config.evidence(item); },
      decisions: function (item) { return config.decisions(item); },
      initialValue: function (item) {
        const decision = String(item.decision || "PENDING").toUpperCase();
        return decision === "PENDING" ? "" : decision;
      },
      initialNote: function (item) { return item.note || ""; },
      decide: function (item, decision, note) { return config.decide(item, decision, note); },
      onNavigate: function (key) {
        if (window.location.pathname === "/review") {
          history.replaceState({}, "", "/review#" + gate + "/" + encodeURIComponent(key));
        }
      },
      emptyHtml: function () { return emptyHtml(gate); }
    });
    return workspaces[gate];
  }

  let switcherHtml = "";

  function renderSwitcher() {
    const bar = document.getElementById("gateReviewSwitcher");
    if (!bar) return;
    const html = '<div class="inbox-tabs" role="tablist" aria-label="Gate">' + GATES.map(function (gate) {
      const on = gate === activeGate;
      const count = pendingCount(gate);
      return '<button type="button" role="tab" class="inbox-tab' + (on ? " active" : "") + '" aria-selected="' + on +
        '" data-gate-tab="' + gate + '">' + esc(CONFIGS[gate].label) + ' <span class="tab-count">' + count + "</span></button>";
    }).join("") + "</div>" +
      '<label class="gate-toggle"><input type="checkbox" data-gate-show-decided' + (showDecided ? " checked" : "") +
      "> Include decided items</label>" +
      '<button type="button" class="ghost compact" data-route="/analysis" title="The original panels, with every option">Classic view</button>';
    if (html === switcherHtml && bar.innerHTML) return;
    switcherHtml = html;
    bar.innerHTML = html;
  }

  function render() {
    renderSwitcher();
    GATES.forEach(function (gate) {
      const root = document.getElementById("gateReview-" + gate);
      if (root) root.hidden = gate !== activeGate;
    });
    const workspace = ensure(activeGate);
    if (!workspace) return;
    if (pendingFocus[activeGate]) {
      const key = pendingFocus[activeGate];
      delete pendingFocus[activeGate];
      workspace.focus(key);
    } else {
      workspace.render();
    }
  }

  function open(subroute) {
    const raw = String(subroute || "");
    const slash = raw.indexOf("/");
    const gate = slash === -1 ? raw : raw.slice(0, slash);
    if (CONFIGS[gate]) {
      activeGate = gate;
      if (slash !== -1) pendingFocus[gate] = decodeURIComponent(raw.slice(slash + 1));
    }
    render();
  }

  document.addEventListener("click", function (event) {
    if (!event.target.closest || !event.target.closest("#viewGateReview")) return;
    const tab = event.target.closest("[data-gate-tab]");
    if (tab) {
      activeGate = tab.dataset.gateTab;
      history.replaceState({}, "", "/review#" + activeGate);
      render();
      return;
    }
    const waive = event.target.closest("[data-waive]");
    if (waive) {
      const action = waive.dataset.waive;
      let note = "";
      if (action === "WAIVE_QUESTION") {
        note = window.prompt("Why can this question stay unanswered? (required)") || "";
        if (!note.trim()) return;
      }
      post("/api/research-gate", {
        action: action,
        concept_id: waive.dataset.concept,
        question_id: waive.dataset.question,
        note: note
      }, action === "WAIVE_QUESTION" ? "Question waived." : "Waiver removed.");
    }
  });

  document.addEventListener("change", function (event) {
    if (!event.target.matches || !event.target.matches("[data-gate-show-decided]")) return;
    showDecided = event.target.checked;
    GATES.forEach(function (gate) { if (workspaces[gate]) workspaces[gate].refresh(); });
    render();
  });

  window.GateReviews = {
    open: open,
    show: function () {
      if (window.location.pathname === "/review") open(window.location.hash.slice(1));
    },
    render: function () {
      if (window.location.pathname === "/review") render();
    },
    pending: pendingCount,
    keyFor: function (gate, item) { return CONFIGS[gate] ? CONFIGS[gate].key(item) : ""; }
  };
})();
