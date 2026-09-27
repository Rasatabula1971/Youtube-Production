const views = Array.from(document.querySelectorAll("[data-view]"));
const navItems = Array.from(document.querySelectorAll("[data-route]"));
const pageKicker = document.getElementById("pageKicker");
const pageTitle = document.getElementById("pageTitle");
const pageSubtitle = document.getElementById("pageSubtitle");

const sidebar = document.getElementById("sidebar");
const sidebarScrim = document.getElementById("sidebarScrim");
const mobileMenu = document.getElementById("mobileMenu");
const sidebarStatus = document.getElementById("sidebarStatus");
const sidebarStatusDot = document.getElementById("sidebarStatusDot");

const homeCurrentTitle = document.getElementById("homeCurrentTitle");
const homeCurrentDetail = document.getElementById("homeCurrentDetail");
const homePrimaryAction = document.getElementById("homePrimaryAction");
const homeNextTitle = document.getElementById("homeNextTitle");
const homeNextDue = document.getElementById("homeNextDue");
const progressStrip = document.getElementById("progressStrip");
const homeOpportunitySummary = document.getElementById("homeOpportunitySummary");
const homeActivitySummary = document.getElementById("homeActivitySummary");
const refreshStatus = document.getElementById("refreshStatus");

const opportunityGate = document.getElementById("opportunityGate");
const analysisActions = document.getElementById("analysisActions");
const analysisCurrentTitle = document.getElementById("analysisCurrentTitle");
const analysisCurrentDetail = document.getElementById("analysisCurrentDetail");
const toolActions = document.getElementById("toolActions");
const stageGrid = document.getElementById("stageGrid");
const creationTabs = Array.from(document.querySelectorAll(".creation-tab"));

const jobSummaryButton = document.getElementById("jobSummaryButton");
const jobSummaryStatus = document.getElementById("jobSummaryStatus");
const jobSummaryLabel = document.getElementById("jobSummaryLabel");
const jobDrawer = document.getElementById("jobDrawer");
const drawerScrim = document.getElementById("drawerScrim");
const closeJobDrawer = document.getElementById("closeJobDrawer");
const jobTitle = document.getElementById("jobTitle");
const jobMeta = document.getElementById("jobMeta");
const logView = document.getElementById("logView");
const stopJob = document.getElementById("stopJob");
const toast = document.getElementById("toast");

let jobTimer = null;
let latestStatus = null;

const ROUTES = {
  "/": {
    view: "home",
    kicker: "WORKFLOW",
    title: "Home",
    subtitle: "What needs your attention now."
  },
  "/opportunity": {
    view: "opportunity",
    kicker: "HUMAN GATE",
    title: "Opportunity",
    subtitle: "Review the evidence and make the topic decision."
  },
  "/analysis": {
    view: "analysis",
    kicker: "ANALYZE & CREATE",
    title: "Analyze & Create",
    subtitle: "Turn approved evidence into an original video."
  },
  "/tools": {
    view: "tools",
    kicker: "MAINTENANCE",
    title: "Tools & Diagnostics",
    subtitle: "Manual controls, Doctors, logs and technical state."
  }
};

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function normalizedPath() {
  return Object.prototype.hasOwnProperty.call(ROUTES, window.location.pathname)
    ? window.location.pathname
    : "/";
}

function renderRoute() {
  const path = normalizedPath();
  const route = ROUTES[path];

  views.forEach(function (view) {
    view.hidden = view.dataset.view !== route.view;
  });

  document.querySelectorAll(".nav-item").forEach(function (item) {
    item.classList.toggle("active", item.dataset.route === path);
  });

  pageKicker.textContent = route.kicker;
  pageTitle.textContent = route.title;
  pageSubtitle.textContent = route.subtitle;
  document.title = route.title === "Home"
    ? "YouTube Production"
    : route.title + " — YouTube Production";

  closeSidebar();
  window.scrollTo({ top: 0, behavior: "instant" });
}

function navigate(path) {
  const target = Object.prototype.hasOwnProperty.call(ROUTES, path) ? path : "/";
  if (window.location.pathname !== target) {
    history.pushState({}, "", target);
  }
  renderRoute();
}

