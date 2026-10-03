/* Tools & Diagnostics (UI-15, D-123).
   /tools: System Health (one row per dependency, with the Doctor or install
   action that fixes it), Recent Jobs (status, times and the saved log on
   demand), and the existing manual controls under Advanced. Read-only apart
   from the predefined actions, which run through the same /api/run path as
   every other action button. */
(function () {
  "use strict";

  const REFRESH_MS = 15000;
  const TONE = { READY: "complete", MISSING: "blocked", WARN: "human", UNKNOWN: "ready" };
  const JOB_TONE = { SUCCEEDED: "complete", FAILED: "blocked", PARTIAL: "human", STOPPED: "human", RUNNING: "running", STOPPING: "running" };

  let snapshot = null;
  let loading = false;
  let lastLoaded = 0;
  let lastJobSignature = "";
  const openLogs = {};   // job id -> text (null while loading)

  function yp() { return window.YP; }
  function esc(value) { return yp().escapeHtml(value); }
  function words(value) { return String(value || "").replace(/_/g, " ").toLowerCase(); }
  function onTools() { return window.location.pathname === "/tools"; }

  function jobRunning() {
    const job = ((yp() && yp().status()) || {}).job || {};
    return job.status === "RUNNING" || job.status === "STOPPING";
  }

  function badge(status, tones) {
    return '<span class="status-badge status-' + (tones[status] || "ready") + '">' + esc(words(status || "unknown")) + "</span>";
  }

  function shortTime(value) {
    const text = String(value || "");
    const match = text.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
    return match ? match[1] + " " + match[2] : text;
  }

  function renderHealth() {
    const host = document.getElementById("toolsHealth");
    if (!host) return;
    const checks = (snapshot && snapshot.health) || [];
    if (!checks.length) {
      host.innerHTML = '<p class="muted">' + (snapshot ? "No checks reported." : "Checking…") + "</p>";
      return;
    }
    const busy = jobRunning();
    host.innerHTML = checks.map(function (check) {
      let action = "";
      if (check.action_id) {
        const label = check.status === "READY" ? "Run again" : (check.action_id.indexOf("install") !== -1 ? "Install" : "Run Doctor");
        action = '<button class="ghost compact" data-action="' + esc(check.action_id) + '"' +
          (busy ? ' disabled title="A job is running."' : "") + ">" + esc(label) + "</button>";
      }
      return '<li class="th-row" data-health="' + esc(check.id) + '">' +
        '<div class="th-main"><strong>' + esc(check.label) + "</strong>" +
        '<span class="muted">' + esc(check.detail || "") + "</span></div>" +
        '<div class="th-side">' + badge(check.status, TONE) + action + "</div></li>";
    }).join("");
  }

  function renderJobs() {
    const host = document.getElementById("toolsJobs");
    if (!host) return;
    const jobs = (snapshot && snapshot.jobs) || [];
    if (!jobs.length) {
      host.innerHTML = '<p class="muted">' + (snapshot ? "No jobs have run yet." : "Loading…") + "</p>";
      return;
    }
    host.innerHTML = jobs.map(function (job) {
      const id = String(job.id || "");
      const open = Object.prototype.hasOwnProperty.call(openLogs, id);
      const times = [shortTime(job.started_at), job.finished_at ? "→ " + shortTime(job.finished_at).slice(-5) : ""]
        .filter(Boolean).join(" ");
      const exit = job.return_code === null || job.return_code === undefined ? "" : " · exit " + esc(job.return_code);
      let log = "";
      if (open) {
        log = '<pre class="tj-log" tabindex="0">' + esc(openLogs[id] === null ? "Loading log…" : openLogs[id]) + "</pre>";
      }
      return '<li class="tj-row">' +
        '<div class="tj-head">' +
        '<div class="th-main"><strong>' + esc(job.label || words(job.action_id) || id) + "</strong>" +
        '<span class="muted">' + esc(times) + exit + "</span></div>" +
        '<div class="th-side">' + badge(job.status, JOB_TONE) +
        (job.has_log
          ? '<button class="ghost compact" data-job-log="' + esc(id) + '" aria-expanded="' + (open ? "true" : "false") + '">' +
            (open ? "Hide log" : "Logs") + "</button>"
          : "") +
        "</div></div>" + log + "</li>";
    }).join("");
  }

  function paint() {
    renderHealth();
    renderJobs();
    const stamp = document.getElementById("toolsUpdated");
    if (stamp) stamp.textContent = snapshot ? "Updated " + shortTime(snapshot.updated_at) : "";
  }

  async function load() {
    if (loading) return;
    loading = true;
    try {
      snapshot = await yp().api("/api/tools");
      lastLoaded = Date.now();
    } catch (error) {
      yp().showToast(error.message, true);
    } finally {
      loading = false;
    }
    paint();
  }

  async function toggleLog(id) {
    if (Object.prototype.hasOwnProperty.call(openLogs, id)) {
      delete openLogs[id];
      renderJobs();
      return;
    }
    openLogs[id] = null;
    renderJobs();
    try {
      const data = await yp().api("/api/job-log?id=" + encodeURIComponent(id));
      if (Object.prototype.hasOwnProperty.call(openLogs, id)) openLogs[id] = data.text || "(empty log)";
    } catch (error) {
      if (Object.prototype.hasOwnProperty.call(openLogs, id)) openLogs[id] = "Could not load log: " + error.message;
    }
    renderJobs();
  }

  document.addEventListener("click", function (event) {
    const logButton = event.target.closest("[data-job-log]");
    if (logButton) {
      toggleLog(logButton.dataset.jobLog);
      return;
    }
    if (event.target.closest("#toolsRefresh")) load();
  });

  window.setInterval(function () {
    if (onTools() && !document.hidden) load();
  }, REFRESH_MS);

  window.Tools = {
    show: load,
    // Called on every status poll: reload when the job changes, otherwise
    // only repaint (the Run buttons follow the running state).
    render: function () {
      if (!onTools()) return;
      const job = ((yp() && yp().status()) || {}).job || {};
      const signature = [job.id, job.status].join("|");
      if (signature !== lastJobSignature || Date.now() - lastLoaded > REFRESH_MS) {
        lastJobSignature = signature;
        load();
      } else {
        renderHealth();
      }
    }
  };
})();
