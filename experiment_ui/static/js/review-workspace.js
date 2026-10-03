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
    return tag === "textarea" || (tag === "input" && target.type !== "radio") || tag === "select";
  }

  function create(options) {
    const root = options.root;
    let currentKey = null;
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
      return {
        key: currentKey,
        value: checked ? checked.value : "",
        note: note ? note.value : ""
      };
    }

    function decisionPanel(item, draft) {
      const decisions = options.decisions(item) || [];
      if (!decisions.length) {
        return '<p class="muted">No decision is available for this item here.</p>';
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
      return '<fieldset class="rw-decisions"><legend>Decision</legend>' + radios + "</fieldset>" +
        '<label class="rw-note-label" for="' + uid + '-note">Note' +
          (noteRequired ? ' <span class="rw-required">required</span>' : "") + "</label>" +
        '<textarea id="' + uid + '-note" data-rw-note rows="4" maxlength="500"' +
          (noteOff ? " disabled" : "") + ' placeholder="' +
          esc(noteOff ? (options.noteOffHint || "This decision does not record a note.") : (selected && selected.notePlaceholder) || "Why you decided this (optional)") +
          '">' + esc(noteOff ? "" : draft.note) + "</textarea>" +
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
        currentIndex = 0;
        root.innerHTML = '<div class="rw-empty">' + (options.emptyHtml || "<p>Nothing to review.</p>") + "</div>";
        return;
      }
      const draft = readDraft();
      const keepDraft = draft.key === options.key(item);
      currentIndex = index;
      currentKey = options.key(item);
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
            decisionPanel(item, keepDraft ? draft : { value: "", note: "" }) +
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
      busy = true;
      render(true);
      try {
        await options.decide(item, decision.value, decision.takesNote === false ? "" : draft.note.trim());
      } finally {
        // A decided item leaves the queue and its draft goes with it; a failed
        // decision keeps the item and the draft so nothing typed is lost.
        busy = false;
        render(true);
      }
    }

    if (root) {
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

  window.ReviewWorkspace = { create: create };
})();