function openSidebar() {
  sidebar.classList.add("open");
  sidebarScrim.classList.add("open");
}

function closeSidebar() {
  sidebar.classList.remove("open");
  sidebarScrim.classList.remove("open");
}

function openJobDrawer() {
  jobDrawer.classList.add("open");
  jobDrawer.setAttribute("aria-hidden", "false");
  drawerScrim.classList.add("open");
}

function closeJob() {
  jobDrawer.classList.remove("open");
  jobDrawer.setAttribute("aria-hidden", "true");
  drawerScrim.classList.remove("open");
}

function statusTone(workflow) {
  const state = String((workflow || {}).state || "");
  if (state === "ACTION_REQUIRED" || state === "HUMAN_GATE") return "attention";
  if (state === "RUNNING_AUTOMATIC" || state === "WAITING_AUTOMATIC") return "running";
  return "ready";
}

function renderSidebarStatus(workflow) {
  const tone = statusTone(workflow);
  sidebarStatusDot.className = "status-dot " + tone;
  sidebarStatus.textContent =
    tone === "running" ? "Automation active" :
    tone === "attention" ? "Action required" :
    "Workflow ready";
}

function findAction(actions, actionId) {
  return (actions || []).find(function (action) {
    return action.id === actionId;
  }) || null;
}

function primaryTargetForWorkflow(workflow) {
  if (!workflow) return { type: "route", value: "/" };
  if (workflow.state === "HUMAN_GATE") {
    return { type: "route", value: "/opportunity", label: "Review opportunity" };
  }
  if (workflow.current_action_id === "opportunity_research") {
    return { type: "action", value: "opportunity_research", label: "Run now" };
  }
  if (workflow.current_action_id) {
    return { type: "route", value: "/analysis", label: "Continue" };
  }
  if (workflow.state === "WAITING_AUTOMATIC" || workflow.state === "RUNNING_AUTOMATIC") {
    return { type: "disabled", value: "", label: "Continuing automatically" };
  }
  return { type: "route", value: "/analysis", label: "View workflow" };
}

function renderHomeWorkflow(data) {
  const workflow = data.workflow || {};
  homeCurrentTitle.textContent = workflow.current_title || "Ready";
  homeCurrentDetail.textContent = workflow.current_detail || "";
  homeNextTitle.textContent = workflow.next_title || "—";
  homeNextDue.textContent = workflow.next_due_at
    ? "Due " + new Date(workflow.next_due_at).toLocaleString()
    : "";

  const target = primaryTargetForWorkflow(workflow);
  if (target.type === "action") {
    const action = findAction(data.actions, target.value);
    homePrimaryAction.innerHTML =
      '<button class="primary-cta" data-action="' + escapeHtml(target.value) + '"' +
      (action && action.enabled ? "" : " disabled") + '>' +
      escapeHtml(target.label) + '</button>';
  } else if (target.type === "route") {
    homePrimaryAction.innerHTML =
      '<button class="primary-cta" data-route="' + escapeHtml(target.value) + '">' +
      escapeHtml(target.label) + '</button>';
  } else {
    homePrimaryAction.innerHTML =
      '<button class="primary-cta" disabled>' + escapeHtml(target.label) + '</button>';
  }
}

function stageById(stages, id) {
  return (stages || []).find(function (stage) { return stage.id === id; }) || {};
}

