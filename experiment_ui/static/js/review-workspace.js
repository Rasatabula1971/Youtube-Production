/* Shared human review workspace (UI Patch 2, D-116).
   One item at a time: evidence on the left, the decision on the right.
   Each gate supplies its own items, evidence HTML, decisions and submit
   function; the workspace owns the header, "N of M", previous/next,
   keyboard behaviour, the decision panel and notes. The Opportunity Gate is
   the first user; later gates (UI-09 onward) reuse it unchanged. */
(function () {
  "use strict";

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function isTyping(target) {
    const tag = String((target && target.tagName) || "").toLowerCase();
    // Media players keep their own arrow keys (seek) and space (play).
    return tag === "textarea" || (tag === "input" && target.type !== "radio") || tag === "select" ||
      tag === "audio" || tag === "video";
  }

  function create(options) {
    const root = options.root;
    let currentKey = null;
    let renderedKey = null; // the item whose decision panel is on screen
    const drafts = Object.create(null); // unsaved choice and note per item, kept while moving around
    const typed = Object.create(null);  // items whose note the user typed and has not sent yet (UI-18)
    let currentIndex = 0;
    let lastSignature = "";
    let busy = false;
    let idSeed = 0;
    const uid = "rw" + Math.random().toString(36).slice(2, 8);

    function list() {
      return (options.items() || []).filter(Boolean);
    }

    function locate(items) {
      if (!items.length) return -1;
      const found = items.findIndex(function (item) { return options.key(item) === currentKey; });
      if (found !== -1) return found;
      // The current item left the queue (decided): stay at the same position.
      return Math.min(currentIndex, items.length - 1);
    }

    function readDraft() {
      const checked = root.querySelector('input[name="' + uid + '-decision"]:checked');
      const note = root.querySelector("[data-rw-note]");
      const select = root.querySelector("[data-rw-select]");
      return {
        key: renderedKey,
        value: checked ? checked.value : "",
        note: note ? note.value : "",
        select: select ? select.value : ""
      };
    }

    function decisionPanel(item, draft) {
      const decisions = options.decisions(item) || [];
      if (!decisions.length) {
        const locked = options.locked ? options.locked(item) : "";
        return '<p class="muted rw-locked">' + esc(locked || "No decision is available for this item here.") + "</p>";
      }
      const selected = decisions.find(function (d) { return d.value === draft.value; }) || null;
      const radios = decisions.map(function (decision, index) {
        idSeed += 1;
        const id = uid + "-opt-" + idSeed;
        return '<label class="rw-option' + (decision.tone ? " tone-" + esc(decision.tone) : "") + '" for="' + id + '">' +
          '<input type="radio" id="' + id + '" name="' + uid + '-decision" value="' + esc(decision.value) + '"' +
          (decision.value === draft.value ? " checked" : "") + '>' +
          '<span class="rw-option-copy"><span class="rw-option-label">' +
          (index < 9 ? '<kbd aria-hidden="true">' + (index + 1) + "</kbd>" : "") + esc(decision.label) + "</span>" +
          (decision.hint ? '<span class="rw-option-hint">' + esc(decision.hint) + "</span>" : "") +
          "</span></label>";
      }).join("");
      const noteOff = selected && selected.takesNote === false;
      const noteRequired = Boolean(selected && selected.needsNote);
      // Optional per-decision extras: a choice list (e.g. a rework reason),
      // a different note label/size, and a pre-filled note (e.g. text to edit).
      const select = selected && selected.select;
      const selectHtml = select
        ? '<label class="rw-note-label" for="' + uid + '-select">' + esc(select.label) + "</label>" +
          '<select id="' + uid + '-select" data-rw-select class="rw-select">' +
            select.options.map(function (option) {
              return '<option value="' + esc(option[0]) + '"' + (option[0] === draft.select ? " selected" : "") + ">" + esc(option[1]) + "</option>";
            }).join("") + "</select>"
        : "";
      const noteValue = draft.note || (selected && selected.notePrefill ? String(selected.notePrefill(item) || "") : "");
      return '<fieldset class="rw-decisions"><legend>Decision</legend>' + radios + "</fieldset>" +
        selectHtml +
        '<label class="rw-note-label" for="' + uid + '-note">' + esc((selected && selected.noteLabel) || "Note") +
          (noteRequired ? ' <span class="rw-required">required</span>' : "") + "</label>" +
        '<textarea id="' + uid + '-note" data-rw-note rows="' + ((selected && selected.noteRows) || 4) +
          '" maxlength="' + ((selected && selected.noteMaxLength) || 500) + '"' +
          (noteOff ? " disabled" : "") + ' placeholder="' +
          esc(noteOff ? (options.noteOffHint || "This decision does not record a note.") : (selected && selected.notePlaceholder) || "Why you decided this (optional)") +
          '">' + esc(noteOff ? "" : noteValue) + "</textarea>" +
        '<button type="button" class="primary-cta rw-submit" data-rw-submit' + (busy ? " disabled" : "") + ">" +
          (busy ? "Saving…" : "Save decision") + "</button>" +
        '<p class="rw-status muted" role="status" aria-live="polite" data-rw-status></p>' +
        '<p class="rw-keys muted">Keys: ← → move · 1–' + Math.min(decisions.length, 9) +
          " choose · Ctrl+Enter save</p>";
    }

    function render(force) {
      if (!root) return;
      const items = list();
      const index = locate(items);
      const item = index === -1 ? null : items[index];
      const signature = items.map(function (entry) { return options.signature ? options.signature(entry) : options.key(entry); }).join("|") +
        "#" + (item ? options.key(item) : "");
      if (!force && signature === lastSignature) return;
      lastSignature = signature;

      if (!item) {
        currentKey = null;
        renderedKey = null;
        currentIndex = 0;
        const empty = typeof options.emptyHtml === "function" ? options.emptyHtml() : options.emptyHtml;
        root.innerHTML = '<div class="rw-empty">' + (empty || "<p>Nothing to review.</p>") + "</div>";
        return;
      }
      const onScreen = readDraft();
      if (onScreen.key && (onScreen.value || onScreen.note)) drafts[onScreen.key] = onScreen;
      else if (onScreen.key) delete drafts[onScreen.key];
      const draft = drafts[options.key(item)] || onScreen;
      const keepDraft = draft.key === options.key(item);
      // Revisiting a decided item starts from the decision and note on file.
      const initial = {
        value: options.initialValue ? String(options.initialValue(item) || "") : "",
        note: options.initialNote ? String(options.initialNote(item) || "") : ""
      };
      currentIndex = index;
      currentKey = options.key(item);
      renderedKey = currentKey;
      root.innerHTML =
        '<header class="rw-head">' +
          '<div class="rw-head-copy">' +
            '<p class="section-kicker">' + esc(options.kicker) +
              ' <span class="rw-position">' + (index + 1) + " of " + items.length + "</span></p>" +
            '<h2 class="rw-title" tabindex="-1">' + esc(options.title(item)) + "</h2>" +
            (options.meta ? '<div class="rw-meta">' + options.meta(item) + "</div>" : "") +
          "</div>" +
          '<nav class="rw-nav" aria-label="Review navigation">' +
            '<button type="button" class="ghost compact" data-rw-move="-1"' + (index === 0 ? " disabled" : "") + '>← Previous</button>' +
            '<button type="button" class="ghost compact" data-rw-move="1"' + (index === items.length - 1 ? " disabled" : "") + ">Next →</button>" +
          "</nav>" +
        "</header>" +
        '<div class="rw-body">' +
          '<section class="rw-evidence" aria-label="Evidence">' + options.renderEvidence(item) + "</section>" +
          '<aside class="rw-panel" aria-label="Decision">' +
            decisionPanel(item, keepDraft ? draft : initial) +
          "</aside>" +
        "</div>";
      if (options.onShow) options.onShow(item);
    }

    function move(step) {
      const items = list();
      if (!items.length) return;
      const index = Math.max(0, Math.min(items.length - 1, locate(items) + step));
      currentKey = options.key(items[index]);
      currentIndex = index;
      render(true);
      if (options.onNavigate) options.onNavigate(currentKey);
      const heading = root.querySelector(".rw-title");
      if (heading) heading.focus({ preventScroll: true });
    }

    function setStatus(text) {
      const status = root.querySelector("[data-rw-status]");
      if (status) status.textContent = text;
    }

    async function submit() {
      if (busy) return;
      const items = list();
      const item = items[locate(items)];
      if (!item) return;
      const draft = readDraft();
      const decision = (options.decisions(item) || []).find(function (d) { return d.value === draft.value; });
      if (!decision) {
        setStatus("Choose a decision first.");
        return;
      }
      if (decision.needsNote && !draft.note.trim()) {
        setStatus("Add a note: " + (decision.notePlaceholder || "this decision needs one") + ".");
        const note = root.querySelector("[data-rw-note]");
        if (note) note.focus();
        return;
      }
      const problem = decision.validate ? decision.validate(item, draft) : "";
      if (problem) {
        setStatus(problem);
        return;
      }
      const question = decision.confirm ? decision.confirm(item, draft) : "";
      if (question && !window.confirm(question)) return;
      busy = true;
      render(true);
      try {
        const outcome = await options.decide(
          item,
          decision.value,
          decision.takesNote === false ? "" : draft.note.trim(),
          { select: draft.select }
        );
        // A refused decision (false) keeps the unsaved-note warning.
        if (outcome !== false) delete typed[draft.key];
        const still = list().find(function (entry) { return options.key(entry) === draft.key; });
        const stillOffered = still && (options.decisions(still) || []).some(function (d) { return d.value === draft.value; });
        if (!still || !stillOffered) {
          // The item left the queue, or its choices changed (e.g. a rework is
          // now pending): the old draft no longer applies.
          delete drafts[draft.key];
          root.querySelectorAll('input[name="' + uid + '-decision"]').forEach(function (radio) { radio.checked = false; });
          const note = root.querySelector("[data-rw-note]");
          if (note) note.value = "";
          const select = root.querySelector("[data-rw-select]");
          if (select) select.value = "";
        }
      } finally {
        // A decided item leaves the queue and its draft goes with it; a failed
        // decision keeps the item and the draft so nothing typed is lost.
        busy = false;
        render(true);
      }
    }

    if (root) {
      root.addEventListener("input", function (event) {
        if (event.target.matches && event.target.matches("[data-rw-note]") && renderedKey) {
          if (event.target.value.trim()) typed[renderedKey] = true;
          else delete typed[renderedKey];
        }
      });
      root.addEventListener("click", function (event) {
        const mover = event.target.closest("[data-rw-move]");
        if (mover) {
          move(Number(mover.dataset.rwMove));
          return;
        }
        if (event.target.closest("[data-rw-submit]")) submit();
      });
      root.addEventListener("change", function (event) {
        // Re-render the panel so the note requirement follows the choice.
        if (event.target.name === uid + "-decision") {
          const value = event.target.value;
          // A decision that edits text starts from that text, not from a note
          // typed for a different choice.
          const items = list();
          const item = items[locate(items)];
          const chosen = item && (options.decisions(item) || []).find(function (d) { return d.value === value; });
          const note = root.querySelector("[data-rw-note]");
          const prefilled = note && item && (options.decisions(item) || []).some(function (d) {
            return d.notePrefill && note.value === String(d.notePrefill(item) || "");
          });
          if (note && ((chosen && chosen.notePrefill) || prefilled)) note.value = "";
          render(true);
          const radio = root.querySelector('input[name="' + uid + '-decision"][value="' + CSS.escape(value) + '"]');
          if (radio) radio.focus();
        }
      });
      // Keys work anywhere while this workspace is on screen, except in text
      // fields and while a drawer or dialog has focus.
      document.addEventListener("keydown", function (event) {
        if (root.offsetParent === null) return;
        if (event.target !== document.body && !root.contains(event.target)) return;
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
          event.preventDefault();
          submit();
          return;
        }
        if (isTyping(event.target) || event.altKey || event.ctrlKey || event.metaKey) return;
        if (event.key === "ArrowRight" && event.target.type !== "radio") { event.preventDefault(); move(1); return; }
        if (event.key === "ArrowLeft" && event.target.type !== "radio") { event.preventDefault(); move(-1); return; }
        if (/^[1-9]$/.test(event.key)) {
          const radios = root.querySelectorAll('input[name="' + uid + '-decision"]');
          const radio = radios[Number(event.key) - 1];
          if (radio) {
            event.preventDefault();
            radio.checked = true;
            radio.dispatchEvent(new Event("change", { bubbles: true }));
          }
        }
      });
    }

    registry.push(function () { return Object.keys(typed).length > 0; });

    return {
      render: function () { render(false); },
      refresh: function () { render(true); },
      focus: function (key) {
        if (key) currentKey = key;
        render(true);
      },
      currentKey: function () { return currentKey; }
    };
  }

  // Warn before closing or reloading the tab while a typed review note has
  // not been sent (Web Interface Guidelines: unsaved changes).
  const registry = [];
  function hasUnsavedNotes() {
    return registry.some(function (check) { return check(); });
  }
  window.addEventListener("beforeunload", function (event) {
    if (!hasUnsavedNotes()) return;
    event.preventDefault();
    event.returnValue = "";
  });

  window.ReviewWorkspace = { create: create, hasUnsavedNotes: hasUnsavedNotes };
})();
