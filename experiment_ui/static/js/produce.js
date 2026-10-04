/* Produce workspace (UI-14, D-122).
   /produce#<tab>: the production gates on the shared review
   workspace — Narration spend, Choose visuals, Footage rights, Rough cut,
   Visual spend, Edit preview, Final export. Every decision posts exactly what
   the classic panel posts. Asset registration (final narration audio,
   managed and generated visuals, final sound) and storyboard editing stay in
   the classic view: they are data entry, not decisions. */
(function () {
  "use strict";

  // Grouped by who decides (D-159): the operator's own decisions first, then
  // the gates the gate policy decides when its checks pass (shown only while
  // they hold something), then tools that are not decisions.
  const TABS = [
    ["budget", "Budget", "yours"],
    ["rights", "Footage rights", "yours"],
    ["export", "Final export", "yours"],
    ["publish", "Publish", "yours"],
    ["plan", "Visual plan", "policy"],
    ["audio", "Final audio", "policy"],
    ["visuals", "Choose visuals", "policy"],
    ["roughcut", "Rough cut", "policy"],
    ["edit", "Edit preview", "policy"],
    ["generate", "Generate visuals", "tools"],
    ["tesseract", "Tesseract", "tools"]
  ];
  const GROUP_LABELS = { yours: "Your decisions", policy: "Held by gate policy", tools: "Tools" };
  // Old deep links keep working.
  const TAB_ALIASES = { narration: "budget", spend: "budget" };

  let activeTab = "budget";
  let showDecided = false;
  const workspaces = Object.create(null);
  const pendingFocus = Object.create(null);
  // Per-item inputs that live in the evidence panel (kept across repaints).
  const spendTicks = Object.create(null);      // narration key -> {criterion: bool}
  const visualChoice = Object.create(null);    // shot key -> candidate_id
  const rightsContext = Object.create(null);   // rights key -> context note
  const maxCost = Object.create(null);         // spend key -> number
  const generatedChoice = Object.create(null); // request file -> candidate_id
  const reworkSegments = Object.create(null);  // final audio key -> {segment_id: bool}
  const pubEdits = Object.create(null);        // publish key -> {field: value}
  const exchangeInputs = Object.create(null);  // exchange key -> {video_path, timeline_path}
  let paintedTabs = "";

  function yp() { return window.YP; }
  function esc(value) { return yp().escapeHtml(value); }
  function status() { return (yp() && yp().status()) || {}; }
  function words(value) { return String(value || "").replace(/_/g, " ").toLowerCase(); }
  function money(value, currency) {
    const number = Number(value);
    return (currency || "USD") + " " + (Number.isFinite(number) ? number.toFixed(2) : "—");
  }

  function section(title, body) {
    return body ? '<h3 class="rw-section">' + esc(title) + "</h3>" + body : "";
  }

  function facts(pairs) {
    const rows = pairs.filter(function (pair) { return pair[1] !== null && pair[1] !== undefined && pair[1] !== ""; });
    if (!rows.length) return "";
    return '<dl class="pw-facts rw-facts">' + rows.map(function (pair) {
      return "<div><dt>" + esc(pair[0]) + "</dt><dd>" + esc(String(pair[1])) + "</dd></div>";
    }).join("") + "</dl>";
  }

  function decidedBadge(text, tone) {
    return text ? '<span class="status-badge status-' + (tone || "ready") + '">' + esc(words(text)) + "</span>" : "";
  }

  function safeLink(url, label) {
    try {
      const parsed = new URL(String(url || ""));
      if (parsed.protocol === "https:" || parsed.protocol === "http:") {
        return '<a href="' + esc(parsed.href) + '" target="_blank" rel="noopener noreferrer">' + esc(label) + " ↗</a>";
      }
    } catch (_) {}
    return "";
  }

  // Resolves true on success and false when the server refused, so callers
  // keep the reviewer's choices after a failure (UI-19).
  async function post(url, body, okMessage) {
    try {
      const payload = await yp().api(url, { method: "POST", body: JSON.stringify(body) });
      const routed = payload && payload.rework_routed_to ? " Routed to " + words(payload.rework_routed_to) + "." : "";
      yp().showToast(okMessage + routed, false);
      await yp().refresh();
      return true;
    } catch (error) {
      yp().showToast(error.message, true);
      return false;
    }
  }

  function seconds(value) {
    const number = Number(value);
    return value !== null && value !== undefined && value !== "" && Number.isFinite(number) ? number.toFixed(1) + " s" : "—";
  }

  // Paid provider dispatch (D-139): one explicit click, after spend approval.
  function dispatchBlock(item, segmentIds, label) {
    const provider = status().narration_dispatch || {};
    if (!provider.ready) {
      return '<p class="muted">Provider generation is off: ' + esc((provider.problems || []).join(" ")) +
        " Register the returned audio in the classic view instead.</p>";
    }
    return '<p><button type="button" class="primary compact" data-pd-dispatch="' + esc(item.concept_id) + '" data-format="' + esc(item.format) +
      '" data-segments="' + esc((segmentIds || []).join(",")) + '">' + esc(label) + "</button></p>" +
      '<p class="muted">A paid call to ' + esc(provider.provider || "the provider") + ", within the approved worst case.</p>";
  }

  function noteRework(value, label, hint, placeholder) {
    return { value: value, label: label, hint: hint, tone: "running", needsNote: true, notePlaceholder: placeholder || "say what must change" };
  }

  // ------------------------------------------------------------ Visual plan
  // The complete visual plan, timed from the approved free preview, approved
  // before any paid narration (D-138).
  const plan = {
    kicker: "VISUAL PLAN",
    gate: function () { return status().visual_plan_gate || {}; },
    all: function () { return (this.gate().items || []).filter(Boolean); },
    pending: function (item) { return ["PENDING", "BLOCKED"].indexOf(String(item.decision || "PENDING").toUpperCase()) !== -1; },
    key: function (item) { return item.concept_id + "::" + item.format; },
    title: function (item) { return item.concept_id + " · " + words(item.format); },
    meta: function (item) {
      return '<span class="source-chip">' + esc((item.shots || []).length) + " shots</span>" +
        '<span class="rw-meta-text">' + esc(seconds(item.preview_total_seconds)) + " in the preview</span>" +
        (this.pending(item) ? "" : decidedBadge(item.decision, item.decision === "APPROVE_VISUAL_PLAN" ? "complete" : "blocked"));
    },
    evidence: function (item) {
      if (item.error) return '<p class="radar-error">The plan cannot be built: ' + esc(item.error) + "</p>";
      const budget = item.budget || {};
      const rows = (item.shots || []).map(function (shot) {
        return "<tr><td>" + esc(shot.beat_id) + "</td><td>" +
          (shot.preview_start_seconds === null || shot.preview_start_seconds === undefined
            ? "—" : esc(seconds(shot.preview_start_seconds)) + "–" + esc(seconds(shot.preview_end_seconds))) +
          "</td><td>" + esc(shot.narrative_purpose) + "</td><td>" + esc(shot.visual_treatment) + "</td><td>" +
          esc(words(shot.first_source_tier)) + "</td><td>" + esc((shot.claim_ids || []).join(", ")) + "</td></tr>";
      }).join("");
      return facts([
        ["Planned length", seconds(item.duration_intent_seconds)],
        ["Preview length", seconds(item.preview_total_seconds)],
        ["Shots without preview timing", item.untimed_shots],
        ["Video budget", budget.ceiling_usd !== undefined
          ? "committed " + money(budget.committed_usd) + " of " + money(budget.ceiling_usd) + " (target " + money(budget.target_usd) + ")" : "—"],
        ["Paid visuals", item.cost_policy ? "at most " + Math.round(100 * Number(item.cost_policy.max_paid_generated_share || 0)) + "% of shots generated" : "—"]
      ]) +
        '<p class="muted">Approving this plan comes before any paid narration. Timing is from the free preview; after the paid narration is approved the storyboard is retimed to it.</p>' +
        section("Shots", rows
          ? '<div class="pd-table-wrap"><table class="pd-plan"><thead><tr><th>Beat</th><th>Preview time</th><th>Purpose</th><th>Visual</th><th>First source</th><th>Claims</th></tr></thead><tbody>' + rows + "</tbody></table></div>"
          : '<p class="muted">No shots.</p>');
    },
    decisions: function (item) {
      if (item.error) return [];
      return [
        { value: "APPROVE_VISUAL_PLAN", label: "Approve visual plan", hint: "The narration quote and spend can proceed.", tone: "complete" },
        noteRework("REWORK_VISUAL_PLAN", "Rework plan", "Holds narration spend; rework the format plan.")
      ];
    },
    decide: function (item, decision, note) {
      return post("/api/visual-plan-gate", {
        concept_id: item.concept_id, format: item.format, decision: decision, note: note
      }, decision === "APPROVE_VISUAL_PLAN" ? "Visual plan approved." : "Visual plan sent for rework.");
    }
  };

  // -------------------------------------------------------- Narration spend
  const narration = {
    kicker: "NARRATION SPEND",
    gate: function () { return status().narration_spend_gate || {}; },
    all: function () { return (this.gate().items || []).filter(Boolean); },
    pending: function (item) { return String(item.decision || "PENDING").toUpperCase() === "PENDING"; },
    key: function (item) { return item.concept_id + "::" + item.format; },
    title: function (item) { return item.concept_id + " · " + words(item.format); },
    meta: function (item) {
      return '<span class="source-chip">paid narration</span><span class="rw-meta-text">' + esc(item.provider || "provider") + "</span>" +
        (this.pending(item) ? "" : decidedBadge(item.decision, item.decision === "ACCEPT" ? "complete" : "blocked"));
    },
    ticks: function (item) {
      const key = this.key(item);
      if (!spendTicks[key]) {
        const saved = item.criteria_decisions || {};
        spendTicks[key] = {};
        (item.required_accept_criteria || []).forEach(function (name) { spendTicks[key][name] = saved[name] === true; });
      }
      return spendTicks[key];
    },
    evidence: function (item) {
      const quote = item.provider_quote || {};
      const ticks = this.ticks(item);
      const key = this.key(item);
      const descriptions = item.criteria || {};
      const checks = (item.required_accept_criteria || []).map(function (name) {
        return '<li><label><input type="checkbox" data-pd-tick="' + esc(name) + '" data-key="' + esc(key) + '"' + (ticks[name] ? " checked" : "") + "> " +
          "<strong>" + esc(words(name)) + "</strong>" + (descriptions[name] ? " — " + esc(descriptions[name]) : "") + "</label></li>";
      }).join("");
      return facts([
        ["Initial estimate", money(item.initial_estimate_usd, item.currency)],
        ["Worst-case ceiling", money(item.worst_case_estimate_usd, item.currency)],
        ["Segments", item.segment_count],
        ["Max attempts per segment", item.max_attempts_per_segment],
        ["Quote reference", quote.quote_reference || "—"]
      ]) +
        '<p class="muted">Accepting authorizes up to the worst-case figure for this exact quote. It does not call the provider; a changed quote invalidates it.</p>' +
        (String(item.decision || "").toUpperCase() === "ACCEPT" ? section("Generate the narration", dispatchBlock(item, [], "Generate narration with the provider")) : "") +
        section("Accepting confirms", checks ? '<ul class="pk-criteria">' + checks + "</ul>" : "");
    },
    locked: function (item) {
      return String(item.decision || "").toUpperCase() === "ACCEPT"
        ? "Spend is authorized for this exact quote. The decision is locked, as in the classic panel; a changed quote reopens it."
        : "";
    },
    decisions: function (item) {
      const self = this;
      return [
        {
          value: "ACCEPT", label: "Authorize spend", hint: "Up to " + money(item.worst_case_estimate_usd, item.currency) + ".", tone: "complete",
          validate: function () {
            const ticks = self.ticks(item);
            return (item.required_accept_criteria || []).every(function (n) { return ticks[n]; }) ? "" : "Confirm every spend check first.";
          },
          confirm: function () {
            return "Authorize paid narration up to " + money(item.worst_case_estimate_usd, item.currency) + " for this exact current quote?";
          }
        },
        noteRework("REWORK", "Rework", "Ask for a different quote or setup."),
        { value: "REJECT", label: "Reject", hint: "Do not spend on this narration.", tone: "blocked" }
      ];
    },
    decide: function (item, decision, note) {
      return post("/api/narration-spend-gate", {
        concept_id: item.concept_id, format: item.format, decision: decision,
        criteria: Object.assign({}, this.ticks(item)), note: note
      }, decision === "ACCEPT" ? "Narration spend authorized." : decision === "REWORK" ? "Narration spend sent for rework." : "Narration spend rejected.");
    }
  };

  // ----------------------------------------------------------- Final audio
  // The exact paid narration, after automatic Audio QC, approved by ear
  // before any visual work uses its timing (D-137).

  const finalAudio = {
    kicker: "FINAL AUDIO",
    gate: function () { return status().final_audio_gate || {}; },
    all: function () { return (this.gate().items || []).filter(Boolean); },
    pending: function (item) { return String(item.decision || "PENDING").toUpperCase() === "PENDING"; },
    key: function (item) { return item.concept_id + "::" + item.format; },
    title: function (item) { return item.concept_id + " · " + words(item.format); },
    meta: function (item) {
      return '<span class="source-chip">paid narration</span><span class="rw-meta-text">' + esc((item.segments || []).length) + " segments</span>" +
        (this.pending(item) ? "" : decidedBadge(item.decision, item.decision === "APPROVE_FINAL_AUDIO" ? "complete" : "blocked"));
    },
    evidence: function (item) {
      const key = this.key(item);
      const marked = reworkSegments[key] || {};
      const rows = (item.segments || []).map(function (segment) {
        const url = "/api/final-audio-file?" + new URLSearchParams({ concept_id: item.concept_id, format: item.format, segment_id: segment.segment_id }).toString();
        return '<li class="pd-audio-row"><strong>' + esc(segment.segment_id) + "</strong> " +
          '<span class="muted">' + esc(seconds(segment.actual_duration_seconds)) + " (planned " + esc(seconds(segment.expected_duration_seconds)) +
          ") · starts " + esc(seconds(segment.audio_start_seconds)) + " · take " + esc(segment.attempt) + "</span>" +
          '<audio controls preload="none" src="' + esc(url) + '"></audio>' +
          '<label><input type="checkbox" data-pd-segment="' + esc(segment.segment_id) + '" data-key="' + esc(key) + '"' +
          (marked[segment.segment_id] ? " checked" : "") + "> Re-record this segment</label></li>";
      }).join("");
      return '<p class="muted">Audio QC passed (duration, silence, clipping). Listen to every segment: approving makes this exact audio the narration, and its timing drives the visuals.</p>' +
        section("Segments", rows ? '<ul class="rw-list pd-audio-list">' + rows + "</ul>" : '<p class="muted">No segments.</p>') +
        (item.note ? '<p class="muted">Last note: ' + esc(item.note) + "</p>" : "") +
        (item.decision === "REWORK_SEGMENTS" && (item.rework_segment_ids || []).length
          ? section("Re-record", dispatchBlock(item, item.rework_segment_ids, "Re-record " + item.rework_segment_ids.length + " segment(s) with the provider"))
          : "");
    },
    decisions: function (item) {
      const key = this.key(item);
      return [
        { value: "APPROVE_FINAL_AUDIO", label: "Approve final audio", hint: "This exact audio becomes the narration; visual planning follows.", tone: "complete" },
        Object.assign(noteRework("REWORK_SEGMENTS", "Re-record segments", "Tick the segments to re-record, then say what is wrong."), {
          validate: function () {
            const marked = reworkSegments[key] || {};
            return Object.keys(marked).some(function (id) { return marked[id]; }) ? "" : "Tick at least one segment to re-record.";
          }
        }),
        noteRework("REJECT_AUDIO", "Reject audio", "The whole return is unusable.", "say what is wrong")
      ];
    },
    decide: function (item, decision, note) {
      const key = this.key(item);
      const marked = reworkSegments[key] || {};
      return post("/api/final-audio-gate", {
        concept_id: item.concept_id, format: item.format, decision: decision, note: note,
        segment_ids: Object.keys(marked).filter(function (id) { return marked[id]; })
      }, decision === "APPROVE_FINAL_AUDIO" ? "Final narration approved." : decision === "REWORK_SEGMENTS" ? "Segments sent for re-recording." : "Narration audio rejected.").then(function (ok) {
        if (ok) delete reworkSegments[key];
        return ok;
      });
    }
  };

  // --------------------------------------------------------- Choose visuals
  const visuals = {
    kicker: "CHOOSE VISUAL",
    gate: function () { return status().visual_candidate_gate || {}; },
    all: function () {
      const rows = [];
      (this.gate().packets || []).forEach(function (packet) {
        (packet.shots || []).forEach(function (shot) {
          rows.push({ packet: packet, shot: shot, decision: (packet.decisions || {})[shot.shot_id] || null });
        });
      });
      return rows;
    },
    // A shot whose storyboard changed must be re-searched by the workflow
    // first; it is not waiting on a human decision yet.
    pending: function (item) { return !item.decision && item.shot.storyboard_current !== false; },
    key: function (item) { return (item.packet.result_file || item.packet.concept_id) + "::" + item.shot.shot_id; },
    title: function (item) { return item.shot.shot_id; },
    meta: function (item) {
      const stale = item.shot.storyboard_current === false;
      return '<span class="source-chip">' + esc(words(item.packet.format)) + '</span><span class="rw-meta-text">' + esc(item.packet.concept_id || "") + "</span>" +
        (stale ? decidedBadge("re-search required", "blocked") : item.decision ? decidedBadge(item.decision.status || item.decision.action, "complete") : "");
    },
    evidence: function (item) {
      const key = this.key(item);
      const shot = item.shot;
      if (shot.storyboard_current === false) {
        return '<p class="radar-error">The storyboard for this shot changed, so these candidates are stale. Continue the workflow to re-search it before choosing.</p>';
      }
      const chosen = visualChoice[key] !== undefined ? visualChoice[key] : (item.decision && item.decision.candidate_id) || "";
      const cards = (shot.candidates || []).map(function (c) {
        const state = c.state === "HUMAN_REVIEW_REQUIRED" ? ["rights review next", "human"] : c.state === "ELIGIBLE" ? ["eligible", "complete"] : ["blocked", "blocked"];
        const pickable = c.state !== "BLOCKED";
        return '<article class="pk-package' + (chosen === c.candidate_id ? " chosen" : "") + (pickable ? "" : " unavailable") + '">' +
          (c.thumbnail_url
            ? '<img class="pk-thumb" src="' + esc(c.thumbnail_url) + '" alt="' + esc(c.title || c.candidate_id) + '" loading="lazy">'
            : '<div class="pk-thumb pk-thumb-missing"><small>No preview</small></div>') +
          '<div class="pk-package-body"><h4 class="pk-package-title">' + esc(c.title || c.candidate_id) + "</h4>" +
          '<p class="muted">' + esc((c.creator || "Unknown creator") + " · " + words(c.source_tier)) + "</p>" +
          '<p class="muted">' + esc(c.license || "Licence requires review") + "</p>" +
          '<p><span class="status-badge status-' + state[1] + '">' + esc(state[0]) + "</span> " + safeLink(c.source_url, "Open source") + "</p>" +
          (pickable
            ? '<label class="pk-choose"><input type="radio" name="pd-visual-' + esc(key) + '" data-pd-visual="' + esc(c.candidate_id) + '" data-key="' + esc(key) + '"' +
              (chosen === c.candidate_id ? " checked" : "") + "> Choose this visual</label>"
            : "") +
          "</div></article>";
      }).join("");
      return facts([
        ["Search gap", shot.search_gap ? "yes" : "no"],
        ["Premium generation candidate", shot.premium_generation_candidate ? "yes — only if existing visuals fail" : "no"]
      ]) +
        section("Candidates", cards ? '<div class="pk-packages">' + cards + "</div>" : '<p class="muted">No usable existing visual was found. Keep it as a gap for sourcing or generation.</p>') +
        '<p class="muted">Creator footage still goes through the Footage rights gate. Editing the storyboard shot stays in the classic view.</p>';
    },
    decisions: function (item) {
      if (item.shot.storyboard_current === false) return [];
      const key = this.key(item);
      return [
        {
          value: "SELECT", label: "Use the chosen visual", hint: "Marks it for the rough cut (creator footage goes to rights review first).", tone: "complete",
          validate: function () { return visualChoice[key] || (item.decision && item.decision.candidate_id) ? "" : "Choose one of the candidates first."; }
        },
        { value: "NEEDS_BETTER_VISUAL", label: "Needs a better visual", hint: "Search again or treat as a gap.", tone: "running" },
        { value: "REJECT_ALL", label: "Reject all", hint: "None of these work; keep it as a gap.", tone: "blocked" }
      ];
    },
    decide: function (item, decision, note) {
      const key = this.key(item);
      const candidate = decision === "SELECT" ? (visualChoice[key] || (item.decision && item.decision.candidate_id)) : null;
      return post("/api/visual-candidate-review", {
        result_file: item.packet.result_file, shot_id: item.shot.shot_id, action: decision,
        candidate_id: candidate || null, note: note
      }, decision === "SELECT" ? "Visual chosen." : decision === "REJECT_ALL" ? "Candidates rejected." : "Marked as needing a better visual.")
        .then(function (ok) { if (ok) delete visualChoice[key]; return ok; });
    }
  };

  // --------------------------------------------------------- Footage rights
  const rights = {
    kicker: "FOOTAGE RIGHTS & CONTEXT",
    gate: function () { return status().visual_rights_gate || {}; },
    all: function () {
      const rows = [];
      (this.gate().items || []).forEach(function (packet) {
        (packet.pending || []).forEach(function (entry) { rows.push({ packet: packet, entry: entry, decision: entry.decision || null }); });
      });
      return rows;
    },
    pending: function (item) { return !item.decision; },
    key: function (item) { return (item.packet.candidate_review_file || "") + "::" + item.entry.shot_id; },
    title: function (item) { return ((item.entry.candidate || {}).title) || item.entry.shot_id; },
    meta: function (item) {
      return '<span class="source-chip">' + esc(item.entry.shot_id) + '</span><span class="rw-meta-text">creator / editorial footage</span>' +
        (item.decision ? decidedBadge(item.decision.decision, item.decision.approved_for_rough_cut ? "complete" : "blocked") : "");
    },
    evidence: function (item) {
      const c = item.entry.candidate || {};
      const key = this.key(item);
      const context = rightsContext[key] !== undefined ? rightsContext[key] : (item.decision && item.decision.context_note) || "";
      return facts([
        ["Creator", c.creator || "Unknown"],
        ["Source tier", words(c.source_tier)],
        ["Licence", c.license || "Requires human context review"]
      ]) +
        (safeLink(c.source_url, "Open source") ? "<p>" + safeLink(c.source_url, "Open source") + "</p>" : "") +
        section("Context note (optional)", '<textarea class="pd-textarea" rows="3" maxlength="1000" data-pd-context="' + esc(key) + '" placeholder="Where and how it appears, credit, length used">' + esc(context) + "</textarea>") +
        '<p class="muted">Approval records the intended editorial transformation and context. It is not a legal fair-use determination.</p>';
    },
    decisions: function () {
      return [
        { value: "APPROVE_CONTEXT_USE", label: "Approve for the rough cut", hint: "Document why this use is transformative or editorial.", tone: "complete",
          needsNote: true, noteLabel: "Editorial purpose", notePlaceholder: "the transformative / editorial purpose" },
        { value: "REJECT_USE", label: "Don't use this footage", hint: "The shot goes back to being a gap.", tone: "blocked", noteLabel: "Why (optional)" }
      ];
    },
    decide: function (item, decision, note) {
      const key = this.key(item);
      const context = rightsContext[key] !== undefined ? rightsContext[key] : (item.decision && item.decision.context_note) || "";
      return post("/api/visual-rights-review", {
        candidate_review_file: item.packet.candidate_review_file, shot_id: item.entry.shot_id, decision: decision,
        transformative_purpose: decision === "APPROVE_CONTEXT_USE" ? note : "",
        context_note: decision === "APPROVE_CONTEXT_USE" ? context : (note || context)
      }, decision === "APPROVE_CONTEXT_USE" ? "Footage approved for the rough cut." : "Footage use rejected.")
        .then(function (ok) { if (ok) delete rightsContext[key]; return ok; });
    }
  };

  // -------------------------------------------------------------- Rough cut
  const roughcut = {
    kicker: "ROUGH CUT",
    gate: function () { return status().visual_rough_cut_gate || {}; },
    all: function () { return (this.gate().items || []).filter(Boolean); },
    pending: function (item) { return !item.decision; },
    key: function (item) { return item.rough_cut_file || (item.concept_id + "::" + item.format); },
    title: function (item) { return item.concept_id + " · " + words(item.format); },
    meta: function (item) {
      const summary = item.summary || {};
      return '<span class="source-chip">structural cut</span><span class="rw-meta-text">' + (item.scenes || []).length + " scenes · " +
        Number(summary.placeholders || summary.unresolved_visual_gaps || 0) + " unresolved gaps</span>" +
        (item.decision ? decidedBadge(item.decision.decision, item.decision.approved_for_gap_planning ? "complete" : "running") : "");
    },
    evidence: function (item) {
      const rows = (item.scenes || []).map(function (scene) {
        const a = scene.visual_assignment || {};
        const st = String(a.status || "PLACEHOLDER");
        return "<tr><th scope=\"row\">" + esc(scene.shot_id || scene.scene_id || "") + "</th><td>" + esc(scene.story_purpose || "") + "</td><td>" +
          esc(scene.desired_visual || "") + '</td><td><span class="status-badge status-' + (st === "PLACEHOLDER" ? "human" : "complete") + '">' + esc(words(st)) + "</span>" +
          (a.reason ? '<br><span class="muted">' + esc(words(a.reason)) + "</span>" : "") + "</td></tr>";
      }).join("");
      return '<p class="muted">The structural rough cut: placeholders may remain and paid generation is still locked.</p>' +
        section("Scenes", rows ? '<div class="pk-table-wrap"><table class="pw-rows"><thead><tr><th scope="col">Shot</th><th scope="col">Purpose</th><th scope="col">Visual</th><th scope="col">Assignment</th></tr></thead><tbody>' + rows + "</tbody></table></div>" : "");
    },
    decisions: function (item) {
      const shots = (item.scenes || []).map(function (s) { const id = String(s.shot_id || s.scene_id || ""); return [id, id]; }).filter(function (o) { return o[0]; });
      return [
        { value: "APPROVE_WITH_GAPS", label: "Approve with gaps", hint: "Gap planning starts; remaining placeholders get sourced or generated.", tone: "complete" },
        {
          value: "REWORK_VISUAL", label: "Rework one shot's visual", hint: "Re-search the chosen shot with your instruction.", tone: "running",
          select: { label: "Shot", options: [["", "Choose the shot"]].concat(shots) }, needsNote: true, notePlaceholder: "what the shot should show",
          validate: function (_i, draft) { return draft.select ? "" : "Choose which shot to rework."; }
        },
        noteRework("REWORK_PACING", "Rework pacing", "Sends the format plan back for rework."),
        noteRework("REWORK_AUDIO", "Rework audio / delivery", "Sends the voice performance back for rework.")
      ];
    },
    decide: function (item, decision, note, extras) {
      return post("/api/visual-rough-cut-review", {
        rough_cut_file: item.rough_cut_file, shot_id: decision === "REWORK_VISUAL" ? extras.select : null, decision: decision, note: note
      }, decision === "APPROVE_WITH_GAPS" ? "Rough cut approved with gaps." : "Rough cut rework sent.");
    }
  };

  // ----------------------------------------------------------- Visual spend
  const spend = {
    kicker: "VISUAL SPEND",
    gate: function () { return status().visual_spend_gate || {}; },
    all: function () {
      const rows = [];
      (this.gate().items || []).forEach(function (packet) {
        (packet.hero_candidates || []).forEach(function (gap) { rows.push({ packet: packet, gap: gap, decision: (packet.decisions || {})[gap.shot_id] || null }); });
      });
      return rows;
    },
    pending: function (item) { return !item.decision; },
    key: function (item) { return (item.packet.gap_plan_file || "") + "::" + item.gap.shot_id; },
    title: function (item) { return item.gap.shot_id; },
    meta: function (item) {
      return '<span class="source-chip">premium gap</span><span class="rw-meta-text">' + esc((item.packet.concept_id || "") + " · " + words(item.packet.format)) + "</span>" +
        (item.decision ? decidedBadge(item.decision.decision, item.decision.paid_generation_authorized ? "complete" : "ready") : "");
    },
    cap: function () { return Number(this.gate().per_shot_hard_cap_usd || 0); },
    cost: function (item) {
      const key = this.key(item);
      return maxCost[key] !== undefined ? maxCost[key] : Number((item.decision && item.decision.max_cost_usd) || 0);
    },
    evidence: function (item) {
      const gap = item.gap;
      const score = gap.visual_value_score || {};
      const gate = this.gate();
      return facts([
        ["Desired visual", gap.desired_visual],
        ["Story purpose", gap.story_purpose],
        ["Visual value score", score.total == null ? "—" : score.total],
        ["Resolution class", words(gap.resolution_class)],
        ["Per-shot hard cap", money(gate.per_shot_hard_cap_usd, gate.currency)],
        ["Workflow hard cap", money(gate.workflow_hard_cap_usd, gate.currency)],
        ["Authorized so far", money(gate.authorized_max_total_usd, gate.currency)]
      ]) +
        section("Maximum cost for this shot", '<label class="pd-cost">' + esc(gate.currency || "USD") +
          ' <input type="number" min="0" step="0.01" max="' + esc(String(this.cap())) + '" data-pd-cost="' + esc(this.key(item)) + '" value="' + esc(this.cost(item).toFixed(2)) + '"></label>' +
          '<p class="muted">A ceiling only; nothing is generated or charged here.</p>');
    },
    decisions: function (item) {
      const self = this;
      return [
        {
          value: "AUTHORIZE_GENERATION", label: "Authorize generation", hint: "Last resort: allow paid generation up to the ceiling.", tone: "complete",
          validate: function () {
            const cost = self.cost(item);
            if (!(cost > 0)) return "Set a maximum cost above zero.";
            if (self.cap() && cost > self.cap()) return "The maximum is above the per-shot hard cap.";
            return "";
          },
          confirm: function () { return "Authorize paid generation for " + item.gap.shot_id + " up to " + money(self.cost(item), self.gate().currency) + "?"; }
        },
        { value: "KEEP_PLACEHOLDER", label: "Keep the placeholder", hint: "No spend; the gap stays as is.", tone: "ready" },
        noteRework("RETRY_EXISTING", "Retry existing footage", "Search again with your instruction instead of paying.", "what to search for")
      ];
    },
    decide: function (item, decision, note) {
      const key = this.key(item);
      return post("/api/visual-spend-review", {
        gap_plan_file: item.packet.gap_plan_file, shot_id: item.gap.shot_id, decision: decision,
        max_cost_usd: Number(this.cost(item) || 0), note: note
      }, decision === "AUTHORIZE_GENERATION" ? "Generation authorized." : decision === "KEEP_PLACEHOLDER" ? "Placeholder kept." : "Retry requested.")
        .then(function (ok) { if (ok) delete maxCost[key]; return ok; });
    }
  };


  // ---------------------------------------------------------------- Budget
  // One place for every paid decision (D-159): narration spend and visual
  // spend items, each shown with its video's budget. The underlying
  // decisions, requests and locks are unchanged.
  function videoBudget(conceptId, fmt) {
    const videos = (status().video_budget || {}).videos || [];
    return videos.find(function (v) { return v && v.video_id === conceptId + ":" + fmt; }) || null;
  }

  function budgetLine(conceptId, fmt) {
    const v = videoBudget(conceptId, fmt);
    if (!v) return "";
    const tone = v.over_ceiling ? "blocked" : v.over_target ? "human" : "complete";
    return '<span class="status-badge status-' + tone + ' pd-budget-line">' + esc(money(v.committed_usd)) +
      " committed of " + esc(Number(v.target_usd).toFixed(2)) + " target (cap " + esc(Number(v.ceiling_usd).toFixed(2)) + ")</span>";
  }

  const budget = {
    kicker: "BUDGET",
    gate: function () {
      const n = narration.gate(), v = spend.gate();
      return { status: n.status || v.status ? [n.status, v.status].filter(Boolean).join(" / ") : "" };
    },
    all: function () {
      return narration.all().map(function (item) { return { kind: "narration", inner: item, decision: item.decision || null }; })
        .concat(spend.all().map(function (item) { return { kind: "spend", inner: item, decision: item.decision || null }; }));
    },
    config: function (item) { return item.kind === "narration" ? narration : spend; },
    video: function (item) {
      return item.kind === "narration" ? [item.inner.concept_id, item.inner.format] : [item.inner.packet.concept_id, item.inner.packet.format];
    },
    pending: function (item) { return this.config(item).pending(item.inner); },
    key: function (item) { return item.kind + "::" + this.config(item).key(item.inner); },
    title: function (item) {
      const video = this.video(item);
      return (item.kind === "narration" ? "Paid narration" : "Generate visual " + item.inner.gap.shot_id) + " · " + video[0] + " · " + words(video[1]);
    },
    meta: function (item) {
      const video = this.video(item);
      return this.config(item).meta(item.inner) + budgetLine(video[0], video[1]);
    },
    evidence: function (item) { return this.config(item).evidence(item.inner); },
    locked: function (item) { const c = this.config(item); return c.locked ? c.locked(item.inner) : ""; },
    decisions: function (item) { return this.config(item).decisions(item.inner); },
    decide: function (item, decision, note) { return this.config(item).decide(item.inner, decision, note); }
  };

  // ------------------------------------------- Edit preview and final export
  // ------------------------------------------------------- Generate visuals
  // Paid generation for shots authorized at Visual spend (D-140): generate
  // variants, then choose the one that becomes the shot's asset.
  const generate = {
    kicker: "GENERATE VISUAL",
    gate: function () { return status().visual_dispatch || {}; },
    all: function () { return (this.gate().shots || []).filter(Boolean); },
    pending: function (item) { return !item.registered; },
    key: function (item) { return item.request_file; },
    title: function (item) { return item.concept_id + " · " + words(item.format) + " · " + item.shot_id; },
    meta: function (item) {
      return '<span class="source-chip">authorized ' + esc(money(item.max_cost_usd)) + '</span><span class="rw-meta-text">spent ' +
        esc(money(item.spent_usd)) + "</span>" + (item.registered ? decidedBadge("REGISTERED", "complete") : "");
    },
    evidence: function (item) {
      const provider = this.gate();
      const key = item.request_file;
      const cards = (item.candidates || []).map(function (c) {
        const url = "/api/visual-dispatch-file?" + new URLSearchParams({ request_file: item.request_file, candidate_id: c.candidate_id }).toString();
        return '<article class="pk-package' + (generatedChoice[key] === c.candidate_id ? " chosen" : "") + '">' +
          '<img class="pk-thumb" src="' + esc(url) + '" alt="Generated variant ' + esc(c.candidate_id) + '" loading="lazy">' +
          '<div class="pk-package-body"><p class="muted">' + esc(c.provider || "") + "</p>" +
          '<label class="pk-choose"><input type="radio" name="pd-gen-' + esc(key) + '" data-pd-generated="' + esc(c.candidate_id) + '" data-key="' + esc(key) + '"' +
          (generatedChoice[key] === c.candidate_id ? " checked" : "") + "> Use this variant</label></div></article>";
      }).join("");
      return facts([
        ["Desired visual", item.desired_visual],
        ["Authorized maximum", money(item.max_cost_usd)],
        ["Spent on this shot", money(item.spent_usd)],
        ["Provider", provider.ready ? (provider.label || provider.active_provider) + " · " + (provider.model || "") : "off"]
      ]) +
        (provider.ready ? "" : '<p class="muted">Generation is off: ' + esc((provider.problems || []).join(" ")) + " Register an asset made elsewhere in the classic view instead.</p>") +
        section("Variants", cards ? '<div class="pk-packages">' + cards + "</div>" : '<p class="muted">No variants generated yet.</p>') +
        (item.prompt ? '<details><summary>Prompt</summary><p class="muted">' + esc(item.prompt) + "</p></details>" : "");
    },
    decisions: function (item) {
      const provider = this.gate();
      const key = item.request_file;
      const options = [];
      if (provider.ready) {
        options.push({
          value: "GENERATE", label: "Generate variants", tone: "running",
          hint: (provider.variants_per_shot || 2) + " variants, a paid call within this shot's authorized maximum.",
          confirm: function () { return "Generate " + (provider.variants_per_shot || 2) + " variants with the paid provider?"; }
        });
      }
      if ((item.candidates || []).length) {
        options.push({
          value: "CHOOSE", label: "Use the chosen variant", tone: "complete", hint: "Registers it as this shot's asset.",
          validate: function () { return generatedChoice[key] ? "" : "Choose a variant first."; }
        });
      }
      return options;
    },
    decide: function (item, decision) {
      const key = item.request_file;
      return post("/api/visual-dispatch", {
        action: decision, request_file: item.request_file, candidate_id: decision === "CHOOSE" ? generatedChoice[key] : null
      }, decision === "GENERATE" ? "Variants generated." : "Variant registered as the shot's asset.");
    }
  };

  function videoGate(config) {
    return {
      kicker: config.kicker,
      gate: function () { return status()[config.key] || {}; },
      all: function () { return (this.gate().items || []).filter(Boolean); },
      pending: function (item) { return String(item.decision || "PENDING").toUpperCase() === "PENDING" && !item.export_approved; },
      key: function (item) { return item.result_file || (item.concept_id + "::" + item.format); },
      title: function (item) { return item.concept_id + " · " + words(item.format); },
      meta: function (item) {
        const d = String(item.decision || "PENDING").toUpperCase();
        return '<span class="source-chip">' + esc(config.chip) + '</span><span class="rw-meta-text">' + Number(item.duration_seconds || 0).toFixed(1) + " s</span>" +
          (d !== "PENDING" ? decidedBadge(d, d === config.approve ? "complete" : "blocked") : "");
      },
      evidence: function (item) {
        const src = config.video + "?concept_id=" + encodeURIComponent(item.concept_id || "") + "&format=" + encodeURIComponent(item.format || "");
        return '<video class="pd-video" controls preload="metadata" src="' + esc(src) + '">Your browser cannot play this video.</video>' +
          facts(config.facts(item)) + '<p class="muted">' + esc(config.note) + "</p>";
      },
      locked: function (item) {
        return String(item.decision || "PENDING").toUpperCase() !== "PENDING"
          ? "Already decided. The decision is locked, as in the classic panel; a new render reopens it."
          : "";
      },
      decisions: function (item) {
        return [
          { value: config.approve, label: config.approveLabel, hint: config.approveHint, tone: "complete" },
          noteRework("RETURN_TO_VISUALS", "Return to visuals", "Visual choices or generation need changing."),
          noteRework("RETURN_TO_NARRATION", "Return to narration", "Narration audio needs changing."),
          noteRework("RETURN_TO_SOUND", "Return to sound", "Music or sound effects need changing.")
        ].concat(config.extraDecisions ? config.extraDecisions(item) : []);
      },
      decide: function (item, decision, note) {
        return post(config.endpoint, { result_file: item.result_file, decision: decision, note: note },
          decision === config.approve ? config.approvedToast : "Sent back: " + words(decision).replace("return to ", "") + ".");
      }
    };
  }

  const edit = videoGate({
    kicker: "EDIT PREVIEW", key: "edit_preview_gate", chip: "structural edit", video: "/api/edit-preview-video", endpoint: "/api/edit-preview-review",
    approve: "APPROVE_EDIT_DIRECTION", approveLabel: "Approve edit direction", approveHint: "Final production handoff follows.",
    approvedToast: "Edit direction approved.",
    note: "Judge pacing, sequence and narration-to-picture rhythm. Dark placeholder frames are unresolved visual slots, not render errors.",
    facts: function (item) { return [["Duration", Number(item.duration_seconds || 0).toFixed(1) + " s"], ["Placeholder segments", Number(item.placeholder_segments || 0)]]; }
  });

  const exportGate = videoGate({
    kicker: "FINAL EXPORT", key: "final_export_gate", chip: "final render", video: "/api/final-render-video", endpoint: "/api/final-export-review",
    approve: "APPROVE_EXPORT", approveLabel: "Approve final export", approveHint: "Binds these exact rendered bytes. Nothing is uploaded or published.",
    approvedToast: "Final export approved.",
    note: "Approval binds these exact rendered bytes. It does not upload or publish the video.",
    extraDecisions: function (item) {
      return item.source === "EDITOR" ? [noteRework("RETURN_TO_EDITOR", "Return to the editor", "The edit needs more work in Tesseract.")] : [];
    },
    facts: function (item) {
      return [
        ["Version", item.source === "EDITOR" ? "Edited in Tesseract" : "Automated render"],
        ["Duration", Number(item.duration_seconds || 0).toFixed(1) + " s"],
        ["Sound assets mixed", Number(item.sound_assets_mixed || 0)],
        ["Sound omissions", Number(item.sound_omissions || 0)],
        ["Render size", Number(item.render_bytes || 0).toLocaleString() + " bytes"]
      ];
    }
  });

  // ------------------------------------------------------------- Tesseract
  // Tesseract project exchange (D-144): export the editable project, then
  // import the finished edit, which becomes the Final Export candidate.
  function fileName(path) { return String(path || "").split(/[\\/]/).pop(); }

  const tesseract = {
    kicker: "TESSERACT",
    gate: function () { return status().editor_exchange || {}; },
    all: function () { return (this.gate().items || []).filter(Boolean); },
    pending: function (item) { return item.status === "EXPORTED"; },
    key: function (item) { return item.key; },
    title: function (item) { return item.concept_id + " · " + words(item.format); },
    meta: function (item) {
      return '<span class="source-chip">' + esc(this.gate().editor_name || "Tesseract") + '</span><span class="rw-meta-text">' + Number(item.duration_seconds || 0).toFixed(1) + " s</span>" +
        decidedBadge(words(item.status), item.status === "EDIT_RETURNED" ? "complete" : item.status === "EXPORTED" ? "human" : "running");
    },
    evidence: function (item) {
      const gate = this.gate();
      const record = item.export || null;
      const edit = item.edit || null;
      const key = item.key;
      const inputs = exchangeInputs[key] || {};
      const field = function (name, label, placeholder) {
        return '<label class="pd-pub-field"><span>' + esc(label) + '</span><input type="text" data-pd-ex="' + name + '" data-key="' + esc(key) +
          '" placeholder="' + esc(placeholder) + '" value="' + esc(inputs[name] || "") + '"></label>';
      };
      let html = gate.round_trip_verified ? "" : '<p class="muted">' + esc(gate.contract_note || "") + "</p>";
      html += record
        ? section("Editable project", facts([
          ["Folder", record.folder],
          ["Timelines", fileName(record.otio_file) + " · " + fileName(record.xml_file)],
          ["Clips", Number(record.clips || 0) + " on " + Number(record.tracks || 0) + " tracks"],
          ["Thumbnail source", (record.thumbnail_files || []).length ? (record.thumbnail_files || []).map(fileName).join(", ") : "not found"],
          ["Exported", record.exported_at]
        ]) + '<p class="muted">Open the .otio or .xml in Tesseract. Keep the clip names (V-, N-, S-) so changed scenes can be traced back.</p>')
        : section("Editable project", '<p class="muted">Not exported yet. Export writes the media, an OpenTimelineIO timeline, a Final Cut Pro 7 XML timeline, the automated render for reference and the thumbnail source into one folder.</p>');
      if (edit) {
        const checks = (edit.quality_checks || []).map(function (c) {
          return "<li>" + esc(words(c.check)) + ": " + esc(c.status) + " — " + esc(c.detail) + "</li>";
        }).join("");
        const changes = edit.scene_changes;
        let changeHtml = '<p class="muted">No edited timeline was imported, so scene changes are not known.</p>';
        if (changes) {
          const counts = Object.keys(changes.counts || {}).map(function (k) { return words(k) + " " + changes.counts[k]; }).join(" · ");
          const rows = (changes.clips || []).filter(function (r) { return r.change !== "KEPT"; }).map(function (r) {
            return "<li><strong>" + esc(r.clip_id) + "</strong> " + esc(words(r.change)) +
              (r.new_start_seconds !== null && r.new_start_seconds !== undefined ? " · now at " + Number(r.new_start_seconds).toFixed(2) + " s for " + Number(r.new_duration_seconds).toFixed(2) + " s" : "") + "</li>";
          }).concat((changes.added || []).map(function (a) { return "<li><strong>" + esc(a.clip_id) + "</strong> added on " + esc(a.track) + "</li>"; })).join("");
          changeHtml = "<p>" + esc(counts) + "</p>" + (rows ? '<ul class="rw-list">' + rows + "</ul>" : "");
        }
        html += section("Returned edit", facts([
          ["File", edit.original_file_name],
          ["Duration", Number(edit.duration_seconds || 0).toFixed(1) + " s"],
          ["Imported", edit.imported_at],
          ["Note", edit.note]
        ]) + '<ul class="rw-list">' + checks + "</ul>" + '<p class="muted">This edit is now the candidate at Final export.</p>') +
          section("Scene changes", changeHtml);
      }
      if (record) {
        html += section(edit ? "Replace the edit" : "Import the finished edit",
          field("video_path", "Edited video file on this computer (.mp4 or .mov)", "C:\\…\\final_edit.mp4") +
          field("timeline_path", "Edited timeline (.otio, optional)", "C:\\…\\final_edit.otio"));
      }
      return html;
    },
    decisions: function (item) {
      const key = item.key;
      const options = [];
      if (!item.export) {
        options.push({ value: "EXPORT", label: "Export editable project", tone: "complete", hint: "Free and local; nothing is uploaded." });
        return options;
      }
      options.push({
        value: "IMPORT_EDIT", label: item.edit ? "Import a new edit" : "Import the finished edit", tone: "complete",
        hint: "Checked for frame size and audio, then sent to Final export.",
        validate: function () { return String((exchangeInputs[key] || {}).video_path || "").trim() ? "" : "Enter the path of the edited video file."; }
      });
      if (item.edit) options.push(noteRework("DISCARD_EDIT", "Discard the edit", "Use the automated render again.", "say why the edit is discarded"));
      return options;
    },
    decide: function (item, decision, note) {
      const inputs = exchangeInputs[item.key] || {};
      const body = { action: decision, concept_id: item.concept_id, format: item.format, note: note };
      if (decision === "IMPORT_EDIT") {
        body.video_path = inputs.video_path || "";
        body.timeline_path = inputs.timeline_path || "";
      }
      const messages = { EXPORT: "Editable project exported.", IMPORT_EDIT: "Edit imported; review it at Final export.", DISCARD_EDIT: "Edit discarded." };
      return post("/api/editor-exchange", body, messages[decision] || "Saved.").then(function (ok) {
        if (ok && decision === "IMPORT_EDIT") delete exchangeInputs[item.key];
        return ok;
      });
    }
  };

  // ---------------------------------------------------------------- Publish
  // The publish package for an approved export (D-142): review and edit the
  // metadata, approve or hold, then upload (D-143) or record a manual upload.
  function pubValue(item, field) {
    const edits = pubEdits[item.key] || {};
    return Object.prototype.hasOwnProperty.call(edits, field) ? edits[field] : (item.metadata || {})[field];
  }

  function localDateTime(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    const pad = function (n) { return String(n).padStart(2, "0"); };
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate()) + "T" + pad(date.getHours()) + ":" + pad(date.getMinutes());
  }

  const publish = {
    kicker: "PUBLISH",
    gate: function () { return status().publish_gate || {}; },
    all: function () { return (this.gate().items || []).filter(Boolean); },
    pending: function (item) { return item.status !== "PUBLISHED"; },
    key: function (item) { return item.key; },
    title: function (item) { return (item.metadata || {}).title || item.key; },
    meta: function (item) {
      return '<span class="source-chip">' + esc(words(item.format)) + '</span><span class="rw-meta-text">' + esc(item.concept_id) + "</span>" +
        decidedBadge(words(item.status), item.status === "PUBLISHED" ? "complete" : item.status === "HELD" ? "blocked" : "human");
    },
    evidence: function (item) {
      const editable = item.status === "PENDING" || item.status === "HELD";
      const key = item.key;
      const field = function (name, label, html) { return '<label class="pd-pub-field"><span>' + esc(label) + "</span>" + html + "</label>"; };
      const dis = editable ? "" : " disabled";
      const tags = pubValue(item, "tags");
      const sources = (item.sources || []).map(function (s) { return "<li>" + esc(s.title) + " — " + esc(s.url) + "</li>"; }).join("");
      const published = item.published || {};
      return ((item.problems || []).length ? '<p class="radar-error">' + esc(item.problems.join(" ")) + "</p>" : "") +
        facts([
          ["Video file", String(item.video_file || "").split(/[\\/]/).pop()],
          ["Thumbnail", item.thumbnail_file ? String(item.thumbnail_file).split(/[\\/]/).pop() : "missing"],
          ["Category", (item.metadata || {}).category_id],
          ["Made for kids", (item.metadata || {}).made_for_kids ? "yes" : "no"]
        ]) +
        (item.status === "PUBLISHED"
          ? '<p>Published as <a href="' + esc(published.url) + '" target="_blank" rel="noopener noreferrer">' + esc(published.youtube_video_id) + "</a> (" + esc(words(published.method)) + ").</p>" +
            (published.thumbnail_set === false ? '<p class="radar-error">The thumbnail was not set: ' + esc(published.thumbnail_error || "") + " Set it in YouTube Studio.</p>" : "")
          : "") +
        section("Title (from the Final Packaging Gate)", "<p><strong>" + esc(pubValue(item, "title")) + "</strong></p>") +
        section("Metadata",
          field("description", "Description", '<textarea rows="8" data-pd-pub="description" data-key="' + esc(key) + '"' + dis + ">" + esc(pubValue(item, "description")) + "</textarea>") +
          field("tags", "Tags (comma separated)", '<input type="text" data-pd-pub="tags" data-key="' + esc(key) + '" value="' + esc(Array.isArray(tags) ? tags.join(", ") : tags || "") + '"' + dis + ">") +
          field("privacy", "Privacy", '<select data-pd-pub="privacy_status" data-key="' + esc(key) + '"' + dis + ">" + ["private", "unlisted", "public"].map(function (v) {
            return '<option value="' + v + '"' + (pubValue(item, "privacy_status") === v ? " selected" : "") + ">" + v + "</option>";
          }).join("") + "</select>") +
          field("publish_at", "Schedule (optional; uploads as private until then)", '<input type="datetime-local" data-pd-pub="publish_at" data-key="' + esc(key) + '" value="' + esc(localDateTime(pubValue(item, "publish_at"))) + '"' + dis + ">") +
          '<label class="pd-pub-check"><input type="checkbox" data-pd-pub="contains_synthetic_media" data-key="' + esc(key) + '"' + (pubValue(item, "contains_synthetic_media") ? " checked" : "") + dis +
            "> Contains realistic altered or synthetic content (AI voice, AI visuals)</label>") +
        section("Sources in the description", sources ? '<ul class="rw-list">' + sources + "</ul>" : '<p class="muted">No verified sources found.</p>') +
        (item.status === "APPROVED_FOR_UPLOAD"
          ? section("Upload",
            ((this.gate().uploader || {}).ready
              ? '<p class="muted">Upload sends this exact video, thumbnail and metadata to YouTube.</p>'
              : '<p class="muted">Direct upload is off: ' + esc(((this.gate().uploader || {}).problems || []).join(" ")) + "</p>") +
            field("video_id", "Uploaded by hand? YouTube video id", '<input type="text" maxlength="11" data-pd-pub="youtube_video_id" data-key="' + esc(key) + '" value="' + esc((pubEdits[key] || {}).youtube_video_id || "") + '">'))
          : "");
    },
    decisions: function (item) {
      const key = item.key;
      if (item.status === "PENDING" || item.status === "HELD") {
        return [
          { value: "APPROVE_PUBLISH", label: "Approve publish package", hint: "Binds this exact video, thumbnail and metadata.", tone: "complete" },
          noteRework("HOLD", "Hold", "Keep it unpublished for now.", "say why it is held")
        ];
      }
      if (item.status === "APPROVED_FOR_UPLOAD") {
        const options = [];
        if ((this.gate().uploader || {}).ready) {
          options.push({ value: "UPLOAD", label: "Upload to YouTube", tone: "complete", hint: "Privacy: " + ((item.metadata || {}).privacy_status || "private") + ".",
            confirm: function () { return "Upload this video to YouTube now as " + ((item.metadata || {}).privacy_status || "private") + "?"; } });
        }
        options.push({ value: "RECORD_UPLOAD", label: "Record a manual upload", tone: "running", hint: "You uploaded it in YouTube Studio.",
          validate: function () { return /^[A-Za-z0-9_-]{11}$/.test(String((pubEdits[key] || {}).youtube_video_id || "")) ? "" : "Enter the 11-character YouTube video id."; } });
        return options;
      }
      return [];
    },
    decide: function (item, decision, note) {
      const edits = Object.assign({}, pubEdits[item.key] || {});
      const body = { action: decision, concept_id: item.concept_id, format: item.format, note: note };
      if (decision === "APPROVE_PUBLISH") {
        if (typeof edits.tags === "string") edits.tags = edits.tags.split(",").map(function (t) { return t.trim(); }).filter(Boolean);
        if (edits.publish_at !== undefined) edits.publish_at = edits.publish_at ? new Date(edits.publish_at).toISOString() : null;
        delete edits.youtube_video_id;
        body.metadata = edits;
      }
      if (decision === "RECORD_UPLOAD") body.youtube_video_id = edits.youtube_video_id;
      const messages = { APPROVE_PUBLISH: "Publish package approved.", HOLD: "Video held.", UPLOAD: "Uploaded to YouTube.", RECORD_UPLOAD: "Upload recorded." };
      return post("/api/publish-gate", body, messages[decision] || "Saved.").then(function (ok) {
        if (ok) delete pubEdits[item.key];
        return ok;
      });
    }
  };

  const CONFIGS = { budget: budget, plan: plan, narration: narration, audio: finalAudio, visuals: visuals, rights: rights, roughcut: roughcut, spend: spend, generate: generate, edit: edit, tesseract: tesseract, export: exportGate, publish: publish };

  // ------------------------------------------------------------ Page shell
  function items(tab) {
    const config = CONFIGS[tab];
    const all = config.all();
    return showDecided ? all : all.filter(function (item) { return config.pending(item); });
  }

  function pendingCount(tab) {
    const config = CONFIGS[tab];
    return config.all().filter(function (item) { return config.pending(item); }).length;
  }

  function ensure(tab) {
    if (workspaces[tab]) return workspaces[tab];
    const root = document.getElementById("produce-" + tab);
    const config = CONFIGS[tab];
    if (!root || !window.ReviewWorkspace || !yp()) return null;
    workspaces[tab] = window.ReviewWorkspace.create({
      root: root,
      kicker: config.kicker,
      items: function () { return items(tab); },
      key: function (item) { return config.key(item); },
      signature: function (item) {
        return config.key(item) + ":" + JSON.stringify([
          item.decision || null,
          item.shot ? [item.shot.storyboard_current, (item.shot.candidates || []).map(function (c) { return c.candidate_id + ":" + c.state; })] : null,
          item.scenes ? item.scenes.length : null,
          item.render_bytes || item.duration_seconds || null
        ]);
      },
      title: function (item) { return config.title(item); },
      meta: function (item) { return config.meta(item); },
      renderEvidence: function (item) { return config.evidence(item); },
      // Decided items the classic panel locks stay locked here (UI-19).
      decisions: function (item) { return config.locked && config.locked(item) ? [] : config.decisions(item); },
      locked: function (item) { return config.locked ? config.locked(item) : ""; },
      initialNote: function (item) {
        const d = item.decision;
        return (d && typeof d === "object" ? d.note : (item.inner || item).note) || "";
      },
      decide: function (item, decision, note, extras) { return config.decide(item, decision, note, extras || {}); },
      onNavigate: function (key) {
        if (window.location.pathname === "/produce") history.replaceState({}, "", "/produce#" + tab + "/" + encodeURIComponent(key));
      },
      emptyHtml: function () {
        const total = config.all().length;
        const label = TABS.find(function (t) { return t[0] === tab; })[1];
        return total && !showDecided
          ? "<h2>Every " + esc(label.toLowerCase()) + " item is decided</h2><p class=\"muted\">Tick “Include decided items” to revisit one.</p>"
          : "<h2>Nothing waiting at " + esc(label) + "</h2><p class=\"muted\">Status: " + esc(words(config.gate().status) || "not started") + ". Items appear when production reaches this step.</p>";
      }
    });
    return workspaces[tab];
  }

  // Keep the active tab visible in the scrolling strip on narrow screens.
  function revealActiveTab(container) {
    const active = container && container.querySelector(".pw-tab.active");
    const strip = active && active.parentElement;
    if (!strip) return;
    const left = active.offsetLeft; // the strip is position: relative
    if (left < strip.scrollLeft || left + active.offsetWidth > strip.scrollLeft + strip.clientWidth) {
      strip.scrollLeft = Math.max(0, left - 16);
    }
  }

  // One budget per video (D-136): what is committed (authorized or spent)
  // against the ceiling, and what has actually been spent.
  function budgetHtml() {
    const budget = status().video_budget || {};
    const videos = (budget.videos || []).filter(Boolean);
    if (!videos.length && !budget.ceiling_usd) return "";
    const rows = videos.map(function (v) {
      const tone = v.over_ceiling ? "blocked" : v.over_target ? "human" : "complete";
      const label = v.over_ceiling ? "Over ceiling" : v.over_target ? "Over target" : "Within target";
      return "<li><strong>" + esc(v.video_id) + "</strong> · committed " + esc(money(v.committed_usd)) +
        " of " + esc(money(v.ceiling_usd)) + " · spent " + esc(money(v.actual_usd)) +
        ' <span class="status-badge status-' + tone + '">' + esc(label) + "</span></li>";
    }).join("");
    return '<section class="pd-budget" aria-label="Budget per video"><p class="attention-kicker">BUDGET PER VIDEO</p>' +
      '<p class="muted">Target ' + esc(money(budget.target_usd)) + " · ceiling " + esc(money(budget.ceiling_usd)) +
      (budget.confirmed_by_human ? "" : " · proposed, not yet confirmed by you") + "</p>" +
      (rows ? '<ul class="rw-list">' + rows + "</ul>" : '<p class="muted">Nothing authorized or spent yet.</p>') + "</section>";
  }

  function visibleTabs() {
    return TABS.filter(function (tab) {
      return tab[2] === "yours" || showDecided || tab[0] === activeTab || pendingCount(tab[0]) > 0;
    });
  }

  function tabButton(tab) {
    const on = tab[0] === activeTab;
    return '<button type="button" role="tab" class="pw-tab' + (on ? " active" : "") + '" aria-selected="' + on + '" data-pd-tab="' + tab[0] + '">' +
      esc(tab[1]) + ' <span class="tab-count">' + pendingCount(tab[0]) + "</span></button>";
  }

  function renderTabs() {
    const bar = document.getElementById("produceTabs");
    if (!bar) return;
    const shown = visibleTabs();
    const groups = ["yours", "policy", "tools"].map(function (group) {
      const tabs = shown.filter(function (tab) { return tab[2] === group; });
      if (!tabs.length) return "";
      return '<div class="pw-tab-group" role="group" aria-label="' + esc(GROUP_LABELS[group]) + '">' +
        '<span class="pw-tab-group-label" aria-hidden="true">' + esc(GROUP_LABELS[group]) + "</span>" + tabs.map(tabButton).join("") + "</div>";
    }).join("");
    const html = budgetHtml() + '<div class="pw-tabs pk-tabs" role="tablist" aria-label="Production gates">' + groups + "</div>" +
      '<div class="gate-switcher"><label class="gate-toggle"><input type="checkbox" data-pd-decided' + (showDecided ? " checked" : "") + "> Include decided items and empty gates</label>" +
      '<a href="/analysis" class="button-link ghost compact" data-route="/analysis" title="Asset registration, storyboard edits and every original option">Classic view</a></div>';
    if (html === paintedTabs && bar.innerHTML) return;
    paintedTabs = html;
    bar.innerHTML = html;
    revealActiveTab(bar);
  }

  function render() {
    renderTabs();
    TABS.forEach(function (tab) {
      const root = document.getElementById("produce-" + tab[0]);
      if (root) root.hidden = tab[0] !== activeTab;
    });
    const workspace = ensure(activeTab);
    if (!workspace) return;
    if (pendingFocus[activeTab]) {
      const key = pendingFocus[activeTab];
      delete pendingFocus[activeTab];
      workspace.focus(key);
    } else {
      workspace.render();
    }
  }

  function open(subroute) {
    const raw = String(subroute || "");
    const slash = raw.indexOf("/");
    const tab = TAB_ALIASES[slash === -1 ? raw : raw.slice(0, slash)] || (slash === -1 ? raw : raw.slice(0, slash));
    if (CONFIGS[tab] && TABS.some(function (t) { return t[0] === tab; })) {
      activeTab = tab;
      if (slash !== -1 && !TAB_ALIASES[raw.slice(0, slash)]) pendingFocus[tab] = window.YPUtil.decode(raw.slice(slash + 1));
    }
    render();
  }

  document.addEventListener("click", async function (event) {
    const button = event.target.closest && event.target.closest("[data-pd-dispatch]");
    if (!button) return;
    const segments = button.dataset.segments ? button.dataset.segments.split(",") : [];
    const what = segments.length ? segments.length + " segment(s)" : "the whole narration";
    if (!window.confirm("Generate " + what + " with the paid provider now? This spends money within the approved worst case.")) return;
    button.disabled = true;
    button.textContent = "Generating…";
    await post("/api/narration-dispatch", { concept_id: button.dataset.pdDispatch, format: button.dataset.format, segment_ids: segments },
      "Narration generated and registered; Audio QC runs next.");
    button.disabled = false;
  });

  document.addEventListener("click", function (event) {
    const tab = event.target.closest && event.target.closest("[data-pd-tab]");
    if (!tab) return;
    activeTab = tab.dataset.pdTab;
    history.replaceState({}, "", "/produce#" + activeTab);
    render();
  });

  document.addEventListener("change", function (event) {
    const t = event.target;
    if (!t.closest || !t.closest("#viewProduce")) return;
    if (t.matches("[data-pd-decided]")) {
      showDecided = t.checked;
      Object.keys(workspaces).forEach(function (k) { workspaces[k].refresh(); });
      render();
    } else if (t.dataset.pdSegment) {
      (reworkSegments[t.dataset.key] = reworkSegments[t.dataset.key] || {})[t.dataset.pdSegment] = t.checked;
    } else if (t.dataset.pdTick) {
      (spendTicks[t.dataset.key] = spendTicks[t.dataset.key] || {})[t.dataset.pdTick] = t.checked;
    } else if (t.dataset.pdGenerated) {
      generatedChoice[t.dataset.key] = t.dataset.pdGenerated;
    } else if (t.dataset.pdVisual) {
      visualChoice[t.dataset.key] = t.dataset.pdVisual;
      t.closest(".pk-packages").querySelectorAll(".pk-package").forEach(function (card) { card.classList.toggle("chosen", card.contains(t)); });
    } else if (t.dataset.pdCost) {
      maxCost[t.dataset.pdCost] = Number(t.value || 0);
    }
  });

  document.addEventListener("input", function (event) {
    const t = event.target;
    if (!t.dataset) return;
    if (t.dataset.pdContext) rightsContext[t.dataset.pdContext] = t.value;
    if (t.dataset.pdCost) maxCost[t.dataset.pdCost] = Number(t.value || 0);
    if (t.dataset.pdEx) {
      (exchangeInputs[t.dataset.key] = exchangeInputs[t.dataset.key] || {})[t.dataset.pdEx] = t.value;
    }
    if (t.dataset.pdPub) {
      (pubEdits[t.dataset.key] = pubEdits[t.dataset.key] || {})[t.dataset.pdPub] = t.type === "checkbox" ? t.checked : t.value;
    }
  });

  window.Produce = {
    open: open,
    show: function () { if (window.location.pathname === "/produce") open(window.location.hash.slice(1)); },
    render: function () { if (window.location.pathname === "/produce") render(); },
    pending: pendingCount
  };
})();