function renderProgress(data) {
  const stages = data.stages || [];
  const s13 = stageById(stages, "01.3");
  const s14 = stageById(stages, "01.4");
  const s2 = stageById(stages, "02");
  const gate = data.opportunity_gate || {};
  const workflow = data.workflow || {};

  const discoveryDone = Boolean((s13.criteria || [])[0] && s13.criteria[0].done);
  const validationDone = Boolean(s13.complete);
  const expansionDone = Boolean(s14.complete);
  const reviewDone = Boolean(gate.ready_for_experiment_02);
  const analysisDone = Boolean(s2.complete);

  const currentName =
    workflow.state === "HUMAN_GATE" ? "Review" :
    workflow.current_action_id === "opportunity_research" ||
    workflow.state === "WAITING_AUTOMATIC" ||
    workflow.state === "RUNNING_AUTOMATIC" ? (
      validationDone ? "Expand" : (discoveryDone ? "Validate" : "Discover")
    ) :
    reviewDone && !analysisDone ? "Analyze" :
    analysisDone ? "Create" : "";

  const steps = [
    { name: "Discover", done: discoveryDone },
    { name: "Validate", done: validationDone },
    { name: "Expand", done: expansionDone },
    { name: "Review", done: reviewDone },
    { name: "Analyze", done: analysisDone },
    { name: "Create", done: false }
  ];

  progressStrip.innerHTML = steps.map(function (step) {
    const current = !step.done && step.name === currentName;
    return '<div class="progress-step ' +
      (step.done ? "complete " : "") +
      (current ? "current" : "") + '">' +
      '<span class="mark">' + (step.done ? "✓" : (current ? "●" : "○")) + '</span>' +
      '<strong>' + escapeHtml(step.name) + '</strong>' +
      '<span>' + (step.done ? "Complete" : (current ? "Current" : "Pending")) + '</span>' +
      '</div>';
  }).join("");
}

function renderHomeOpportunity(gate) {
  const opportunities = (gate && gate.opportunities) || [];
  if (!opportunities.length) {
    homeOpportunitySummary.innerHTML =
      '<h3>No opportunity selected yet</h3>' +
      '<p>Run Opportunity Research. The strongest evidence-backed direction will appear here.</p>';
    return;
  }

  const opportunity = opportunities[0];
  const evidence = opportunity.topic_evidence || {};
  const decision = opportunity.decision || "PENDING";

  homeOpportunitySummary.innerHTML =
    '<h3>' + escapeHtml(humanizeToken(opportunity.topic)) + '</h3>' +
    '<p>' + escapeHtml([
      humanizeToken(opportunity.niche),
      humanizeToken(opportunity.format_candidate)
    ].filter(Boolean).join(" · ")) + '</p>' +
    '<div class="summary-inline">' +
    '<span>' + escapeHtml((opportunity.selected_examples || []).length) + ' examples</span>' +
    '<span>' + escapeHtml(evidence.age_matched_velocity_index == null ? "—" : evidence.age_matched_velocity_index) + '× velocity</span>' +
    '<span>' + escapeHtml(decision) + '</span>' +
    '</div>';
}

function renderHomeActivity(job, research) {
  if (job && Object.keys(job).length) {
    homeActivitySummary.innerHTML =
      '<h3>' + escapeHtml(job.label || job.action_id || "Job") + '</h3>' +
      '<p>' + escapeHtml(job.status || "UNKNOWN") +
      (job.return_code == null ? "" : " · Exit " + escapeHtml(job.return_code)) + '</p>' +
      '<div class="summary-inline">' +
      '<button class="ghost compact" data-job-drawer>View job</button>' +
      '</div>';
    return;
  }

  if (research && research.status) {
    homeActivitySummary.innerHTML =
      '<h3>' + escapeHtml(humanizeToken(research.status)) + '</h3>' +
      '<p>' + escapeHtml(research.message || "Opportunity Research state.") + '</p>';
    return;
  }

  homeActivitySummary.innerHTML =
    '<h3>No recent activity</h3><p>Run the next highlighted workflow step when you are ready.</p>';
}

