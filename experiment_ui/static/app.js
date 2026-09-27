const stageGrid = document.getElementById("stageGrid");
const actionGroups = document.getElementById("actionGroups");
const currentNotice = document.getElementById("currentNotice");
const lastUpdated = document.getElementById("lastUpdated");
const refreshStatus = document.getElementById("refreshStatus");
const jobTitle = document.getElementById("jobTitle");
const jobMeta = document.getElementById("jobMeta");
const logView = document.getElementById("logView");
const stopJob = document.getElementById("stopJob");
const toast = document.getElementById("toast");
const opportunityGate = document.getElementById("opportunityGate");
const controlsPanel = document.getElementById("controlsPanel");
const jobPanel = document.getElementById("jobPanel");
const backToControls = document.getElementById("backToControls");

let jobTimer = null;

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message, error) {
  toast.textContent = message;
  toast.classList.toggle("error", Boolean(error));
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(function () {
    toast.classList.remove("show");
  }, 3200);
}

async function api(url, options) {
  const response = await fetch(url, Object.assign({
    headers: { "Content-Type": "application/json" }
  }, options || {}));

  let payload = {};
  try {
    payload = await response.json();
  } catch (_) {}

  if (!response.ok) {
    throw new Error(payload.error || ("Request failed (" + response.status + ")"));
  }
  return payload;
}

function compactNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 1
  }).format(number);
}

function humanizeToken(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, function (match) { return match.toUpperCase(); });
}

function safeYoutubeUrl(value) {
  try {
    const url = new URL(String(value || ""));
    const host = url.hostname.toLowerCase();
    if (
      url.protocol === "https:" &&
      (host === "youtube.com" || host === "www.youtube.com" || host === "youtu.be")
    ) {
      return url.href;
    }
  } catch (_) {}
  return "";
}

