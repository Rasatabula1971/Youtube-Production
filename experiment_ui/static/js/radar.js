/* Viral Radar page (UI-04, D-116).
   Reads /api/opportunity/viral/overview (themes, tracked videos and their
   snapshot series, all from the radar's own files) while /radar is open,
   and the status payload for the schedule and the run action. */
(function () {
  "use strict";

  const REFRESH_MS = 30000;
  const FORMATS = [["all", "All formats"], ["long_form", "Long-form"], ["short", "Shorts"]];
  // Shortlist filters (D-162). Lane comes from the server's word lists;
  // ratio and freshness are the two numbers worth a threshold.
  const LANES = [["lane", "My lane"], ["all", "Everything"]];
  const RATIOS = [[0, "Any ratio"], [3, "≥ 3×"], [5, "≥ 5×"], [10, "≥ 10×"]];
  const AGES = [[0, "Any age"], [7, "≤ 7 days"], [3, "≤ 3 days"]];
  const FILTER_KEY = "radarFilters";
  const DEFAULT_FILTERS = { lane: "lane", minRatio: 3, maxDay: 0, order: "ratio" };
  // Order: by outlier, or by what you tend to pick (D-165, once learned).
  const ORDERS = [["ratio", "Strongest outlier"], ["taste", "What I pick"]];
  const TASTE_LABEL = { LIKELY: "like your picks", UNSURE: "unsure", UNLIKELY: "unlike your picks" };
  const LANE_LABEL = { ON_LANE: "on lane", UNCLEAR: "unclear lane", OFF_LANE: "off lane", OTHER_LANGUAGE: "other language" };

  let overview = null;
  let fetchedAt = 0;
  let fetchedFor = "";
  let loading = false;
  let error = "";
  let formatFilter = "all";
  let latestStatus = null;
  let filtersState = loadFilters();

  function loadFilters() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(FILTER_KEY) || "null");
      if (saved && typeof saved === "object") return Object.assign({}, DEFAULT_FILTERS, saved);
    } catch (_) {}
    return Object.assign({}, DEFAULT_FILTERS);
  }

  function saveFilters() {
    try { window.localStorage.setItem(FILTER_KEY, JSON.stringify(filtersState)); } catch (_) {}
  }

  function laneAllowed(lane) {
    return filtersState.lane === "all" || lane === "ON_LANE" || lane === "UNCLEAR" || !lane;
  }

  function rowPasses(row) {
    if (!matchesFormat(row)) return false;
    if (!laneAllowed(row.lane)) return false;
    if (filtersState.minRatio && !((row.lifetime_ratio || 0) >= filtersState.minRatio)) return false;
    if (filtersState.maxDay && !(row.day != null && row.day <= filtersState.maxDay)) return false;
    return true;
  }

  function themePasses(theme) {
    const rows = (theme.videos || []).map(function (video) {
      const tracked = (overview.tracked || []).find(function (r) { return r.video_id === video.video_id; });
      return tracked || video;
    });
    if (formatFilter !== "all" && !rows.some(matchesFormat)) return false;
    if (!laneAllowed(theme.lane)) return false;
    if (filtersState.minRatio && !((theme.strongest_ratio || 0) >= filtersState.minRatio)) return false;
    if (filtersState.maxDay && !rows.some(function (r) { return r.day != null && r.day <= filtersState.maxDay; })) return false;
    return true;
  }

  function learning() {
    return (overview && overview.learning) || { active: false, decisions: 0, needed: 20 };
  }

  function orderActive() {
    return filtersState.order === "taste" && learning().active;
  }

  function tasteBadge(row) {
    if (!learning().active || !row || !row.taste_label) return "";
    const tone = row.taste_label === "LIKELY" ? "complete" : row.taste_label === "UNLIKELY" ? "blocked" : "ready";
    return ' <span class="status-badge status-' + tone + '" title="Learned from your Approve, Watch, Save and Reject decisions">' +
      esc(TASTE_LABEL[row.taste_label] || words(row.taste_label)) + "</span>";
  }

  function byOrder(a, b, ratioA, ratioB) {
    if (orderActive()) {
      const ta = a.taste == null ? -2 : a.taste;
      const tb = b.taste == null ? -2 : b.taste;
      if (tb !== ta) return tb - ta;
    }
    return (ratioB || 0) - (ratioA || 0);
  }

  function learningNote() {
    const state = learning();
    if (state.active) {
      const strongest = state.strongest || { for: [], against: [] };
      return '<p class="muted radar-learning">Learned from ' + esc(String(state.decisions)) + " of your decisions" +
        (strongest.for.length ? ". Words you pick: " + esc(strongest.for.slice(0, 6).join(", ")) : "") +
        (strongest.against.length ? ". Words you reject: " + esc(strongest.against.slice(0, 6).join(", ")) : "") + ".</p>";
    }
    return '<p class="muted radar-learning">\"What I pick\" ordering starts after ' + esc(String(state.needed || 20)) +
      " Approve, Watch, Save or Reject decisions on radar candidates, with at least " + esc(String(state.needed_each_side || 5)) +
      " on each side (" + esc(String(state.decisions || 0)) + " so far).</p>";
  }

  function laneBadge(lane) {
    if (!lane || lane === "ON_LANE") return "";
    const tone = lane === "OFF_LANE" ? "blocked" : "ready";
    return ' <span class="status-badge status-' + tone + '">' + esc(LANE_LABEL[lane] || words(lane)) + "</span>";
  }

  function $(id) { return document.getElementById(id); }
  function yp() { return window.YP; }
  function esc(value) { return yp().escapeHtml(value); }

  function words(value) {
    return String(value || "").replace(/_/g, " ").toLowerCase();
  }

  function ratio(value) {
    return value == null ? "—" : Number(value).toFixed(1) + "×";
  }

  function ago(iso) {
    const time = Date.parse(iso || "");
    if (!Number.isFinite(time)) return "unknown";
    const hours = (Date.now() - time) / 3600000;
    if (hours < 1) return Math.max(1, Math.round(hours * 60)) + " min ago";
    if (hours < 48) return Math.round(hours) + "h ago";
    return Math.round(hours / 24) + "d ago";
  }

  function clock(iso) {
    const time = Date.parse(iso || "");
    if (!Number.isFinite(time)) return "—";
    return new Date(time).toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" });
  }

  function trajectoryTone(trajectory) {
    if (trajectory === "ACCELERATING") return "complete";
    if (trajectory === "DECELERATING") return "blocked";
    if (trajectory === "STABLE_HIGH") return "running";
    return "ready";
  }

  // A single-series sparkline: no legend, no axes; the numbers sit beside it.
  function sparkline(points, label) {
    const series = (points || []).filter(function (p) { return Array.isArray(p) && p.length === 2; });
    if (series.length < 2) {
      return '<span class="sparkline-empty muted">' + (series.length ? "1 snapshot" : "No snapshots yet") + "</span>";
    }
    const width = 120;
    const height = 32;
    const pad = 3;
    const xs = series.map(function (p) { return p[0]; });
    const ys = series.map(function (p) { return p[1]; });
    const xMin = Math.min.apply(null, xs);
    const xMax = Math.max.apply(null, xs);
    const yMin = Math.min.apply(null, ys);
    const yMax = Math.max.apply(null, ys);
    const sx = function (x) { return pad + (xMax === xMin ? 0.5 : (x - xMin) / (xMax - xMin)) * (width - pad * 2); };
    const sy = function (y) { return height - pad - (yMax === yMin ? 0.5 : (y - yMin) / (yMax - yMin)) * (height - pad * 2); };
    const last = series[series.length - 1];
    const summary = label + ": views went from " + yp().formatCount(series[0][1]) + " at " +
      Math.round(series[0][0]) + "h to " + yp().formatCount(last[1]) + " at " + Math.round(last[0]) +
      "h after publishing (" + series.length + " snapshots).";
    return '<svg class="sparkline" viewBox="0 0 ' + width + " " + height + '" width="' + width + '" height="' + height +
      '" role="img" aria-label="' + esc(summary) + '"><title>' + esc(summary) + "</title>" +
      '<polyline points="' + series.map(function (p) { return sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1); }).join(" ") + '"/>' +
      '<circle r="3" cx="' + sx(last[0]).toFixed(1) + '" cy="' + sy(last[1]).toFixed(1) + '"/></svg>';
  }

  function inboxStatus(opportunityId) {
    const item = yp().inboxItem(opportunityId);
    return item ? item.status : null;
  }

  function matchesFormat(row) {
    return formatFilter === "all" || row.format === formatFilter;
  }

  function header(data) {
    const radar = data.viral_radar || {};
    const schedule = radar.schedule || null;
    const last = radar.last_run || null;
    const action = (data.actions || []).find(function (a) { return a.id === "viral_radar"; }) || {};
    const automatic = Boolean(schedule && schedule.checked_at);
    return '<div class="radar-status">' +
      '<span class="health-pill tone-' + (automatic ? "complete" : "ready") + '"><span class="status-dot tone-' +
        (automatic ? "complete" : "ready") + '"></span>' + (automatic ? "Automatic monitoring" : "Manual only") + "</span>" +
      '<dl class="radar-facts">' +
        "<div><dt>Last scan</dt><dd>" + esc(last ? clock(last.run_at) + " · " + words(last.status) : "never") + "</dd></div>" +
        "<div><dt>Next discovery</dt><dd>" + esc(schedule && schedule.next_discovery_due ? clock(schedule.next_discovery_due) : "—") + "</dd></div>" +
        "<div><dt>Next snapshots</dt><dd>" + esc(schedule && schedule.next_snapshot_due ? clock(schedule.next_snapshot_due) : "—") + "</dd></div>" +
        "<div><dt>Tracking</dt><dd>" + esc(String(radar.tracked_count || 0)) + " videos · " + esc(String(radar.watchlist_size || 0)) + " channels</dd></div>" +
      "</dl>" +
      '<button type="button" data-action="viral_radar"' + (action.enabled ? "" : " disabled") +
        ' title="' + esc(action.reason || "") + '">Run scan now</button>' +
    "</div>" +
    (automatic ? "" : '<p class="muted radar-note">Install Opportunity Automation from Tools and the radar re-measures tracked videos on its own every 2 hours.</p>') +
    (last && (last.errors || []).length ? '<p class="radar-error">' + esc(last.errors[0]) + "</p>" : "") +
    (radar.throttled_until ? '<p class="radar-error">YouTube search is backing off until ' + esc(clock(radar.throttled_until)) + ".</p>" : "");
  }

  function pills(name, options, current, attr) {
    return '<div class="radar-filter-group" role="group" aria-label="' + esc(name) + '">' +
      options.map(function (option) {
        const on = String(option[0]) === String(current);
        return '<button type="button" class="inbox-tab' + (on ? " active" : "") + '" aria-pressed="' + on +
          '" ' + attr + '="' + esc(String(option[0])) + '">' + esc(option[1]) + "</button>";
      }).join("") + "</div>";
  }

  function filters(hidden) {
    const isDefault = filtersState.lane === DEFAULT_FILTERS.lane && filtersState.minRatio === DEFAULT_FILTERS.minRatio &&
      filtersState.maxDay === DEFAULT_FILTERS.maxDay && filtersState.order === DEFAULT_FILTERS.order && formatFilter === "all";
    return '<div class="radar-filters">' +
      pills("Lane", LANES, filtersState.lane, "data-radar-lane") +
      pills("Minimum outlier", RATIOS, filtersState.minRatio, "data-radar-ratio") +
      pills("Freshness", AGES, filtersState.maxDay, "data-radar-age") +
      pills("Format", FORMATS, formatFilter, "data-radar-format") +
      (learning().active ? pills("Order", ORDERS, filtersState.order, "data-radar-order") : "") +
      '<span class="muted radar-note">' + (hidden ? esc(String(hidden)) + " hidden by these filters. " : "") +
        (isDefault ? "Default: your lane, at least 3× the channel's normal." : '<button type="button" class="ghost compact" data-radar-reset>Reset filters</button>') +
      "</span>" +
      learningNote() +
    "</div>";
  }

  // The watch page for a tracked video: only an 11-character YouTube id
  // becomes a link, and only to youtube.com.
  function watchLink(videoId, label) {
    const id = String(videoId || "");
    if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return esc(label || id);
    return '<a href="https://www.youtube.com/watch?v=' + id + '" target="_blank" rel="noopener noreferrer">' + esc(label || id) + " ↗</a>";
  }

  function themeCard(theme) {
    const replicated = theme.breadth === "REPLICATED";
    const evidenceId = theme.top_opportunity_id && yp().inboxItem(theme.top_opportunity_id) ? theme.top_opportunity_id : "";
    const videos = (theme.videos || []).map(function (video) {
      return "<li>" + watchLink(video.video_id, video.title || video.video_id) + ' <span class="muted">· ' + esc(video.channel_title || "") +
        " · " + esc(ratio(video.lifetime_ratio)) + (video.day != null ? " · day " + esc(String(video.day)) : "") + " · " + esc(words(video.trajectory)) + "</span>" + tasteBadge(video) + "</li>";
    }).join("");
    return '<article class="theme-card' + (replicated ? " replicated" : "") + '">' +
      '<div class="theme-head"><p class="attention-kicker">' + esc(replicated ? "Replicated breakout" : words(theme.breadth || "one off")) +
        (theme.kind ? " · " + esc(words(theme.kind)) : "") + laneBadge(theme.lane) + "</p>" +
        '<h3 class="theme-title">' + esc(theme.label || theme.cluster_id) + "</h3>" +
        '<p class="muted">' + esc((theme.member_count || 0) + " video(s) · " + (theme.independent_channel_count || 0) +
          " independent channel(s)" + (theme.first_detected_at ? " · first detected " + ago(theme.first_detected_at) : "")) + "</p></div>" +
      '<div class="theme-momentum"><span class="theme-metric-label">Momentum (top video)</span>' + sparkline(theme.momentum, theme.label || "Theme") + "</div>" +
      '<dl class="theme-metrics">' +
        "<div><dt>Strongest outlier</dt><dd>" + esc(ratio(theme.strongest_ratio)) + "</dd></div>" +
        "<div><dt>Median outlier</dt><dd>" + esc(ratio(theme.median_ratio)) + "</dd></div>" +
        '<div><dt>Current direction</dt><dd><span class="status-badge status-' + trajectoryTone(theme.direction) + '">' + esc(words(theme.direction) || "unknown") + "</span></dd></div>" +
        "<div><dt>Historical demand</dt><dd>" + esc(words(theme.historical_alignment) || "unassessed") + "</dd></div>" +
      "</dl>" +
      (videos ? '<details class="theme-videos"><summary>View videos</summary><ul class="rw-list">' + videos + "</ul></details>" : "") +
      '<div class="theme-actions">' +
        (evidenceId ? '<button type="button" class="ghost compact" data-radar-evidence="' + esc(evidenceId) + '">Evidence</button>' : "") +
        (replicated
          ? '<button type="button" class="compact" data-radar-theme="' + esc(theme.cluster_id) + '">Analyze why →</button>'
          : (evidenceId && inboxStatus(evidenceId) === "NEEDS_REVIEW" ? '<a href="/opportunity/review#' + esc(encodeURIComponent(evidenceId)) + '" class="button-link ghost compact" data-route="/opportunity/review" data-subroute="' + esc(encodeURIComponent(evidenceId)) + '">Review →</a>' : "")) +
      "</div>" +
    "</article>";
  }

  function trackedRow(row) {
    const status = inboxStatus(row.opportunity_id);
    const statusLabel = status ? words(status) : "excluded or not in inbox";
    return '<article class="tracked-row">' +
      '<div class="tracked-main"><h3 class="production-title">' + watchLink(row.video_id, row.title || row.video_id) + "</h3>" +
        '<p class="production-detail">' + esc((row.channel_title || "") + " · " + (row.format === "short" ? "Short" : "Long-form") + " · " + statusLabel) + laneBadge(row.lane) + tasteBadge(row) + "</p></div>" +
      '<div class="tracked-day"><strong>' + esc(row.day == null ? "—" : "Day " + row.day + " / " + row.window_days) + "</strong></div>" +
      '<div class="tracked-ratio"><strong>' + esc(ratio(row.lifetime_ratio)) + '</strong><span class="muted">channel normal</span></div>' +
      '<div class="tracked-trend">' + sparkline(row.series, row.title || row.video_id) + "</div>" +
      '<div><span class="status-badge status-' + trajectoryTone(row.trajectory) + '">' + esc(words(row.trajectory) || "unknown") + "</span></div>" +
      '<div class="tracked-actions">' +
        (status ? '<button type="button" class="ghost compact" data-radar-evidence="' + esc(row.opportunity_id) + '">Evidence</button>' : "") +
        (status === "NEEDS_REVIEW" ? '<a href="/opportunity/review#' + esc(encodeURIComponent(row.opportunity_id)) + '" class="button-link ghost compact" data-route="/opportunity/review" data-subroute="' + esc(encodeURIComponent(row.opportunity_id)) + '">Review →</a>' : "") +
      "</div>" +
    "</article>";
  }

  function body() {
    if (!overview) {
      return '<p class="empty-state">' + esc(error || (loading ? "Loading the radar…" : "Open this page to load the radar.")) + "</p>";
    }
    const allThemes = overview.themes || [];
    const themes = allThemes.filter(themePasses);
    // Replication is the strongest signal: pinned first, then by ratio.
    themes.sort(function (a, b) {
      const ra = (a.independent_channel_count || 0) >= 2 ? 0 : 1;
      const rb = (b.independent_channel_count || 0) >= 2 ? 0 : 1;
      return ra - rb || byOrder(a, b, a.strongest_ratio, b.strongest_ratio);
    });
    const allTracked = overview.tracked || [];
    // Watched videos always show: you asked to follow them.
    const tracked = allTracked.filter(function (row) { return inboxStatus(row.opportunity_id) === "WATCHING" || rowPasses(row); });
    const watching = tracked.filter(function (row) { return inboxStatus(row.opportunity_id) === "WATCHING"; });
    const others = tracked.filter(function (row) { return inboxStatus(row.opportunity_id) !== "WATCHING"; })
      .sort(function (a, b) { return byOrder(a, b, a.lifetime_ratio, b.lifetime_ratio); });
    hiddenCount = (allThemes.length - themes.length) + (allTracked.length - tracked.length);
    return (error ? '<p class="radar-error">' + esc(error) + "</p>" : "") +
      '<section class="cc-section" aria-labelledby="radarEmergingTitle"><div class="cc-section-head"><h2 id="radarEmergingTitle">Emerging now</h2>' +
        '<p class="muted">Themes from the last scan, replicated across independent channels first.</p></div>' +
        (themes.length ? '<div class="theme-grid">' + themes.map(themeCard).join("") + "</div>"
          : '<p class="empty-state">No themes yet. Themes appear after a scan finds breakouts.</p>') +
      "</section>" +
      '<section class="cc-section" aria-labelledby="radarWatchingTitle"><div class="cc-section-head"><h2 id="radarWatchingTitle">Watching</h2>' +
        '<p class="muted">Breakouts you chose to watch. The radar keeps snapshotting them until day ' + esc(String(overview.window_days || 15)) + ".</p></div>" +
        (watching.length ? '<div class="production-list">' + watching.map(trackedRow).join("") + "</div>"
          : '<p class="empty-state">Nothing watched. Choose Watch in Opportunity Review to follow a breakout here.</p>') +
      "</section>" +
      '<section class="cc-section" aria-labelledby="radarTrackedTitle"><div class="cc-section-head"><h2 id="radarTrackedTitle">All tracked videos</h2>' +
        '<p class="muted">' + (orderActive() ? "What you tend to pick first, then strongest outlier." : "Strongest outlier first.") + "</p></div>" +
        (others.length ? '<div class="production-list">' + others.map(trackedRow).join("") + "</div>"
          : '<p class="empty-state">No other tracked videos.</p>') +
      "</section>";
  }

  let painted = "";
  let hiddenCount = 0;

  function paint() {
    const root = $("radarPage");
    if (!root || !latestStatus || !yp()) return;
    const main = body();
    const html = header(latestStatus) + filters(hiddenCount) + main;
    // Polling repaints only on change, so open details and focus survive.
    if (html === painted && root.innerHTML) return;
    painted = html;
    root.innerHTML = html;
  }

  async function load() {
    if (loading || !yp()) return;
    loading = true;
    paint();
    try {
      overview = await yp().api("/api/opportunity/viral/overview");
      error = "";
      fetchedAt = Date.now();
    } catch (err) {
      error = "The radar could not be loaded: " + err.message;
    } finally {
      loading = false;
      paint();
    }
  }

  function render(data) {
    latestStatus = data;
    if (window.location.pathname !== "/radar") return;
    const last = ((data.viral_radar || {}).last_run || {}).run_at || "";
    const schedule = ((data.viral_radar || {}).schedule || {}).checked_at || "";
    const marker = last + "|" + schedule;
    if (!overview || marker !== fetchedFor || Date.now() - fetchedAt > REFRESH_MS) {
      fetchedFor = marker;
      load();
      return;
    }
    paint();
  }

  document.addEventListener("click", function (event) {
    if (!event.target.closest("#radarPage")) return;
    const format = event.target.closest("[data-radar-format]");
    if (format) {
      formatFilter = format.dataset.radarFormat;
      paint();
      return;
    }
    const lane = event.target.closest("[data-radar-lane]");
    const ratioPill = event.target.closest("[data-radar-ratio]");
    const age = event.target.closest("[data-radar-age]");
    const order = event.target.closest("[data-radar-order]");
    const reset = event.target.closest("[data-radar-reset]");
    if (lane || ratioPill || age || order || reset) {
      if (lane) filtersState.lane = lane.dataset.radarLane;
      if (ratioPill) filtersState.minRatio = Number(ratioPill.dataset.radarRatio);
      if (age) filtersState.maxDay = Number(age.dataset.radarAge);
      if (order) filtersState.order = order.dataset.radarOrder === "taste" ? "taste" : "ratio";
      if (reset) { filtersState = Object.assign({}, DEFAULT_FILTERS); formatFilter = "all"; }
      saveFilters();
      paint();
      return;
    }
    const evidence = event.target.closest("[data-radar-evidence]");
    if (evidence) {
      yp().openEvidence(evidence.dataset.radarEvidence, evidence);
      return;
    }
    const theme = event.target.closest("[data-radar-theme]");
    if (theme) yp().analyzeTheme(theme.dataset.radarTheme);
  });

  window.RadarPage = {
    render: render,
    show: function () { if (latestStatus) render(latestStatus); }
  };
})();