function renderOpportunityGate(gate) {
  if (!gate || !(gate.opportunities || []).length) {
    opportunityGate.innerHTML =
      '<p class="empty-state">Waiting for Opportunity Research to create a study set.</p>';
    return;
  }

  const status = escapeHtml(gate.status || "AWAITING_HUMAN_DECISION");
  let html =
    '<div class="gate-summary"><div class="gate-summary-copy">' +
    '<span class="status-chip ' +
    (gate.ready_for_experiment_02 ? "success" : "running") + '">' +
    status + '</span><span>' +
    (gate.ready_for_experiment_02
      ? "Opportunity approved. Analysis is unlocked."
      : "Keep or replace the examples, then make the topic decision.") +
    '</span></div>' +
    (gate.ready_for_experiment_02
      ? '<button data-route="/analysis">Continue to Analyze →</button>'
      : '') +
    '</div>';

  (gate.opportunities || []).forEach(function (opportunity) {
    const evidence = opportunity.topic_evidence || {};
    const decision = opportunity.decision || "PENDING";

    html += '<article class="opportunity-card">' +
      '<div class="opportunity-head"><div>' +
      '<div class="opportunity-label">OPPORTUNITY</div>' +
      '<h3>' + escapeHtml(humanizeToken(opportunity.topic)) + '</h3>' +
      '<p>' + escapeHtml([
        humanizeToken(opportunity.niche),
        humanizeToken(opportunity.format_candidate)
      ].filter(Boolean).join(" · ")) + '</p></div>' +
      '<span class="decision-chip decision-' +
      escapeHtml(decision.toLowerCase()) + '">' + escapeHtml(decision) + '</span></div>' +

      '<div class="metric-grid">' +
      '<div><span>Velocity</span><strong>' +
      escapeHtml(evidence.age_matched_velocity_index == null ? "—" : evidence.age_matched_velocity_index + "×") +
      '</strong></div>' +
      '<div><span>Channels</span><strong>' + escapeHtml(evidence.unique_channels == null ? "—" : evidence.unique_channels) + '</strong></div>' +
      '<div><span>Samples</span><strong>' + escapeHtml(evidence.velocity_sample_count == null ? "—" : evidence.velocity_sample_count) + '</strong></div>' +
      '<div><span>Median views</span><strong>' + escapeHtml(compactNumber(evidence.median_views)) + '</strong></div>' +
      '<div><span>Views/day</span><strong>' + escapeHtml(compactNumber(evidence.median_current_views_per_day)) + '</strong></div>' +
      '<div><span>Confidence</span><strong>' +
      escapeHtml(evidence.topic_channel_confidence || evidence.confidence || "—") +
      '</strong></div></div><div class="example-grid">';

    (opportunity.selected_examples || []).forEach(function (example, index) {
      const youtubeUrl = safeYoutubeUrl(example.youtube_url);
      const kept = example.decision === "KEEP";
      html += '<section class="example-card">' +
        '<div class="example-thumb-wrap"><img class="example-thumbnail" src="https://i.ytimg.com/vi/' +
        escapeHtml(encodeURIComponent(example.video_id)) +
        '/hqdefault.jpg" alt="" loading="lazy"></div>' +
        '<div><div class="example-topline"><span>EXAMPLE ' + (index + 1) + '</span>' +
        '<span class="decision-chip decision-' +
        escapeHtml(String(example.decision || "PENDING").toLowerCase()) + '">' +
        escapeHtml(example.decision || "PENDING") + '</span></div>' +
        '<h4>' + escapeHtml(example.title || example.video_id) + '</h4>' +
        '<p class="example-channel">' + escapeHtml(example.channel_title || "Unknown channel") + '</p>' +
        '<div class="example-stats"><span>' + escapeHtml(compactNumber(example.views)) + ' views</span>' +
        '<span>' + escapeHtml(example.duration_seconds == null ? "—" : example.duration_seconds) + ' sec</span>' +
        '<span>' + escapeHtml(example.age_days == null ? "—" : Math.round(Number(example.age_days))) + ' days old</span></div>' +
        '<p class="example-families"><strong>Matched:</strong> ' +
        escapeHtml((example.matched_families || []).join(", ") || "—") + '</p>' +
        '<div class="example-actions">' +
        (youtubeUrl ? '<a class="external-button" href="' + escapeHtml(youtubeUrl) +
          '" target="_blank" rel="noopener noreferrer">Open YouTube</a>' : '') +
        '<button class="gate-button keep" data-gate-action="KEEP_EXAMPLE" data-opportunity-id="' +
        escapeHtml(opportunity.opportunity_id) + '" data-video-id="' +
        escapeHtml(example.video_id) + '"' + (kept ? " disabled" : "") + '>' +
        (kept ? "Kept" : "Keep") + '</button>' +
        '<button class="gate-button replace" data-gate-action="REPLACE_EXAMPLE" data-opportunity-id="' +
        escapeHtml(opportunity.opportunity_id) + '" data-video-id="' +
        escapeHtml(example.video_id) + '"' +
        (opportunity.alternatives_available > 0 ? "" : " disabled") +
        '>Replace</button></div></div></section>';
    });

    html += '</div><div class="topic-actions"><div class="topic-action-copy">' +
      '<strong>Your decision</strong><span>Approve only after every selected example is kept.</span></div>' +
      '<div class="topic-action-buttons">' +
      '<button class="gate-button approve" data-gate-action="APPROVE_TOPIC" data-opportunity-id="' +
      escapeHtml(opportunity.opportunity_id) + '"' +
      (opportunity.can_approve && decision !== "APPROVE" ? "" : " disabled") +
      '>Approve Opportunity</button>' +
      '<button class="gate-button hold" data-gate-action="HOLD_TOPIC" data-opportunity-id="' +
      escapeHtml(opportunity.opportunity_id) + '"' +
      (decision === "HOLD" ? " disabled" : "") + '>Hold</button>' +
      '<button class="gate-button reject" data-gate-action="REJECT_TOPIC" data-opportunity-id="' +
      escapeHtml(opportunity.opportunity_id) + '"' +
      (decision === "REJECT" ? " disabled" : "") + '>Reject</button>' +
      '</div></div></article>';
  });

  opportunityGate.innerHTML = html;
}

