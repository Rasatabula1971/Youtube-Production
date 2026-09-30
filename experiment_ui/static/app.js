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

const visionReviewPanel = document.getElementById("visionReviewPanel");
const visionReviewTitle = document.getElementById("visionReviewTitle");
const visionReviewSummary = document.getElementById("visionReviewSummary");
const visionReviewStatus = document.getElementById("visionReviewStatus");
const visionFrameImage = document.getElementById("visionFrameImage");
const visionFrameMeta = document.getElementById("visionFrameMeta");
const visionProposal = document.getElementById("visionProposal");
const visionObservation = document.getElementById("visionObservation");
const visionPrev = document.getElementById("visionPrev");
const visionReject = document.getElementById("visionReject");
const visionAccept = document.getElementById("visionAccept");
const visionNext = document.getElementById("visionNext");

const humanAnalysisReviewPanel = document.getElementById("humanAnalysisReviewPanel");
const humanAnalysisReviewTitle = document.getElementById("humanAnalysisReviewTitle");
const humanAnalysisReviewSummary = document.getElementById("humanAnalysisReviewSummary");
const humanAnalysisReviewStatus = document.getElementById("humanAnalysisReviewStatus");
const humanAnalysisDetail = document.getElementById("humanAnalysisDetail");
const humanAnalysisNote = document.getElementById("humanAnalysisNote");
const humanAnalysisPrev = document.getElementById("humanAnalysisPrev");
const humanAnalysisReject = document.getElementById("humanAnalysisReject");
const humanAnalysisAccept = document.getElementById("humanAnalysisAccept");
const humanAnalysisNext = document.getElementById("humanAnalysisNext");

const conceptReviewPanel = document.getElementById("conceptReviewPanel");
const conceptReviewTitle = document.getElementById("conceptReviewTitle");
const conceptReviewSummary = document.getElementById("conceptReviewSummary");
const conceptReviewStatus = document.getElementById("conceptReviewStatus");
const conceptDetail = document.getElementById("conceptDetail");
const conceptOverridesPanel = document.getElementById("conceptOverridesPanel");
const conceptOverrides = document.getElementById("conceptOverrides");
const savedIdeasPanel = document.getElementById("savedIdeasPanel");
const savedIdeasSummary = document.getElementById("savedIdeasSummary");
const savedIdeas = document.getElementById("savedIdeas");
const conceptCriteria = document.getElementById("conceptCriteria");
const conceptNote = document.getElementById("conceptNote");
const conceptPrev = document.getElementById("conceptPrev");
const conceptReject = document.getElementById("conceptReject");
const conceptRework = document.getElementById("conceptRework");
const conceptSaveIdea = document.getElementById("conceptSaveIdea");
const conceptAccept = document.getElementById("conceptAccept");
const conceptNext = document.getElementById("conceptNext");

const packagingReviewPanel = document.getElementById("packagingReviewPanel");
const packagingReviewTitle = document.getElementById("packagingReviewTitle");
const packagingReviewSummary = document.getElementById("packagingReviewSummary");
const packagingReviewStatus = document.getElementById("packagingReviewStatus");
const packagingDetail = document.getElementById("packagingDetail");
const packagingCriteria = document.getElementById("packagingCriteria");
const packagingNote = document.getElementById("packagingNote");
const packagingPrev = document.getElementById("packagingPrev");
const packagingReject = document.getElementById("packagingReject");
const packagingRework = document.getElementById("packagingRework");
const packagingAccept = document.getElementById("packagingAccept");
const packagingNext = document.getElementById("packagingNext");

const researchReviewPanel = document.getElementById("researchReviewPanel");
const researchReviewTitle = document.getElementById("researchReviewTitle");
const researchReviewSummary = document.getElementById("researchReviewSummary");
const researchReviewStatus = document.getElementById("researchReviewStatus");
const researchDetail = document.getElementById("researchDetail");
const researchCriteria = document.getElementById("researchCriteria");
const researchNote = document.getElementById("researchNote");
const researchPrev = document.getElementById("researchPrev");
const researchReject = document.getElementById("researchReject");
const researchRework = document.getElementById("researchRework");
const researchAccept = document.getElementById("researchAccept");
const researchNext = document.getElementById("researchNext");

const scriptReviewPanel = document.getElementById("scriptReviewPanel");
const scriptReviewTitle = document.getElementById("scriptReviewTitle");
const scriptReviewSummary = document.getElementById("scriptReviewSummary");
const scriptReviewStatus = document.getElementById("scriptReviewStatus");
const scriptDetail = document.getElementById("scriptDetail");
const scriptCriteria = document.getElementById("scriptCriteria");
const scriptNote = document.getElementById("scriptNote");
const scriptPrev = document.getElementById("scriptPrev");
const scriptReject = document.getElementById("scriptReject");
const scriptRework = document.getElementById("scriptRework");
const scriptAccept = document.getElementById("scriptAccept");
const scriptNext = document.getElementById("scriptNext");

const formatReviewPanel = document.getElementById("formatReviewPanel");
const formatReviewTitle = document.getElementById("formatReviewTitle");
const formatReviewSummary = document.getElementById("formatReviewSummary");
const formatReviewStatus = document.getElementById("formatReviewStatus");
const formatDetail = document.getElementById("formatDetail");
const formatCriteria = document.getElementById("formatCriteria");
const formatNote = document.getElementById("formatNote");
const formatPrev = document.getElementById("formatPrev");
const formatReject = document.getElementById("formatReject");
const formatRework = document.getElementById("formatRework");
const formatAccept = document.getElementById("formatAccept");
const formatNext = document.getElementById("formatNext");

const performanceReviewPanel = document.getElementById("performanceReviewPanel");
const performanceReviewTitle = document.getElementById("performanceReviewTitle");
const performanceReviewSummary = document.getElementById("performanceReviewSummary");
const performanceReviewStatus = document.getElementById("performanceReviewStatus");
const performanceDetail = document.getElementById("performanceDetail");
const performanceCriteria = document.getElementById("performanceCriteria");
const performanceNote = document.getElementById("performanceNote");
const performancePrev = document.getElementById("performancePrev");
const performanceReject = document.getElementById("performanceReject");
const performanceRework = document.getElementById("performanceRework");
const performanceAccept = document.getElementById("performanceAccept");
const performanceNext = document.getElementById("performanceNext");

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
let csrfToken = "";
let renderedPath = null;
let latestVisionSnapshot = null;
let visionCursor = 0;
let visionEditing = false;
let latestHumanAnalysisSnapshot = null;
let humanAnalysisCursor = 0;
let humanAnalysisEditing = false;
let latestConceptSnapshot = null;
let conceptCursor = 0;
let conceptEditing = false;
let latestPackagingSnapshot = null;
let packagingCursor = 0;
let packagingEditing = false;
let latestResearchSnapshot = null;
let researchCursor = 0;
let researchEditing = false;
let latestScriptSnapshot = null;
let scriptCursor = 0;
let scriptEditing = false;
let latestFormatSnapshot = null;
let formatCursor = 0;
let formatEditing = false;
let latestPerformanceSnapshot = null;
let performanceCursor = 0;
let performanceEditing = false;

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
  const requestOptions = Object.assign({}, options || {});
  const headers = Object.assign(
    { "Content-Type": "application/json" },
    requestOptions.headers || {}
  );
  if (String(requestOptions.method || "GET").toUpperCase() !== "GET") {
    if (!csrfToken) {
      throw new Error("Security token is not loaded yet. Refresh the page.");
    }
    headers["X-CSRF-Token"] = csrfToken;
  }
  requestOptions.headers = headers;
  const response = await fetch(url, requestOptions);

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

function renderRoute(options) {
  const path = normalizedPath();
  const route = ROUTES[path];
  const shouldScroll = Boolean(options && options.scroll) || renderedPath === null;

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
  if (shouldScroll && renderedPath !== path) {
    window.scrollTo({ top: 0, behavior: "auto" });
  }
  renderedPath = path;
}

