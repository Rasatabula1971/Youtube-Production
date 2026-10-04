/* Produce workspace (UI-14, D-122).
   /produce#<tab>: the seven production gates on the shared review
   workspace — Narration spend, Choose visuals, Footage rights, Rough cut,
   Visual spend, Edit preview, Final export. Every decision posts exactly what
   the classic panel posts. Asset registration (final narration audio,
   managed and generated visuals, final sound) and storyboard editing stay in
   the classic view: they are data entry, not decisions. */
(function () {
  "use strict";

  const TABS = [
    ["narration", "Narration spend"],
    ["visuals", "Choose visuals"],
    ["rights", "Footage rights"],
    ["roughcut", "Rough cut"],
    ["spend", "Visual spend"],
    ["edit", "Edit preview"],
    ["export", "Final export"]
  ];

  let activeTab = "narration";
  let showDecided = false;
  const workspaces = Object.create(null);
  const pendingFocus = Object.create(null);
  // Per-item inputs that live in the evidence panel (kept across repaints).
  const spendTicks = Object.create(null);      // narration key -> {criterion: bool}
  const visualChoice = Object.create(null);    // shot key -> candidate_id
  const rightsContext = Object.create(null);   // rights key -> context note
  const maxCost = Object.create(null);         // spend key -> number
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

  function noteRework(value, label, hint, placeholder) {
    return { value: value, label: label, hint: hint, tone: "running", needsNote: true, notePlaceholder: placeholder || "say what must change" };
  }

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

  // ------------------------------------------- Edit preview and final export
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
      decisions: function () {
        return [
          { value: config.approve, label: config.approveLabel, hint: config.approveHint, tone: "complete" },
          noteRework("RETURN_TO_VISUALS", "Return to visuals", "Visual choices or generation need changing."),
          noteRework("RETURN_TO_NARRATION", "Return to narration", "Narration audio needs changing."),
          noteRework("RETURN_TO_SOUND", "Return to sound", "Music or sound effects need changing.")
        ];
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
    facts: function (item) {
      return [
        ["Duration", Number(item.duration_seconds || 0).toFixed(1) + " s"],
        ["Sound assets mixed", Number(item.sound_assets_mixed || 0)],
        ["Sound omissions", Number(item.sound_omissions || 0)],
        ["Render size", Number(item.render_bytes || 0).toLocaleString() + " bytes"]
      ];
    }
  });

  const CONFIGS = { narration: narration, visuals: visuals, rights: rights, roughcut: roughcut, spend: spend, edit: edit, export: exportGate };

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
        return (d && typeof d === "object" ? d.note : item.note) || "";
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

  function renderTabs() {
    const bar = document.getElementById("produceTabs");
    if (!bar) return;
    const html = budgetHtml() + '<div class="pw-tabs pk-tabs" role="tablist" aria-label="Production gates">' + TABS.map(function (tab) {
      const on = tab[0] === activeTab;
      return '<button type="button" role="tab" class="pw-tab' + (on ? " active" : "") + '" aria-selected="' + on + '" data-pd-tab="' + tab[0] + '">' +
        esc(tab[1]) + ' <span class="tab-count">' + pendingCount(tab[0]) + "</span></button>";
    }).join("") + "</div>" +
      '<div class="gate-switcher"><label class="gate-toggle"><input type="checkbox" data-pd-decided' + (showDecided ? " checked" : "") + "> Include decided items</label>" +
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
    const tab = slash === -1 ? raw : raw.slice(0, slash);
    if (CONFIGS[tab]) {
      activeTab = tab;
      if (slash !== -1) pendingFocus[tab] = window.YPUtil.decode(raw.slice(slash + 1));
    }
    render();
  }

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
    } else if (t.dataset.pdTick) {
      (spendTicks[t.dataset.key] = spendTicks[t.dataset.key] || {})[t.dataset.pdTick] = t.checked;
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
  });

  window.Produce = {
    open: open,
    show: function () { if (window.location.pathname === "/produce") open(window.location.hash.slice(1)); },
    render: function () { if (window.location.pathname === "/produce") render(); },
    pending: pendingCount
  };
})();
