/* Human Opportunity Gate on the shared review workspace (UI-06, D-116).
   Reviews the inbox's "Needs review" items one at a time. Decisions go
   through YP.decide, the same dispatcher the inbox cards use. */
(function () {
  "use strict";

  const DECISIONS = {
    APPROVE: {
      label: "Approve",
      hint: "Becomes the study set; analysis continues automatically.",
      tone: "complete",
      takesNote: false
    },
    APPROVE_THEME: {
      label: "Approve theme",
      hint: "Studies one video per independent channel in this theme.",
      tone: "complete",
      takesNote: false
    },
    WATCH: {
      label: "Watch",
      hint: "Keep it on the radar and decide when the trajectory is clearer.",
      tone: "running"
    },
    REWORK: {
      label: "Investigate",
      hint: "Gather fresh evidence for it.",
      tone: "running",
      needsNote: true,
      notePlaceholder: "say what evidence is missing"
    },
    SAVE: {
      label: "Save idea",
      hint: "Park it for later or for a future channel.",
      tone: "human"
    },
    REJECT: {
      label: "Reject",
      hint: "Not for this channel.",
      tone: "blocked"
    },
    REVIEW_BELOW: {
      label: "Approve in historical review",
      hint: "Historical topics need their example videos kept or replaced first; this opens that review.",
      tone: "complete",
      takesNote: false
    },
    STOP: {
      label: "Stop analyzing",
      hint: "Your idea stops being the study set.",
      tone: "blocked",
      takesNote: false
    }
  };

  let workspace = null;

  function yp() { return window.YP; }

  function esc(value) { return yp().escapeHtml(value); }

  function items() {
    if (!yp()) return [];
    return ((yp().inbox() || {}).items || []).filter(function (item) {
      return item && item.status === "NEEDS_REVIEW";
    });
  }

  function levelTone(level) {
    if (level === "STRONG" || level === "EVIDENCED") return "complete";
    if (level === "MODERATE") return "running";
    if (level === "WEAK") return "human";
    return "ready";
  }

  function whyInteresting(item) {
    const bullets = [];
    const viral = item.viral;
    if (viral) {
      if (viral.lifetime_ratio != null) {
        bullets.push(viral.lifetime_ratio + "× its channel's median views" +
          (viral.strength ? " (" + String(viral.strength).replace(/_/g, " ").toLowerCase() + ")" : ""));
      }
      if (viral.breadth === "REPLICATED" && viral.cluster) {
        bullets.push(viral.cluster.independent_channel_count + " independent channels breaking out on the same theme");
      }
      if (viral.trajectory && viral.trajectory !== "INSUFFICIENT_SNAPSHOTS") {
        bullets.push("Views per hour: " + String(viral.trajectory).replace(/_/g, " ").toLowerCase());
      }
      if (viral.historical_alignment === "ALIGNED") bullets.push("Matches a topic with proven historical demand");
    }
    (item.evidence || []).forEach(function (chip) {
      const level = chip.level || "UNASSESSED";
      if (level === "UNASSESSED" || level === "HYPOTHESIS") return;
      const basis = (chip.basis || [])[0];
      bullets.push(chip.label + ": " + level.toLowerCase() + (basis ? " — " + basis : ""));
    });
    return bullets;
  }

  function matrix(item) {
    const rows = (item.matrix || []).map(function (row) {
      const level = row.level || "UNASSESSED";
      const open = level === "UNASSESSED" || level === "HYPOTHESIS";
      return '<div class="rw-level"><dt>' + esc(row.label) + '</dt><dd><span class="status-badge status-' +
        levelTone(level) + '" title="' + esc(open ? "Not yet evidenced" : (row.rule_id || "") + " " + (row.basis || []).join("; ")) +
        '">' + esc(open ? "Not yet evidenced" : level) + "</span></dd></div>";
    }).join("");
    return rows ? '<dl class="rw-levels">' + rows + "</dl>" : "";
  }

  function videos(item) {
    const list = (item.videos || []).slice(0, 3).map(function (video) {
      return "<li>" + esc(video.title || video.video_id) + ' <span class="muted">· ' +
        esc(video.channel_title || "") + " · " + esc(yp().formatCount(video.views)) + " views</span></li>";
    }).join("");
    if (!list) return "";
    const more = (item.video_count || 0) > 3 ? '<p class="muted">+ ' + (item.video_count - 3) + " more in the full evidence.</p>" : "";
    return '<h3 class="rw-section">Videos</h3><ul class="rw-list">' + list + "</ul>" + more;
  }

  function evidence(item) {
    const bullets = whyInteresting(item);
    return (item.summary ? '<p class="rw-summary">' + esc(item.summary) + "</p>" : "") +
      (item.status_reason ? '<p class="muted">' + esc(item.status_reason) + "</p>" : "") +
      '<h3 class="rw-section">Why this is interesting</h3>' +
      (bullets.length
        ? '<ul class="rw-list">' + bullets.map(function (b) { return "<li>" + esc(b) + "</li>"; }).join("") + "</ul>"
        : '<p class="muted">No rule-backed evidence yet. The full evidence shows what is still open.</p>') +
      '<h3 class="rw-section">Evidence levels</h3>' + matrix(item) +
      videos(item) +
      '<button type="button" class="ghost compact" data-rw-evidence="' + esc(item.opportunity_id) + '">Open full evidence</button>';
  }

  function meta(item) {
    return '<span class="source-chip">' + esc(item.source_label || "") + "</span>" +
      '<span class="rw-meta-text">' + esc(yp().routeLabel(item.route || "UNSCOPED")) +
      (item.route_channel_id && item.route === "FUTURE_CHANNEL" ? " · " + esc(item.route_channel_id) : "") + "</span>";
  }

  function decisions(item) {
    return (item.actions || [])
      .filter(function (action) { return DECISIONS[action]; })
      .map(function (action) { return Object.assign({ value: action }, DECISIONS[action]); });
  }

  function ensure() {
    if (workspace) return workspace;
    const root = document.getElementById("opportunityReview");
    if (!root || !window.ReviewWorkspace || !yp()) return null;
    workspace = window.ReviewWorkspace.create({
      root: root,
      kicker: "OPPORTUNITY REVIEW",
      items: items,
      key: function (item) { return item.opportunity_id; },
      signature: function (item) { return item.opportunity_id + ":" + (item.packet_sha256 || "") + ":" + (item.actions || []).join(","); },
      title: function (item) { return item.title || item.opportunity_id; },
      meta: meta,
      renderEvidence: evidence,
      decisions: decisions,
      noteOffHint: "Approving starts analysis; notes are recorded with Watch, Investigate, Save and Reject.",
      decide: function (item, action, note) { return yp().decide(item, action, note); },
      onNavigate: function (key) {
        if (window.location.pathname === "/opportunity/review") {
          history.replaceState({}, "", "/opportunity/review#" + encodeURIComponent(key));
        }
      },
      emptyHtml: "<h2>Nothing waiting for review</h2>" +
        '<p class="muted">New ideas from every lane land here: proven demand, your topics and videos, and radar breakouts.</p>' +
        '<div class="rw-empty-actions"><a href="/opportunity" class="button-link ghost compact" data-route="/opportunity">Find opportunities</a>' +
        '<a href="/radar" class="button-link ghost compact" data-route="/radar">Open Viral Radar</a></div>'
    });
    if (window.location.pathname === "/opportunity/review" && window.location.hash) {
      workspace.focus(decodeURIComponent(window.location.hash.slice(1)));
    }
    root.addEventListener("click", function (event) {
      const button = event.target.closest("[data-rw-evidence]");
      if (button) yp().openEvidence(button.dataset.rwEvidence, button);
    });
    return workspace;
  }

  window.OpportunityReview = {
    render: function () {
      const instance = ensure();
      if (instance) instance.render();
    },
    focus: function (opportunityId) {
      const instance = ensure();
      if (instance) instance.focus(opportunityId);
    },
    count: function () { return items().length; }
  };
})();
