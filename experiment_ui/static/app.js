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

async function runAction(actionId) {
  try {
    const data = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({ action_id: actionId })
    });
    renderJob(data.job, "");
    showToast("Started: " + data.job.label, false);
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

document.querySelectorAll("[data-open]").forEach(function (button) {
  button.addEventListener("click", function () {
    openTarget(button.dataset.open);
  });
});

loadStatus();
setInterval(loadStatus, 5000);
