/* Viral Radar page (UI-04, D-116).
   Reads /api/opportunity/viral/overview (themes, tracked videos and their
   snapshot series, all from the radar's own files) while /radar is open,
   and the status payload for the schedule and the run action. */
(function () {
  "use strict";

  const REFRESH_MS = 30000;
  const FORMATS = [["all", "All formats"], ["long_form", "Long-form"], ["short", "Shorts"]];

  let overview = null;
  let fetchedAt = 0;
  let fetchedFor = "";
  let loading = false;
  let error = "";
  let formatFilter = "all";
  let latestStatus = null;

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

  function filters() {
    return '<div class="radar-filters" role="group" aria-label="Format">' +
      FORMATS.map(function (f) {
        return '<button type="button" class="inbox-tab' + (f[0] === formatFilter ? " active" : "") +
          '" aria-pressed="' + (f[0] === formatFilter) + '" data-radar-format="' + f[0] + '">' + esc(f[1]) + "</button>";
      }).join("") +
      '<span class="muted radar-note">Topic and region filters are not available yet: the radar scans its channel watchlist and rotating science queries.</span>' +
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
        " · " + esc(ratio(video.lifetime_ratio)) + " · " + esc(words(video.trajectory)) + "</span></li>";
    }).join("");
    return '<article class="theme-card' + (replicated ? " replicated" : "") + '">' +
      '<div class="theme-head"><p class="attention-kicker">' + esc(replicated ? "Replicated breakout" : words(theme.breadth || "one off")) +
        (theme.kind ? " · " + esc(words(theme.kind)) : "") + "</p>" +
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
        '<p class="production-detail">' + esc((row.channel_title || "") + " · " + (row.format === "short" ? "Short" : "Long-form") + " · " + statusLabel) + "</p></div>" +
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
    const themes = (overview.themes || []).filter(function (theme) {
      return formatFilter === "all" || (theme.videos || []).some(function (video) {
        const row = (overview.tracked || []).find(function (r) { return r.video_id === video.video_id; });
        return row && matchesFormat(row);
      });
    });
    const tracked = (overview.tracked || []).filter(matchesFormat);
    const watching = tracked.filter(function (row) { return inboxStatus(row.opportunity_id) === "WATCHING"; });
    const others = tracked.filter(function (row) { return inboxStatus(row.opportunity_id) !== "WATCHING"; });
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
        '<p class="muted">Strongest outlier first.</p></div>' +
        (others.length ? '<div class="production-list">' + others.map(trackedRow).join("") + "</div>"
          : '<p class="empty-state">No other tracked videos.</p>') +
      "</section>";
  }

  let painted = "";

  function paint() {
    const root = $("radarPage");
    if (!root || !latestStatus || !yp()) return;
    const html = header(latestStatus) + filters() + body();
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