function navigate(path) {
  const target = Object.prototype.hasOwnProperty.call(ROUTES, path) ? path : "/";
  if (window.location.pathname !== target) {
    history.pushState({}, "", target);
  }
  renderRoute({ scroll: true });
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
  if (
    state === "ACTION_REQUIRED" ||
    state === "HUMAN_GATE" ||
    state === "HUMAN_VISION_GATE" ||
    state === "HUMAN_ANALYSIS_GATE" ||
    state === "HUMAN_CONCEPT_GATE" ||
    state === "HUMAN_SCRIPT_GATE"
  ) return "attention";
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
  if (workflow.state === "HUMAN_VISION_GATE") {
    return { type: "route", value: "/analysis", label: "Review visual evidence" };
  }
  if (workflow.state === "HUMAN_ANALYSIS_GATE") {
    return { type: "route", value: "/analysis", label: "Review analysis findings" };
  }
  if (workflow.state === "HUMAN_SCRIPT_GATE") {
    return { type: "route", value: "/analysis", label: "Review script" };
  }
  if (workflow.state === "HUMAN_CONCEPT_GATE") {
    return { type: "route", value: "/analysis", label: "Review concepts" };
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
  const s4 = stageById(stages, "04");
  const gate = data.opportunity_gate || {};
  const workflow = data.workflow || {};

  const discoveryDone = Boolean((s13.criteria || [])[0] && s13.criteria[0].done);
  const validationDone = Boolean(s13.complete);
  const expansionDone = Boolean(s14.complete);
  const reviewDone = Boolean(gate.ready_for_experiment_02);
  const analysisDone = Boolean(s2.complete);
  const createDone = Boolean(s4.complete);

  const currentName =
    workflow.state === "HUMAN_GATE" ? "Review" :
    workflow.current_action_id === "opportunity_research" ||
    workflow.state === "WAITING_AUTOMATIC" ||
    workflow.state === "RUNNING_AUTOMATIC" ? (
      validationDone ? "Expand" : (discoveryDone ? "Validate" : "Discover")
    ) :
    reviewDone && !analysisDone ? "Analyze" :
    analysisDone && !createDone ? "Create" :
    createDone ? "" : "";

  const steps = [
    { name: "Discover", done: discoveryDone },
    { name: "Validate", done: validationDone },
    { name: "Expand", done: expansionDone },
    { name: "Review", done: reviewDone },
    { name: "Analyze", done: analysisDone },
    { name: "Create", done: createDone }
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
  const vidiq = gate.vidiq || {};
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
    '</div>' +
    '<div class="gate-summary"><div class="gate-summary-copy">' +
      '<strong>vidIQ supplemental check</strong><span>' +
      escapeHtml(
        (vidiq.status || "NOT_RUN") +
        (vidiq.provider_remaining_credits == null
          ? ""
          : " · " + vidiq.provider_remaining_credits + " provider credits remaining") +
        (vidiq.local_charged_credits == null
          ? ""
          : " · " + vidiq.local_charged_credits + "/" + (vidiq.hard_credit_cap || 149) + " local credits reserved")
      ) +
      '</span><span class="muted">Runs automatically before this Human Opportunity Gate when its safety checks are READY.</span></div>' +
    '</div>';

  (gate.opportunities || []).forEach(function (opportunity) {
    const evidence = opportunity.topic_evidence || {};
    const vidiqEvidence = opportunity.vidiq_evidence || {};
    const vidiqTools = vidiqEvidence.tools || {};
    const decision = opportunity.decision || "PENDING";
    const vidiqRows = ["keyword_research", "outliers", "trending_videos"].map(function (toolName) {
      const item = vidiqTools[toolName] || {};
      return '<div class="concept-detail-card"><h4>' +
        escapeHtml(humanizeToken(toolName)) + '</h4><p><strong>' +
        escapeHtml(item.status || "NOT_RUN") + '</strong>' +
        (item.preview ? '<br>' + escapeHtml(item.preview) : '') +
        '</p></div>';
    }).join("");

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
      '</strong></div></div>' +
      (vidiqRows
        ? '<details class="technical-details"><summary>vidIQ market evidence</summary>' +
          '<div class="technical-body">' + vidiqRows + '</div></details>'
        : '') +
      '<div class="example-grid">';

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

function flattenVisionFrames(snapshot) {
  const items = [];
  (snapshot && snapshot.packets || []).forEach(function (packet) {
    (packet.frames || []).forEach(function (frame) {
      items.push({
        video_id: packet.video_id,
        provider: packet.provider,
        model: packet.model,
        packet_status: packet.status,
        counts: packet.counts || {},
        frame: frame
      });
    });
  });
  return items;
}

function pendingVisionIndex(items) {
  return items.findIndex(function (item) {
    return item.frame && item.frame.decision === "PENDING";
  });
}

function currentVisionItem() {
  const items = flattenVisionFrames(latestVisionSnapshot || {});
  if (!items.length) return null;
  visionCursor = Math.max(0, Math.min(visionCursor, items.length - 1));
  return { item: items[visionCursor], items: items };
}

function renderVisionReview(snapshot, force) {
  latestVisionSnapshot = snapshot || {};

  if (
    !snapshot ||
    snapshot.status === "NOT_APPLICABLE" ||
    snapshot.status === "READY_TO_PREPARE" ||
    !(snapshot.packets || []).length
  ) {
    visionReviewPanel.hidden = true;
    return;
  }

  if (snapshot.complete) {
    visionReviewPanel.hidden = false;
    visionReviewTitle.textContent = "Visual evidence reviewed";
    visionReviewSummary.textContent =
      "Accepted observations have been ingested into the current Experiment 02 profiles.";
    visionReviewStatus.textContent = "COMPLETE";
    visionReviewStatus.className = "status-chip success";
    visionFrameImage.removeAttribute("src");
    visionFrameImage.hidden = true;
    visionFrameMeta.innerHTML = "";
    visionProposal.innerHTML =
      '<div class="vision-review-complete">Visual review is complete. The next analysis step can continue.</div>';
    visionObservation.hidden = true;
    visionPrev.disabled = true;
    visionNext.disabled = true;
    visionReject.disabled = true;
    visionAccept.disabled = true;
    return;
  }

  if (visionEditing && !force) return;

  const items = flattenVisionFrames(snapshot);
  if (!items.length) {
    visionReviewPanel.hidden = true;
    return;
  }

  if (visionCursor >= items.length) {
    visionCursor = Math.max(0, items.length - 1);
  }

  const entry = items[visionCursor];
  const frame = entry.frame || {};
  const proposal = frame.proposal || null;
  const counts = snapshot.packets.reduce(function (acc, packet) {
    const value = packet.counts || {};
    acc.total += Number(value.total || 0);
    acc.pending += Number(value.pending || 0);
    acc.accepted += Number(value.accepted || 0);
    acc.rejected += Number(value.rejected || 0);
    return acc;
  }, { total: 0, pending: 0, accepted: 0, rejected: 0 });

  visionReviewPanel.hidden = false;
  visionFrameImage.hidden = false;
  visionObservation.hidden = false;
  visionFrameImage.src =
    "/api/vision-frame?video_id=" + encodeURIComponent(entry.video_id) +
    "&frame_id=" + encodeURIComponent(frame.frame_id || "");
  visionReviewTitle.textContent =
    "Frame " + (visionCursor + 1) + " of " + items.length;
  visionReviewSummary.textContent =
    counts.pending + " pending · " +
    counts.accepted + " accepted · " +
    counts.rejected + " rejected";
  visionReviewStatus.textContent = frame.decision || "PENDING";
  visionReviewStatus.className =
    "status-chip " +
    (frame.decision === "ACCEPT"
      ? "success"
      : frame.decision === "REJECT"
        ? "failed"
        : "running");

  visionFrameMeta.innerHTML =
    '<span>Video ' + escapeHtml(entry.video_id) + '</span>' +
    '<span>' + escapeHtml(humanizeToken(frame.kind)) + '</span>' +
    '<span>' + escapeHtml(
      Number(frame.timestamp_seconds || 0).toFixed(3)
    ) + ' sec</span>' +
    '<span>' + escapeHtml(
      entry.provider === "ollama"
        ? "Drafted by local vision model"
        : "Human observation required"
    ) + '</span>';

  if (proposal) {
    visionProposal.innerHTML =
      '<strong>MODEL DRAFT — NOT EVIDENCE YET</strong>' +
      '<div>' + escapeHtml(proposal.observation || "") + '</div>' +
      (proposal.uncertainty
        ? '<div class="muted">Uncertainty: ' +
          escapeHtml(proposal.uncertainty) + '</div>'
        : '') +
      '<div class="muted">Confidence: ' +
      escapeHtml(proposal.confidence || "LOW") + '</div>';
  } else {
    visionProposal.innerHTML =
      '<strong>HUMAN REVIEW</strong>' +
      '<div>No model draft is available. Describe only what is directly visible, or reject the frame if it adds no useful evidence.</div>';
  }

  visionObservation.value =
    frame.final_observation ||
    (proposal && proposal.observation) ||
    "";
  visionPrev.disabled = visionCursor <= 0;
  visionNext.disabled = visionCursor >= items.length - 1;
  visionReject.disabled = false;
  visionAccept.disabled = false;
  visionEditing = false;
}

function moveVisionCursor(delta) {
  const current = currentVisionItem();
  if (!current) return;
  visionCursor = Math.max(
    0,
    Math.min(current.items.length - 1, visionCursor + delta)
  );
  visionEditing = false;
  renderVisionReview(latestVisionSnapshot, true);
}

async function submitVisionDecision(action) {
  const current = currentVisionItem();
  if (!current) return;
  const entry = current.item;
  const frame = entry.frame || {};

  try {
    const payload = await api("/api/vision-review", {
      method: "POST",
      body: JSON.stringify({
        action: action,
        video_id: entry.video_id,
        frame_id: frame.frame_id,
        observation: action === "ACCEPT_FRAME"
          ? visionObservation.value
          : null
      })
    });
    visionEditing = false;
    latestVisionSnapshot = payload;
    const items = flattenVisionFrames(payload);
    const nextPending = pendingVisionIndex(items);
    if (nextPending >= 0) visionCursor = nextPending;
    renderVisionReview(payload, true);
    showToast(
      action === "ACCEPT_FRAME"
        ? "Visual observation accepted."
        : "Frame rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function pendingHumanAnalysisIndex(items) {
  return (items || []).findIndex(function (item) {
    return item && item.decision === "PENDING";
  });
}

function currentHumanAnalysisItem() {
  const items = (latestHumanAnalysisSnapshot && latestHumanAnalysisSnapshot.items) || [];
  if (!items.length) return null;
  humanAnalysisCursor = Math.max(0, Math.min(humanAnalysisCursor, items.length - 1));
  return { item: items[humanAnalysisCursor], items: items };
}

function renderHumanAnalysisReview(snapshot, force) {
  latestHumanAnalysisSnapshot = snapshot || {};

  if (
    !snapshot ||
    snapshot.status === "READY_TO_PREPARE" ||
    !(snapshot.items || []).length
  ) {
    humanAnalysisReviewPanel.hidden = true;
    return;
  }

  if (snapshot.complete) {
    humanAnalysisReviewPanel.hidden = false;
    humanAnalysisReviewTitle.textContent = "Human Analysis Gate complete";
    humanAnalysisReviewSummary.textContent =
      (snapshot.accepted || 0) + " accepted · " +
      (snapshot.rejected || 0) + " rejected";
    humanAnalysisReviewStatus.textContent = "COMPLETE";
    humanAnalysisReviewStatus.className = "status-chip success";
    humanAnalysisDetail.innerHTML =
      '<div class="concept-complete">All current analysis findings have been reviewed. Synthesis can continue.</div>';
    humanAnalysisNote.hidden = true;
    humanAnalysisPrev.disabled = true;
    humanAnalysisNext.disabled = true;
    humanAnalysisReject.disabled = true;
    humanAnalysisAccept.disabled = true;
    return;
  }

  if (humanAnalysisEditing && !force) return;

  const items = snapshot.items || [];
  if (humanAnalysisCursor >= items.length) {
    humanAnalysisCursor = Math.max(0, items.length - 1);
  }
  const item = items[humanAnalysisCursor] || {};
  const evidence = item.supporting_evidence || [];
  const mechanismIds = item.mechanism_ids || [];

  humanAnalysisReviewPanel.hidden = false;
  humanAnalysisNote.hidden = false;
  humanAnalysisReviewTitle.textContent =
    "Finding " + (humanAnalysisCursor + 1) + " of " + items.length;
  humanAnalysisReviewSummary.textContent =
    (snapshot.pending || 0) + " pending · " +
    (snapshot.accepted || 0) + " accepted · " +
    (snapshot.rejected || 0) + " rejected";
  humanAnalysisReviewStatus.textContent = item.decision || "PENDING";
  humanAnalysisReviewStatus.className =
    "status-chip " +
    (item.decision === "ACCEPT"
      ? "success"
      : item.decision === "REJECT"
        ? "failed"
        : "running");

  const evidenceHtml = evidence.map(function (row) {
    return '<div class="analysis-evidence-card">' +
      '<div class="analysis-evidence-meta">' +
        '<span>' + escapeHtml(row.evidence_id || "") + '</span>' +
        '<span>' + escapeHtml(humanizeToken(row.type || "")) + '</span>' +
        '<span>' + escapeHtml(row.locator || "") + '</span>' +
      '</div>' +
      '<p>' + escapeHtml(row.observation || "") + '</p>' +
    '</div>';
  }).join("");

  humanAnalysisDetail.innerHTML =
    '<div class="concept-detail-card">' +
      '<h4>' + escapeHtml(humanizeToken(item.kind || "analysis finding")) + '</h4>' +
      '<h3>' + escapeHtml(item.statement || "") + '</h3>' +
      '<div class="concept-meta">' +
        '<span>Video ' + escapeHtml(item.video_id || "") + '</span>' +
        '<span>' + escapeHtml(humanizeToken(item.dimension || "")) + '</span>' +
        '<span>Confidence ' + escapeHtml(item.confidence || "—") + '</span>' +
      '</div>' +
      (mechanismIds.length
        ? '<div class="concept-meta"><span>Mechanisms: ' +
          escapeHtml(mechanismIds.join(", ")) + '</span></div>'
        : '') +
    '</div>' +
    '<div class="concept-detail-card"><h4>SUPPORTING EVIDENCE</h4>' +
      (evidenceHtml || '<p>No supporting evidence was attached.</p>') +
    '</div>';

  humanAnalysisNote.value = item.note || "";
  humanAnalysisPrev.disabled = humanAnalysisCursor <= 0;
  humanAnalysisNext.disabled = humanAnalysisCursor >= items.length - 1;
  humanAnalysisReject.disabled = false;
  humanAnalysisAccept.disabled = false;
  humanAnalysisEditing = false;
}

function moveHumanAnalysisCursor(delta) {
  const current = currentHumanAnalysisItem();
  if (!current) return;
  humanAnalysisCursor = Math.max(
    0,
    Math.min(current.items.length - 1, humanAnalysisCursor + delta)
  );
  humanAnalysisEditing = false;
  renderHumanAnalysisReview(latestHumanAnalysisSnapshot, true);
}

async function submitHumanAnalysisDecision(decision) {
  const current = currentHumanAnalysisItem();
  if (!current) return;
  const item = current.item;

  try {
    const payload = await api("/api/human-analysis-review", {
      method: "POST",
      body: JSON.stringify({
        video_id: item.video_id,
        item_id: item.item_id,
        decision: decision,
        note: humanAnalysisNote.value
      })
    });
    humanAnalysisEditing = false;
    latestHumanAnalysisSnapshot = payload;
    const nextPending = pendingHumanAnalysisIndex(payload.items || []);
    if (nextPending >= 0) humanAnalysisCursor = nextPending;
    renderHumanAnalysisReview(payload, true);
    showToast(
      decision === "ACCEPT"
        ? "Analysis finding accepted."
        : "Analysis finding rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function pendingConceptIndex(items) {
  return (items || []).findIndex(function (item) {
    return item && item.decision === "PENDING";
  });
}

function currentConceptItem() {
  const items = (latestConceptSnapshot && latestConceptSnapshot.concepts) || [];
  if (!items.length) return null;
  conceptCursor = Math.max(0, Math.min(conceptCursor, items.length - 1));
  return { item: items[conceptCursor], items: items };
}

function renderConceptOverrides(snapshot) {
  const items = (snapshot && snapshot.override_concepts) || [];
  const complete = Boolean(snapshot && snapshot.complete);
  conceptOverridesPanel.hidden = items.length === 0;
  conceptOverrides.innerHTML = items.map(function (item) {
    const triage = item.llm_triage || {};
    const reviewButton = complete
      ? ""
      : '<button class="ghost" type="button" data-concept-override="' +
        escapeHtml(item.concept_id) + '">Review anyway</button>';
    const saveButton = '<button class="ghost" type="button" data-concept-save="' +
      escapeHtml(item.concept_id) + '"' +
      (item.idea_saved ? " disabled" : "") + '>' +
      (item.idea_saved ? "Saved" : "Save idea") + '</button>';
    return '<div class="concept-detail-card">' +
      '<h4>' + escapeHtml(triage.decision || "TRIAGE") + ' · ' +
      escapeHtml(triage.overall_score == null ? "—" : triage.overall_score + "/100") + '</h4>' +
      '<h3>' + escapeHtml(item.working_title || item.concept_id) + '</h3>' +
      '<p>' + escapeHtml(triage.rationale || "") + '</p>' +
      reviewButton + saveButton +
      '</div>';
  }).join("");
}

function renderSavedIdeas(snapshot) {
  const items = (snapshot && snapshot.saved_ideas) || [];
  savedIdeasPanel.hidden = items.length === 0;
  savedIdeasSummary.textContent = "Saved Ideas / Title Bank (" + items.length + ")";
  savedIdeas.innerHTML = items.slice().reverse().map(function (item) {
    const triage = item.triage_score == null
      ? "No triage score"
      : String(item.triage_score) + "/100";
    const note = item.note
      ? '<p><strong>Note:</strong> ' + escapeHtml(item.note) + '</p>'
      : "";
    return '<div class="concept-detail-card">' +
      '<h4>' + escapeHtml(triage) + ' · ' +
      escapeHtml(item.triage_decision || "SAVED") + '</h4>' +
      '<h3>' + escapeHtml(item.working_title || item.concept_id || "Saved idea") + '</h3>' +
      '<p>' + escapeHtml(item.premise || "") + '</p>' +
      note +
      '</div>';
  }).join("");
}

function renderConceptReview(snapshot, force) {
  latestConceptSnapshot = snapshot || {};
  renderConceptOverrides(snapshot || {});
  renderSavedIdeas(snapshot || {});

  if (
    !snapshot ||
    snapshot.status === "WAITING_FOR_CONCEPT_CANDIDATES" ||
    snapshot.status === "READY_TO_PREPARE" ||
    !(snapshot.concepts || []).length
  ) {
    if ((snapshot.override_concepts || []).length) {
      conceptReviewPanel.hidden = false;
      conceptReviewTitle.textContent = "No default concepts shortlisted";
      conceptReviewSummary.textContent = "Review an override only if you disagree with triage.";
      conceptReviewStatus.textContent = "0 SHORTLISTED";
      conceptReviewStatus.className = "status-chip running";
      conceptDetail.innerHTML = '<div class="concept-complete">Triage found no concept strong enough for the default Human Gate.</div>';
      conceptCriteria.innerHTML = "";
      conceptNote.hidden = true;
      conceptReject.disabled = true;
      conceptRework.disabled = true;
      conceptSaveIdea.disabled = true;
      conceptAccept.disabled = true;
      conceptPrev.disabled = true;
      conceptNext.disabled = true;
      return;
    }
    conceptReviewPanel.hidden = true;
    return;
  }

  if (snapshot.complete) {
    const closedItems = snapshot.concepts || [];
    const closedCards = closedItems.map(function (item) {
      return '<div class="concept-detail-card">' +
        '<h4>' + escapeHtml(item.decision || "CLOSED") + '</h4>' +
        '<h3>' + escapeHtml(item.working_title || item.concept_id) + '</h3>' +
        '<button class="ghost" type="button" data-concept-save="' +
        escapeHtml(item.concept_id) + '"' +
        (item.idea_saved ? " disabled" : "") + '>' +
        (item.idea_saved ? "Saved" : "Save idea") + '</button>' +
        '</div>';
    }).join("");

    conceptReviewPanel.hidden = false;
    conceptReviewTitle.textContent = "Concept Gate complete";
    conceptReviewSummary.textContent =
      (snapshot.accepted || 0) + " accepted · " +
      (snapshot.rework || 0) + " rework · " +
      (snapshot.rejected || 0) + " rejected · " +
      (snapshot.saved || 0) + " saved for later";
    conceptReviewStatus.textContent = snapshot.research_status || "COMPLETE";
    conceptReviewStatus.className =
      "status-chip " + ((snapshot.accepted || 0) > 0 ? "success" : "failed");
    conceptDetail.innerHTML =
      '<div class="concept-complete">' +
      ((snapshot.accepted || 0) > 0
        ? "Accepted concepts are ready for the next Research / Packaging stage."
        : "No concept was accepted. Regenerate or rework before continuing.") +
      '</div>' +
      (closedCards
        ? '<details class="technical-details"><summary>Closed-gate concepts</summary>' +
          '<div class="technical-body">' + closedCards + '</div></details>'
        : "");
    conceptCriteria.innerHTML = "";
    conceptNote.hidden = true;
    conceptPrev.disabled = true;
    conceptNext.disabled = true;
    conceptReject.disabled = true;
    conceptRework.disabled = true;
    conceptSaveIdea.disabled = true;
    conceptAccept.disabled = true;
    return;
  }

  if (conceptEditing && !force) return;

  const items = snapshot.concepts || [];
  if (!items.length) {
    conceptReviewPanel.hidden = true;
    return;
  }
  if (conceptCursor >= items.length) {
    conceptCursor = Math.max(0, items.length - 1);
  }

  const concept = items[conceptCursor] || {};
  const needEvidence = concept.viewer_need_evidence || {};
  const framing = concept.human_framing || {};
  const hookExperience = framing.hook_experience || {};
  const pull = framing.psychological_pull || {};
  const visualOpening = framing.visual_opening_plan || {};
  const drama = framing.drama || {};
  const gap = concept.content_gap || {};
  const fit = concept.channel_fit || {};
  const titleTest = concept.title_clarity_test || {};
  const sourceTest = concept.source_dependency_test || {};
  const triage = concept.llm_triage || {};
  const overlap = concept.source_overlap || {};

  conceptReviewPanel.hidden = false;
  conceptNote.hidden = false;
  conceptReviewTitle.textContent =
    "Concept " + (conceptCursor + 1) + " of " + items.length;
  conceptReviewSummary.textContent =
    (snapshot.pending || 0) + " pending · reviewer " +
    escapeHtml(snapshot.reviewer || "local-operator");
  conceptReviewStatus.textContent = concept.decision || "PENDING";
  conceptReviewStatus.className =
    "status-chip " +
    (concept.decision === "ACCEPT"
      ? "success"
      : concept.decision === "REJECT"
        ? "failed"
        : "running");

  const titles = (titleTest.options || []).map(function (title) {
    return "<li>" + escapeHtml(title) + "</li>";
  }).join("");
  const questions = (concept.research_questions || []).map(function (question) {
    return "<li>" + escapeHtml(question) + "</li>";
  }).join("");
  const needBasis = (needEvidence.evidence_basis || []).map(function (item) {
    return "<li>" + escapeHtml(item) + "</li>";
  }).join("");

  const openingMoments = (visualOpening.moments || []).map(function (moment, index) {
    return "<li><strong>" + escapeHtml("Moment " + (index + 1)) + ":</strong> " +
      escapeHtml(moment.visual || "") + " <span class=\"muted\">— " +
      escapeHtml(moment.purpose || "") + "</span></li>";
  }).join("");
  const dramaCurve = (drama.story_curve || []).join(" → ");
  const tempoCurve = (drama.tempo_curve || []).join(" → ");

  conceptDetail.innerHTML =
    '<div class="concept-detail-card">' +
      '<h4>WORKING CONCEPT</h4>' +
      '<h3>' + escapeHtml(concept.working_title || concept.concept_id) + '</h3>' +
      '<div class="concept-meta">' +
        '<span>' + escapeHtml(humanizeToken(concept.mechanism_label || concept.mechanism_id)) + '</span>' +
        '<span>' + escapeHtml(humanizeToken(concept.format_intent)) + '</span>' +
      '</div>' +
    '</div>' +
    '<div class="concept-detail-card"><h4>LLM TRIAGE</h4><p>' +
      '<strong>Score:</strong> ' + escapeHtml(triage.overall_score == null ? "—" : triage.overall_score + "/100") +
      '<br><strong>Decision:</strong> ' + escapeHtml(triage.decision || "—") +
      '<br><strong>Why:</strong> ' + escapeHtml(triage.rationale || "") +
      '<br><strong>Strengths:</strong> ' + escapeHtml((triage.strengths || []).join(" · ") || "—") +
      '<br><strong>Risks:</strong> ' + escapeHtml((triage.risks || []).join(" · ") || "—") +
      '</p></div>' +
    (overlap.matches && overlap.matches.length
      ? '<div class="concept-detail-card"><h4>SOURCE OVERLAP CHECK</h4><p>' +
        overlap.matches.map(function (match) {
          return escapeHtml((match.blocking ? "BLOCK " : "WARN ") + match.word_count + " words: " + match.overlap_text);
        }).join("<br>") + '</p></div>'
      : '') +
    '<div class="concept-detail-card"><h4>PREMISE</h4><p>' +
      escapeHtml(concept.premise || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>AUDIENCE PROMISE</h4><p>' +
      escapeHtml(concept.audience_promise || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>HUMAN FRAMING</h4><p>' +
      '<strong>Hook experience:</strong> ' +
      escapeHtml(hookExperience.description || "") +
      '<br><strong>Hook archetype:</strong> ' +
      escapeHtml(humanizeToken(hookExperience.archetype || "")) +
      '<br><strong>Viewer question:</strong> ' +
      escapeHtml(framing.viewer_question || "") +
      '<br><strong>Primary pull:</strong> ' +
      escapeHtml(humanizeToken(pull.primary_pull || "")) +
      '<br><strong>Expectation:</strong> ' +
      escapeHtml(pull.viewer_expectation || "") +
      '<br><strong>Tension:</strong> ' +
      escapeHtml(pull.violation_or_tension || "") +
      '<br><strong>Stakes:</strong> ' +
      escapeHtml(pull.stakes || "") +
      '<br><strong>Information gap:</strong> ' +
      escapeHtml(pull.information_gap || "") +
      '<br><strong>Payoff:</strong> ' +
      escapeHtml(framing.explanation_payoff || "") +
      '</p></div>' +
    '<div class="concept-detail-card"><h4>DRAMA / TEMPO</h4><p>' +
      '<strong>Capacity:</strong> ' + escapeHtml(drama.capacity == null ? "—" : drama.capacity + "/10") +
      '<br><strong>Target:</strong> ' + escapeHtml(drama.target == null ? "—" : drama.target + "/10") +
      '<br><strong>Hook:</strong> ' + escapeHtml(drama.hook_level == null ? "—" : drama.hook_level + "/10") +
      '<br><strong>Drama source:</strong> ' + escapeHtml(drama.source || "") +
      '<br><strong>Do not exaggerate:</strong> ' + escapeHtml(drama.constraint || "") +
      '<br><strong>Drama curve:</strong> ' + escapeHtml(dramaCurve || "—") +
      '<br><strong>Tempo curve:</strong> ' + escapeHtml(tempoCurve || "—") +
      '</p></div>' +
    '<div class="concept-detail-card"><h4>VISUAL OPENING PLAN</h4>' +
      (openingMoments ? '<ol>' + openingMoments + '</ol>' : '<p>—</p>') +
      '<p><strong>Narration intent:</strong> ' +
      escapeHtml(visualOpening.opening_narration_intent || "") +
      '</p></div>' +
    '<div class="concept-detail-card"><h4>VIEWER NEED</h4><p><strong>Problem:</strong> ' +
      escapeHtml(concept.viewer_problem || "") + '<br><strong>Moment:</strong> ' +
      escapeHtml(concept.viewer_moment || "") + '<br><strong>Outcome:</strong> ' +
      escapeHtml(concept.desired_outcome || "") + '<br><strong>Evidence state:</strong> ' +
      escapeHtml(needEvidence.status || "HYPOTHESIS") + '<br><strong>Why:</strong> ' +
      escapeHtml(needEvidence.rationale || "") + '</p>' +
      (needBasis ? '<ul>' + needBasis + '</ul>' : '') + '</div>' +
    '<div class="concept-detail-card"><h4>CONTENT GAP / CHANNEL FIT</h4><p>' +
      '<strong>' + escapeHtml(gap.evidence_status || "UNASSESSED") + ':</strong> ' +
      escapeHtml(gap.hypothesis || "") + '<br><strong>Fit ' +
      escapeHtml(fit.status || "UNASSESSED") + ':</strong> ' +
      escapeHtml(fit.rationale || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>TITLE CLARITY TEST</h4><ul>' +
      titles + '</ul></div>' +
    '<div class="concept-detail-card"><h4>RESEARCH QUESTIONS</h4><ul>' +
      questions + '</ul></div>' +
    '<div class="concept-detail-card"><h4>SOURCE DEPENDENCY TEST</h4><p>' +
      escapeHtml(sourceTest.rationale || "") + '</p></div>';

  const criteriaDescriptions = snapshot.criteria || {};
  const checked = concept.criteria_decisions || {};
  const required = concept.required_accept_criteria || Object.keys(criteriaDescriptions);
  conceptCriteria.innerHTML =
    '<div class="concept-criteria-help">' +
      '<strong>Rework only:</strong> check what you want to keep. ' +
      'Leave unchecked anything you want changed. Accept, Reject and Save Idea ignore these boxes.' +
    '</div>' +
    required.map(function (criterion) {
      const id = "concept-criterion-" + conceptCursor + "-" + criterion;
      return '<label class="concept-criterion" for="' + escapeHtml(id) + '">' +
        '<input type="checkbox" id="' + escapeHtml(id) + '" data-concept-criterion="' +
        escapeHtml(criterion) + '"' + (checked[criterion] ? " checked" : "") + '>' +
        '<span><strong>' + escapeHtml(humanizeToken(criterion)) + '</strong>' +
        escapeHtml(criteriaDescriptions[criterion] || "") + '</span></label>';
    }).join("");

  conceptNote.value = concept.note || "";
  conceptPrev.disabled = conceptCursor <= 0;
  conceptNext.disabled = conceptCursor >= items.length - 1;
  conceptReject.disabled = false;
  conceptRework.disabled = false;
  conceptSaveIdea.disabled = false;
  conceptSaveIdea.textContent = concept.idea_saved
    ? "Save idea (already banked)"
    : "Save idea";
  conceptAccept.disabled = false;
  conceptEditing = false;
}

function moveConceptCursor(delta) {
  const current = currentConceptItem();
  if (!current) return;
  conceptCursor = Math.max(
    0,
    Math.min(current.items.length - 1, conceptCursor + delta)
  );
  conceptEditing = false;
  renderConceptReview(latestConceptSnapshot, true);
}

function collectConceptCriteria() {
  const values = {};
  conceptCriteria.querySelectorAll("[data-concept-criterion]").forEach(function (input) {
    values[input.dataset.conceptCriterion] = Boolean(input.checked);
  });
  return values;
}

async function saveConceptIdea(conceptId, note) {
  if (!conceptId) return;
  const preservedNote = note || "";
  try {
    const payload = await api("/api/concept-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: conceptId,
        decision: "SAVE_IDEA",
        criteria: {},
        note: preservedNote
      })
    });
    latestConceptSnapshot = payload;
    renderConceptReview(payload, true);
    const current = currentConceptItem();
    if (
      !payload.complete &&
      current &&
      current.item.concept_id === conceptId &&
      preservedNote
    ) {
      conceptNote.value = preservedNote;
      conceptEditing = true;
    }
    showToast("Idea saved to the Title Bank.", false);
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function submitConceptDecision(decision) {
  const current = currentConceptItem();
  if (!current) return;
  const concept = current.item;

  try {
    const payload = await api("/api/concept-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: concept.concept_id,
        decision: decision,
        criteria: decision === "REWORK" ? collectConceptCriteria() : {},
        note: conceptNote.value
      })
    });
    conceptEditing = false;
    latestConceptSnapshot = payload;
    const nextPending = pendingConceptIndex(payload.concepts || []);
    if (nextPending >= 0) conceptCursor = nextPending;
    renderConceptReview(payload, true);
    showToast(
      decision === "ACCEPT"
        ? "Concept accepted."
        : decision === "REWORK"
          ? "Concept marked for rework."
          : decision === "SAVE_IDEA"
            ? "Concept saved for later."
            : "Concept rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}


function pendingPackagingIndex(items) {
  return (items || []).findIndex(function (item) {
    return item && item.decision === "PENDING";
  });
}

function currentPackagingItem() {
  const items = (latestPackagingSnapshot && latestPackagingSnapshot.packages) || [];
  if (!items.length) return null;
  packagingCursor = Math.max(0, Math.min(packagingCursor, items.length - 1));
  return { item: items[packagingCursor], items: items };
}

function renderPackagingReview(snapshot, force) {
  latestPackagingSnapshot = snapshot || {};

  if (
    !snapshot ||
    snapshot.status === "WAITING_FOR_PACKAGE_CANDIDATES" ||
    snapshot.status === "READY_TO_PREPARE" ||
    !(snapshot.packages || []).length
  ) {
    packagingReviewPanel.hidden = true;
    return;
  }

  if (snapshot.complete) {
    packagingReviewPanel.hidden = false;
    packagingReviewTitle.textContent = "Packaging Gate complete";
    packagingReviewSummary.textContent =
      (snapshot.accepted || 0) + " accepted · " +
      (snapshot.rework || 0) + " rework · " +
      (snapshot.rejected || 0) + " rejected";
    packagingReviewStatus.textContent = snapshot.research_status || "COMPLETE";
    packagingReviewStatus.className =
      "status-chip " + ((snapshot.accepted || 0) > 0 ? "success" : "failed");
    packagingDetail.innerHTML =
      '<div class="concept-complete">' +
      ((snapshot.accepted || 0) > 0
        ? "Approved package is ready for Research."
        : "No package was approved. Regenerate or rework before Research.") +
      '</div>';
    packagingCriteria.innerHTML = "";
    packagingNote.hidden = true;
    packagingPrev.disabled = true;
    packagingNext.disabled = true;
    packagingReject.disabled = true;
    packagingRework.disabled = true;
    packagingAccept.disabled = true;
    return;
  }

  if (packagingEditing && !force) return;

  const items = snapshot.packages || [];
  if (!items.length) {
    packagingReviewPanel.hidden = true;
    return;
  }
  if (packagingCursor >= items.length) {
    packagingCursor = Math.max(0, items.length - 1);
  }

  const pkg = items[packagingCursor] || {};
  const thumbnail = pkg.thumbnail || {};
  const opening = pkg.opening_frame || {};
  const dependencies = (pkg.research_dependencies || []).map(function (item) {
    return "<li>" + escapeHtml(item) + "</li>";
  }).join("");

  packagingReviewPanel.hidden = false;
  packagingNote.hidden = false;
  packagingReviewTitle.textContent =
    "Package " + (packagingCursor + 1) + " of " + items.length;
  packagingReviewSummary.textContent =
    (snapshot.pending || 0) + " pending · reviewer " +
    escapeHtml(snapshot.reviewer || "local-operator");
  packagingReviewStatus.textContent = pkg.decision || "PENDING";
  packagingReviewStatus.className =
    "status-chip " +
    (pkg.decision === "ACCEPT"
      ? "success"
      : pkg.decision === "REJECT"
        ? "failed"
        : "running");

  packagingDetail.innerHTML =
    '<div class="concept-detail-card">' +
      '<h4>PACKAGE</h4>' +
      '<h3>' + escapeHtml(pkg.title || pkg.package_id) + '</h3>' +
      '<div class="concept-meta">' +
        '<span>' + escapeHtml(humanizeToken(pkg.format_intent)) + '</span>' +
        '<span>Concept ' + escapeHtml(pkg.concept_id || "") + '</span>' +
      '</div>' +
    '</div>' +
    '<div class="concept-detail-card"><h4>THUMBNAIL</h4><p><strong>Message:</strong> ' +
      escapeHtml(thumbnail.message || "") + '<br><strong>Visual:</strong> ' +
      escapeHtml(thumbnail.visual_concept || "") +
      (thumbnail.text_overlay
        ? '<br><strong>Text:</strong> ' + escapeHtml(thumbnail.text_overlay)
        : "") +
      '</p></div>' +
    '<div class="concept-detail-card"><h4>OPENING FRAME</h4><p><strong>Purpose:</strong> ' +
      escapeHtml(opening.purpose || "") + '<br><strong>Visual:</strong> ' +
      escapeHtml(opening.visual_concept || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>ONE-SENTENCE PROMISE</h4><p>' +
      escapeHtml(pkg.one_sentence_promise || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>VIEWER NEED</h4><p><strong>Viewer:</strong> ' +
      escapeHtml(pkg.expected_viewer || "") + '<br><strong>Awareness:</strong> ' +
      escapeHtml(pkg.awareness_level || "") + '<br><strong>Problem:</strong> ' +
      escapeHtml(pkg.viewer_problem || "") + '<br><strong>Moment:</strong> ' +
      escapeHtml(pkg.viewer_moment || "") + '<br><strong>Outcome:</strong> ' +
      escapeHtml(pkg.desired_outcome || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>PROMISE / CURIOSITY / PAYOFF</h4><p><strong>Core promise:</strong> ' +
      escapeHtml(pkg.core_promise || "") + '<br><strong>Curiosity gap:</strong> ' +
      escapeHtml(pkg.curiosity_gap || "") + '<br><strong>Expected payoff:</strong> ' +
      escapeHtml(pkg.expected_payoff || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>TITLE + THUMBNAIL</h4><p>' +
      escapeHtml(pkg.title_thumbnail_relationship || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>POSITIONING</h4><p><strong>Gap:</strong> ' +
      escapeHtml(pkg.gap_positioning || "") + '<br><strong>Channel fit:</strong> ' +
      escapeHtml(pkg.channel_fit_alignment || "") + '</p></div>' +
    '<div class="concept-detail-card"><h4>RESEARCH DEPENDENCIES</h4>' +
      (dependencies ? '<ul>' + dependencies + '</ul>' : '<p>None declared.</p>') +
      '</div>';

  const criteriaDescriptions = snapshot.criteria || {};
  const checked = pkg.criteria_decisions || {};
  const required = pkg.required_accept_criteria || Object.keys(criteriaDescriptions);
  packagingCriteria.innerHTML = required.map(function (criterion) {
    const id = "packaging-criterion-" + packagingCursor + "-" + criterion;
    return '<label class="concept-criterion" for="' + escapeHtml(id) + '">' +
      '<input type="checkbox" id="' + escapeHtml(id) +
      '" data-packaging-criterion="' + escapeHtml(criterion) + '"' +
      (checked[criterion] ? " checked" : "") + '>' +
      '<span><strong>' + escapeHtml(humanizeToken(criterion)) + '</strong>' +
      escapeHtml(criteriaDescriptions[criterion] || "") + '</span></label>';
  }).join("");

  packagingNote.value = pkg.note || "";
  packagingPrev.disabled = packagingCursor <= 0;
  packagingNext.disabled = packagingCursor >= items.length - 1;
  packagingReject.disabled = false;
  packagingRework.disabled = false;
  packagingAccept.disabled = false;
  packagingEditing = false;
}

function movePackagingCursor(delta) {
  const current = currentPackagingItem();
  if (!current) return;
  packagingCursor = Math.max(
    0,
    Math.min(current.items.length - 1, packagingCursor + delta)
  );
  packagingEditing = false;
  renderPackagingReview(latestPackagingSnapshot, true);
}

function collectPackagingCriteria() {
  const values = {};
  packagingCriteria.querySelectorAll("[data-packaging-criterion]").forEach(function (input) {
    values[input.dataset.packagingCriterion] = Boolean(input.checked);
  });
  return values;
}

async function submitPackagingDecision(decision) {
  const current = currentPackagingItem();
  if (!current) return;
  const pkg = current.item;

  try {
    const payload = await api("/api/packaging-gate", {
      method: "POST",
      body: JSON.stringify({
        package_id: pkg.package_id,
        decision: decision,
        criteria: collectPackagingCriteria(),
        note: packagingNote.value
      })
    });
    packagingEditing = false;
    latestPackagingSnapshot = payload;
    const nextPending = pendingPackagingIndex(payload.packages || []);
    if (nextPending >= 0) packagingCursor = nextPending;
    renderPackagingReview(payload, true);
    showToast(
      decision === "ACCEPT"
        ? "Package accepted."
        : decision === "REWORK"
          ? "Package sent for rework."
          : "Package rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}


function pendingResearchIndex(items) {
  return (items || []).findIndex(function (item) {
    return item && item.decision === "PENDING";
  });
}

function currentResearchItem() {
  const items = (latestResearchSnapshot && latestResearchSnapshot.claims) || [];
  if (!items.length) return null;
  researchCursor = Math.max(0, Math.min(researchCursor, items.length - 1));
  return { item: items[researchCursor], items: items };
}

function renderResearchReview(snapshot, force) {
  latestResearchSnapshot = snapshot || {};
  if (
    !snapshot ||
    snapshot.status === "WAITING_FOR_DRAFT_RESEARCH_PACKAGES" ||
    snapshot.status === "READY_TO_PREPARE" ||
    !(snapshot.claims || []).length
  ) {
    researchReviewPanel.hidden = true;
    return;
  }

  if (snapshot.complete) {
    researchReviewPanel.hidden = false;
    researchReviewTitle.textContent = "Research Gate complete";
    researchReviewSummary.textContent =
      (snapshot.ready_for_story_script || 0) + " package(s) ready for Story / Script";
    researchReviewStatus.textContent =
      (snapshot.verified_packages || []).every(function (item) {
        return item.status === "READY_FOR_STORY_SCRIPT";
      }) ? "READY FOR SCRIPT" : "RESEARCH INCOMPLETE";
    researchReviewStatus.className =
      "status-chip " +
      ((snapshot.verified_packages || []).length &&
       (snapshot.verified_packages || []).every(function (item) {
         return item.status === "READY_FOR_STORY_SCRIPT";
       }) ? "success" : "failed");
    const unresolved = (snapshot.verified_packages || []).flatMap(function (item) {
      return item.unresolved_question_ids || [];
    });
    researchDetail.innerHTML =
      '<div class="concept-complete">' +
      (unresolved.length
        ? "Unresolved research questions: " + escapeHtml(unresolved.join(", "))
        : "Human-approved research is ready for Story / Script.") +
      '</div>';
    researchCriteria.innerHTML = "";
    researchNote.hidden = true;
    researchPrev.disabled = true;
    researchNext.disabled = true;
    researchReject.disabled = true;
    researchRework.disabled = true;
    researchAccept.disabled = true;
    return;
  }

  if (researchEditing && !force) return;
  const items = snapshot.claims || [];
  if (!items.length) {
    researchReviewPanel.hidden = true;
    return;
  }
  if (researchCursor >= items.length) {
    researchCursor = Math.max(0, items.length - 1);
  }

  const claim = items[researchCursor] || {};
  const coverage = claim.coverage || {};
  const evidence = (claim.evidence || []).map(function (link) {
    const source = link.source || {};
    return '<div class="concept-detail-card">' +
      '<h4>' + escapeHtml(link.stance || "EVIDENCE") + '</h4>' +
      '<p><strong>Source:</strong> ' + escapeHtml(source.title || link.source_id || "") +
      '<br><strong>Publisher:</strong> ' + escapeHtml(source.publisher || "") +
      '<br><strong>Type:</strong> ' + escapeHtml(humanizeToken(source.source_type || "")) +
      '<br><strong>Locator:</strong> ' + escapeHtml(link.locator || "") +
      '<br><strong>Evidence:</strong> ' + escapeHtml(link.evidence_note || "") +
      '<br><strong>URL:</strong> ' + escapeHtml(source.url || "") + '</p></div>';
  }).join("");

  const questions = (claim.question_ids || []).map(function (id) {
    const match = (claim.research_questions || []).find(function (q) {
      return q.question_id === id;
    });
    return match ? id + " — " + (match.question || "") : id;
  });

  researchReviewPanel.hidden = false;
  researchNote.hidden = false;
  researchReviewTitle.textContent =
    "Claim " + (researchCursor + 1) + " of " + items.length;
  researchReviewSummary.textContent =
    (snapshot.pending || 0) + " pending · reviewer " +
    escapeHtml(snapshot.reviewer || "local-operator");
  researchReviewStatus.textContent = claim.decision || "PENDING";
  researchReviewStatus.className =
    "status-chip " +
    (claim.decision === "ACCEPT"
      ? "success"
      : claim.decision === "REJECT"
        ? "failed"
        : "running");

  researchDetail.innerHTML =
    '<div class="concept-detail-card"><h4>CLAIM</h4><h3>' +
      escapeHtml(claim.statement || claim.claim_id) + '</h3>' +
      '<div class="concept-meta"><span>' + escapeHtml(humanizeToken(claim.role)) +
      '</span><span>' + escapeHtml(humanizeToken(coverage.state)) +
      '</span><span>Concept ' + escapeHtml(claim.concept_id || "") +
      '</span></div></div>' +
    '<div class="concept-detail-card"><h4>RESEARCH QUESTIONS</h4><p>' +
      escapeHtml(questions.join(" | ")) + '</p></div>' +
    evidence;

  const descriptions = claim.criteria_descriptions || {};
  const checked = claim.criteria_decisions || {};
  const required = claim.required_accept_criteria || Object.keys(descriptions);
  researchCriteria.innerHTML = required.map(function (criterion) {
    const id = "research-criterion-" + researchCursor + "-" + criterion;
    return '<label class="concept-criterion" for="' + escapeHtml(id) + '">' +
      '<input type="checkbox" id="' + escapeHtml(id) +
      '" data-research-criterion="' + escapeHtml(criterion) + '"' +
      (checked[criterion] ? " checked" : "") + '>' +
      '<span><strong>' + escapeHtml(humanizeToken(criterion)) + '</strong>' +
      escapeHtml(descriptions[criterion] || "") + '</span></label>';
  }).join("");

  researchNote.value = claim.note || "";
  researchPrev.disabled = researchCursor <= 0;
  researchNext.disabled = researchCursor >= items.length - 1;
  researchReject.disabled = false;
  researchRework.disabled = false;
  researchAccept.disabled = false;
  researchEditing = false;
}

function moveResearchCursor(delta) {
  const current = currentResearchItem();
  if (!current) return;
  researchCursor = Math.max(
    0,
    Math.min(current.items.length - 1, researchCursor + delta)
  );
  researchEditing = false;
  renderResearchReview(latestResearchSnapshot, true);
}

function collectResearchCriteria() {
  const values = {};
  researchCriteria.querySelectorAll("[data-research-criterion]").forEach(function (input) {
    values[input.dataset.researchCriterion] = Boolean(input.checked);
  });
  return values;
}

async function submitResearchDecision(decision) {
  const current = currentResearchItem();
  if (!current) return;
  const claim = current.item;
  try {
    const payload = await api("/api/research-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: claim.concept_id,
        claim_id: claim.claim_id,
        decision: decision,
        criteria: collectResearchCriteria(),
        note: researchNote.value
      })
    });
    researchEditing = false;
    latestResearchSnapshot = payload;
    const nextPending = pendingResearchIndex(payload.claims || []);
    if (nextPending >= 0) researchCursor = nextPending;
    renderResearchReview(payload, true);
    showToast(
      decision === "ACCEPT"
        ? "Research claim accepted."
        : decision === "REWORK"
          ? "Research claim sent for rework."
          : "Research claim rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function pendingScriptIndex(items) {
  return (items || []).findIndex(function (item) {
    return item && item.decision === "PENDING";
  });
}

function currentScriptItem() {
  const items = (latestScriptSnapshot && latestScriptSnapshot.scripts) || [];
  if (!items.length) return null;
  scriptCursor = Math.max(0, Math.min(scriptCursor, items.length - 1));
  return { item: items[scriptCursor], items: items };
}

function renderScriptReview(snapshot, force) {
  latestScriptSnapshot = snapshot || {};
  if (
    !snapshot ||
    snapshot.status === "WAITING_FOR_SCRIPT_DRAFTS" ||
    snapshot.status === "READY_TO_PREPARE" ||
    !(snapshot.scripts || []).length
  ) {
    scriptReviewPanel.hidden = true;
    return;
  }

  if (snapshot.complete) {
    scriptReviewPanel.hidden = false;
    scriptReviewTitle.textContent = "Script Gate complete";
    scriptReviewSummary.textContent =
      (snapshot.accepted || 0) + " accepted · " +
      (snapshot.rework || 0) + " rework · " +
      (snapshot.rejected || 0) + " rejected";
    const readyConcepts = snapshot.production_ready_concept_ids || [];
    scriptReviewStatus.textContent =
      readyConcepts.length ? "ALL REQUIRED BRANCHES APPROVED" : "BRANCH WORK INCOMPLETE";
    scriptReviewStatus.className =
      "status-chip " + (readyConcepts.length ? "success" : "failed");
    scriptDetail.innerHTML =
      '<div class="concept-complete">' +
      (readyConcepts.length
        ? "All required format-specific scripts are approved and bundled for Format planning."
        : "All branch decisions are recorded, but at least one required branch was rejected or sent for rework.") +
      '</div>';
    scriptCriteria.innerHTML = "";
    scriptNote.hidden = true;
    scriptPrev.disabled = true;
    scriptNext.disabled = true;
    scriptReject.disabled = true;
    scriptRework.disabled = true;
    scriptAccept.disabled = true;
    return;
  }

  if (scriptEditing && !force) return;
  const items = snapshot.scripts || [];
  if (scriptCursor >= items.length) {
    scriptCursor = Math.max(0, items.length - 1);
  }
  const script = items[scriptCursor] || {};
  const pkg = script.package || {};
  const scriptOverlap = script.source_overlap || {};
  const sections = (script.sections || []).map(function (section) {
    return '<div class="concept-detail-card">' +
      '<h4>' + escapeHtml(section.section_id || "SECTION") + ' · ' +
      escapeHtml(section.purpose || "") + '</h4>' +
      '<p>' + escapeHtml(section.narration || "") + '</p>' +
      '<div class="concept-meta"><span>Psychology: ' +
      escapeHtml(section.psychology_mechanism || "—") +
      '</span><span>Reward: ' +
      escapeHtml(section.reward_type || "—") +
      '</span><span>Story beats: ' +
      escapeHtml((section.source_story_beat_ids || []).join(", ") || "none") +
      '</span><span>Claims: ' +
      escapeHtml((section.claim_ids || []).join(", ") || "none") +
      '</span></div></div>';
  }).join("");

  scriptReviewPanel.hidden = false;
  scriptNote.hidden = false;
  scriptReviewTitle.textContent =
    humanizeToken(script.format || "script") + " Script · " +
    (scriptCursor + 1) + " of " + items.length;
  scriptReviewSummary.textContent =
    (snapshot.pending || 0) + " pending · " +
    (snapshot.accepted || 0) + " accepted · " +
    (snapshot.rework || 0) + " rework";
  scriptReviewStatus.textContent = script.decision || "PENDING";
  scriptReviewStatus.className =
    "status-chip " +
    (script.decision === "ACCEPT"
      ? "success"
      : script.decision === "REJECT"
        ? "failed"
        : "running");

  const profile = script.psychology_profile || {};
  const refreshWindow = profile.attention_refresh_window_seconds || [];
  scriptDetail.innerHTML =
    '<div class="concept-detail-card"><h4>FORMAT PSYCHOLOGY</h4><p>' +
      '<strong>Branch:</strong> ' + escapeHtml(humanizeToken(script.format || "")) +
      '<br><strong>Reward density:</strong> ' + escapeHtml(profile.reward_density || "—") +
      '<br><strong>Hook target:</strong> ' +
      escapeHtml(profile.hook_target_seconds == null ? "No fixed target" : profile.hook_target_seconds + "s hypothesis") +
      '<br><strong>Attention refresh:</strong> ' +
      escapeHtml(refreshWindow.length ? refreshWindow.join("–") + "s hypothesis" : "No fixed interval") +
      '</p></div>' +
    '<div class="concept-detail-card"><h4>APPROVED PACKAGE</h4><h3>' +
      escapeHtml(pkg.title || script.title || script.concept_id) + '</h3>' +
      '<p><strong>Promise:</strong> ' + escapeHtml(pkg.one_sentence_promise || "") +
      '<br><strong>Expected payoff:</strong> ' + escapeHtml(pkg.expected_payoff || "") +
      '<br><strong>Viewer outcome:</strong> ' + escapeHtml(pkg.desired_outcome || "") +
      '</p></div>' +
    (scriptOverlap.matches && scriptOverlap.matches.length
      ? '<div class="concept-detail-card"><h4>SOURCE OVERLAP CHECK</h4><p>' +
        scriptOverlap.matches.map(function (match) {
          return escapeHtml((match.blocking ? "BLOCK " : "WARN ") + match.word_count + " words: " + match.overlap_text);
        }).join("<br>") + '</p></div>'
      : '') +
    '<div class="concept-detail-card"><h4>OPENING HOOK · ' +
      escapeHtml(humanizeToken(script.opening_hook_mechanism || "")) +
      '</h4><p>' +
      escapeHtml(script.opening_hook || "") + '</p></div>' +
    sections +
    '<div class="concept-detail-card"><h4>CLOSING</h4><p>' +
      escapeHtml(script.closing || "") + '</p></div>';

  const descriptions = script.criteria || {};
  const checked = script.criteria_decisions || {};
  const required = script.required_accept_criteria || Object.keys(descriptions);
  scriptCriteria.innerHTML = required.map(function (criterion) {
    const id = "script-criterion-" + scriptCursor + "-" + criterion;
    return '<label class="concept-criterion" for="' + escapeHtml(id) + '">' +
      '<input type="checkbox" id="' + escapeHtml(id) +
      '" data-script-criterion="' + escapeHtml(criterion) + '"' +
      (checked[criterion] ? " checked" : "") + '>' +
      '<span><strong>' + escapeHtml(humanizeToken(criterion)) + '</strong>' +
      escapeHtml(descriptions[criterion] || "") + '</span></label>';
  }).join("");

  scriptNote.value = script.note || "";
  scriptPrev.disabled = scriptCursor <= 0;
  scriptNext.disabled = scriptCursor >= items.length - 1;
  scriptReject.disabled = false;
  scriptRework.disabled = false;
  scriptAccept.disabled = false;
  scriptEditing = false;
}

function moveScriptCursor(delta) {
  const current = currentScriptItem();
  if (!current) return;
  scriptCursor = Math.max(0, Math.min(current.items.length - 1, scriptCursor + delta));
  scriptEditing = false;
  renderScriptReview(latestScriptSnapshot, true);
}

function collectScriptCriteria() {
  const values = {};
  scriptCriteria.querySelectorAll("[data-script-criterion]").forEach(function (input) {
    values[input.dataset.scriptCriterion] = Boolean(input.checked);
  });
  return values;
}

async function submitScriptDecision(decision) {
  const current = currentScriptItem();
  if (!current) return;
  const script = current.item;
  try {
    const payload = await api("/api/script-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: script.concept_id,
        format: script.format,
        decision: decision,
        criteria: collectScriptCriteria(),
        note: scriptNote.value
      })
    });
    scriptEditing = false;
    latestScriptSnapshot = payload;
    const nextPending = pendingScriptIndex(payload.scripts || []);
    if (nextPending >= 0) scriptCursor = nextPending;
    renderScriptReview(payload, true);
    showToast(
      decision === "ACCEPT"
        ? humanizeToken(script.format || "Script") + " branch accepted."
        : decision === "REWORK"
          ? "Script sent for rework."
          : "Script rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function pendingFormatIndex(items) {
  return (items || []).findIndex(function (item) {
    return item && item.decision === "PENDING";
  });
}

function currentFormatItem() {
  const items = (latestFormatSnapshot && latestFormatSnapshot.plans) || [];
  if (!items.length) return null;
  formatCursor = Math.max(0, Math.min(formatCursor, items.length - 1));
  return { item: items[formatCursor], items: items };
}

function renderFormatBranch(branch) {
  const beats = (branch.beats || []).map(function (beat) {
    return '<div class="concept-detail-card">' +
      '<h4>' + escapeHtml(beat.beat_id || "BEAT") + ' · ' +
      escapeHtml(beat.purpose || "") + '</h4>' +
      '<p>' + escapeHtml(beat.treatment || "") + '</p>' +
      '<div class="concept-meta"><span>Claims: ' +
      escapeHtml((beat.claim_ids || []).join(", ") || "none") +
      '</span><span>Script sections: ' +
      escapeHtml((beat.source_section_ids || []).join(", ") || "none") +
      '</span></div></div>';
  }).join("");
  return '<div class="concept-detail-card"><h4>' +
      escapeHtml(humanizeToken(branch.format || "branch")) + ' BRANCH</h4>' +
      '<p><strong>Duration intent:</strong> ' +
      escapeHtml(String(branch.duration_intent_seconds || "")) + ' s' +
      '<br><strong>Promise delivery:</strong> ' + escapeHtml(branch.promise_delivery || "") +
      '<br><strong>Payoff:</strong> ' + escapeHtml(branch.payoff || "") +
      '</p></div>' + beats;
}

function renderFormatReview(snapshot, force) {
  latestFormatSnapshot = snapshot || {};
  if (
    !snapshot ||
    snapshot.status === "WAITING_FOR_FORMAT_PLANS" ||
    snapshot.status === "READY_TO_PREPARE" ||
    !(snapshot.plans || []).length
  ) {
    formatReviewPanel.hidden = true;
    return;
  }

  if (snapshot.complete) {
    formatReviewPanel.hidden = false;
    formatReviewTitle.textContent = "Format Gate complete";
    formatReviewSummary.textContent =
      (snapshot.accepted || 0) + " accepted · " +
      (snapshot.rework || 0) + " rework · " +
      (snapshot.rejected || 0) + " rejected";
    formatReviewStatus.textContent =
      (snapshot.accepted || 0) > 0 ? "READY FOR PRODUCTION ENGINE" : "NO APPROVED FORMAT PLAN";
    formatReviewStatus.className =
      "status-chip " + ((snapshot.accepted || 0) > 0 ? "success" : "failed");
    formatDetail.innerHTML =
      '<div class="concept-complete">' +
      ((snapshot.accepted || 0) > 0
        ? "Approved format plan is ready for the Production Engine."
        : "No format plan was approved. Rework or regenerate before production.") +
      '</div>';
    formatCriteria.innerHTML = "";
    formatNote.hidden = true;
    formatPrev.disabled = true;
    formatNext.disabled = true;
    formatReject.disabled = true;
    formatRework.disabled = true;
    formatAccept.disabled = true;
    return;
  }

  if (formatEditing && !force) return;
  const items = snapshot.plans || [];
  if (formatCursor >= items.length) {
    formatCursor = Math.max(0, items.length - 1);
  }
  const plan = items[formatCursor] || {};
  const pkg = plan.package || {};
  const separation = plan.branch_separation || {};
  const overlap = plan.source_overlap || {};
  const branches = (plan.branches || []).map(renderFormatBranch).join("");

  formatReviewPanel.hidden = false;
  formatNote.hidden = false;
  formatReviewTitle.textContent =
    "Format plan " + (formatCursor + 1) + " of " + items.length;
  formatReviewSummary.textContent =
    (snapshot.pending || 0) + " pending · " +
    (snapshot.accepted || 0) + " accepted · " +
    (snapshot.rework || 0) + " rework";
  formatReviewStatus.textContent = plan.decision || "PENDING";
  formatReviewStatus.className =
    "status-chip " +
    (plan.decision === "ACCEPT"
      ? "success"
      : plan.decision === "REJECT"
        ? "failed"
        : "running");

  formatDetail.innerHTML =
    '<div class="concept-detail-card"><h4>APPROVED PACKAGE</h4><h3>' +
      escapeHtml(pkg.title || plan.concept_id) + '</h3>' +
      '<p><strong>Promise:</strong> ' + escapeHtml(pkg.one_sentence_promise || "") +
      '<br><strong>Expected payoff:</strong> ' + escapeHtml(pkg.expected_payoff || "") +
      '<br><strong>Format intent:</strong> ' + escapeHtml(plan.format_intent || "") +
      '<br><strong>Required branches:</strong> ' +
      escapeHtml((plan.required_branches || []).join(", ")) +
      '</p></div>' +
    '<div class="concept-detail-card"><h4>BRANCH SEPARATION CHECK</h4><p>' +
      escapeHtml(
        separation.identical
          ? "BLOCK: branches are identical edits of one timeline."
          : separation.truncation
            ? "BLOCK: one branch is a truncation of the other."
            : "Branches differ in structure (deterministic check passed)."
      ) + '</p></div>' +
    (overlap.matches && overlap.matches.length
      ? '<div class="concept-detail-card"><h4>SOURCE OVERLAP CHECK</h4><p>' +
        overlap.matches.map(function (match) {
          return escapeHtml((match.blocking ? "BLOCK " : "WARN ") + match.word_count + " words: " + match.overlap_text);
        }).join("<br>") + '</p></div>'
      : '') +
    branches;

  const descriptions = plan.criteria || {};
  const checked = plan.criteria_decisions || {};
  const required = plan.required_accept_criteria || Object.keys(descriptions);
  formatCriteria.innerHTML = required.map(function (criterion) {
    const id = "format-criterion-" + formatCursor + "-" + criterion;
    return '<label class="concept-criterion" for="' + escapeHtml(id) + '">' +
      '<input type="checkbox" id="' + escapeHtml(id) +
      '" data-format-criterion="' + escapeHtml(criterion) + '"' +
      (checked[criterion] ? " checked" : "") + '>' +
      '<span><strong>' + escapeHtml(humanizeToken(criterion)) + '</strong>' +
      escapeHtml(descriptions[criterion] || "") + '</span></label>';
  }).join("");

  formatNote.value = plan.note || "";
  formatPrev.disabled = formatCursor <= 0;
  formatNext.disabled = formatCursor >= items.length - 1;
  formatReject.disabled = false;
  formatRework.disabled = false;
  formatAccept.disabled = false;
  formatEditing = false;
}

function moveFormatCursor(delta) {
  const current = currentFormatItem();
  if (!current) return;
  formatCursor = Math.max(0, Math.min(current.items.length - 1, formatCursor + delta));
  formatEditing = false;
  renderFormatReview(latestFormatSnapshot, true);
}

function collectFormatCriteria() {
  const values = {};
  formatCriteria.querySelectorAll("[data-format-criterion]").forEach(function (input) {
    values[input.dataset.formatCriterion] = Boolean(input.checked);
  });
  return values;
}

async function submitFormatDecision(decision) {
  const current = currentFormatItem();
  if (!current) return;
  const plan = current.item;
  try {
    const payload = await api("/api/format-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: plan.concept_id,
        decision: decision,
        criteria: collectFormatCriteria(),
        note: formatNote.value
      })
    });
    formatEditing = false;
    latestFormatSnapshot = payload;
    const nextPending = pendingFormatIndex(payload.plans || []);
    if (nextPending >= 0) formatCursor = nextPending;
    renderFormatReview(payload, true);
    showToast(
      decision === "ACCEPT"
        ? "Format plan accepted for production."
        : decision === "REWORK"
          ? "Format plan sent for rework."
          : "Format plan rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}


function pendingPerformanceIndex(items) {
  return (items || []).findIndex(function (item) {
    return item && item.decision === "PENDING";
  });
}

function currentPerformanceItem() {
  const items = (latestPerformanceSnapshot && latestPerformanceSnapshot.specs) || [];
  if (!items.length) return null;
  performanceCursor = Math.max(0, Math.min(performanceCursor, items.length - 1));
  return { item: items[performanceCursor], items: items };
}

function renderPerformanceReview(snapshot, force) {
  latestPerformanceSnapshot = snapshot || {};
  if (
    !snapshot ||
    snapshot.status === "WAITING_FOR_VOICE_PERFORMANCE_SPECS" ||
    snapshot.status === "READY_TO_PREPARE" ||
    !(snapshot.specs || []).length
  ) {
    performanceReviewPanel.hidden = true;
    return;
  }

  if (snapshot.complete) {
    performanceReviewPanel.hidden = false;
    performanceReviewTitle.textContent = "Performance Gate complete";
    performanceReviewSummary.textContent =
      (snapshot.accepted || 0) + " accepted · " +
      (snapshot.rework || 0) + " rework · " +
      (snapshot.rejected || 0) + " rejected";
    performanceReviewStatus.textContent =
      (snapshot.accepted || 0) > 0 ? "PERFORMANCE APPROVED" : "NO APPROVED PERFORMANCE";
    performanceReviewStatus.className =
      "status-chip " + ((snapshot.accepted || 0) > 0 ? "success" : "failed");
    performanceDetail.innerHTML =
      '<div class="concept-complete">' +
      ((snapshot.accepted || 0) > 0
        ? "Performance plan approved. No audio has been rendered or paid for by this gate."
        : "No performance plan was approved. Rework or regenerate before rendering.") +
      '</div>';
    performanceCriteria.innerHTML = "";
    performanceNote.hidden = true;
    performancePrev.disabled = true;
    performanceNext.disabled = true;
    performanceReject.disabled = true;
    performanceRework.disabled = true;
    performanceAccept.disabled = true;
    return;
  }

  if (performanceEditing && !force) return;
  const items = snapshot.specs || [];
  if (performanceCursor >= items.length) {
    performanceCursor = Math.max(0, items.length - 1);
  }
  const spec = items[performanceCursor] || {};
  const directions = {};
  (spec.directions || []).forEach(function (direction) {
    directions[direction.beat_id] = direction;
  });
  const beats = (spec.beats || []).map(function (beat) {
    const direction = directions[beat.beat_id] || {};
    return '<div class="concept-detail-card">' +
      '<h4>' + escapeHtml(beat.beat_id || "BEAT") + ' · ' +
      escapeHtml(beat.purpose || "") + '</h4>' +
      '<p><strong>Immutable narration:</strong> ' +
      escapeHtml(beat.immutable_narration || "") + '</p>' +
      '<div class="concept-meta">' +
      '<span>Emotion: ' + escapeHtml(direction.emotion || "") + '</span>' +
      '<span>Intensity: ' + escapeHtml(String(direction.intensity ?? "")) + '</span>' +
      '<span>Speed: ' + escapeHtml(String(direction.speed ?? "")) + '</span>' +
      '<span>Pause before: ' + escapeHtml(String(direction.pause_before_ms ?? "")) + ' ms</span>' +
      '<span>Pause after: ' + escapeHtml(String(direction.pause_after_ms ?? "")) + ' ms</span>' +
      '<span>Emphasis: ' + escapeHtml((direction.emphasis_terms || []).join(", ") || "none") + '</span>' +
      '</div></div>';
  }).join("");

  performanceReviewPanel.hidden = false;
  performanceNote.hidden = false;
  performanceReviewTitle.textContent =
    "Performance plan " + (performanceCursor + 1) + " of " + items.length;
  performanceReviewSummary.textContent =
    (snapshot.pending || 0) + " pending · " +
    (snapshot.accepted || 0) + " accepted · " +
    (snapshot.rework || 0) + " rework";
  performanceReviewStatus.textContent = spec.decision || "PENDING";
  performanceReviewStatus.className =
    "status-chip " +
    (spec.decision === "ACCEPT"
      ? "success"
      : spec.decision === "REJECT"
        ? "failed"
        : "running");

  const identity = spec.voice_identity || {};
  performanceDetail.innerHTML =
    '<div class="concept-detail-card"><h4>VOICE PERFORMANCE</h4><h3>' +
      escapeHtml(spec.title || spec.concept_id) + '</h3>' +
      '<p><strong>Branch:</strong> ' + escapeHtml(humanizeToken(spec.format || "")) +
      '<br><strong>Provider target:</strong> ' + escapeHtml(identity.provider || "higgsfield") +
      '<br><strong>Render prerequisites:</strong> ' +
      escapeHtml(spec.render_prerequisites_configured ? "configured" : "not configured — paid render remains blocked") +
      '</p></div>' +
    beats;

  const descriptions = spec.criteria || {};
  const checked = spec.criteria_decisions || {};
  const required = spec.required_accept_criteria || Object.keys(descriptions);
  performanceCriteria.innerHTML = required.map(function (criterion) {
    const id = "performance-criterion-" + performanceCursor + "-" + criterion;
    return '<label class="concept-criterion" for="' + escapeHtml(id) + '">' +
      '<input type="checkbox" id="' + escapeHtml(id) +
      '" data-performance-criterion="' + escapeHtml(criterion) + '"' +
      (checked[criterion] ? " checked" : "") + '>' +
      '<span><strong>' + escapeHtml(humanizeToken(criterion)) + '</strong>' +
      escapeHtml(descriptions[criterion] || "") + '</span></label>';
  }).join("");

  performanceNote.value = spec.note || "";
  performancePrev.disabled = performanceCursor <= 0;
  performanceNext.disabled = performanceCursor >= items.length - 1;
  performanceReject.disabled = false;
  performanceRework.disabled = false;
  performanceAccept.disabled = false;
  performanceEditing = false;
}

function movePerformanceCursor(delta) {
  const current = currentPerformanceItem();
  if (!current) return;
  performanceCursor = Math.max(
    0,
    Math.min(current.items.length - 1, performanceCursor + delta)
  );
  performanceEditing = false;
  renderPerformanceReview(latestPerformanceSnapshot, true);
}

function collectPerformanceCriteria() {
  const values = {};
  performanceCriteria
    .querySelectorAll("[data-performance-criterion]")
    .forEach(function (input) {
      values[input.dataset.performanceCriterion] = Boolean(input.checked);
    });
  return values;
}

async function submitPerformanceDecision(decision) {
  const current = currentPerformanceItem();
  if (!current) return;
  const spec = current.item;
  try {
    const payload = await api("/api/performance-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: spec.concept_id,
        format: spec.format,
        decision: decision,
        criteria: collectPerformanceCriteria(),
        note: performanceNote.value
      })
    });
    performanceEditing = false;
    latestPerformanceSnapshot = payload;
    const nextPending = pendingPerformanceIndex(payload.specs || []);
    if (nextPending >= 0) performanceCursor = nextPending;
    renderPerformanceReview(payload, true);
    showToast(
      decision === "ACCEPT"
        ? "Voice performance accepted."
        : decision === "REWORK"
          ? "Voice performance sent for rework."
          : "Voice performance rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderAnalysis(data) {
  const workflow = data.workflow || {};
  const humanCreateGate = [
    "HUMAN_VISION_GATE",
    "HUMAN_CONCEPT_GATE",
    "HUMAN_PACKAGING_GATE",
    "HUMAN_RESEARCH_GATE",
    "HUMAN_SCRIPT_GATE",
    "HUMAN_FORMAT_GATE",
    "HUMAN_PERFORMANCE_GATE"
  ].includes(workflow.state);

  analysisCurrentTitle.textContent =
    humanCreateGate
      ? workflow.current_title
      : (
        workflow.current_action_id && workflow.current_action_id !== "opportunity_research"
          ? workflow.current_title
          : (data.opportunity_gate && data.opportunity_gate.ready_for_experiment_02
            ? "Prepare the approved source evidence"
            : "Waiting for opportunity approval")
      );

  analysisCurrentDetail.textContent =
    humanCreateGate
      ? workflow.current_detail
      : (
        data.opportunity_gate && data.opportunity_gate.ready_for_experiment_02
          ? (workflow.current_detail || "The next available analysis step is highlighted.")
          : "Approve an opportunity before Experiment 02 can begin."
      );

  const actions = (data.actions || []).filter(function (action) {
    return action.surface === "workflow" && action.id !== "opportunity_research";
  });
  renderActionCollection(actions, analysisActions);
  renderVisionReview(data.vision_review || {}, false);
  renderHumanAnalysisReview(data.human_analysis_review || {}, false);
  renderConceptReview(data.concept_gate || {}, false);
  renderPackagingReview(data.packaging_gate || {}, false);
  renderResearchReview(data.research_gate || {}, false);
  renderScriptReview(data.script_gate || {}, false);
  renderFormatReview(data.format_gate || {}, false);
  renderPerformanceReview(data.performance_gate || {}, false);

  let activeIndex = 0;
  const exp2 = data.experiment_02_artifacts || {};
  const transform = data.transformation || {};
  const packaging = data.packaging || {};
  const research = data.research || {};
  const story = data.story_script || {};
  const fmt = data.format || {};
  const voice = data.voice_performance || {};

  if (
    workflow.state === "HUMAN_PERFORMANCE_GATE" ||
    voice.requests_ready || voice.specs_ready || voice.performance_gate_complete
  ) {
    activeIndex = 7;
  } else if (
    workflow.state === "HUMAN_FORMAT_GATE" ||
    fmt.requests_ready || fmt.plans_ready || fmt.format_gate_complete
  ) {
    activeIndex = 6;
  } else if (
    workflow.state === "HUMAN_SCRIPT_GATE" ||
    story.requests_ready || story.drafts_ready || story.script_gate_complete
  ) {
    activeIndex = 5;
  } else if (
    workflow.state === "HUMAN_RESEARCH_GATE" ||
    research.plans_ready || research.evidence_complete ||
    research.drafts_ready || research.research_gate_complete
  ) {
    activeIndex = 4;
  } else if (
    workflow.state === "HUMAN_PACKAGING_GATE" ||
    packaging.requests_ready || packaging.candidates_ready ||
    packaging.packaging_gate_complete
  ) {
    activeIndex = 3;
  } else if (
    workflow.state === "HUMAN_CONCEPT_GATE" ||
    transform.requests_ready || transform.candidates_ready ||
    transform.triage_ready || transform.concept_gate_complete
  ) {
    activeIndex = 2;
  } else if (
    workflow.state === "HUMAN_ANALYSIS_GATE" ||
    Number(exp2.analyzed_current_count || 0) > 0 ||
    Number(exp2.review_requests_current_count || 0) > 0 ||
    Boolean(exp2.requests_complete)
  ) {
    activeIndex = 1;
  }

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
  else if (job.status === "PARTIAL") statusClass = "running";
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
  renderRoute({ scroll: false });
}

async function loadStatus() {
  try {
    const data = await api("/api/status");
    csrfToken = String(data.csrf_token || "");
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

  const saveIdeaButton = event.target.closest("[data-concept-save]");
  if (saveIdeaButton) {
    saveConceptIdea(saveIdeaButton.dataset.conceptSave, "");
    return;
  }

  const overrideButton = event.target.closest("[data-concept-override]");
  if (overrideButton) {
    api("/api/concept-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: overrideButton.dataset.conceptOverride,
        decision: "OVERRIDE",
        criteria: {},
        note: ""
      })
    }).then(function (payload) {
      latestConceptSnapshot = payload;
      const nextPending = pendingConceptIndex(payload.concepts || []);
      if (nextPending >= 0) conceptCursor = nextPending;
      renderConceptReview(payload, true);
      showToast("Concept added to Human Gate.", false);
      loadStatus();
    }).catch(function (error) {
      showToast(error.message, true);
    });
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

window.addEventListener("popstate", function () {
  renderRoute({ scroll: true });
});
refreshStatus.addEventListener("click", loadStatus);
jobSummaryButton.addEventListener("click", openJobDrawer);
closeJobDrawer.addEventListener("click", closeJob);
drawerScrim.addEventListener("click", closeJob);
stopJob.addEventListener("click", stopCurrentJob);
mobileMenu.addEventListener("click", openSidebar);
sidebarScrim.addEventListener("click", closeSidebar);
visionObservation.addEventListener("input", function () {
  visionEditing = true;
});
visionPrev.addEventListener("click", function () {
  moveVisionCursor(-1);
});
visionNext.addEventListener("click", function () {
  moveVisionCursor(1);
});
visionReject.addEventListener("click", function () {
  submitVisionDecision("REJECT_FRAME");
});
visionAccept.addEventListener("click", function () {
  submitVisionDecision("ACCEPT_FRAME");
});
humanAnalysisNote.addEventListener("input", function () {
  humanAnalysisEditing = true;
});
humanAnalysisPrev.addEventListener("click", function () {
  moveHumanAnalysisCursor(-1);
});
humanAnalysisNext.addEventListener("click", function () {
  moveHumanAnalysisCursor(1);
});
humanAnalysisReject.addEventListener("click", function () {
  submitHumanAnalysisDecision("REJECT");
});
humanAnalysisAccept.addEventListener("click", function () {
  submitHumanAnalysisDecision("ACCEPT");
});
conceptNote.addEventListener("input", function () {
  conceptEditing = true;
});
conceptCriteria.addEventListener("change", function () {
  conceptEditing = true;
});
conceptPrev.addEventListener("click", function () {
  moveConceptCursor(-1);
});
conceptNext.addEventListener("click", function () {
  moveConceptCursor(1);
});
conceptReject.addEventListener("click", function () {
  submitConceptDecision("REJECT");
});
conceptRework.addEventListener("click", function () {
  submitConceptDecision("REWORK");
});
conceptSaveIdea.addEventListener("click", function () {
  submitConceptDecision("SAVE_IDEA");
});
conceptAccept.addEventListener("click", function () {
  submitConceptDecision("ACCEPT");
});
packagingNote.addEventListener("input", function () {
  packagingEditing = true;
});
packagingCriteria.addEventListener("change", function () {
  packagingEditing = true;
});
packagingPrev.addEventListener("click", function () {
  movePackagingCursor(-1);
});
packagingNext.addEventListener("click", function () {
  movePackagingCursor(1);
});
packagingReject.addEventListener("click", function () {
  submitPackagingDecision("REJECT");
});
packagingRework.addEventListener("click", function () {
  submitPackagingDecision("REWORK");
});
packagingAccept.addEventListener("click", function () {
  submitPackagingDecision("ACCEPT");
});
researchNote.addEventListener("input", function () {
  researchEditing = true;
});
researchCriteria.addEventListener("change", function () {
  researchEditing = true;
});
researchPrev.addEventListener("click", function () {
  moveResearchCursor(-1);
});
researchNext.addEventListener("click", function () {
  moveResearchCursor(1);
});
researchReject.addEventListener("click", function () {
  submitResearchDecision("REJECT");
});
researchRework.addEventListener("click", function () {
  submitResearchDecision("REWORK");
});
researchAccept.addEventListener("click", function () {
  submitResearchDecision("ACCEPT");
});
scriptNote.addEventListener("input", function () {
  scriptEditing = true;
});
scriptCriteria.addEventListener("change", function () {
  scriptEditing = true;
});
scriptPrev.addEventListener("click", function () {
  moveScriptCursor(-1);
});
scriptNext.addEventListener("click", function () {
  moveScriptCursor(1);
});
scriptReject.addEventListener("click", function () {
  submitScriptDecision("REJECT");
});
scriptRework.addEventListener("click", function () {
  submitScriptDecision("REWORK");
});
scriptAccept.addEventListener("click", function () {
  submitScriptDecision("ACCEPT");
});
formatNote.addEventListener("input", function () {
  formatEditing = true;
});
formatCriteria.addEventListener("change", function () {
  formatEditing = true;
});
formatPrev.addEventListener("click", function () {
  moveFormatCursor(-1);
});
formatNext.addEventListener("click", function () {
  moveFormatCursor(1);
});
formatReject.addEventListener("click", function () {
  submitFormatDecision("REJECT");
});
formatRework.addEventListener("click", function () {
  submitFormatDecision("REWORK");
});
formatAccept.addEventListener("click", function () {
  submitFormatDecision("ACCEPT");
});
performanceNote.addEventListener("input", function () {
  performanceEditing = true;
});
performanceCriteria.addEventListener("change", function () {
  performanceEditing = true;
});
performancePrev.addEventListener("click", function () {
  movePerformanceCursor(-1);
});
performanceNext.addEventListener("click", function () {
  movePerformanceCursor(1);
});
performanceReject.addEventListener("click", function () {
  submitPerformanceDecision("REJECT");
});
performanceRework.addEventListener("click", function () {
  submitPerformanceDecision("REWORK");
});
performanceAccept.addEventListener("click", function () {
  submitPerformanceDecision("ACCEPT");
});

renderRoute({ scroll: true });
loadStatus();
setInterval(loadStatus, 5000);