function renderOpportunityGate(gate) {
  if (!opportunityGate) return;

  if (!gate || !(gate.opportunities || []).length) {
    opportunityGate.innerHTML =
      '<p class="gate-empty">Waiting for Experiment 01.5 to create a study set.</p>';
    return;
  }

  const status = escapeHtml(gate.status || "AWAITING_HUMAN_DECISION");
  let html =
    '<div class="gate-summary">' +
    '<span class="status-chip ' +
    (gate.ready_for_experiment_02 ? "success" : "running") +
    '">' + status + '</span>' +
    '<span>' +
    (gate.ready_for_experiment_02
      ? "Experiment 02 is unlocked."
      : "Experiment 02 stays locked until your decision is complete.") +
    '</span></div>';

  (gate.opportunities || []).forEach(function (opportunity) {
    const evidence = opportunity.topic_evidence || {};
    const decision = opportunity.decision || "PENDING";

    html += '<article class="opportunity-card">' +
      '<div class="opportunity-head">' +
      '<div>' +
      '<div class="opportunity-label">OPPORTUNITY</div>' +
      '<h3>' + escapeHtml(humanizeToken(opportunity.topic)) + '</h3>' +
      '<p>' +
      escapeHtml(
        [
          humanizeToken(opportunity.niche),
          humanizeToken(opportunity.format_candidate)
        ].filter(Boolean).join(" · ")
      ) +
      '</p>' +
      '</div>' +
      '<span class="decision-chip decision-' +
      escapeHtml(decision.toLowerCase()) + '">' +
      escapeHtml(decision) + '</span>' +
      '</div>' +

      '<div class="metric-grid">' +
      '<div><span>Velocity index</span><strong>' +
      escapeHtml(evidence.age_matched_velocity_index == null ? "—" : evidence.age_matched_velocity_index) +
      '</strong></div>' +
      '<div><span>Independent channels</span><strong>' +
      escapeHtml(evidence.unique_channels == null ? "—" : evidence.unique_channels) +
      '</strong></div>' +
      '<div><span>Velocity samples</span><strong>' +
      escapeHtml(evidence.velocity_sample_count == null ? "—" : evidence.velocity_sample_count) +
      '</strong></div>' +
      '<div><span>Median views</span><strong>' +
      escapeHtml(compactNumber(evidence.median_views)) +
      '</strong></div>' +
      '<div><span>Current views/day</span><strong>' +
      escapeHtml(compactNumber(evidence.median_current_views_per_day)) +
      '</strong></div>' +
      '<div><span>Topic channel confidence</span><strong>' +
      escapeHtml(
        evidence.topic_channel_confidence ||
        evidence.confidence ||
        "—"
      ) +
      '</strong></div>' +
      '</div>' +

      '<div class="example-grid">';

    (opportunity.selected_examples || []).forEach(function (example, index) {
      const youtubeUrl = safeYoutubeUrl(example.youtube_url);
      const kept = example.decision === "KEEP";
      html += '<section class="example-card">' +
        '<div class="example-topline">' +
        '<span>EXAMPLE ' + (index + 1) + '</span>' +
        '<span class="decision-chip decision-' +
        escapeHtml(String(example.decision || "PENDING").toLowerCase()) + '">' +
        escapeHtml(example.decision || "PENDING") + '</span>' +
        '</div>' +
        '<img class="example-thumbnail" src="https://i.ytimg.com/vi/' +
        escapeHtml(encodeURIComponent(example.video_id)) +
        '/hqdefault.jpg" alt="" loading="lazy">' +
        '<h4>' + escapeHtml(example.title || example.video_id) + '</h4>' +
        '<p class="example-channel">' +
        escapeHtml(example.channel_title || "Unknown channel") + '</p>' +
        '<div class="example-stats">' +
        '<span>' + escapeHtml(compactNumber(example.views)) + ' views</span>' +
        '<span>' + escapeHtml(example.duration_seconds == null ? "—" : example.duration_seconds) + ' sec</span>' +
        '<span>' + escapeHtml(example.age_days == null ? "—" : Math.round(Number(example.age_days))) + ' days old</span>' +
        '</div>' +
        '<p class="example-families"><strong>Matched:</strong> ' +
        escapeHtml((example.matched_families || []).join(", ") || "—") + '</p>' +
        '<div class="example-actions">' +
        (youtubeUrl
          ? '<a class="external-button" href="' + escapeHtml(youtubeUrl) +
            '" target="_blank" rel="noopener noreferrer">Open on YouTube</a>'
          : '') +
        '<button class="gate-button keep" data-gate-action="KEEP_EXAMPLE"' +
        ' data-opportunity-id="' + escapeHtml(opportunity.opportunity_id) + '"' +
        ' data-video-id="' + escapeHtml(example.video_id) + '"' +
        (kept ? " disabled" : "") + '>' +
        (kept ? "Kept" : "Keep Example") + '</button>' +
        '<button class="gate-button replace" data-gate-action="REPLACE_EXAMPLE"' +
        ' data-opportunity-id="' + escapeHtml(opportunity.opportunity_id) + '"' +
        ' data-video-id="' + escapeHtml(example.video_id) + '"' +
        (opportunity.alternatives_available > 0 ? "" : " disabled") +
        '>Replace Example</button>' +
        '</div>' +
        '</section>';
    });

    html += '</div>' +
      '<div class="topic-actions">' +
      '<div class="topic-action-copy">' +
      '<strong>Your topic decision</strong>' +
      '<span>Keep or replace every example before approving the topic.</span>' +
      '</div>' +
      '<div class="topic-action-buttons">' +
      '<button class="gate-button approve" data-gate-action="APPROVE_TOPIC"' +
      ' data-opportunity-id="' + escapeHtml(opportunity.opportunity_id) + '"' +
      (opportunity.can_approve && decision !== "APPROVE" ? "" : " disabled") +
      '>Approve Topic</button>' +
      '<button class="gate-button hold" data-gate-action="HOLD_TOPIC"' +
      ' data-opportunity-id="' + escapeHtml(opportunity.opportunity_id) + '"' +
      (decision === "HOLD" ? " disabled" : "") + '>Hold / Review</button>' +
      '<button class="gate-button reject" data-gate-action="REJECT_TOPIC"' +
      ' data-opportunity-id="' + escapeHtml(opportunity.opportunity_id) + '"' +
      (decision === "REJECT" ? " disabled" : "") + '>Reject Topic</button>' +
      '</div></div>' +
      '</article>';
  });

  opportunityGate.innerHTML = html;

  opportunityGate.querySelectorAll("[data-gate-action]").forEach(function (button) {
    button.addEventListener("click", function () {
      const action = button.dataset.gateAction;
      if (
        action === "REJECT_TOPIC" &&
        !confirm("Reject this opportunity and keep Experiment 02 locked for it?")
      ) {
        return;
      }
      submitGateAction(
        action,
        button.dataset.opportunityId,
        button.dataset.videoId || null
      );
    });
  });
}

