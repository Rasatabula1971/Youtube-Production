/* Packaging workspace (UI-12, D-120).
   /packaging#<tab>: Title Direction | Brief & angles | Thumbnail concepts |
   Pairing | Final package. The two human gates (Title Direction, Final
   package) run on the shared review workspace and post exactly what the
   classic panels post; the other tabs show what the automatic steps made.
   Rendered-thumbnail approval stays in the classic Thumbnail panel. */
(function () {
  "use strict";

  // Grouped by who decides (D-159): the final package is the operator's
  // decision; title direction is decided by the gate policy when its checks
  // pass and shown only while it holds something; the rest is reference.
  const TABS = [
    ["final", "Final package", "yours"],
    ["titles", "Title Direction", "policy"],
    ["angles", "Brief & angles", "reference"],
    ["thumbnails", "Thumbnail concepts", "reference"],
    ["pairing", "Pairing", "reference"]
  ];
  const GROUP_ORDER = ["yours", "policy", "reference"];
  const GROUP_LABELS = { yours: "Your decision", policy: "Held by gate policy", reference: "What the automatic steps made" };
  const FORMATS = [["short", "Short"], ["long_form", "Long-form"]];
  const CRITERIA_LABELS = {
    title_and_thumbnail_read_as_one_unit: "Title and thumbnail add different information and read as one idea.",
    single_clear_promise: "The package makes one clear promise, not two.",
    opening_hook_confirms_the_click: "The approved opening confirms why the viewer clicked, early.",
    script_delivers_the_promise: "The approved script pays the promise off.",
    claims_within_approved_evidence: "Every claim in the title and thumbnail is backed by accepted research.",
    approved_image_is_the_thumbnail: "The approved rendered image is the thumbnail you want to publish."
  };
  const REWORK_LABELS = {
    TITLE_DIRECTIONS: "Title directions",
    THUMBNAIL_CONCEPTS: "Thumbnail concepts",
    SCRIPT: "Script branch"
  };

  let activeTab = "final";
  const pendingFocus = Object.create(null);
  const workspaces = Object.create(null);
  // Selections made in the evidence panels, kept per item so repaints keep them.
  // Maps keyed by ids from generated content have no prototype, so an id
  // such as "__proto__" cannot reach Object.prototype (UI-19).
  const titleChoices = Object.create(null);   // concept_id -> { short: {title_id, title_text}, long_form: {...} }
  const packageChoice = Object.create(null);  // video_id -> package_id
  const criteriaTicks = Object.create(null);  // video_id -> { criterion: bool }
  let painted = {};

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

  function badge(value) {
    const v = String(value || "").toUpperCase();
    const tone = v === "PASS" || v === "ACCEPT" || v === "ALIGNED" || v === "CONSISTENT" ? "complete"
      : v === "REWORK" || v === "WEAK" ? "human"
      : v === "REJECT" || v === "MISALIGNED" || v === "INCONSISTENT" ? "blocked" : "ready";
    return '<span class="status-badge status-' + tone + '">' + esc(words(v) || "unknown") + "</span>";
  }

  // Resolves true on success and false when the server refused, so callers
  // keep the reviewer's choices after a failure (UI-19).
  async function post(url, body, okMessage) {
    try {
      await yp().api(url, { method: "POST", body: JSON.stringify(body) });
      yp().showToast(okMessage, false);
      await yp().refresh();
      return true;
    } catch (error) {
      yp().showToast(error.message, true);
      return false;
    }
  }

  // ------------------------------------------------------ Title Direction
  function titleGate() { return status().title_direction_gate || {}; }

  function titleItems() {
    return (titleGate().concepts || []).filter(Boolean);
  }

  function choicesFor(item) {
    if (!titleChoices[item.concept_id]) {
      const chosen = {};
      FORMATS.forEach(function (f) {
        const saved = (item.selected_titles || {})[f[0]];
        if (saved && saved.selected_title_id) {
          chosen[f[0]] = { title_id: saved.selected_title_id, title_text: saved.selected_title_text || "" };
        }
      });
      titleChoices[item.concept_id] = chosen;
    }
    return titleChoices[item.concept_id];
  }

  function titleEvidence(item) {
    const chosen = choicesFor(item);
    const locked = String(item.decision || "PENDING").toUpperCase() !== "PENDING";
    return FORMATS.map(function (f) {
      const candidates = ((item.titles || {})[f[0]] || []).filter(Boolean);
      const rows = candidates.map(function (c) {
        const on = chosen[f[0]] && chosen[f[0]].title_id === c.title_id;
        const value = on && chosen[f[0]].title_text ? chosen[f[0]].title_text : c.title_text;
        return '<li class="pk-title' + (on ? " chosen" : "") + '">' +
          '<label class="pk-title-pick"><input type="radio" name="pk-title-' + esc(item.concept_id) + "-" + f[0] +
            '" data-pk-title="' + esc(f[0]) + '" data-concept="' + esc(item.concept_id) + '" value="' + esc(c.title_id) + '"' +
            (on ? " checked" : "") + (locked ? " disabled" : "") + "> " +
            '<span class="pk-title-angle">' + esc(words(c.psychological_angle)) + "</span></label>" +
          '<input type="text" class="pk-title-text" maxlength="120" aria-label="Title wording" data-pk-title-text="' + esc(f[0]) +
            '" data-concept="' + esc(item.concept_id) + '" data-title-id="' + esc(c.title_id) + '" value="' + esc(value) + '"' +
            (locked ? " disabled" : "") + ">" +
          '<p class="muted">' + esc([c.primary_driver, c.secondary_driver].filter(Boolean).join(" + ")) +
            " · " + esc(words(c.search_intent)) + " · " + esc(String((value || "").length)) + " characters</p>" +
          (c.core_claim ? '<p class="muted">Claim: ' + esc(c.core_claim) + "</p>" : "") +
        "</li>";
      }).join("");
      return section(f[1] + " title", rows ? '<ul class="pk-titles">' + rows + "</ul>" : '<p class="muted">No candidates for this format.</p>');
    }).join("") +
      (locked ? '<p class="muted">This selection is final. Choose Rework to change it.</p>' : '<p class="muted">Pick one title per format; you can edit the wording before accepting.</p>');
  }

  const titleConfig = {
    kicker: "TITLE DIRECTION",
    items: function () { return titleItems(); },
    pending: function (item) { return String(item.decision || "PENDING").toUpperCase() === "PENDING"; },
    key: function (item) { return item.concept_id; },
    signature: function (item) { return item.concept_id + ":" + item.decision + ":" + JSON.stringify(item.selected_titles || {}); },
    title: function (item) { return item.working_title || item.concept_id; },
    meta: function (item) {
      const decided = String(item.decision || "PENDING").toUpperCase();
      return '<span class="source-chip">titles</span><span class="rw-meta-text">' + esc(item.concept_id) + "</span>" +
        (decided !== "PENDING" ? badge(decided) : "");
    },
    evidence: titleEvidence,
    decisions: function (item) {
      if (String(item.decision || "PENDING").toUpperCase() !== "PENDING") {
        return [{ value: "REWORK", label: "Rework", hint: "Regenerate title directions; the current selection is withdrawn.", tone: "running", needsNote: true, notePlaceholder: "say what the titles should do differently" }];
      }
      return [
        {
          value: "ACCEPT", label: "Accept these titles", hint: "Packaging brief, angles and thumbnails follow automatically.", tone: "complete",
          validate: function () {
            const chosen = choicesFor(item);
            for (let i = 0; i < FORMATS.length; i += 1) {
              const pick = chosen[FORMATS[i][0]];
              if (!pick || !pick.title_id) return "Choose one " + FORMATS[i][1] + " title.";
              if (!String(pick.title_text || "").trim()) return "The " + FORMATS[i][1] + " title wording cannot be blank.";
            }
            return "";
          }
        },
        { value: "REWORK", label: "Rework", hint: "Regenerate title directions with your direction.", tone: "running", needsNote: true, notePlaceholder: "say what the titles should do differently" },
        { value: "REJECT", label: "Reject", hint: "None of these work for this concept.", tone: "blocked" }
      ];
    },
    decide: function (item, decision, note) {
      let selected = null;
      if (decision === "ACCEPT") {
        selected = {};
        const chosen = choicesFor(item);
        FORMATS.forEach(function (f) {
          selected[f[0]] = { title_id: chosen[f[0]].title_id, title_text: String(chosen[f[0]].title_text || "").trim() };
        });
      }
      const messages = { ACCEPT: "Title directions accepted.", REWORK: "Title directions sent for regeneration.", REJECT: "Title directions rejected." };
      return post("/api/title-direction-gate", {
        concept_id: item.concept_id,
        decision: decision,
        selected_titles: selected,
        note: note
      }, messages[decision] || "Saved.").then(function (ok) { if (ok) delete titleChoices[item.concept_id]; return ok; });
    }
  };

  // ------------------------------------------------------- Final package
  function finalGate() { return status().final_packaging_gate || {}; }

  function ticksFor(item) {
    if (!criteriaTicks[item.video_id]) {
      const saved = item.criteria || {};
      const ticks = {};
      (finalGate().required_criteria || []).forEach(function (key) { ticks[key] = saved[key] === true; });
      criteriaTicks[item.video_id] = ticks;
    }
    return criteriaTicks[item.video_id];
  }

  function chosenPackage(item) {
    if (packageChoice[item.video_id] === undefined) {
      packageChoice[item.video_id] = item.selected_package_id || "";
    }
    return packageChoice[item.video_id];
  }

  function packageCard(item, p) {
    const chosen = chosenPackage(item) === p.package_id;
    const d = p.diagnostics || {};
    const image = p.image_url
      ? '<img class="pk-thumb" src="' + esc(p.image_url) + '" alt="Rendered thumbnail for ' + esc(p.title_text || p.package_id) + '" loading="lazy">'
      : '<div class="pk-thumb pk-thumb-missing"><span>' + esc(p.thumbnail_text || p.thumbnail_hero_subject || "Thumbnail") + "</span>" +
        '<small>' + (p.image_approved ? "Approved image (no preview)" : p.render_id ? "Image not approved yet" : "Not rendered yet") + "</small></div>";
    const blocked = (p.blocked_reasons || []).filter(Boolean);
    return '<article class="pk-package' + (chosen ? " chosen" : "") + (p.acceptable ? "" : " unavailable") + '">' +
      image +
      '<div class="pk-package-body">' +
        '<p class="attention-kicker">' + esc(p.package_id) + " · " + esc(words(p.angle_primary_driver)) + "</p>" +
        '<h4 class="pk-package-title">' + esc(p.title_text || "") + "</h4>" +
        '<p class="muted">Thumbnail text: ' + esc(p.thumbnail_text || "—") + "</p>" +
        '<p class="muted">' + esc([p.thumbnail_hero_subject, p.thumbnail_visual_anomaly].filter(Boolean).join(" · ")) + "</p>" +
        '<dl class="pk-checks">' +
          "<div><dt>Validation</dt><dd>" + badge(p.validation_status) + "</dd></div>" +
          "<div><dt>Promise</dt><dd>" + badge(p.promise_consistency || d.promise_consistency) + "</dd></div>" +
          "<div><dt>Hook</dt><dd>" + badge(p.hook_alignment_status || d.hook_alignment_status) + "</dd></div>" +
          ((p.semantic_redundancy || d.semantic_redundancy) ? "<div><dt>Redundancy</dt><dd>" + badge(p.semantic_redundancy || d.semantic_redundancy) + "</dd></div>" : "") +
          "<div><dt>Matches chosen title</dt><dd>" + badge(p.selected_title_direction_match ? "PASS" : "NOT_SELECTED") + "</dd></div>" +
        "</dl>" +
        (blocked.length ? '<p class="pk-blocked">' + esc(blocked.join("; ")) + "</p>" : "") +
        (p.acceptable
          ? '<label class="pk-choose"><input type="radio" name="pk-package-' + esc(item.video_id) + '" data-pk-package="' + esc(p.package_id) +
            '" data-video="' + esc(item.video_id) + '"' + (chosen ? " checked" : "") + "> Choose this package</label>"
          : "") +
      "</div>" +
    "</article>";
  }

  // The 2–3 title shortlist ranked from the pair validations (D-134).
  function shortlistHtml(item) {
    const shortlist = item.title_shortlist || {};
    const rows = (shortlist.entries || []).filter(Boolean).map(function (entry) {
      return '<li><span class="source-chip">' + esc(entry.rank) + "</span> <strong>" + esc(entry.title_text || entry.title_id) + "</strong>" +
        '<br><span class="muted">' + esc(entry.reason || "") + "</span></li>";
    }).join("");
    return section("Title shortlist", (rows ? '<ul class="rw-list pk-shortlist">' + rows + "</ul>" : "") +
      (shortlist.note ? '<p class="' + (shortlist.shortfall ? "radar-error" : "muted") + '">' + esc(shortlist.note) + "</p>" : ""));
  }

  function chosenOutsideShortlist(item) {
    const id = chosenPackage(item);
    const chosen = (item.packages || []).find(function (p) { return p && p.package_id === id; });
    return Boolean(chosen && chosen.in_title_shortlist === false);
  }

  function finalEvidence(item) {
    const packages = (item.packages || []).filter(Boolean);
    const acceptable = packages.filter(function (p) { return p.acceptable && p.in_title_shortlist !== false; });
    const outside = packages.filter(function (p) { return p.acceptable && p.in_title_shortlist === false; });
    const others = packages.filter(function (p) { return !p.acceptable; });
    const ticks = ticksFor(item);
    const missingImage = packages.some(function (p) { return p.render_id && !p.image_approved; });
    const criteria = (finalGate().required_criteria || []).map(function (key) {
      return '<li><label><input type="checkbox" data-pk-criterion="' + esc(key) + '" data-video="' + esc(item.video_id) + '"' +
        (ticks[key] ? " checked" : "") + "> " + esc(CRITERIA_LABELS[key] || words(key)) + "</label></li>";
    }).join("");
    return facts([
      ["Viewer promise", item.viewer_promise],
      ["Opening hook", item.opening_hook],
      ["Matrix", (item.pass || 0) + " pass · " + (item.rework || 0) + " rework · " + (item.reject || 0) + " reject"]
    ]) +
      (item.stale_decision ? '<p class="radar-error">The package matrix changed after your decision; decide again.</p>' : "") +
      (item.last_rework ? '<p class="muted">Last rework: ' + esc(words(item.last_rework.rework_target)) + " — " + esc(item.last_rework.note || "") + "</p>" : "") +
      shortlistHtml(item) +
      section("Finalists", acceptable.length
        ? '<div class="pk-packages">' + acceptable.map(function (p) { return packageCard(item, p); }).join("") + "</div>"
        : '<p class="muted">No package can be accepted yet' + (missingImage ? ": approve the rendered thumbnail images first." : ".") + "</p>") +
      (missingImage
        ? '<p class="muted">Rendered thumbnails are approved in the classic Thumbnail panel. ' +
          '<a href="/analysis" class="button-link ghost compact" data-route="/analysis">Open classic view</a></p>'
        : "") +
      (outside.length
        ? '<details class="pk-others"><summary>' + outside.length + " acceptable package(s) with titles outside the shortlist</summary>" +
          '<p class="muted">Choosing one of these needs a note saying why.</p>' +
          '<div class="pk-packages">' + outside.map(function (p) { return packageCard(item, p); }).join("") + "</div></details>"
        : "") +
      (others.length
        ? '<details class="pk-others"><summary>' + others.length + " other package(s) not acceptable</summary>" +
          '<div class="pk-packages">' + others.map(function (p) { return packageCard(item, p); }).join("") + "</div></details>"
        : "") +
      section("Accepting confirms", criteria ? '<ul class="pk-criteria">' + criteria + "</ul>" : "");
  }

  const finalConfig = {
    kicker: "FINAL PACKAGE",
    items: function () { return (finalGate().items || []).filter(Boolean); },
    pending: function (item) { return String(item.decision || "PENDING").toUpperCase() === "PENDING" || item.stale_decision; },
    key: function (item) { return item.video_id; },
    signature: function (item) {
      return item.video_id + ":" + item.decision + ":" + item.matrix_fingerprint + ":" +
        (item.packages || []).map(function (p) { return p.package_id + (p.image_approved ? "+" : "-"); }).join(",");
    },
    title: function (item) { return (item.concept_id || item.video_id) + " · " + words(item.format); },
    meta: function (item) {
      const decided = String(item.decision || "PENDING").toUpperCase();
      return '<span class="source-chip">' + esc(words(item.format)) + '</span><span class="rw-meta-text">' + esc(item.video_id) + "</span>" +
        (decided !== "PENDING" ? badge(decided) : "");
    },
    evidence: finalEvidence,
    decisions: function (item) {
      const targets = (finalGate().rework_targets || Object.keys(REWORK_LABELS)).map(function (t) { return [t, REWORK_LABELS[t] || words(t)]; });
      return [
        {
          value: "ACCEPT", label: "Accept this package", hint: "Locks title, thumbnail, hook and promise as one unit; format planning follows.", tone: "complete",
          validate: function (_item, draft) {
            if (!chosenPackage(item)) return "Choose one of the finalist packages.";
            const ticks = ticksFor(item);
            const missing = (finalGate().required_criteria || []).filter(function (key) { return !ticks[key]; });
            if (missing.length) return "Confirm every check under “Accepting confirms”.";
            if (chosenOutsideShortlist(item) && !String((draft || {}).note || "").trim()) {
              return "This title is outside the shortlist: add a note saying why you chose it.";
            }
            return "";
          }
        },
        {
          value: "REWORK", label: "Rework", hint: "Send it back to one upstream step; its packaging work is regenerated.", tone: "running",
          select: { label: "What to rework", options: [["", "Choose what to rework"]].concat(targets) },
          needsNote: true, noteLabel: "Instruction", notePlaceholder: "say what must change",
          validate: function (_item, draft) { return draft.select ? "" : "Choose what to rework first."; },
          confirm: function (_item, draft) {
            return "Send rework to the " + (REWORK_LABELS[draft.select] || words(draft.select)).toLowerCase() +
              "? Downstream packaging work for this concept will be regenerated.";
          }
        },
        { value: "REJECT", label: "Reject this format", hint: "This format will not be produced.", tone: "blocked" }
      ];
    },
    decide: function (item, decision, note, extras) {
      const messages = {
        ACCEPT: "Package accepted.",
        REWORK: "Rework sent to the " + (REWORK_LABELS[extras.select] || "").toLowerCase() + ".",
        REJECT: "Format rejected."
      };
      return post("/api/final-packaging-gate", {
        video_id: item.video_id,
        decision: decision,
        package_id: decision === "ACCEPT" ? chosenPackage(item) : null,
        criteria: Object.assign({}, ticksFor(item)),
        note: note,
        rework_target: decision === "REWORK" ? extras.select : null
      }, messages[decision] || "Saved.").then(function (ok) {
        if (ok) {
          delete packageChoice[item.video_id];
          delete criteriaTicks[item.video_id];
        }
        return ok;
      });
    }
  };

  // --------------------------------------------------------- Read-only tabs
  function byVideo(rows) {
    const groups = Object.create(null);
    (rows || []).forEach(function (row) {
      if (!row) return;
      const key = row.video_id || row.concept_id || "unknown";
      (groups[key] = groups[key] || []).push(row);
    });
    return groups;
  }

  function anglesHtml() {
    const brief = status().packaging_brief || {};
    const angles = status().psychological_angles || {};
    const briefs = (brief.briefs || []).map(function (b) {
      return '<article class="pk-card"><p class="attention-kicker">' + esc(words(b.format)) + " · brief</p>" +
        facts([["Viewer expectation", b.viewer_expectation], ["Search or browse", b.search_vs_browse_intent], ["Video", b.video_id]]) + "</article>";
    }).join("");
    const sets = (angles.items || []).map(function (set) {
      const cards = (set.angles || []).map(function (a) {
        const extra = Object.keys(a).filter(function (k) {
          return ["angle_id", "primary_driver", "secondary_driver", "evidence_refs", "selected_title_direction_alignment"].indexOf(k) === -1 && typeof a[k] !== "object";
        }).map(function (k) { return [words(k).replace(/^./, function (c) { return c.toUpperCase(); }), a[k]]; });
        return '<article class="pk-card"><p class="attention-kicker">' + esc(a.angle_id) + "</p>" +
          "<h4>" + esc(words(a.primary_driver)) + (a.secondary_driver ? " + " + esc(words(a.secondary_driver)) : "") + "</h4>" +
          facts(extra) + "</article>";
      }).join("");
      return section(words(set.format) + " · " + (set.angle_count || 0) + " angles", '<div class="pk-grid">' + cards + "</div>");
    }).join("");
    return section("Packaging brief", briefs ? '<div class="pk-grid">' + briefs + "</div>" : '<p class="muted">Status: ' + esc(words(brief.status)) + "</p>") +
      (sets || section("Psychological angles", '<p class="muted">Status: ' + esc(words(angles.status)) + "</p>"));
  }

  function thumbnailsHtml() {
    const concepts = status().thumbnail_concepts || {};
    const sets = (concepts.items || []).map(function (set) {
      const cards = (set.thumbnail_concepts || []).map(function (t) {
        return '<article class="pk-card"><p class="attention-kicker">' + esc(t.thumbnail_id) + " · " + esc(t.angle_id || "") + "</p>" +
          "<h4>" + esc(t.text || t.hero_subject || "") + "</h4>" +
          facts([
            ["Hero subject", t.hero_subject],
            ["Secondary element", t.secondary_element],
            ["Visual anomaly", t.visual_anomaly],
            ["Viewer question", t.viewer_visual_question],
            ["Visual action", t.visual_action],
            ["Face", t.face_present ? "yes" : "no"]
          ]) + "</article>";
      }).join("");
      return section(words(set.format) + " · " + (set.concept_count || (set.thumbnail_concepts || []).length) + " concepts", '<div class="pk-grid">' + cards + "</div>");
    }).join("");
    return sets || section("Thumbnail concepts", '<p class="muted">Status: ' + esc(words(concepts.status)) + "</p>");
  }

  function pairingHtml() {
    const validation = status().package_validation || {};
    const groups = byVideo(validation.packages);
    const tables = Object.keys(groups).map(function (video) {
      const rows = groups[video].map(function (p) {
        return "<tr><th scope=\"row\">" + esc(p.title_text || p.title_id) + "</th><td>" + esc(p.thumbnail_text || p.thumbnail_id) + "</td><td>" +
          badge(p.validation_status) + "</td><td>" + badge(p.promise_consistency) + "</td><td>" + badge(p.hook_alignment_status) + "</td></tr>";
      }).join("");
      return section(video, '<div class="pk-table-wrap"><table class="pw-rows"><thead><tr><th scope="col">Title</th><th scope="col">Thumbnail text</th>' +
        '<th scope="col">Validation</th><th scope="col">Promise</th><th scope="col">Hook</th></tr></thead><tbody>' + rows + "</tbody></table></div>");
    }).join("");
    return facts([
      ["Status", words(validation.status)],
      ["Pairs", (validation.current_pairs || 0) + " of " + (validation.expected_pairs || 0)],
      ["Results", (validation.pass || 0) + " pass · " + (validation.rework || 0) + " rework · " + (validation.reject || 0) + " reject"]
    ]) + (tables || '<p class="muted">The pairing matrix appears once title and thumbnail concepts are ready.</p>');
  }

  // ------------------------------------------------------------ Page shell
  const REVIEW_TABS = { titles: titleConfig, final: finalConfig };

  function pendingCount(tab) {
    const config = REVIEW_TABS[tab];
    return config ? config.items().filter(config.pending).length : 0;
  }

  function ensureWorkspace(tab) {
    if (workspaces[tab]) return workspaces[tab];
    const root = document.getElementById("packaging-" + tab);
    const config = REVIEW_TABS[tab];
    if (!root || !config || !window.ReviewWorkspace || !yp()) return null;
    workspaces[tab] = window.ReviewWorkspace.create({
      root: root,
      kicker: config.kicker,
      items: function () { return config.items().filter(config.pending); },
      key: config.key,
      signature: config.signature,
      title: config.title,
      meta: config.meta,
      renderEvidence: config.evidence,
      decisions: config.decisions,
      initialNote: function (item) { return item.note || ""; },
      decide: function (item, decision, note, extras) { return config.decide(item, decision, note, extras || {}); },
      onNavigate: function (key) {
        if (window.location.pathname === "/packaging") {
          history.replaceState({}, "", "/packaging#" + tab + "/" + encodeURIComponent(key));
        }
      },
      emptyHtml: function () {
        const gate = tab === "titles" ? titleGate() : finalGate();
        return "<h2>Nothing waiting at " + esc(tab === "titles" ? "Title Direction" : "the Final Package gate") + "</h2>" +
          '<p class="muted">Status: ' + esc(words(gate.status) || "not started") + ". Decisions appear here when packaging reaches this step.</p>" +
          '<div class="rw-empty-actions"><a href="/analysis" class="button-link ghost compact" data-route="/analysis">Classic view</a></div>';
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

  function tabButton(tab) {
    const on = tab[0] === activeTab;
    const count = pendingCount(tab[0]);
    return '<button type="button" role="tab" class="pw-tab' + (on ? " active" : "") + '" aria-selected="' + on +
      '" data-pk-tab="' + tab[0] + '">' + esc(tab[1]) + (REVIEW_TABS[tab[0]] ? ' <span class="tab-count">' + count + "</span>" : "") + "</button>";
  }

  function renderTabs() {
    const bar = document.getElementById("packagingTabs");
    if (!bar) return;
    const html = GROUP_ORDER.map(function (group) {
      const tabs = TABS.filter(function (tab) {
        return tab[2] === group && (group !== "policy" || tab[0] === activeTab || pendingCount(tab[0]) > 0);
      });
      if (!tabs.length) return "";
      return '<div class="pw-tab-group" role="group" aria-label="' + esc(GROUP_LABELS[group]) + '">' +
        '<span class="pw-tab-group-label" aria-hidden="true">' + esc(GROUP_LABELS[group]) + "</span>" + tabs.map(tabButton).join("") + "</div>";
    }).join("");
    if (painted.tabs === html) return;
    painted.tabs = html;
    bar.innerHTML = html;
    revealActiveTab(bar);
  }

  function render() {
    renderTabs();
    TABS.forEach(function (tab) {
      const root = document.getElementById("packaging-" + tab[0]);
      if (root) root.hidden = tab[0] !== activeTab;
    });
    if (REVIEW_TABS[activeTab]) {
      const workspace = ensureWorkspace(activeTab);
      if (!workspace) return;
      if (pendingFocus[activeTab]) {
        const key = pendingFocus[activeTab];
        delete pendingFocus[activeTab];
        workspace.focus(key);
      } else {
        workspace.render();
      }
      return;
    }
    const root = document.getElementById("packaging-" + activeTab);
    if (!root) return;
    const html = activeTab === "angles" ? anglesHtml() : activeTab === "thumbnails" ? thumbnailsHtml() : pairingHtml();
    if (painted[activeTab] === html) return;
    painted[activeTab] = html;
    root.innerHTML = '<div class="pk-readonly">' + html + "</div>";
  }

  function open(subroute) {
    const raw = String(subroute || "");
    const slash = raw.indexOf("/");
    const tab = slash === -1 ? raw : raw.slice(0, slash);
    if (TABS.some(function (t) { return t[0] === tab; })) {
      activeTab = tab;
      if (slash !== -1) pendingFocus[tab] = window.YPUtil.decode(raw.slice(slash + 1));
    }
    render();
  }

  document.addEventListener("click", function (event) {
    const tab = event.target.closest && event.target.closest("[data-pk-tab]");
    if (!tab) return;
    activeTab = tab.dataset.pkTab;
    history.replaceState({}, "", "/packaging#" + activeTab);
    render();
  });

  // Selections live in module state so repaints and polls keep them.
  document.addEventListener("change", function (event) {
    const target = event.target;
    if (!target.closest || !target.closest("#viewPackaging")) return;
    if (target.dataset.pkTitle) {
      const chosen = titleChoices[target.dataset.concept] = titleChoices[target.dataset.concept] || {};
      const input = target.closest(".pk-title").querySelector("[data-pk-title-text]");
      chosen[target.dataset.pkTitle] = { title_id: target.value, title_text: input ? input.value : "" };
      target.closest(".pk-titles").querySelectorAll(".pk-title").forEach(function (li) {
        li.classList.toggle("chosen", li.contains(target));
      });
    } else if (target.dataset.pkPackage) {
      packageChoice[target.dataset.video] = target.dataset.pkPackage;
      target.closest(".pk-packages").querySelectorAll(".pk-package").forEach(function (card) {
        card.classList.toggle("chosen", card.contains(target));
      });
    } else if (target.dataset.pkCriterion) {
      const ticks = criteriaTicks[target.dataset.video] = criteriaTicks[target.dataset.video] || {};
      ticks[target.dataset.pkCriterion] = target.checked;
    }
  });

  document.addEventListener("input", function (event) {
    const target = event.target;
    if (!target.dataset || !target.dataset.pkTitleText) return;
    const chosen = titleChoices[target.dataset.concept] = titleChoices[target.dataset.concept] || {};
    const format = target.dataset.pkTitleText;
    // Editing a title's wording also selects that title.
    chosen[format] = { title_id: target.dataset.titleId, title_text: target.value };
    const li = target.closest(".pk-title");
    const radio = li && li.querySelector("[data-pk-title]");
    if (radio && !radio.checked) {
      radio.checked = true;
      li.parentElement.querySelectorAll(".pk-title").forEach(function (row) { row.classList.toggle("chosen", row === li); });
    }
    const counter = li && li.querySelector(".muted");
    if (counter) counter.textContent = counter.textContent.replace(/\d+ characters$/, target.value.length + " characters");
  });

  // Pending packaging decisions for the one Review Queue (D-164).
  function queueItems() {
    const rows = [];
    TABS.forEach(function (tab) {
      const config = REVIEW_TABS[tab[0]];
      if (!config) return;
      config.items().filter(config.pending).forEach(function (item) {
        rows.push({
          route: "/packaging", subroute: tab[0] + "/" + encodeURIComponent(config.key(item)),
          gate: tab[1], group: tab[2], title: String(config.title(item) || ""),
          concept_id: item.concept_id || ""
        });
      });
    });
    return rows;
  }

  window.Packaging = {
    queueItems: queueItems,
    open: open,
    show: function () { if (window.location.pathname === "/packaging") open(window.location.hash.slice(1)); },
    render: function () { if (window.location.pathname === "/packaging") render(); },
    pending: pendingCount
  };
})();