function actionGroupTitle(stage) {
  if (stage === "OPPORTUNITY") return "OPPORTUNITY RESEARCH";
  return "EXPERIMENT " + stage;
}

function renderActionCollection(actions, target) {
  const groups = new Map();
  actions.forEach(function (action) {
    if (!groups.has(action.stage)) groups.set(action.stage, []);
    groups.get(action.stage).push(action);
  });

  let html = "";
  groups.forEach(function (items, stage) {
    html += '<section class="action-group"><div class="action-group-title">' +
      escapeHtml(actionGroupTitle(stage)) + '</div>';

    items.forEach(function (action) {
      const role = action.role || "normal";
      html += '<div class="action-row ' + escapeHtml(role) + '">' +
        '<div class="action-copy"><strong>' + escapeHtml(action.label) + '</strong>' +
        '<p>' + escapeHtml(action.description) + '</p>' +
        '<p class="reason">' + escapeHtml(action.reason) + '</p></div>' +
        '<button class="run-button ' + escapeHtml(role) + '" data-action="' +
        escapeHtml(action.id) + '"' + (action.enabled ? "" : " disabled") + '>' +
        (role === "do_now" ? "Run now" : "Run") + '</button></div>';
    });

    html += '</section>';
  });

  target.innerHTML = html || '<p class="empty-state">No actions available here yet.</p>';
}

function renderAnalysis(data) {
  const workflow = data.workflow || {};
  analysisCurrentTitle.textContent =
    workflow.current_action_id && workflow.current_action_id !== "opportunity_research"
      ? workflow.current_title
      : (data.opportunity_gate && data.opportunity_gate.ready_for_experiment_02
        ? "Prepare the approved source evidence"
        : "Waiting for opportunity approval");

  analysisCurrentDetail.textContent =
    data.opportunity_gate && data.opportunity_gate.ready_for_experiment_02
      ? (workflow.current_detail || "The next available analysis step is highlighted.")
      : "Approve an opportunity before Experiment 02 can begin.";

  const actions = (data.actions || []).filter(function (action) {
    return action.surface === "workflow" && action.id !== "opportunity_research";
  });
  renderActionCollection(actions, analysisActions);

  const currentId = workflow.current_action_id || "";
  const activeIndex = currentId === "exp2_prepare" ? 0 :
    ["analysis_batch_prepare", "analysis_model_one", "human_review_prepare", "synthesis_build"].includes(currentId) ? 1 : 0;
  creationTabs.forEach(function (tab, index) {
    tab.classList.toggle("active", index === activeIndex);
  });
}

function stateClass(stage) {
  const classes = [];
  if (stage.current) classes.push("current");
  if (!stage.ready) classes.push("blocked");
  if (stage.complete) classes.push("complete");
  return classes.join(" ");
}