async function submitGateAction(action, opportunityId, videoId) {
  try {
    const payload = await api("/api/opportunity-gate", {
      method: "POST",
      body: JSON.stringify({
        action: action,
        opportunity_id: opportunityId,
        video_id: videoId
      })
    });
    renderOpportunityGate(payload);
    showToast("Opportunity gate updated.", false);
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function stateClass(stage) {
  const classes = [];
  if (stage.current) classes.push("current");
  if (!stage.ready) classes.push("blocked");
  if (stage.complete) classes.push("complete");
  if (stage.tone) classes.push("tone-" + stage.tone);
  return classes.join(" ");
}

function renderStages(stages) {
  stageGrid.innerHTML = stages.map(function (stage) {
    const criteria = (stage.criteria || []).map(function (item) {
      return '<li class="' + (item.done ? "done" : "pending") + '">' +
        '<span class="criterion-mark">' + (item.done ? "✓" : "○") + '</span>' +
        '<span>' + escapeHtml(item.label) + '</span>' +
        '</li>';
    }).join("");

    return '<article class="stage-card ' + stateClass(stage) + '">' +
      '<div class="stage-id">EXPERIMENT ' + escapeHtml(stage.id) + '</div>' +
      '<div class="stage-title">' + escapeHtml(stage.title) + '</div>' +
      '<div class="human-status">' + escapeHtml(stage.human_status || stage.state) + '</div>' +
      '<div class="stage-detail">' + escapeHtml(stage.detail) + '</div>' +
      '<ul class="criteria-list">' + criteria + '</ul>' +
      '<div class="stage-next"><strong>Next:</strong> ' +
        escapeHtml(stage.next_action || "No action.") + '</div>' +
      '<div class="machine-state">Machine: ' + escapeHtml(stage.state) + '</div>' +
      '</article>';
  }).join("");
}

function renderActions(actions) {
  const groups = new Map();

  actions.forEach(function (action) {
    if (!groups.has(action.stage)) groups.set(action.stage, []);
    groups.get(action.stage).push(action);
  });

  let html = "";
  groups.forEach(function (items, stage) {
    html += '<section class="action-group">' +
      '<div class="action-group-title">EXPERIMENT ' + escapeHtml(stage) + '</div>';

    items.forEach(function (action) {
      html += '<div class="action-row">' +
        '<div class="action-copy">' +
        '<strong>' + escapeHtml(action.label) + '</strong>' +
        '<p>' + escapeHtml(action.description) + '</p>' +
        '<p class="reason">' + escapeHtml(action.reason) + '</p>' +
        '</div>' +
        '<button class="run-button" data-action="' + escapeHtml(action.id) + '"' +
        (action.enabled ? "" : " disabled") + '>Run</button>' +
        '</div>';
    });

    html += '</section>';
  });

  actionGroups.innerHTML = html;

  document.querySelectorAll("[data-action]").forEach(function (button) {
    button.addEventListener("click", function () {
      runAction(button.dataset.action);
    });
  });
}

function currentStageMessage(stages) {
  const current = stages.find(function (stage) { return stage.current; });
  if (!current) {
    const complete = stages.length && stages.every(function (stage) {
      return stage.complete;
    });
    return complete
      ? "All displayed experiment stages are complete."
      : "No active experiment stage detected.";
  }

  return "Experiment " + current.id + " — " +
    (current.human_status || current.state) +
    ". Next: " + (current.next_action || "No action.");
}

function renderJob(job, log) {
  if (!job) {
    jobTitle.textContent = "No job running";
    jobMeta.innerHTML =
      '<span class="status-chip neutral">IDLE</span>' +
      '<span>Choose an enabled action to start.</span>';
    stopJob.disabled = true;
    if (log !== undefined && log !== null) {
      logView.textContent = log || "No job output yet.";
    }
    return;
  }

  const running = job.status === "RUNNING" || job.status === "STOPPING";
  let statusClass = "neutral";
  if (job.status === "SUCCEEDED") statusClass = "success";
  else if (job.status === "FAILED") statusClass = "failed";
  else if (running) statusClass = "running";

  jobTitle.textContent = job.label || job.action_id;
  let meta =
    '<span class="status-chip ' + statusClass + '">' + escapeHtml(job.status) + '</span>' +
    '<span>PID ' + escapeHtml(job.pid == null ? "—" : job.pid) + '</span>' +
    '<span>' + escapeHtml(job.started_at || "") + '</span>';

  if (job.return_code !== null && job.return_code !== undefined) {
    meta += '<span>Exit ' + escapeHtml(job.return_code) + '</span>';
  }
  jobMeta.innerHTML = meta;
  stopJob.disabled = !running;

  if (log !== undefined && log !== null) {
    const shouldStick =
      Math.abs(logView.scrollHeight - logView.scrollTop - logView.clientHeight) < 80;
    logView.textContent = log || "Job started. Waiting for output…";
    if (shouldStick) logView.scrollTop = logView.scrollHeight;
  }
}

async function loadStatus() {
  try {
    const data = await api("/api/status");
    renderStages(data.stages);
    renderActions(data.actions);
    renderOpportunityGate(data.opportunity_gate);
    renderJob(data.job);

    currentNotice.querySelector("strong").textContent =
      currentStageMessage(data.stages);

    const currentStage = data.stages.find(function (stage) {
      return stage.current;
    });
    const tone = currentStage ? currentStage.tone : "ready";

    currentNotice.classList.toggle("blocked", tone === "blocked");
    currentNotice.classList.toggle(
      "ready",
      tone === "complete" || tone === "ready"
    );
    currentNotice.classList.toggle(
      "running",
      tone === "running" || tone === "action"
    );
    lastUpdated.textContent = new Date(data.updated_at).toLocaleTimeString();

    if (data.job && (data.job.status === "RUNNING" || data.job.status === "STOPPING")) {
      startJobPolling();
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

async function loadJob() {
  try {
    const data = await api("/api/job");
    renderJob(data.job, data.log);

    const running = data.job &&
      (data.job.status === "RUNNING" || data.job.status === "STOPPING");

    if (!running) {
      stopJobPolling();
      await loadStatus();
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

function elementMostlyVisible(element) {
  if (!element) return true;
  const rect = element.getBoundingClientRect();
  const viewportHeight =
    window.innerHeight || document.documentElement.clientHeight;
  return rect.top >= 0 && rect.top <= viewportHeight * 0.35;
}

function focusJobPanel() {
  if (!jobPanel || elementMostlyVisible(jobPanel)) return;
  jobPanel.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}

function focusControlsPanel() {
  if (!controlsPanel) return;
  controlsPanel.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}

async function runAction(actionId) {
  try {
    const data = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({ action_id: actionId })
    });
    renderJob(data.job, "");
    showToast("Started: " + data.job.label, false);
    focusJobPanel();
    startJobPolling();
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function stopCurrentJob() {
  if (!confirm("Stop the running experiment job?")) return;

  try {
    const data = await api("/api/stop", {
      method: "POST",
      body: "{}"
    });
    renderJob(data.job);
    showToast("Job stopped.", false);
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function openTarget(targetId) {
  try {
    const data = await api("/api/open", {
      method: "POST",
      body: JSON.stringify({ target_id: targetId })
    });
    showToast("Opened " + data.opened, false);
  } catch (error) {
    showToast(error.message, true);
  }
}

function startJobPolling() {
  if (jobTimer) return;
  loadJob();
  jobTimer = setInterval(loadJob, 1200);
}

function stopJobPolling() {
  if (!jobTimer) return;
  clearInterval(jobTimer);
  jobTimer = null;
}

refreshStatus.addEventListener("click", loadStatus);
stopJob.addEventListener("click", stopCurrentJob);
backToControls.addEventListener("click", focusControlsPanel);

document.querySelectorAll("[data-open]").forEach(function (button) {
  button.addEventListener("click", function () {
    openTarget(button.dataset.open);
  });
});

loadStatus();
setInterval(loadStatus, 5000);
