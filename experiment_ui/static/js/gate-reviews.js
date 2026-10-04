/* Analysis, Concept and Research gates on the shared review workspace
   (UI-09/UI-10, D-118). Same endpoints and payloads as the classic panels
   in Workspace (/analysis); only the review experience changes.
   Route: /review#<gate> or /review#<gate>/<item key>. */
(function () {
  "use strict";

  const GATES = ["analysis", "concept", "research", "script", "format", "voice", "preview"];
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

  // ------------------------------------------------------------------ Script
  // A script branch is reviewed section by section (hook, sections, closing),
  // then as a whole. Section actions use /api/script-section-review and the
  // whole-script decision /api/script-gate, exactly as the classic panel does.
  const sectionSnapshots = {};
  const sectionLoading = {};
  const REWORK_REASONS = [
    ["", "Choose a reason (or write an instruction)"],
    ["TOO_BORING", "Too boring"],
    ["TOO_LONG", "Too long"],
    ["TOO_TECHNICAL", "Too technical"],
    ["NOT_DRAMATIC_ENOUGH", "Not dramatic enough"],
    ["WEAK_TRANSITION", "Weak transition"],
    ["FACT_UNCLEAR", "Fact unclear"],
    ["UNNATURAL", "Sounds unnatural"],
    ["WEAK_CURIOSITY", "Weak curiosity"],
    ["WEAK_EMOTION", "Weak emotion"],
    ["CUSTOM", "Custom (instruction below)"]
  ];

  function branchKey(conceptId, format) { return conceptId + "::" + format; }

  function scripts() {
    return ((status().script_gate || {}).scripts || []).filter(Boolean);
  }

  async function loadSections(conceptId, format) {
    const key = branchKey(conceptId, format);
    if (sectionLoading[key]) return;
    sectionLoading[key] = true;
    try {
      sectionSnapshots[key] = await yp().api(
        "/api/script-section-review?concept_id=" + encodeURIComponent(conceptId) +
        "&format=" + encodeURIComponent(format)
      );
    } catch (error) {
      sectionSnapshots[key] = { status: "ERROR", error: error.message, targets: [] };
    } finally {
      sectionLoading[key] = false;
      if (workspaces.script) workspaces.script.refresh();
      renderSwitcher();
    }
  }

  function targetLabel(target) {
    if (target.target_type === "OPENING_HOOK") return "Opening hook";
    if (target.target_type === "CLOSING") return "Closing";
    const purpose = (target.metadata || {}).purpose;
    return (target.section_id || "Section") + (purpose ? ": " + purpose : "");
  }

  function sectionState(target) {
    if (target.locked) return target.decision === "ACCEPTED" ? "ACCEPTED" : "LOCKED";
    return String(target.decision || "PENDING").toUpperCase();
  }

  const script = {
    label: "Script",
    kicker: "SCRIPT REVIEW",
    snapshot: function () { return status().script_gate || {}; },
    sections: function (item) { return sectionSnapshots[branchKey(item.concept_id, item.format)] || null; },
    all: function () {
      const rows = [];
      scripts().forEach(function (branch) {
        const key = branchKey(branch.concept_id, branch.format);
        const decided = String(branch.decision || "PENDING").toUpperCase() !== "PENDING";
        if (!sectionSnapshots[key]) {
          // List nothing for this branch until its sections are known, so the
          // review starts at the opening hook rather than the whole script.
          loadSections(branch.concept_id, branch.format);
          return;
        }
        const snap = sectionSnapshots[key];
        ((snap && snap.targets) || []).forEach(function (target) {
          rows.push({ kind: "section", concept_id: branch.concept_id, format: branch.format, branch: branch, target: target, branchDecided: decided });
        });
        rows.push({ kind: "whole", concept_id: branch.concept_id, format: branch.format, branch: branch, decision: branch.decision, note: branch.note, branchDecided: decided });
      });
      return rows;
    },
    isPending: function (item) {
      if (item.branchDecided) return false;
      if (item.kind === "whole") return true;
      return !(item.target.locked && item.target.decision === "ACCEPTED");
    },
    initialValue: function (item) {
      if (item.kind !== "whole") return "";
      const decision = String(item.decision || "PENDING").toUpperCase();
      return decision === "PENDING" ? "" : decision;
    },
    key: function (item) {
      return branchKey(item.concept_id, item.format) + "::" + (item.kind === "whole" ? "WHOLE" : item.target.target_id);
    },
    extraSignature: function (item) {
      const snap = this.sections(item) || {};
      if (item.kind === "whole") {
        return (snap.status || "") + ":" + JSON.stringify((snap.targets || []).map(sectionState));
      }
      const t = item.target;
      return [snap.status, t.decision, t.locked, t.rework_reason, t.target_sha256, JSON.stringify(t.alternatives || null)].join("|");
    },
    title: function (item) {
      return item.kind === "whole"
        ? "Whole script: " + (item.branch.title || item.concept_id)
        : targetLabel(item.target);
    },
    meta: function (item) {
      const chip = '<span class="source-chip">' + esc(words(item.format)) + "</span>";
      if (item.kind === "whole") {
        return chip + '<span class="rw-meta-text">' + esc(item.concept_id) + " · whole-script decision</span>" + decidedBadge(item.decision);
      }
      const state = sectionState(item.target);
      const tone = state === "ACCEPTED" || state === "LOCKED" ? "complete" : state === "REWORK_REQUESTED" ? "blocked" : "human";
      return chip + '<span class="rw-meta-text">' + esc(item.branch.title || item.concept_id) + "</span>" +
        '<span class="status-badge status-' + tone + '">' + esc(words(state)) + (item.target.locked ? " · locked" : "") + "</span>";
    },
    claims: function (item, ids) {
      const byId = {};
      (item.branch.accepted_claims || []).forEach(function (c) { if (c && c.claim_id) byId[c.claim_id] = c.statement; });
      return (ids || []).map(function (id) { return byId[id] ? id + ": " + byId[id] : id; });
    },
    evidence: function (item) {
      const snap = this.sections(item);
      const notice = !snap
        ? '<p class="muted">Loading the section review…</p>'
        : snap.status === "STALE_SECTION_STATE"
          ? '<p class="radar-error">Section review is out of date with the draft: ' + esc(snap.error || "") + " Use the classic view to resolve it.</p>"
          : snap.status === "ERROR"
            ? '<p class="radar-error">' + esc(snap.error || "Section review could not be loaded.") + "</p>"
            : "";
      if (item.kind === "whole") return notice + this.wholeEvidence(item, snap);
      const target = item.target;
      const meta = target.metadata || {};
      const branch = branchKey(item.concept_id, item.format);
      let rework = "";
      if (target.decision === "REWORK_REQUESTED") {
        rework = section("Rework requested",
          '<p>' + esc(words(target.rework_reason || "custom")) + (target.custom_instruction ? " — " + esc(target.custom_instruction) : "") + "</p>" +
          '<div class="rw-actions">' +
            '<button type="button" class="compact" data-script-act="GENERATE_ALTERNATIVES" data-branch="' + esc(branch) + '" data-target="' + esc(target.target_id) + '">Generate A / B / C</button>' +
            '<button type="button" class="ghost compact" data-script-act="CANCEL_REWORK" data-branch="' + esc(branch) + '" data-target="' + esc(target.target_id) + '">Cancel rework</button>' +
          "</div>" +
          '<p class="muted">Generating calls the script model once for three bounded alternatives; nothing changes until you pick one.</p>');
      }
      const alternatives = target.alternatives;
      let options = "";
      if (alternatives && alternatives.selection) {
        options = section("Alternatives", '<p>Selected <strong>' + esc(alternatives.selection.selection_id || "") + "</strong>; this part is accepted and locked.</p>");
      } else if (alternatives && (alternatives.alternatives || []).length) {
        const cards = [{ id: "ORIGINAL", text: (alternatives.original || {}).text || target.text, summary: "Keep the current text", claims: meta.claim_ids }]
          .concat((alternatives.alternatives || []).map(function (alt) {
            return { id: alt.alternative_id, text: alt.replacement_text, summary: alt.change_summary, claims: alt.claim_ids_used };
          }));
        options = section("Alternatives", '<div class="rw-alternatives">' + cards.map(function (card) {
          return '<article class="rw-alternative"><p class="attention-kicker">' + esc(card.id === "ORIGINAL" ? "Original" : "Option " + card.id) + "</p>" +
            '<p class="rw-script-text">' + esc(card.text || "") + "</p>" +
            (card.summary ? '<p class="muted">' + esc(card.summary) + "</p>" : "") +
            '<p class="muted">Claims: ' + esc((card.claims || []).join(", ") || "none") + "</p>" +
            '<button type="button" class="' + (card.id === "ORIGINAL" ? "ghost " : "") + 'compact" data-script-act="SELECT_ALTERNATIVE" data-selection="' + esc(card.id) +
              '" data-branch="' + esc(branch) + '" data-target="' + esc(target.target_id) + '">' + (card.id === "ORIGINAL" ? "Keep original" : "Use " + esc(card.id)) + "</button>" +
          "</article>";
        }).join("") + "</div>");
      }
      return notice +
        section("Script text", '<p class="rw-script-text">' + esc(target.text || "") + "</p>") +
        section("Why this part exists", facts([
          ["Purpose", meta.purpose],
          ["Psychology", meta.psychology_mechanism],
          ["Reward", meta.reward_type]
        ])) +
        section("Claims used", list(this.claims(item, meta.claim_ids || (target.target_type === "OPENING_HOOK" ? item.branch.opening_hook_claim_ids : [])))) +
        rework + options;
    },
    wholeEvidence: function (item, snap) {
      const rows = ((snap && snap.targets) || []).map(function (t) {
        const state = sectionState(t);
        const tone = state === "ACCEPTED" || state === "LOCKED" ? "complete" : state === "REWORK_REQUESTED" ? "blocked" : "human";
        return "<tr><th scope=\"row\">" + esc(targetLabel(t)) + '</th><td><span class="status-badge status-' + tone + '">' + esc(words(state)) + "</span></td></tr>";
      }).join("");
      const validation = item.branch.validation || {};
      // Prefer the live section text, which already reflects edits and selections.
      const live = function (type, fallback) {
        const found = ((snap && snap.targets) || []).find(function (t) { return t.target_type === type; });
        return (found && found.text) || fallback || "";
      };
      return section("Opening hook", '<p class="rw-script-text">' + esc(live("OPENING_HOOK", item.branch.opening_hook)) + "</p>") +
        section("Sections", rows ? '<table class="pw-rows"><tbody>' + rows + "</tbody></table>" : '<p class="muted">Sections appear once the section review loads.</p>') +
        section("Closing", '<p class="rw-script-text">' + esc(live("CLOSING", item.branch.closing)) + "</p>") +
        section("Validation", (validation.errors || []).length
          ? list(validation.errors)
          : '<p class="muted">' + (validation.valid === false ? "Not valid." : "No validation errors recorded.") + "</p>") +
        section("Approved claims available", list(this.claims(item, (item.branch.accepted_claims || []).map(function (c) { return c.claim_id; }))));
    },
    openTargets: function (item) {
      const snap = this.sections(item);
      if (!snap || snap.status !== "READY_FOR_SECTION_REVIEW") return [];
      return (snap.targets || []).filter(function (t) { return t.decision !== "ACCEPTED" || t.locked !== true; });
    },
    decisions: function (item) {
      if (item.kind === "whole") {
        const self = this;
        return [
          {
            value: "ACCEPT", label: "Accept the whole script", tone: "complete",
            hint: "Packaging (title directions) starts automatically.",
            confirm: function () {
              const open = self.openTargets(item);
              if (!open.length) return "";
              return "Accept the whole script as it stands? " + open.length +
                " section(s) you have not edited or accepted will be accepted too" +
                (open.some(function (t) { return t.decision === "REWORK_REQUESTED"; }) ? ", and pending section reworks will be cancelled." : ".");
            }
          },
          { value: "REWORK", label: "Rework the whole script", hint: "Regenerate the draft with your direction.", tone: "running", needsNote: true, notePlaceholder: "say what must change" },
          { value: "REJECT", label: "Reject", hint: "This branch will not be produced.", tone: "blocked" }
        ];
      }
      const target = item.target;
      if (target.locked) {
        return [{ value: "UNLOCK", label: "Unlock to change it", hint: "Withdraws any whole-script approval for this branch.", tone: "running", takesNote: false }];
      }
      const manual = {
        value: "MANUAL_EDIT", label: "Edit by hand", hint: "Your text replaces this part and locks it.", tone: "human",
        needsNote: true, noteLabel: "New text", noteRows: 8, noteMaxLength: 6000, notePlaceholder: "write the replacement text",
        notePrefill: function () { return target.text || ""; },
        validate: function (_item, draft) {
          return draft.note.trim() === String(target.text || "").trim() ? "Change the text before saving the edit." : "";
        }
      };
      if (target.decision === "REWORK_REQUESTED") {
        return [
          { value: "CANCEL_REWORK", label: "Cancel rework", hint: "Keep this part as it is for now.", tone: "running", takesNote: false },
          manual
        ];
      }
      return [
        { value: "ACCEPT", label: "Accept and lock", hint: "This part is final unless you unlock it.", tone: "complete", takesNote: false },
        {
          value: "REWORK", label: "Rework", hint: "Ask for A / B / C alternatives for this part only.", tone: "running",
          select: { label: "Reason", options: REWORK_REASONS }, noteLabel: "Instruction", notePlaceholder: "what should change (optional with a reason)",
          validate: function (_item, draft) {
            if (!draft.select && !draft.note.trim()) return "Choose a rework reason or write an instruction.";
            if (draft.select === "CUSTOM" && !draft.note.trim()) return "A custom rework needs an instruction.";
            return "";
          }
        },
        manual
      ];
    },
    decide: function (item, decision, note, extras) {
      if (item.kind === "whole") {
        const open = this.openTargets(item);
        const messages = { ACCEPT: words(item.format) + " script accepted.", REWORK: "Script sent for rework.", REJECT: "Script rejected." };
        return post("/api/script-gate", {
          concept_id: item.concept_id,
          format: item.format,
          decision: decision,
          criteria: {},
          note: note,
          accept_open_sections: decision === "ACCEPT" && open.length > 0
        }, messages[decision] || "Saved.").then(function () { return loadSections(item.concept_id, item.format); });
      }
      return sectionAction(item.concept_id, item.format, decision, item.target.target_id, {
        reason: decision === "REWORK" ? (extras.select || null) : null,
        custom_instruction: decision === "REWORK" ? (note || null) : null,
        replacement_text: decision === "MANUAL_EDIT" ? note : null
      });
    }
  };

  const SECTION_MESSAGES = {
    ACCEPT: "Accepted and locked.",
    UNLOCK: "Unlocked.",
    REWORK: "Rework requested. Generate A / B / C when you are ready.",
    CANCEL_REWORK: "Rework cancelled.",
    GENERATE_ALTERNATIVES: "A / B / C alternatives are ready.",
    SELECT_ALTERNATIVE: "Selection applied and locked.",
    MANUAL_EDIT: "Edit applied and locked."
  };

  async function sectionAction(conceptId, format, action, targetId, extra) {
    const snap = sectionSnapshots[branchKey(conceptId, format)] || {};
    const body = function (act) {
      return {
        concept_id: conceptId,
        format: format,
        action: act,
        target_id: act === "PREPARE" ? null : targetId,
        reason: (extra && extra.reason) || null,
        custom_instruction: (extra && extra.custom_instruction) || null,
        selection_id: (extra && extra.selection_id) || null,
        replacement_text: (extra && extra.replacement_text) || null,
        version_id: null
      };
    };
    try {
      // Section actions need the section state; prepare it first, as the
      // classic panel's Edit button does.
      if (snap.status !== "READY_FOR_SECTION_REVIEW") {
        await yp().api("/api/script-section-review", { method: "POST", body: JSON.stringify(body("PREPARE")) });
      }
      const payload = await yp().api("/api/script-section-review", { method: "POST", body: JSON.stringify(body(action)) });
      if (payload && payload.status === "ALTERNATIVE_GENERATION_FAILED") {
        yp().showToast("Alternative generation failed: " + words((payload.generation || {}).status || "unknown"), true);
      } else {
        yp().showToast(SECTION_MESSAGES[action] || "Script section updated.", false);
      }
    } catch (error) {
      yp().showToast(error.message, true);
    }
    await loadSections(conceptId, format);
    await yp().refresh();
  }

  // ------------------------------------------------------------------ Format
  function criteriaList(item) {
    const criteria = item.criteria || {};
    return list((item.required_accept_criteria || Object.keys(criteria)).map(function (key) { return criteria[key] || words(key); }));
  }

  function beatsTable(beats, directions) {
    const byBeat = {};
    (directions || []).forEach(function (d) { if (d && d.beat_id) byBeat[d.beat_id] = d; });
    const rows = (beats || []).filter(Boolean).map(function (beat) {
      const d = byBeat[beat.beat_id];
      const delivery = d ? [
        d.emotion, d.intensity != null ? "intensity " + d.intensity : "", d.speed != null ? "speed " + d.speed : "",
        d.pause_before_ms ? "pause before " + d.pause_before_ms + " ms" : "", d.pause_after_ms ? "pause after " + d.pause_after_ms + " ms" : "",
        (d.emphasis_terms || []).length ? "stress: " + d.emphasis_terms.join(", ") : ""
      ].filter(Boolean).join(" · ") : "";
      return '<li class="rw-beat"><p class="attention-kicker">' + esc(beat.beat_id) + (beat.reveal_beat ? " · reveal" : "") +
        (beat.purpose ? " · " + esc(beat.purpose) : "") + "</p>" +
        (beat.immutable_narration ? '<p class="rw-script-text">' + esc(beat.immutable_narration) + "</p>" : "") +
        (beat.treatment ? '<p class="muted">' + esc(beat.treatment) + "</p>" : "") +
        (delivery ? '<p class="rw-delivery">' + esc(delivery) + "</p>" : "") +
        "</li>";
    }).join("");
    return rows ? '<ol class="rw-beats">' + rows + "</ol>" : "";
  }

  const ACCEPT_REWORK_REJECT = function (acceptHint, reworkHint) {
    return [
      { value: "ACCEPT", label: "Accept", hint: acceptHint, tone: "complete" },
      { value: "REWORK", label: "Rework", hint: reworkHint, tone: "running", needsNote: true, notePlaceholder: "say what must change" },
      { value: "REJECT", label: "Reject", hint: "Stop here for this item.", tone: "blocked" }
    ];
  };

  const format = {
    label: "Format",
    kicker: "FORMAT REVIEW",
    snapshot: function () { return status().format_gate || {}; },
    all: function () { return this.snapshot().plans || []; },
    key: function (item) { return item.concept_id; },
    title: function (item) { return (item.package || {}).title || item.concept_id; },
    meta: function (item) {
      return '<span class="source-chip">' + esc((item.required_branches || []).map(words).join(" + ") || "format") + "</span>" +
        '<span class="rw-meta-text">' + esc(words(item.format_intent)) + "</span>" + decidedBadge(item.decision);
    },
    evidence: function (item) {
      const branches = (item.branches || []).filter(Boolean).map(function (branch) {
        return section(words(branch.format) + " · " + (branch.duration_intent_seconds ? Math.round(branch.duration_intent_seconds) + " s" : "duration not set"),
          facts([["Promise delivery", branch.promise_delivery], ["Payoff", branch.payoff]]) + beatsTable(branch.beats));
      }).join("");
      return branches +
        section("Branch separation", facts([["Separation", item.branch_separation]])) +
        section("Claims used by branch", facts(Object.keys(item.claim_usage_by_branch || {}).map(function (k) { return [words(k), item.claim_usage_by_branch[k]]; }))) +
        section("Unused accepted claims", list(item.unused_accepted_claim_ids)) +
        section("Source overlap", facts([["Overlap", item.source_overlap]])) +
        section("Accepting confirms", criteriaList(item));
    },
    decisions: function () {
      return ACCEPT_REWORK_REJECT("Voice performance planning starts automatically.", "Re-plan the formats with your direction.");
    },
    decide: function (item, decision, note) {
      const messages = { ACCEPT: "Format plan accepted.", REWORK: "Format plan sent for rework.", REJECT: "Format plan rejected." };
      return post("/api/format-gate", { concept_id: item.concept_id, decision: decision, criteria: {}, note: note }, messages[decision] || "Saved.");
    }
  };

  // ------------------------------------------------------------------- Voice
  const voice = {
    label: "Voice",
    kicker: "VOICE PERFORMANCE REVIEW",
    snapshot: function () { return status().performance_gate || {}; },
    all: function () { return this.snapshot().specs || []; },
    key: function (item) { return item.concept_id + "::" + item.format; },
    title: function (item) { return item.title || item.concept_id; },
    meta: function (item) {
      return '<span class="source-chip">' + esc(words(item.format)) + "</span>" +
        '<span class="rw-meta-text">' + esc(item.concept_id) +
        (item.duration_intent_seconds ? " · " + Math.round(item.duration_intent_seconds) + " s" : "") + "</span>" + decidedBadge(item.decision);
    },
    evidence: function (item) {
      return facts([
        ["Promise delivery", item.promise_delivery],
        ["Payoff", item.payoff],
        ["Voice", item.voice_identity],
        ["Rendering", item.render_prerequisites_configured ? "Voice provider configured" : "Voice provider not configured yet: the free preview may not render"]
      ]) +
        section("Beats and delivery", beatsTable(item.beats, item.directions) || '<p class="muted">No beats on this spec.</p>') +
        section("Accepting confirms", criteriaList(item));
    },
    decisions: function () {
      return ACCEPT_REWORK_REJECT("A free narration preview renders automatically.", "Re-direct the performance with your notes.");
    },
    decide: function (item, decision, note) {
      const messages = { ACCEPT: "Voice performance accepted.", REWORK: "Voice performance sent for rework.", REJECT: "Voice performance rejected." };
      return post("/api/performance-gate", { concept_id: item.concept_id, format: item.format, decision: decision, criteria: {}, note: note }, messages[decision] || "Saved.");
    }
  };

  // ----------------------------------------------------- Narration preview
  const preview = {
    label: "Preview",
    kicker: "NARRATION PREVIEW",
    snapshot: function () { return status().narration_preview_gate || {}; },
    all: function () { return this.snapshot().items || []; },
    key: function (item) { return item.concept_id + "::" + item.format; },
    title: function (item) { return item.concept_id + " · " + words(item.format); },
    meta: function (item) {
      return '<span class="source-chip">free prototype</span>' +
        '<span class="rw-meta-text">' + (item.audio_ready ? "audio ready" : "audio not rendered yet") + "</span>" + decidedBadge(item.decision);
    },
    extraSignature: function (item) { return String(item.audio_sha256 || ""); },
    evidence: function (item) {
      const src = "/api/narration-preview-audio?concept_id=" + encodeURIComponent(item.concept_id) + "&format=" + encodeURIComponent(item.format);
      return section("Listen", item.audio_ready
        ? '<audio class="rw-audio" controls preload="none" src="' + esc(src) + '">Your browser cannot play this preview.</audio>' +
          '<p class="muted">Free local preview of the approved performance. Approving unlocks the paid narration quote; nothing is spent yet.</p>'
        : '<p class="muted">The preview has not rendered yet. It must exist before it can be approved.</p>') +
        section("Fine-tune one segment", '<p class="muted">Revising a single segment and re-rendering stays in the classic panel. ' +
          '<a href="/analysis" class="button-link ghost compact" data-route="/analysis">Open classic view</a></p>');
    },
    decisions: function (item) {
      return [
        { value: "APPROVE_FINAL", label: "Approve → get paid quote", hint: "Sound brief and narration cost preparation start automatically.", tone: "complete",
          validate: function () { return item.audio_ready ? "" : "Listen first: the preview audio has not rendered yet."; } },
        { value: "REWORK_PERFORMANCE", label: "Rework performance", hint: "Delivery, pacing or emphasis is wrong.", tone: "running", needsNote: true, notePlaceholder: "say what to change in the delivery" },
        { value: "REWORK_SCRIPT", label: "Rework script", hint: "The words themselves need changing.", tone: "running", needsNote: true, notePlaceholder: "say what to change in the script" },
        { value: "REWORK_MUSIC_SFX", label: "Rework music / SFX", hint: "Sound design needs changing.", tone: "running", needsNote: true, notePlaceholder: "say what to change in music or sound effects" }
      ];
    },
    decide: function (item, decision, note) {
      return post("/api/narration-preview-gate", { concept_id: item.concept_id, format: item.format, decision: decision, note: note },
        decision === "APPROVE_FINAL" ? "Free prototype approved. Narration quote preparation is unlocked." : "Prototype sent back for " + words(decision).replace("rework ", "") + " rework.");
    }
  };

  const CONFIGS = { analysis: analysis, concept: concept, research: research, script: script, format: format, voice: voice, preview: preview };

  function isPending(gate, item) {
    const config = CONFIGS[gate];
    if (config.isPending) return config.isPending(item);
    return String((item || {}).decision || "PENDING").toUpperCase() === "PENDING";
  }

  function items(gate) {
    const all = CONFIGS[gate].all().filter(Boolean);
    return showDecided ? all : all.filter(function (item) { return isPending(gate, item); });
  }

  function pendingCount(gate) {
    return CONFIGS[gate].all().filter(function (item) { return item && isPending(gate, item); }).length;
  }

  function emptyHtml(gate) {
    const config = CONFIGS[gate];
    if (gate === "script" && Object.keys(sectionLoading).some(function (key) { return sectionLoading[key]; })) {
      return '<p class="muted">Loading the script sections…</p>';
    }
    const snap = config.snapshot();
    const total = config.all().length;
    const state = snap.status ? words(snap.status) : "not started";
    if (total && !showDecided) {
      return "<h2>Every " + esc(config.label.toLowerCase()) + " item is decided</h2>" +
        '<p class="muted">Gate status: ' + esc(state) + '. Switch to "All items" to revisit a decision.</p>';
    }
    return "<h2>Nothing to review at the " + esc(config.label) + " Gate</h2>" +
      '<p class="muted">Gate status: ' + esc(state) + ". Items appear here when the pipeline reaches this gate.</p>" +
      '<div class="rw-empty-actions"><a href="/" class="button-link ghost compact" data-route="/">Command Center</a></div>';
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
        if (config.initialValue) return config.initialValue(item);
        const decision = String(item.decision || "PENDING").toUpperCase();
        return decision === "PENDING" ? "" : decision;
      },
      initialNote: function (item) { return item.note || ""; },
      decide: function (item, decision, note, extras) { return config.decide(item, decision, note, extras || {}); },
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
    // Same underline tab bar and switcher row as Packaging and Produce (UI-17).
    const html = '<div class="pw-tabs pk-tabs" role="tablist" aria-label="Gate">' + GATES.map(function (gate) {
      const on = gate === activeGate;
      const count = pendingCount(gate);
      return '<button type="button" role="tab" class="pw-tab' + (on ? " active" : "") + '" aria-selected="' + on +
        '" data-gate-tab="' + gate + '">' + esc(CONFIGS[gate].label) + ' <span class="tab-count">' + count + "</span></button>";
    }).join("") + "</div>" +
      '<div class="gate-switcher"><label class="gate-toggle"><input type="checkbox" data-gate-show-decided' + (showDecided ? " checked" : "") +
      "> Include decided items</label>" +
      '<a href="/analysis" class="button-link ghost compact" data-route="/analysis" title="The original panels, with every option">Classic view</a></div>';
    if (html === switcherHtml && bar.innerHTML) return;
    switcherHtml = html;
    bar.innerHTML = html;
  }

  // Section snapshots are fetched separately; drop them whenever the Script
  // Gate itself changes (a decision here, in the classic panel, or a redraft).
  let scriptsSignature = "";

  function syncScripts() {
    const signature = JSON.stringify(scripts().map(function (b) {
      return [b.concept_id, b.format, b.decision, (b.request_provenance || {}).script_draft_sha256];
    }));
    if (signature !== scriptsSignature) {
      scriptsSignature = signature;
      Object.keys(sectionSnapshots).forEach(function (key) { delete sectionSnapshots[key]; });
    }
  }

  function render() {
    syncScripts();
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
    const act = event.target.closest("[data-script-act]");
    if (act) {
      const parts = act.dataset.branch.split("::");
      act.disabled = true;
      if (act.dataset.scriptAct === "GENERATE_ALTERNATIVES") act.textContent = "Generating…";
      sectionAction(parts[0], parts.slice(1).join("::"), act.dataset.scriptAct, act.dataset.target, {
        selection_id: act.dataset.selection || null
      });
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