function renderStages(stages) {
  stageGrid.innerHTML = (stages || []).map(function (stage) {
    const criteria = (stage.criteria || []).map(function (item) {
      return '<li class="' + (item.done ? "done" : "pending") + '">' +
        '<span>' + (item.done ? "✓" : "○") + '</span><span>' +
        escapeHtml(item.label) + '</span></li>';
    }).join("");

    return '<article class="stage-card ' + stateClass(stage) + '">' +
      '<div class="stage-id">EXPERIMENT ' + escapeHtml(stage.id) + '</div>' +
      '<div class="stage-title">' + escapeHtml(stage.title) + '</div>' +
      '<div class="human-status">' + escapeHtml(stage.human_status || stage.state) + '</div>' +
      '<div class="stage-detail">' + escapeHtml(stage.detail || "") + '</div>' +
      '<ul class="criteria-list">' + criteria + '</ul>' +
      '<div class="stage-next"><strong>Next:</strong> ' +
      escapeHtml(stage.next_action || "No action.") + '</div>' +
      '<div class="machine-state">Machine: ' + escapeHtml(stage.state || "") + '</div>' +
      '</article>';
  }).join("");
}

function renderTools(data) {
  const actions = (data.actions || []).filter(function (action) {
    return action.surface === "tools";
  });
  renderActionCollection(actions, toolActions);
  renderStages(data.stages || []);
}

function renderJob(job, log) {
  const hasJob = job && Object.keys(job).length;
  if (!hasJob) {
    jobSummaryButton.className = "job-summary neutral";
    jobSummaryStatus.textContent = "IDLE";
    jobSummaryLabel.textContent = "No job running";
    jobTitle.textContent = "No job running";
    jobMeta.innerHTML =
      '<span class="status-chip neutral">IDLE</span><span>Choose an enabled action to start.</span>';
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

  jobSummaryButton.className = "job-summary " + statusClass;
  jobSummaryStatus.textContent = job.status || "UNKNOWN";
  jobSummaryLabel.textContent = job.label || job.action_id || "Job";

  jobTitle.textContent = job.label || job.action_id || "Job";
  let meta =
    '<span class="status-chip ' + statusClass + '">' + escapeHtml(job.status || "UNKNOWN") + '</span>' +
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

function renderAll(data) {
  latestStatus = data;
  renderSidebarStatus(data.workflow || {});
  renderHomeWorkflow(data);
  renderProgress(data);
  renderHomeOpportunity(data.opportunity_gate || {});
  renderHomeActivity(data.job || {}, data.opportunity_research || {});
  renderOpportunityGate(data.opportunity_gate || {});
  renderAnalysis(data);
  renderTools(data);
  renderJob(data.job || {});
  renderRoute();
}

async function loadStatus() {
  try {
    const data = await api("/api/status");
    renderAll(data);
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
    openJobDrawer();
    showToast("Started: " + data.job.label, false);
    startJobPolling();
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function stopCurrentJob() {
  if (!confirm("Stop the running job?")) return;
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
    showToast("Opportunity updated.", false);
    await loadStatus();
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

document.addEventListener("click", function (event) {
  const routeTarget = event.target.closest("[data-route]");
  if (routeTarget) {
    event.preventDefault();
    navigate(routeTarget.dataset.route);
    return;
  }

  const actionTarget = event.target.closest("[data-action]");
  if (actionTarget) {
    runAction(actionTarget.dataset.action);
    return;
  }

  const openTargetButton = event.target.closest("[data-open]");
  if (openTargetButton) {
    openTarget(openTargetButton.dataset.open);
    return;
  }

  const gateButton = event.target.closest("[data-gate-action]");
  if (gateButton) {
    const action = gateButton.dataset.gateAction;
    if (
      action === "REJECT_TOPIC" &&
      !confirm("Reject this opportunity and keep analysis locked for it?")
    ) {
      return;
    }
    submitGateAction(
      action,
      gateButton.dataset.opportunityId,
      gateButton.dataset.videoId || null
    );
    return;
  }

  if (event.target.closest("[data-job-drawer]")) {
    openJobDrawer();
  }
});

window.addEventListener("popstate", renderRoute);
refreshStatus.addEventListener("click", loadStatus);
jobSummaryButton.addEventListener("click", openJobDrawer);
closeJobDrawer.addEventListener("click", closeJob);
drawerScrim.addEventListener("click", closeJob);
stopJob.addEventListener("click", stopCurrentJob);
mobileMenu.addEventListener("click", openSidebar);
sidebarScrim.addEventListener("click", closeSidebar);

renderRoute();
loadStatus();
setInterval(loadStatus, 5000);
