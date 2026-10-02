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
const analysisCurrentPanel = document.getElementById("analysisCurrentPanel");
const analysisCurrentTitle = document.getElementById("analysisCurrentTitle");
const analysisCurrentDetail = document.getElementById("analysisCurrentDetail");
const analysisRunningActivity = document.getElementById("analysisRunningActivity");
const analysisRunningLabel = document.getElementById("analysisRunningLabel");
const analysisRunningElapsed = document.getElementById("analysisRunningElapsed");
const analysisRunningHeartbeat = document.getElementById("analysisRunningHeartbeat");
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
const packagingSaveIdea = document.getElementById("packagingSaveIdea");
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
const scriptSectionReviewPane = document.getElementById("scriptSectionReviewPane");
const scriptSectionReviewState = document.getElementById("scriptSectionReviewState");
const scriptSectionTargetStatus = document.getElementById("scriptSectionTargetStatus");
const scriptSectionProgress = document.getElementById("scriptSectionProgress");
const scriptSectionPrepare = document.getElementById("scriptSectionPrepare");
const scriptSectionControls = document.getElementById("scriptSectionControls");
const scriptSectionTarget = document.getElementById("scriptSectionTarget");
const scriptSectionNextPending = document.getElementById("scriptSectionNextPending");
const scriptSectionTargetDetail = document.getElementById("scriptSectionTargetDetail");
const scriptSectionManualText = document.getElementById("scriptSectionManualText");
const scriptSectionSaveManual = document.getElementById("scriptSectionSaveManual");
const scriptSectionReason = document.getElementById("scriptSectionReason");
const scriptSectionInstruction = document.getElementById("scriptSectionInstruction");
const scriptSectionAccept = document.getElementById("scriptSectionAccept");
const scriptSectionLock = document.getElementById("scriptSectionLock");
const scriptSectionUnlock = document.getElementById("scriptSectionUnlock");
const scriptSectionRework = document.getElementById("scriptSectionRework");
const scriptSectionCancelRework = document.getElementById("scriptSectionCancelRework");
const scriptSectionPrepareRework = document.getElementById("scriptSectionPrepareRework");
const scriptSectionGenerate = document.getElementById("scriptSectionGenerate");
const scriptSectionAlternatives = document.getElementById("scriptSectionAlternatives");
const scriptSectionAlternativeCards = document.getElementById("scriptSectionAlternativeCards");

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
const visualCandidateReviewPanel = document.getElementById("visualCandidateReviewPanel");
const visualCandidateReviewTitle = document.getElementById("visualCandidateReviewTitle");
const visualCandidateReviewSummary = document.getElementById("visualCandidateReviewSummary");
const visualCandidateReviewStatus = document.getElementById("visualCandidateReviewStatus");
const visualShotDetail = document.getElementById("visualShotDetail");
const visualCandidateCards = document.getElementById("visualCandidateCards");
const visualCandidateNote = document.getElementById("visualCandidateNote");
const visualShotPrev = document.getElementById("visualShotPrev");
const visualRejectAll = document.getElementById("visualRejectAll");
const visualNeedsBetter = document.getElementById("visualNeedsBetter");
const visualShotNext = document.getElementById("visualShotNext");
const storyboardCreativeInstruction = document.getElementById("storyboardCreativeInstruction");
const storyboardDesiredVisual = document.getElementById("storyboardDesiredVisual");
const storyboardSearchTerms = document.getElementById("storyboardSearchTerms");
const storyboardFraming = document.getElementById("storyboardFraming");
const storyboardCameraAngle = document.getElementById("storyboardCameraAngle");
const storyboardCameraMovement = document.getElementById("storyboardCameraMovement");
const storyboardLens = document.getElementById("storyboardLens");
const storyboardLighting = document.getElementById("storyboardLighting");
const storyboardTransition = document.getElementById("storyboardTransition");
const storyboardSaveRevision = document.getElementById("storyboardSaveRevision");

const visualRightsReviewPanel = document.getElementById("visualRightsReviewPanel");
const visualRightsReviewTitle = document.getElementById("visualRightsReviewTitle");
const visualRightsReviewSummary = document.getElementById("visualRightsReviewSummary");
const visualRightsReviewStatus = document.getElementById("visualRightsReviewStatus");
const visualRightsDetail = document.getElementById("visualRightsDetail");
const visualRightsPurpose = document.getElementById("visualRightsPurpose");
const visualRightsNote = document.getElementById("visualRightsNote");
const visualRightsPrev = document.getElementById("visualRightsPrev");
const visualRightsReject = document.getElementById("visualRightsReject");
const visualRightsApprove = document.getElementById("visualRightsApprove");
const visualRightsNext = document.getElementById("visualRightsNext");

const managedVisualImportPanel = document.getElementById("managedVisualImportPanel");
const managedVisualImportTitle = document.getElementById("managedVisualImportTitle");
const managedVisualImportSummary = document.getElementById("managedVisualImportSummary");
const managedVisualImportStatus = document.getElementById("managedVisualImportStatus");
const managedVisualImportDetail = document.getElementById("managedVisualImportDetail");
const managedVisualAssetPath = document.getElementById("managedVisualAssetPath");
const managedVisualNote = document.getElementById("managedVisualNote");
const managedVisualPrev = document.getElementById("managedVisualPrev");
const managedVisualRegister = document.getElementById("managedVisualRegister");
const managedVisualNext = document.getElementById("managedVisualNext");

const visualRoughCutReviewPanel = document.getElementById("visualRoughCutReviewPanel");
const visualRoughCutReviewTitle = document.getElementById("visualRoughCutReviewTitle");
const visualRoughCutReviewSummary = document.getElementById("visualRoughCutReviewSummary");
const visualRoughCutReviewStatus = document.getElementById("visualRoughCutReviewStatus");
const visualRoughCutDetail = document.getElementById("visualRoughCutDetail");
const visualRoughCutShotSelect = document.getElementById("visualRoughCutShotSelect");
const visualRoughCutNote = document.getElementById("visualRoughCutNote");
const visualRoughCutPrev = document.getElementById("visualRoughCutPrev");
const visualRoughCutVisual = document.getElementById("visualRoughCutVisual");
const visualRoughCutPacing = document.getElementById("visualRoughCutPacing");
const visualRoughCutAudio = document.getElementById("visualRoughCutAudio");
const visualRoughCutApprove = document.getElementById("visualRoughCutApprove");
const visualRoughCutNext = document.getElementById("visualRoughCutNext");

const visualSpendReviewPanel = document.getElementById("visualSpendReviewPanel");
const visualSpendReviewTitle = document.getElementById("visualSpendReviewTitle");
const visualSpendReviewSummary = document.getElementById("visualSpendReviewSummary");
const visualSpendReviewStatus = document.getElementById("visualSpendReviewStatus");
const visualSpendDetail = document.getElementById("visualSpendDetail");
const visualSpendMaxCost = document.getElementById("visualSpendMaxCost");
const visualSpendNote = document.getElementById("visualSpendNote");
const visualSpendPrev = document.getElementById("visualSpendPrev");
const visualSpendRetry = document.getElementById("visualSpendRetry");
const visualSpendKeep = document.getElementById("visualSpendKeep");
const visualSpendAuthorize = document.getElementById("visualSpendAuthorize");
const visualSpendNext = document.getElementById("visualSpendNext");

const generatedVisualImportPanel = document.getElementById("generatedVisualImportPanel");
const generatedVisualImportTitle = document.getElementById("generatedVisualImportTitle");
const generatedVisualImportSummary = document.getElementById("generatedVisualImportSummary");
const generatedVisualImportStatus = document.getElementById("generatedVisualImportStatus");
const generatedVisualImportDetail = document.getElementById("generatedVisualImportDetail");
const generatedVisualAssetPath = document.getElementById("generatedVisualAssetPath");
const generatedVisualActualCost = document.getElementById("generatedVisualActualCost");
const generatedVisualProvider = document.getElementById("generatedVisualProvider");
const generatedVisualProviderJobId = document.getElementById("generatedVisualProviderJobId");
const generatedVisualNote = document.getElementById("generatedVisualNote");
const generatedVisualPrev = document.getElementById("generatedVisualPrev");
const generatedVisualRegister = document.getElementById("generatedVisualRegister");
const generatedVisualNext = document.getElementById("generatedVisualNext");

const editPreviewReviewPanel = document.getElementById("editPreviewReviewPanel");
const editPreviewReviewTitle = document.getElementById("editPreviewReviewTitle");
const editPreviewReviewSummary = document.getElementById("editPreviewReviewSummary");
const editPreviewReviewStatus = document.getElementById("editPreviewReviewStatus");
const editPreviewVideo = document.getElementById("editPreviewVideo");
const editPreviewDetail = document.getElementById("editPreviewDetail");
const editPreviewNote = document.getElementById("editPreviewNote");
const editPreviewPrev = document.getElementById("editPreviewPrev");
const editPreviewVisuals = document.getElementById("editPreviewVisuals");
const editPreviewNarration = document.getElementById("editPreviewNarration");
const editPreviewSound = document.getElementById("editPreviewSound");
const editPreviewApprove = document.getElementById("editPreviewApprove");
const editPreviewNext = document.getElementById("editPreviewNext");

const previewReviewPanel = document.getElementById("previewReviewPanel");
const previewReviewTitle = document.getElementById("previewReviewTitle");
const previewReviewSummary = document.getElementById("previewReviewSummary");
const previewReviewStatus = document.getElementById("previewReviewStatus");
const previewDetail = document.getElementById("previewDetail");
const previewNote = document.getElementById("previewNote");
const previewScript = document.getElementById("previewScript");
const previewPerformance = document.getElementById("previewPerformance");
const previewSound = document.getElementById("previewSound");
const previewApprove = document.getElementById("previewApprove");
const narrationSegmentSelect = document.getElementById("narrationSegmentSelect");
const narrationLockedWords = document.getElementById("narrationLockedWords");
const narrationCreativeInstruction = document.getElementById("narrationCreativeInstruction");
const narrationEmotion = document.getElementById("narrationEmotion");
const narrationIntensity = document.getElementById("narrationIntensity");
const narrationSpeed = document.getElementById("narrationSpeed");
const narrationPauseBefore = document.getElementById("narrationPauseBefore");
const narrationPauseAfter = document.getElementById("narrationPauseAfter");
const narrationEmphasis = document.getElementById("narrationEmphasis");
const narrationSaveRevision = document.getElementById("narrationSaveRevision");

const narrationSpendReviewPanel = document.getElementById("narrationSpendReviewPanel");
const narrationSpendReviewTitle = document.getElementById("narrationSpendReviewTitle");
const narrationSpendReviewSummary = document.getElementById("narrationSpendReviewSummary");
const narrationSpendReviewStatus = document.getElementById("narrationSpendReviewStatus");
const narrationSpendDetail = document.getElementById("narrationSpendDetail");
const narrationSpendCriteria = document.getElementById("narrationSpendCriteria");
const narrationSpendNote = document.getElementById("narrationSpendNote");
const narrationSpendPrev = document.getElementById("narrationSpendPrev");
const narrationSpendReject = document.getElementById("narrationSpendReject");
const narrationSpendRework = document.getElementById("narrationSpendRework");
const narrationSpendAccept = document.getElementById("narrationSpendAccept");
const narrationSpendNext = document.getElementById("narrationSpendNext");

const narrationReturnPanel = document.getElementById("narrationReturnPanel");
const narrationReturnTitle = document.getElementById("narrationReturnTitle");
const narrationReturnSummary = document.getElementById("narrationReturnSummary");
const narrationReturnStatus = document.getElementById("narrationReturnStatus");
const narrationReturnDetail = document.getElementById("narrationReturnDetail");
const narrationProviderJobId = document.getElementById("narrationProviderJobId");
const narrationActualCost = document.getElementById("narrationActualCost");
const narrationReturnSegments = document.getElementById("narrationReturnSegments");
const narrationReturnPrev = document.getElementById("narrationReturnPrev");
const narrationReturnRegister = document.getElementById("narrationReturnRegister");
const narrationReturnNext = document.getElementById("narrationReturnNext");

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
let runningUiTimer = null;
let runningJobId = null;
let runningJobStartedAt = null;
let runningLastPollAt = null;
let runningLastOutputAt = null;
let runningLastLogSignature = "";
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
let latestScriptSectionSnapshot = null;
let scriptSectionTargetId = null;
let scriptSectionRenderedTargetId = null;
let scriptSectionBusy = false;
let scriptSectionBusyAction = null;
let scriptSectionLoadToken = 0;
let latestFormatSnapshot = null;
let formatCursor = 0;
let formatEditing = false;
let latestPerformanceSnapshot = null;
let performanceCursor = 0;
let performanceEditing = false;
let latestEditPreviewSnapshot = null;
let editPreviewCursor = 0;
let latestPreviewSnapshot = null;
let latestNarrationSpendSnapshot = null;
let narrationSpendCursor = 0;
let latestNarrationReturnSnapshot = null;
let narrationReturnCursor = 0;
let latestNarrationPerformanceSnapshot = null;
let latestVisualCandidateSnapshot = null;
let visualShotCursor = 0;
let latestStoryboardSnapshot = null;
let latestVisualRightsSnapshot = null;
let visualRightsCursor = 0;
let latestManagedVisualAcquisition = null;
let latestManagedVisualAssets = null;
let managedVisualCursor = 0;
let latestVisualRoughCutSnapshot = null;
let visualRoughCutCursor = 0;
let latestVisualSpendSnapshot = null;
let visualSpendCursor = 0;
let latestGeneratedVisualHandoff = null;
let latestGeneratedVisualAssets = null;
let generatedVisualCursor = 0;

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
    state === "HUMAN_PACKAGING_GATE" ||
    state === "HUMAN_RESEARCH_GATE" ||
    state === "HUMAN_SCRIPT_GATE" ||
    state === "HUMAN_FORMAT_GATE" ||
    state === "HUMAN_PERFORMANCE_GATE" ||
    state === "HUMAN_NARRATION_PREVIEW_GATE" ||
    state === "HUMAN_NARRATION_SPEND_GATE" ||
    state === "WAITING_NARRATION_PROVIDER_QUOTE" ||
    state === "NARRATION_PROVIDER_SETUP_REQUIRED" ||
    state === "WAITING_NARRATION_RENDER_RETURN" ||
    state === "NARRATION_AUDIO_QC_FAILED" ||
    state === "HUMAN_VISUAL_CANDIDATE_GATE" ||
    state === "HUMAN_VISUAL_RIGHTS_GATE" ||
    state === "HUMAN_ROUGH_CUT_GATE" ||
    state === "HUMAN_VISUAL_SPEND_GATE" ||
    state === "HUMAN_EDIT_PREVIEW_GATE"
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
  const analysisHumanGateLabels = {
    HUMAN_ANALYSIS_GATE: "Review analysis findings",
    HUMAN_CONCEPT_GATE: "Review concepts",
    HUMAN_PACKAGING_GATE: "Review packages",
    HUMAN_RESEARCH_GATE: "Review research",
    HUMAN_SCRIPT_GATE: "Review script",
    HUMAN_FORMAT_GATE: "Review format",
    HUMAN_PERFORMANCE_GATE: "Review performance",
    HUMAN_NARRATION_PREVIEW_GATE: "Listen to prototype",
    HUMAN_NARRATION_SPEND_GATE: "Review narration spend",
    WAITING_NARRATION_RENDER_RETURN: "Register final narration",
    NARRATION_AUDIO_QC_FAILED: "Fix narration audio",
    NARRATION_AUDIO_READY: "Narration audio ready",
    HUMAN_VISUAL_CANDIDATE_GATE: "Choose visuals",
    HUMAN_VISUAL_RIGHTS_GATE: "Review footage context",
    HUMAN_ROUGH_CUT_GATE: "Review rough cut",
    HUMAN_VISUAL_SPEND_GATE: "Review visual spend"
  };
  if (analysisHumanGateLabels[workflow.state]) {
    return {
      type: "route",
      value: "/analysis",
      label: analysisHumanGateLabels[workflow.state]
    };
  }
  if (workflow.current_action_id) {
    return {
      type: "action",
      value: workflow.current_action_id,
      label: workflow.current_action_id === "opportunity_research"
        ? "Run now"
        : "Continue Automatically"
    };
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

  conceptCriteria.innerHTML = "";

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
        criteria: {},
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
    if (payload.complete) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
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

function packagingTitleChoicesHtml(format, candidates, selected) {
  const list = Array.isArray(candidates) ? candidates : [];
  const chosenId = selected && selected.candidate_id ? String(selected.candidate_id) : "";
  const chosenTitle = selected && selected.title ? String(selected.title) : "";
  const label = format === "short" ? "SHORT TITLE" : "LONG-FORM TITLE";
  const radioName = "packaging-title-" + format;
  let html = '<div class="concept-detail-card"><h4>' + label + '</h4>';
  if (!list.length) {
    html += '<p>No title candidates available.</p>';
  } else {
    list.forEach(function (candidate) {
      const candidateId = String(candidate.candidate_id || "");
      const candidateTitle = String(candidate.title || "");
      const checked = chosenId === candidateId ? " checked" : "";
      html += '<label class="criterion-item">' +
        '<input type="radio" name="' + escapeHtml(radioName) + '" value="' +
        escapeHtml(candidateId) + '" data-title="' + escapeHtml(candidateTitle) + '"' +
        checked + '>' +
        '<span><strong>' + escapeHtml(humanizeToken(candidate.angle || "")) +
        '</strong> — ' + escapeHtml(candidateTitle) + '</span></label>';
    });
  }
  const manualChecked = chosenId === "manual" ? " checked" : "";
  const manualValue = chosenId === "manual" ? chosenTitle : "";
  html += '<label class="criterion-item">' +
    '<input type="radio" name="' + escapeHtml(radioName) + '" value="manual"' +
    manualChecked + '>' +
    '<span><strong>Custom</strong> — edit your own title</span></label>' +
    '<input class="text-input packaging-title-manual" data-format="' +
    escapeHtml(format) + '" type="text" maxlength="' +
    (format === "short" ? "48" : "70") + '" value="' +
    escapeHtml(manualValue) + '" placeholder="Type a custom ' +
    (format === "short" ? "Short" : "Long-form") + ' title">' +
    '</div>';
  return html;
}

function collectPackagingTitleSelections() {
  const result = {};
  ["short", "long_form"].forEach(function (format) {
    const checked = packagingDetail.querySelector(
      'input[name="packaging-title-' + format + '"]:checked'
    );
    if (!checked) {
      throw new Error(
        format === "short"
          ? "Choose a Short title before accepting."
          : "Choose a Long-form title before accepting."
      );
    }
    const candidateId = String(checked.value || "");
    let title = String(checked.dataset.title || "");
    if (candidateId === "manual") {
      const manual = packagingDetail.querySelector(
        '.packaging-title-manual[data-format="' + format + '"]'
      );
      title = String((manual && manual.value) || "").trim();
      if (!title) {
        throw new Error(
          format === "short"
            ? "Enter the custom Short title."
            : "Enter the custom Long-form title."
        );
      }
    }
    result[format] = { candidate_id: candidateId, title: title };
  });
  return result;
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
    packagingSaveIdea.disabled = true;
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
  const titleSets = pkg.titles || {};
  const selectedTitles = pkg.selected_titles || {};
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
      '<h4>TITLE SELECTION</h4>' +
      '<p>Choose one Short title and one Long-form title. The two formats are independent; the thumbnail should add information rather than repeat either title.</p>' +
      '<div class="concept-meta">' +
        '<span>' + escapeHtml(humanizeToken(pkg.format_intent)) + '</span>' +
        '<span>Concept ' + escapeHtml(pkg.concept_id || "") + '</span>' +
      '</div>' +
    '</div>' +
    packagingTitleChoicesHtml("short", titleSets.short, selectedTitles.short) +
    packagingTitleChoicesHtml("long_form", titleSets.long_form, selectedTitles.long_form) +
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

  packagingCriteria.innerHTML = "";

  packagingNote.value = pkg.note || "";
  packagingPrev.disabled = packagingCursor <= 0;
  packagingNext.disabled = packagingCursor >= items.length - 1;
  packagingReject.disabled = false;
  packagingRework.disabled = false;
  packagingSaveIdea.disabled = false;
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
    const selectedTitles =
      decision === "ACCEPT" ? collectPackagingTitleSelections() : null;
    const payload = await api("/api/packaging-gate", {
      method: "POST",
      body: JSON.stringify({
        package_id: pkg.package_id,
        decision: decision,
        criteria: {},
        note: packagingNote.value,
        selected_titles: selectedTitles
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
          : decision === "SAVE_IDEA"
            ? "Package saved for later."
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

  researchCriteria.innerHTML = "";

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
        criteria: {},
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


function scriptSectionTargetLabel(target) {
  const marker = target.locked
    ? "🔒 "
    : target.decision === "REWORK_REQUESTED"
      ? "⚠ "
      : "";
  const name = target.section_id ||
    humanizeToken(target.target_type || target.target_id || "Target");
  return marker + name + " — " + humanizeToken(target.decision || "PENDING");
}

function currentScriptSectionTarget() {
  const targets = (latestScriptSectionSnapshot && latestScriptSectionSnapshot.targets) || [];
  if (!targets.length) return null;
  const selected = scriptSectionTargetId ||
    (scriptSectionTarget && scriptSectionTarget.value) ||
    targets[0].target_id;
  return targets.find(function (target) {
    return target.target_id === selected;
  }) || targets[0];
}

function scriptSectionCounts(targets) {
  const result = {
    total: (targets || []).length,
    accepted: 0,
    rework: 0,
    pending: 0,
    locked: 0
  };
  (targets || []).forEach(function (target) {
    if (target.decision === "ACCEPTED") result.accepted += 1;
    else if (target.decision === "REWORK_REQUESTED") result.rework += 1;
    else result.pending += 1;
    if (target.locked) result.locked += 1;
  });
  return result;
}

function scriptSectionStatusTone(target) {
  if (!target) return "running";
  if (target.decision === "ACCEPTED") return "success";
  if (target.decision === "REWORK_REQUESTED") return "failed";
  return "running";
}

function unresolvedScriptSectionTargets(targets) {
  return (targets || []).filter(function (target) {
    return target.decision !== "ACCEPTED";
  });
}

function nextUnresolvedScriptSectionTarget(targets, currentId) {
  const unresolved = unresolvedScriptSectionTargets(targets);
  if (!unresolved.length) return null;
  const currentIndex = unresolved.findIndex(function (target) {
    return target.target_id === currentId;
  });
  if (currentIndex < 0 || currentIndex >= unresolved.length - 1) {
    return unresolved[0];
  }
  return unresolved[currentIndex + 1];
}

function syncWholeScriptAcceptWithSectionState(snapshot) {
  if (!latestScriptSnapshot || latestScriptSnapshot.complete) return;
  const status = String((snapshot && snapshot.status) || "");
  const targets = (snapshot && snapshot.targets) || [];
  const prepared = status === "READY_FOR_SECTION_REVIEW";
  const unresolved = prepared && targets.some(function (target) {
    return target.decision !== "ACCEPTED" || target.locked !== true;
  });
  const stale = status === "STALE_SECTION_STATE";
  scriptReject.disabled = Boolean(scriptSectionBusy);
  scriptRework.disabled = Boolean(scriptSectionBusy);
  scriptAccept.disabled = Boolean(scriptSectionBusy || unresolved || stale);
  scriptAccept.title = stale
    ? "Resolve the stale section-review state before whole-script approval."
    : unresolved
      ? "Finish the prepared section review before whole-script approval."
      : scriptSectionBusy
        ? "Wait for the current section action to finish."
        : "";
}

function scriptSectionBusyLabel(action) {
  const labels = {
    PREPARE: "Preparing section review…",
    ACCEPT: "Accepting target…",
    LOCK: "Locking target…",
    UNLOCK: "Unlocking target…",
    REWORK: "Recording rework request…",
    CANCEL_REWORK: "Cancelling rework…",
    PREPARE_REWORK_REQUEST: "Preparing bounded request…",
    GENERATE_ALTERNATIVES: "Generating A / B / C…",
    SELECT_ALTERNATIVE: "Applying selection…",
    MANUAL_EDIT: "Saving manual edit…"
  };
  return labels[action] || "Updating section review…";
}

async function refreshScriptGateAfterSectionAction(conceptId, format) {
  const preservedNote = scriptNote.value;
  const preserveEditing = scriptEditing;
  const payload = await api("/api/script-gate");
  const items = payload.scripts || [];
  const index = items.findIndex(function (item) {
    return String(item.concept_id || "") === String(conceptId || "") &&
      String(item.format || "") === String(format || "");
  });
  if (index >= 0) scriptCursor = index;
  renderScriptReview(payload, true);
  if (preserveEditing) {
    scriptNote.value = preservedNote;
    scriptEditing = true;
  }
}

function renderScriptSectionReview(snapshot) {
  latestScriptSectionSnapshot = snapshot || {};
  const status = String((snapshot && snapshot.status) || "");
  const targets = (snapshot && snapshot.targets) || [];
  const counts = scriptSectionCounts(targets);

  scriptSectionPrepare.hidden = status !== "SECTION_STATE_NOT_PREPARED";
  scriptSectionControls.hidden = status !== "READY_FOR_SECTION_REVIEW";
  scriptSectionProgress.innerHTML = targets.length
    ? '<span class="script-section-stat success">' +
        counts.accepted + ' accepted</span>' +
      '<span class="script-section-stat">' +
        counts.pending + ' pending</span>' +
      '<span class="script-section-stat attention">' +
        counts.rework + ' rework</span>' +
      '<span class="script-section-stat">' +
        counts.locked + ' locked</span>'
    : "";

  if (scriptSectionBusy) {
    scriptSectionReviewState.textContent =
      scriptSectionBusyLabel(scriptSectionBusyAction);
  }

  if (status === "SECTION_STATE_NOT_PREPARED") {
    if (!scriptSectionBusy) {
      scriptSectionReviewState.textContent =
        "Prepare section review to enable target-level decisions.";
    }
    scriptSectionTargetStatus.textContent = "NOT PREPARED";
    scriptSectionTargetStatus.className = "status-chip running";
    scriptSectionAlternativeCards.innerHTML = "";
    scriptSectionAlternatives.hidden = true;
    scriptSectionPrepare.disabled = scriptSectionBusy;
    syncWholeScriptAcceptWithSectionState(snapshot);
    return;
  }

  if (status === "STALE_SECTION_STATE") {
    scriptSectionReviewState.textContent =
      "Section state is stale because the script draft changed. " +
      "Resolve/reset the section state before continuing.";
    scriptSectionTargetStatus.textContent = "STALE";
    scriptSectionTargetStatus.className = "status-chip failed";
    scriptSectionControls.hidden = true;
    scriptSectionPrepare.hidden = true;
    syncWholeScriptAcceptWithSectionState(snapshot);
    return;
  }

  if (status !== "READY_FOR_SECTION_REVIEW") {
    scriptSectionReviewState.textContent =
      status === "SCRIPT_DRAFT_NOT_FOUND"
        ? "The current script draft is not available."
        : "Selective section review is not ready.";
    scriptSectionTargetStatus.textContent = humanizeToken(status || "WAITING");
    scriptSectionTargetStatus.className = "status-chip running";
    scriptSectionControls.hidden = true;
    syncWholeScriptAcceptWithSectionState(snapshot);
    return;
  }

  if (!targets.length) {
    scriptSectionReviewState.textContent = "No script targets are available.";
    scriptSectionTargetStatus.textContent = "EMPTY";
    scriptSectionTargetStatus.className = "status-chip failed";
    scriptSectionControls.hidden = true;
    syncWholeScriptAcceptWithSectionState(snapshot);
    return;
  }

  if (!scriptSectionBusy) {
    scriptSectionReviewState.textContent =
      "State v" + String(snapshot.state_version || "—") +
      " · " + counts.accepted + " of " + counts.total +
      " targets accepted.";
  }

  const existingTarget = scriptSectionTargetId || scriptSectionTarget.value;
  let selected = targets.find(function (target) {
    return target.target_id === existingTarget;
  });
  if (!selected) {
    selected =
      targets.find(function (target) {
        return target.decision === "REWORK_REQUESTED";
      }) ||
      targets.find(function (target) {
        return target.decision === "PENDING";
      }) ||
      targets[0];
  }
  scriptSectionTargetId = selected.target_id;

  scriptSectionTarget.innerHTML = targets.map(function (target) {
    return '<option value="' + escapeHtml(target.target_id || "") + '">' +
      escapeHtml(scriptSectionTargetLabel(target)) +
      '</option>';
  }).join("");
  scriptSectionTarget.value = selected.target_id;
  scriptSectionTarget.disabled = scriptSectionBusy;

  scriptSectionTargetStatus.textContent =
    humanizeToken(selected.decision || "PENDING") +
    (selected.locked ? " · LOCKED" : "");
  scriptSectionTargetStatus.className =
    "status-chip " + scriptSectionStatusTone(selected);

  const meta = selected.metadata || {};
  const claimIds = meta.claim_ids || meta.opening_hook_claim_ids || [];
  const storyBeatIds = meta.source_story_beat_ids || [];
  const reworkDetail = selected.decision === "REWORK_REQUESTED"
    ? '<div class="script-section-rework-current"><strong>Requested:</strong> ' +
      escapeHtml(humanizeToken(selected.rework_reason || "CUSTOM")) +
      (selected.custom_instruction
        ? '<br>' + escapeHtml(selected.custom_instruction)
        : "") +
      '</div>'
    : "";
  scriptSectionTargetDetail.innerHTML =
    '<div class="script-section-target-copy">' +
      '<strong>' + escapeHtml(
        selected.section_id || humanizeToken(selected.target_type || "Target")
      ) + '</strong>' +
      '<p>' + escapeHtml(selected.text || "") + '</p>' +
    '</div>' +
    '<div class="concept-meta">' +
      (meta.psychology_mechanism
        ? '<span>Psychology: ' +
          escapeHtml(humanizeToken(meta.psychology_mechanism)) + '</span>'
        : '') +
      (meta.reward_type
        ? '<span>Reward: ' + escapeHtml(humanizeToken(meta.reward_type)) + '</span>'
        : '') +
      (storyBeatIds.length
        ? '<span>Story beats: ' + escapeHtml(storyBeatIds.join(", ")) + '</span>'
        : '') +
      '<span>Claims: ' + escapeHtml(claimIds.join(", ") || "none") + '</span>' +
    '</div>' +
    reworkDetail;

  const reasons = snapshot.rework_reasons || [];
  const targetChanged = scriptSectionRenderedTargetId !== selected.target_id;
  const currentReason = targetChanged
    ? String(selected.rework_reason || "")
    : String(scriptSectionReason.value || selected.rework_reason || "");
  scriptSectionReason.innerHTML =
    '<option value="">Select reason</option>' +
    reasons.map(function (reason) {
      return '<option value="' + escapeHtml(reason) + '">' +
        escapeHtml(humanizeToken(reason)) +
        '</option>';
    }).join("");
  if (reasons.includes(currentReason)) {
    scriptSectionReason.value = currentReason;
  }
  if (targetChanged) {
    scriptSectionInstruction.value = selected.custom_instruction || "";
    scriptSectionManualText.value = selected.text || "";
    scriptSectionRenderedTargetId = selected.target_id;
  }

  const locked = Boolean(selected.locked);
  const reworkRequested = selected.decision === "REWORK_REQUESTED";
  const acceptedLocked = selected.decision === "ACCEPTED" && locked;
  const nextUnresolved = nextUnresolvedScriptSectionTarget(
    targets,
    selected.target_id
  );

  scriptSectionNextPending.disabled =
    scriptSectionBusy || !nextUnresolved ||
    nextUnresolved.target_id === selected.target_id ||
    (counts.accepted === counts.total);
  scriptSectionNextPending.textContent = counts.accepted === counts.total
    ? "All targets resolved"
    : "Next unresolved →";

  scriptSectionAccept.disabled = scriptSectionBusy || acceptedLocked;
  scriptSectionLock.disabled = scriptSectionBusy || locked || reworkRequested;
  scriptSectionUnlock.disabled = scriptSectionBusy || !locked;
  scriptSectionRework.disabled = scriptSectionBusy || locked || reworkRequested;
  scriptSectionCancelRework.disabled = scriptSectionBusy || !reworkRequested;
  scriptSectionCancelRework.hidden = !reworkRequested;
  scriptSectionPrepareRework.disabled = scriptSectionBusy || !reworkRequested;
  scriptSectionGenerate.disabled = scriptSectionBusy || !reworkRequested;
  scriptSectionManualText.disabled = scriptSectionBusy || locked;
  scriptSectionSaveManual.disabled = scriptSectionBusy || locked;
  scriptSectionReason.disabled =
    scriptSectionBusy || locked || reworkRequested;
  scriptSectionInstruction.disabled =
    scriptSectionBusy || locked || reworkRequested;

  scriptSectionPrepareRework.textContent =
    scriptSectionBusy && scriptSectionBusyAction === "PREPARE_REWORK_REQUEST"
      ? "Preparing…"
      : "Prepare rework request";
  scriptSectionGenerate.textContent =
    scriptSectionBusy && scriptSectionBusyAction === "GENERATE_ALTERNATIVES"
      ? "Generating…"
      : "Generate A / B / C";

  const alternatives = selected.alternatives;
  if (!alternatives) {
    scriptSectionAlternatives.hidden = true;
    scriptSectionAlternativeCards.innerHTML = "";
    syncWholeScriptAcceptWithSectionState(snapshot);
    return;
  }

  scriptSectionAlternatives.hidden = false;
  const selection = alternatives.selection || null;
  if (selection) {
    scriptSectionAlternativeCards.innerHTML =
      '<div class="concept-complete">Selected <strong>' +
      escapeHtml(selection.selection_id || "") +
      '</strong> · target is accepted and locked.</div>';
    syncWholeScriptAcceptWithSectionState(snapshot);
    return;
  }

  const original = alternatives.original || {};
  const originalCard =
    '<article class="script-section-alternative-card original">' +
      '<div class="script-section-alternative-label">ORIGINAL</div>' +
      '<p>' + escapeHtml(original.text || selected.text || "") + '</p>' +
      '<div class="concept-meta"><span>Claims: ' +
        escapeHtml(claimIds.join(", ") || "none") +
      '</span></div>' +
      '<button class="ghost" type="button" data-script-section-selection="ORIGINAL"' +
      (scriptSectionBusy ? " disabled" : "") +
      '>Keep original</button>' +
    '</article>';

  const optionCards = (alternatives.alternatives || []).map(function (item) {
    return '<article class="script-section-alternative-card">' +
      '<div class="script-section-alternative-label">OPTION ' +
        escapeHtml(item.alternative_id || "") + '</div>' +
      '<p>' + escapeHtml(item.replacement_text || "") + '</p>' +
      '<p class="muted">' + escapeHtml(item.change_summary || "") + '</p>' +
      '<div class="concept-meta"><span>Claims used: ' +
        escapeHtml((item.claim_ids_used || []).join(", ") || "none") +
      '</span></div>' +
      '<button type="button" data-script-section-selection="' +
        escapeHtml(item.alternative_id || "") + '"' +
        (scriptSectionBusy ? " disabled" : "") +
      '>Use ' + escapeHtml(item.alternative_id || "") + '</button>' +
    '</article>';
  }).join("");

  scriptSectionAlternativeCards.innerHTML = originalCard + optionCards;
  syncWholeScriptAcceptWithSectionState(snapshot);
}

async function loadScriptSectionReviewForCurrent() {
  const current = currentScriptItem();
  if (!current) return;
  const script = current.item || {};
  const conceptId = String(script.concept_id || "");
  const format = String(script.format || "");
  if (!conceptId || !format) return;

  const token = ++scriptSectionLoadToken;
  try {
    const payload = await api(
      "/api/script-section-review?concept_id=" +
      encodeURIComponent(conceptId) +
      "&format=" +
      encodeURIComponent(format)
    );
    if (token !== scriptSectionLoadToken) return;
    const latest = currentScriptItem();
    if (
      !latest ||
      String(latest.item.concept_id || "") !== conceptId ||
      String(latest.item.format || "") !== format
    ) {
      return;
    }
    renderScriptSectionReview(payload);
  } catch (error) {
    if (token !== scriptSectionLoadToken) return;
    scriptSectionReviewState.textContent =
      "Selective review error: " + error.message;
  }
}

async function submitScriptSectionAction(action, extra) {
  const current = currentScriptItem();
  if (!current || scriptSectionBusy) return;
  const script = current.item || {};
  const target = currentScriptSectionTarget();
  const extras = extra || {};
  const reason = scriptSectionReason.value || null;
  const instruction = scriptSectionInstruction.value.trim();

  if (action !== "PREPARE" && !target) {
    showToast("Choose a script target first.", true);
    return;
  }
  if (action === "REWORK") {
    if (!reason && !instruction) {
      showToast("Choose a rework reason or enter a specific instruction.", true);
      scriptSectionReason.focus();
      return;
    }
    if (reason === "CUSTOM" && !instruction) {
      showToast("Custom rework requires a specific instruction.", true);
      scriptSectionInstruction.focus();
      return;
    }
  }
  if (action === "MANUAL_EDIT") {
    const replacement = scriptSectionManualText.value.trim();
    if (!replacement) {
      showToast("Manual target text cannot be empty.", true);
      scriptSectionManualText.focus();
      return;
    }
    if (target && replacement === String(target.text || "").trim()) {
      showToast("Manual edit must change the selected target.", true);
      scriptSectionManualText.focus();
      return;
    }
  }
  if (
    action === "SELECT_ALTERNATIVE" &&
    !["ORIGINAL", "A", "B", "C"].includes(String(extras.selection_id || "").toUpperCase())
  ) {
    showToast("Choose Original, A, B or C.", true);
    return;
  }

  scriptSectionBusy = true;
  scriptSectionBusyAction = action;
  if (latestScriptSectionSnapshot) {
    renderScriptSectionReview(latestScriptSectionSnapshot);
  }

  try {
    const body = {
      concept_id: script.concept_id,
      format: script.format,
      action: action,
      target_id: target ? target.target_id : null,
      reason: reason,
      custom_instruction: instruction || null,
      selection_id: extras.selection_id || null,
      replacement_text: action === "MANUAL_EDIT"
        ? scriptSectionManualText.value
        : null
    };
    const payload = await api("/api/script-section-review", {
      method: "POST",
      body: JSON.stringify(body)
    });
    const sectionPayload = payload.section_review || payload;
    renderScriptSectionReview(sectionPayload);

    if (payload.status === "ALTERNATIVE_GENERATION_FAILED") {
      const generation = payload.generation || {};
      showToast(
        "Alternative generation failed: " +
        humanizeToken(generation.status || "UNKNOWN"),
        true
      );
    } else {
      const messages = {
        PREPARE: "Section review prepared.",
        ACCEPT: "Target accepted and locked.",
        LOCK: "Target locked.",
        UNLOCK: "Target unlocked.",
        REWORK: "Selective rework requested.",
        CANCEL_REWORK: "Selective rework cancelled.",
        PREPARE_REWORK_REQUEST: "Bounded rework request prepared. No model call was made.",
        GENERATE_ALTERNATIVES: "A / B / C alternatives are ready.",
        SELECT_ALTERNATIVE: "Selection applied. Review the updated script before whole-script approval.",
        MANUAL_EDIT: "Manual edit applied and locked. Review the updated script before whole-script approval."
      };
      showToast(messages[action] || "Script section updated.", false);
    }

    await refreshScriptGateAfterSectionAction(
      script.concept_id,
      script.format
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    scriptSectionBusy = false;
    scriptSectionBusyAction = null;
    if (latestScriptSectionSnapshot) {
      renderScriptSectionReview(latestScriptSectionSnapshot);
    }
  }
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
    loadScriptSectionReviewForCurrent();
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

  scriptCriteria.innerHTML = "";

  scriptNote.value = script.note || "";
  scriptPrev.disabled = scriptCursor <= 0;
  scriptNext.disabled = scriptCursor >= items.length - 1;
  scriptReject.disabled = false;
  scriptRework.disabled = false;
  scriptAccept.disabled = true;
  scriptAccept.title = "Checking section-review state…";
  scriptEditing = false;
  loadScriptSectionReviewForCurrent();
}

function moveScriptCursor(delta) {
  const current = currentScriptItem();
  if (!current) return;
  scriptCursor = Math.max(0, Math.min(current.items.length - 1, scriptCursor + delta));
  scriptEditing = false;
  scriptSectionTargetId = null;
  scriptSectionRenderedTargetId = null;
  latestScriptSectionSnapshot = null;
  scriptSectionLoadToken += 1;
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
  if (scriptSectionBusy) {
    showToast("Wait for the current section action to finish.", true);
    return;
  }
  if (
    decision === "ACCEPT" &&
    latestScriptSectionSnapshot &&
    latestScriptSectionSnapshot.status === "READY_FOR_SECTION_REVIEW" &&
    (latestScriptSectionSnapshot.targets || []).some(function (target) {
      return target.decision !== "ACCEPTED" || target.locked !== true;
    })
  ) {
    showToast("Finish the prepared section review before accepting the whole script.", true);
    return;
  }
  const script = current.item;
  try {
    const payload = await api("/api/script-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: script.concept_id,
        format: script.format,
        decision: decision,
        criteria: {},
        note: scriptNote.value
      })
    });
    scriptEditing = false;
    latestScriptSnapshot = payload;
    const nextPending = pendingScriptIndex(payload.scripts || []);
    if (nextPending >= 0) scriptCursor = nextPending;
    renderScriptReview(payload, true);
    const automaticFormatStarted = Boolean(
      decision === "ACCEPT" &&
      payload.automation_job &&
      payload.automation_job.action_id === "auto_continue"
    );
    showToast(
      automaticFormatStarted
        ? "Script Gate complete. Format planning started automatically."
        : decision === "ACCEPT"
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

  formatCriteria.innerHTML = "";

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
        criteria: {},
        note: formatNote.value
      })
    });
    formatEditing = false;
    latestFormatSnapshot = payload;
    const nextPending = pendingFormatIndex(payload.plans || []);
    if (nextPending >= 0) formatCursor = nextPending;
    renderFormatReview(payload, true);
    const automaticPerformanceStarted = Boolean(
      decision === "ACCEPT" &&
      payload.automation_job &&
      payload.automation_job.action_id === "auto_continue"
    );
    showToast(
      automaticPerformanceStarted
        ? "Format Gate complete. Voice Performance planning started automatically."
        : decision === "ACCEPT"
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

  performanceCriteria.innerHTML = "";

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
        criteria: {},
        note: performanceNote.value
      })
    });
    performanceEditing = false;
    latestPerformanceSnapshot = payload;
    const nextPending = pendingPerformanceIndex(payload.specs || []);
    if (nextPending >= 0) performanceCursor = nextPending;
    renderPerformanceReview(payload, true);
    const automaticPreviewStarted = Boolean(
      decision === "ACCEPT" &&
      payload.automation_job &&
      payload.automation_job.action_id === "auto_continue"
    );
    showToast(
      automaticPreviewStarted
        ? "Performance Gate complete. Free narration preview started automatically."
        : decision === "ACCEPT"
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

function currentPreviewItem() {
  const items = (latestPreviewSnapshot && latestPreviewSnapshot.items) || [];
  return items.find(function (item) { return !item.approved_for_paid_quote; }) || items[0] || null;
}

function narrationCurrentItem() {
  const items=(latestNarrationPerformanceSnapshot&&latestNarrationPerformanceSnapshot.items)||[];
  if(!items.length)return null;
  const previewItems=(latestPreviewSnapshot&&latestPreviewSnapshot.items)||[];
  const active=previewItems[0]||{};
  return items.find(function(x){return x.concept_id===active.concept_id&&x.format===active.format;})||items[0];
}
function fillNarrationSegmentEditor() {
  const item=narrationCurrentItem(); if(!item)return;
  const segments=item.segments||[];
  const currentId=narrationSegmentSelect.value||String((segments[0]||{}).segment_id||"");
  narrationSegmentSelect.innerHTML=segments.map(function(s){return '<option value="'+escapeHtml(s.segment_id)+'">'+escapeHtml(s.segment_id)+' · v'+escapeHtml(s.performance_version||1)+'</option>';}).join("");
  narrationSegmentSelect.value=segments.some(function(s){return String(s.segment_id)===currentId;})?currentId:String((segments[0]||{}).segment_id||"");
  const s=segments.find(function(x){return String(x.segment_id)===narrationSegmentSelect.value;});if(!s)return;
  const d=s.delivery||{};
  narrationLockedWords.innerHTML='<h4>LOCKED APPROVED WORDS</h4><p>'+escapeHtml(s.immutable_narration||"")+'</p>';
  narrationCreativeInstruction.value=s.creative_instruction||"";
  narrationEmotion.value=d.emotion||"";narrationIntensity.value=d.intensity||"";
  narrationSpeed.value=d.speed||1;narrationPauseBefore.value=d.pause_before_ms||0;narrationPauseAfter.value=d.pause_after_ms||0;
  narrationEmphasis.value=(d.emphasis_terms||[]).join(", ");
  narrationSaveRevision.dataset.manifestFile=item.manifest_file||"";narrationSaveRevision.dataset.segmentId=s.segment_id||"";
}
async function saveNarrationSegmentRevision(){
 try{
  await api("/api/narration-performance-review",{method:"POST",body:JSON.stringify({
   manifest_file:narrationSaveRevision.dataset.manifestFile,segment_id:narrationSaveRevision.dataset.segmentId,
   instruction:narrationCreativeInstruction.value,delivery_changes:{emotion:narrationEmotion.value,
    intensity:Number(narrationIntensity.value),speed:Number(narrationSpeed.value),pause_before_ms:Number(narrationPauseBefore.value),
    pause_after_ms:Number(narrationPauseAfter.value),emphasis_terms:narrationEmphasis.value.split(",").map(function(x){return x.trim();}).filter(Boolean)}
  })});
  latestNarrationPerformanceSnapshot=await api("/api/narration-performance-review");fillNarrationSegmentEditor();
  showToast("Narration segment revised. Re-render the free preview before approval.",false);
 }catch(error){showToast(error.message,true);}
}

function renderPreviewReview(snapshot) {
  latestPreviewSnapshot = snapshot || {};
  const items = (snapshot && snapshot.items) || [];
  if (!items.length) {
    previewReviewPanel.hidden = true;
    return;
  }
  previewReviewPanel.hidden = false;
  const item = currentPreviewItem();
  if (!item) return;
  previewReviewTitle.textContent = snapshot.complete
    ? "Free audio prototype approved"
    : "Listen before spending";
  previewReviewSummary.textContent =
    "This is a zero-cost draft for judging story, tone, spacing and sound design. Paid narration remains locked.";
  previewReviewStatus.textContent = item.decision || "PENDING";
  previewReviewStatus.className =
    "status-chip " + (item.approved_for_paid_quote ? "success" : "running");
  const audio = item.audio_ready
    ? '<audio controls preload="metadata" style="width:100%" src="/api/narration-preview-audio?concept_id=' +
      encodeURIComponent(item.concept_id || "") + '&format=' +
      encodeURIComponent(item.format || "") + '"></audio>'
    : '<p><strong>Audio not ready.</strong> Run the free local preview renderer first.</p>';
  previewDetail.innerHTML =
    '<div class="concept-detail-card"><h4>ZERO-COST PROTOTYPE</h4>' +
    '<h3>' + escapeHtml(item.concept_id || "Narration preview") + '</h3>' +
    '<p><strong>Branch:</strong> ' + escapeHtml(humanizeToken(item.format || "")) + '</p>' +
    audio +
    '<p class="muted">Music/SFX are draft editorial cues using local/free-compatible assets. Approval unlocks quote preparation only; it does not spend money.</p></div>';
  previewApprove.disabled = !item.audio_ready || Boolean(item.approved_for_paid_quote);
  previewScript.disabled = Boolean(item.approved_for_paid_quote);
  previewPerformance.disabled = Boolean(item.approved_for_paid_quote);
  previewSound.disabled = Boolean(item.approved_for_paid_quote);
  if (snapshot.complete) previewNote.value = "";
}

async function submitPreviewDecision(decision) {
  const item = currentPreviewItem();
  if (!item) return;
  try {
    const payload = await api("/api/narration-preview-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: item.concept_id,
        format: item.format,
        decision: decision,
        note: previewNote.value
      })
    });
    renderPreviewReview(payload);
    const automaticQuotePreparation = Boolean(
      decision === "APPROVE_FINAL" &&
      payload.automation_job &&
      payload.automation_job.action_id === "auto_continue"
    );
    showToast(
      automaticQuotePreparation
        ? "Free prototype approved. Sound brief and narration cost preparation started automatically."
        : decision === "APPROVE_FINAL"
          ? "Free prototype approved. Narration quote preparation is unlocked."
          : "Prototype sent back for " + humanizeToken(decision).toLowerCase() + ".",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function narrationSpendItems(snapshot) {
  return (snapshot && snapshot.items) || [];
}

function currentNarrationSpendItem() {
  const items = narrationSpendItems(latestNarrationSpendSnapshot || {});
  if (!items.length) return null;
  narrationSpendCursor = Math.max(
    0,
    Math.min(narrationSpendCursor, items.length - 1)
  );
  const firstPending = items.findIndex(function (item) {
    return (item.decision || "PENDING") === "PENDING";
  });
  if (firstPending >= 0 && (items[narrationSpendCursor].decision || "PENDING") !== "PENDING") {
    narrationSpendCursor = firstPending;
  }
  return items[narrationSpendCursor] || null;
}

function renderNarrationSpendReview(snapshot) {
  latestNarrationSpendSnapshot = snapshot || {};
  const items = narrationSpendItems(snapshot);
  narrationSpendReviewPanel.hidden = items.length === 0;
  if (!items.length) return;

  const item = currentNarrationSpendItem();
  if (!item) return;
  const decision = item.decision || "PENDING";
  narrationSpendReviewTitle.textContent =
    "Narration spend — " + humanizeToken(item.format || "");
  narrationSpendReviewSummary.textContent =
    (narrationSpendCursor + 1) + " of " + items.length +
    " branch" + (items.length === 1 ? "" : "es") +
    ". Accept authorizes up to the displayed worst-case cost; it does not itself call the provider.";
  narrationSpendReviewStatus.textContent = decision;
  narrationSpendReviewStatus.className =
    "status-chip " + (decision === "ACCEPT" ? "success" : decision === "PENDING" ? "running" : "failed");

  const currency = item.currency || "USD";
  const initial = Number(item.initial_estimate_usd);
  const worst = Number(item.worst_case_estimate_usd);
  const quote = item.provider_quote || {};
  narrationSpendDetail.innerHTML =
    '<div class="concept-detail-card"><h4>CURRENT PROVIDER QUOTE</h4>' +
    '<h3>' + escapeHtml(item.provider || "Narration provider") + '</h3>' +
    '<p><strong>Branch:</strong> ' + escapeHtml(humanizeToken(item.format || "")) +
    '<br><strong>Initial estimate:</strong> ' + escapeHtml(currency) + ' ' +
      escapeHtml(Number.isFinite(initial) ? initial.toFixed(2) : "—") +
    '<br><strong>Worst-case authorization:</strong> ' + escapeHtml(currency) + ' ' +
      escapeHtml(Number.isFinite(worst) ? worst.toFixed(2) : "—") +
    '<br><strong>Segments:</strong> ' + escapeHtml(item.segment_count || 0) +
    '<br><strong>Max attempts/segment:</strong> ' + escapeHtml(item.max_attempts_per_segment || 0) +
    '<br><strong>Quote reference:</strong> ' + escapeHtml(quote.quote_reference || "—") +
    '</p><p class="muted">The worst-case figure is the ceiling you are authorizing for this current quote. A changed request or quote invalidates this decision.</p></div>';

  const descriptions = item.criteria || {};
  const selected = item.criteria_decisions || {};
  narrationSpendCriteria.innerHTML = (item.required_accept_criteria || []).map(function (name) {
    return '<label class="criterion-row"><input type="checkbox" data-narration-spend-criterion="' +
      escapeHtml(name) + '"' + (selected[name] ? " checked" : "") + '>' +
      '<span><strong>' + escapeHtml(humanizeToken(name)) + '</strong><small>' +
      escapeHtml(descriptions[name] || "") + '</small></span></label>';
  }).join("");

  narrationSpendNote.value = item.note || "";
  narrationSpendPrev.disabled = narrationSpendCursor <= 0;
  narrationSpendNext.disabled = narrationSpendCursor >= items.length - 1;
  narrationSpendReject.disabled = decision === "ACCEPT";
  narrationSpendRework.disabled = decision === "ACCEPT";
  narrationSpendAccept.disabled = decision === "ACCEPT";
}

function moveNarrationSpendCursor(delta) {
  const items = narrationSpendItems(latestNarrationSpendSnapshot || {});
  if (!items.length) return;
  narrationSpendCursor = Math.max(
    0,
    Math.min(items.length - 1, narrationSpendCursor + delta)
  );
  renderNarrationSpendReview(latestNarrationSpendSnapshot);
}

function collectNarrationSpendCriteria() {
  const values = {};
  narrationSpendCriteria
    .querySelectorAll("[data-narration-spend-criterion]")
    .forEach(function (input) {
      values[input.dataset.narrationSpendCriterion] = Boolean(input.checked);
    });
  return values;
}

async function submitNarrationSpendDecision(decision) {
  const item = currentNarrationSpendItem();
  if (!item) return;
  const criteria = collectNarrationSpendCriteria();
  if (decision === "ACCEPT") {
    const worst = Number(item.worst_case_estimate_usd);
    const currency = item.currency || "USD";
    if (!(item.required_accept_criteria || []).every(function (name) { return criteria[name] === true; })) {
      showToast("Confirm every spend criterion before accepting.", true);
      return;
    }
    if (!confirm(
      "Authorize paid narration up to " + currency + " " +
      (Number.isFinite(worst) ? worst.toFixed(2) : "the displayed worst-case amount") +
      " for this exact current quote?"
    )) return;
  }

  try {
    const payload = await api("/api/narration-spend-gate", {
      method: "POST",
      body: JSON.stringify({
        concept_id: item.concept_id,
        format: item.format,
        decision: decision,
        criteria: criteria,
        note: narrationSpendNote.value
      })
    });
    latestNarrationSpendSnapshot = payload;
    const pendingIndex = narrationSpendItems(payload).findIndex(function (entry) {
      return (entry.decision || "PENDING") === "PENDING";
    });
    if (pendingIndex >= 0) narrationSpendCursor = pendingIndex;
    renderNarrationSpendReview(payload);
    showToast(
      decision === "ACCEPT"
        ? "Narration spend authorized for this current quote. Register the provider audio return next; this gate did not call the provider."
        : decision === "REWORK"
          ? "Narration quote/setup sent for rework."
          : "Narration spend rejected.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function narrationReturnItems(snapshot) {
  return (snapshot && snapshot.items) || [];
}

function currentNarrationReturnItem() {
  const items = narrationReturnItems(latestNarrationReturnSnapshot || {});
  if (!items.length) return null;
  narrationReturnCursor = Math.max(
    0,
    Math.min(narrationReturnCursor, items.length - 1)
  );
  return items[narrationReturnCursor] || null;
}

function renderNarrationReturn(snapshot, narrationState, workflow) {
  latestNarrationReturnSnapshot = snapshot || {};
  const items = narrationReturnItems(snapshot);
  const qc = (narrationState && narrationState.audio_qc) || {};
  const audioReady = Boolean(narrationState && narrationState.audio_ready);
  narrationReturnPanel.hidden = items.length === 0 || audioReady;
  if (!items.length || audioReady) return;

  const item = currentNarrationReturnItem();
  if (!item) return;
  const qcFailed = qc.status === "FAIL";
  narrationReturnTitle.textContent =
    qcFailed ? "Replace narration audio that failed QC" :
    "Register final narration — " + humanizeToken(item.format || "");
  narrationReturnSummary.textContent =
    (narrationReturnCursor + 1) + " of " + items.length +
    " branch" + (items.length === 1 ? "" : "es") +
    ". Local Audio QC runs after a complete current return is registered.";
  narrationReturnStatus.textContent =
    qcFailed ? "QC FAILED — REIMPORT" :
    item.current_result ? "REGISTERED" : "RETURN REQUIRED";
  narrationReturnStatus.className =
    "status-chip " + (item.current_result && !qcFailed ? "success" : "running");

  const ceiling = Number(item.worst_case_estimate_usd);
  narrationReturnDetail.innerHTML =
    '<div class="concept-detail-card"><h4>AUTHORIZED PROVIDER RETURN</h4>' +
    '<h3>' + escapeHtml(item.provider || "Narration provider") + '</h3>' +
    '<p><strong>Branch:</strong> ' + escapeHtml(humanizeToken(item.format || "")) +
    '<br><strong>Approved ceiling:</strong> ' + escapeHtml(item.currency || "USD") + ' ' +
    escapeHtml(Number.isFinite(ceiling) ? ceiling.toFixed(2) : "—") +
    '<br><strong>Render request:</strong> ' + escapeHtml(item.render_request || "—") +
    '</p><p class="muted">Actual cumulative cost cannot exceed the approved ceiling. Imported files are copied into managed project storage and hash-bound to this authorization.</p></div>';

  narrationProviderJobId.value = item.provider_job_id || "";
  narrationActualCost.value =
    item.actual_cost_usd == null ? "" : String(item.actual_cost_usd);
  narrationReturnSegments.innerHTML = (item.segments || []).map(function (segment, index) {
    return '<div class="criterion-row" data-narration-return-row data-segment-id="' +
      escapeHtml(segment.segment_id || "") + '">' +
      '<span><strong>' + escapeHtml(segment.segment_id || ("Segment " + (index + 1))) +
      '</strong><small>' + escapeHtml(segment.purpose || "") +
      ' · target ≈ ' + escapeHtml(segment.expected_duration_seconds == null ? "—" : segment.expected_duration_seconds) +
      's · max attempts ' + escapeHtml(segment.max_attempts || "—") + '</small></span>' +
      '<label>Attempt<input data-return-attempt type="number" min="1" max="' +
      escapeHtml(segment.max_attempts || 1) + '" value="' +
      escapeHtml(segment.attempt || 1) + '"></label>' +
      '<label>Local audio path<input data-return-audio type="text" value="' +
      escapeHtml(segment.audio_file || "") + '" placeholder="C:\\path\\segment.wav"></label>' +
      '</div>';
  }).join("");

  narrationReturnPrev.disabled = narrationReturnCursor <= 0;
  narrationReturnNext.disabled = narrationReturnCursor >= items.length - 1;
  narrationReturnRegister.disabled =
    Boolean(item.current_result) && !qcFailed &&
    (!workflow || workflow.state !== "WAITING_NARRATION_RENDER_RETURN");
}

function moveNarrationReturnCursor(delta) {
  const items = narrationReturnItems(latestNarrationReturnSnapshot || {});
  if (!items.length) return;
  narrationReturnCursor = Math.max(
    0,
    Math.min(items.length - 1, narrationReturnCursor + delta)
  );
  renderNarrationReturn(
    latestNarrationReturnSnapshot,
    (latestStatus && latestStatus.narration) || {},
    (latestStatus && latestStatus.workflow) || {}
  );
}

async function submitNarrationReturn() {
  const item = currentNarrationReturnItem();
  if (!item) return;
  const rows = narrationReturnSegments.querySelectorAll("[data-narration-return-row]");
  const segments = Array.from(rows).map(function (row) {
    return {
      segment_id: row.dataset.segmentId,
      attempt: Number(row.querySelector("[data-return-attempt]").value),
      audio_file: row.querySelector("[data-return-audio]").value
    };
  });

  try {
    const payload = await api("/api/narration-render-return", {
      method: "POST",
      body: JSON.stringify({
        concept_id: item.concept_id,
        format: item.format,
        provider_job_id: narrationProviderJobId.value,
        actual_cost_usd: Number(narrationActualCost.value),
        segments: segments
      })
    });
    latestNarrationReturnSnapshot = payload.snapshot || {};
    renderNarrationReturn(
      latestNarrationReturnSnapshot,
      (latestStatus && latestStatus.narration) || {},
      (latestStatus && latestStatus.workflow) || {}
    );
    showToast(
      payload.automation_job && payload.automation_job.action_id === "auto_continue"
        ? "Final narration registered. Local Audio QC started automatically."
        : "Final narration registered. Local Audio QC is ready.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function visualReviewItems() {
  const packets = (latestVisualCandidateSnapshot && latestVisualCandidateSnapshot.packets) || [];
  const items = [];
  packets.forEach(function (packet) {
    (packet.shots || []).forEach(function (shot) { items.push({ packet: packet, shot: shot }); });
  });
  return items;
}

function renderVisualCandidateReview(snapshot) {
  latestVisualCandidateSnapshot = snapshot || {};
  const items = visualReviewItems();
  visualCandidateReviewPanel.hidden = items.length === 0;
  if (!items.length) return;
  visualShotCursor = Math.max(0, Math.min(visualShotCursor, items.length - 1));
  const current = items[visualShotCursor], shot = current.shot, packet = current.packet;
  const decision = (packet.decisions || {})[shot.shot_id];
  visualCandidateReviewTitle.textContent = "Choose visual — " + (shot.shot_id || "");
  visualCandidateReviewSummary.textContent = (visualShotCursor + 1) + " of " + items.length + " storyboard shots";
  const staleShot = shot.storyboard_current === false;
  visualCandidateReviewStatus.textContent = staleShot
    ? "RE-SEARCH REQUIRED"
    : (decision ? humanizeToken(decision.status || decision.action) : "PENDING");
  visualCandidateReviewStatus.className =
    "status-chip " + (staleShot ? "failed" : (decision ? "success" : "running"));
  visualShotDetail.innerHTML =
    '<div class="concept-detail-card"><h4>STORYBOARD TARGET</h4><h3>' + escapeHtml(shot.shot_id || "") + '</h3>' +
    '<p><strong>Search gap:</strong> ' + (shot.search_gap ? "Yes" : "No") + '</p>' +
    '<p><strong>Premium candidate:</strong> ' + (shot.premium_generation_candidate ? "Yes — only if existing visuals fail" : "No") + '</p>' +
    '<p class="muted">Select the visual that best serves the planned shot. Creator excerpts remain subject to the separate rights/context gate.</p></div>';
  const candidates = shot.candidates || [];
  visualCandidateCards.innerHTML = staleShot
    ? '<p class="empty-state"><strong>Storyboard changed.</strong> These candidates are stale. Run Continue Automatically to re-search this shot before making a visual decision.</p>'
    : candidates.length ? candidates.map(function (candidate) {
    const thumb = candidate.thumbnail_url
      ? '<img class="visual-candidate-thumb" src="' + escapeHtml(candidate.thumbnail_url) + '" alt="">'
      : '<div class="visual-candidate-placeholder">No preview</div>';
    const review = candidate.state === "HUMAN_REVIEW_REQUIRED"
      ? '<span class="status-chip running">RIGHTS REVIEW</span>'
      : candidate.state === "ELIGIBLE"
        ? '<span class="status-chip success">ELIGIBLE</span>'
        : '<span class="status-chip failed">BLOCKED</span>';
    const source = candidate.source_url
      ? '<a class="external-button" href="' + escapeHtml(candidate.source_url) + '" target="_blank" rel="noopener noreferrer">Open source ↗</a>'
      : '';
    const choose = candidate.state !== "BLOCKED"
      ? '<button class="gate-button approve visual-select-candidate" data-candidate-id="' + escapeHtml(candidate.candidate_id) + '">Select</button>'
      : '';
    return '<article class="visual-candidate-card">' + thumb + '<div><strong>' + escapeHtml(candidate.title || candidate.candidate_id) +
      '</strong><p>' + escapeHtml(candidate.creator || "Unknown creator") + ' · ' + escapeHtml(candidate.source_tier || "") +
      '</p><p>' + escapeHtml(candidate.license || "Licence requires review") + '</p><div class="visual-candidate-actions">' +
      review + source + choose + '</div></div></article>';
  }).join("") : '<p class="empty-state">No usable existing visual was found. Keep this as a gap for the next sourcing/generation stage.</p>';
  visualCandidateCards.querySelectorAll(".visual-select-candidate").forEach(function (button) {
    button.addEventListener("click", function () { submitVisualCandidateDecision("SELECT", button.dataset.candidateId); });
  });
  visualShotPrev.disabled = visualShotCursor === 0;
  visualShotNext.disabled = visualShotCursor >= items.length - 1;
  visualRejectAll.disabled = staleShot;
  visualNeedsBetter.disabled = staleShot;
  visualCandidateNote.value = decision && decision.note ? decision.note : "";
  const boards = (latestStoryboardSnapshot && latestStoryboardSnapshot.items) || [];
  const board = boards.find(function (x) { return x.concept_id === packet.concept_id && x.format === packet.format; });
  const card = board && (board.cards || []).find(function (x) { return x.shot_id === shot.shot_id; });
  if (card) {
    const cine = card.cinematic_direction || {};
    storyboardCreativeInstruction.value = card.creative_instruction || "";
    storyboardDesiredVisual.value = card.desired_visual || "";
    storyboardSearchTerms.value = (card.search_terms || []).join(", ");
    storyboardFraming.value = cine.framing || "";
    storyboardCameraAngle.value = cine.camera_angle || "";
    storyboardCameraMovement.value = cine.camera_movement || "";
    storyboardLens.value = cine.lens_feel || "";
    storyboardLighting.value = cine.lighting || "";
    storyboardTransition.value = cine.transition || "";
    storyboardSaveRevision.dataset.storyboardFile = board.storyboard_file || "";
    storyboardSaveRevision.dataset.shotId = shot.shot_id || "";
  }
}

async function saveStoryboardRevision() {
  const file = storyboardSaveRevision.dataset.storyboardFile, shotId = storyboardSaveRevision.dataset.shotId;
  if (!file || !shotId) return;
  try {
    await api("/api/storyboard-review", {method:"POST", body:JSON.stringify({
      storyboard_file:file, shot_id:shotId, instruction:storyboardCreativeInstruction.value,
      changes:{
        desired_visual:storyboardDesiredVisual.value,
        search_terms:storyboardSearchTerms.value.split(",").map(function(x){return x.trim();}).filter(Boolean),
        cinematic_direction:{framing:storyboardFraming.value,camera_angle:storyboardCameraAngle.value,
          camera_movement:storyboardCameraMovement.value,lens_feel:storyboardLens.value,
          lighting:storyboardLighting.value,transition:storyboardTransition.value}
      }
    })});
    latestStoryboardSnapshot = await api("/api/storyboard-review");
    showToast("Shot revised. Its old visual approvals are now stale; re-search this shot.", false);
    renderVisualCandidateReview(latestVisualCandidateSnapshot);
  } catch(error) { showToast(error.message,true); }
}

async function submitVisualCandidateDecision(action, candidateId) {
  const items = visualReviewItems(), current = items[visualShotCursor];
  if (!current) return;
  try {
    await api("/api/visual-candidate-review", { method:"POST", body:JSON.stringify({
      result_file: current.packet.result_file, shot_id: current.shot.shot_id,
      action: action, candidate_id: candidateId || null, note: visualCandidateNote.value
    })});
    const refreshed = await api("/api/visual-candidate-review");
    renderVisualCandidateReview(refreshed);
    showToast(action === "SELECT" ? "Visual selected." : "Shot preserved as a visual gap.", false);
    await loadStatus();
  } catch (error) { showToast(error.message, true); }
}

function visualRightsItems(snapshot) {
  const items = [];
  (snapshot && snapshot.items || []).forEach(function (packet) {
    (packet.pending || []).forEach(function (entry) {
      items.push({ packet: packet, entry: entry });
    });
  });
  return items;
}

function renderVisualRightsReview(snapshot) {
  latestVisualRightsSnapshot = snapshot || {};
  const items = visualRightsItems(latestVisualRightsSnapshot);
  visualRightsReviewPanel.hidden = items.length === 0;
  if (!items.length) return;

  visualRightsCursor = Math.max(
    0,
    Math.min(visualRightsCursor, items.length - 1)
  );
  const current = items[visualRightsCursor];
  const packet = current.packet;
  const entry = current.entry || {};
  const candidate = entry.candidate || {};
  const decision = entry.decision || null;

  visualRightsReviewTitle.textContent =
    "Creator footage — " + (entry.shot_id || "");
  visualRightsReviewSummary.textContent =
    (visualRightsCursor + 1) + " of " + items.length +
    " rights/context decisions · " +
    Number(snapshot.decided || 0) + " decided";
  visualRightsReviewStatus.textContent = decision
    ? humanizeToken(decision.decision || "DECIDED")
    : "PENDING";
  visualRightsReviewStatus.className =
    "status-chip " +
    (decision && decision.approved_for_rough_cut
      ? "success"
      : decision
        ? "failed"
        : "running");

  const source = candidate.source_url
    ? '<a class="external-button" href="' +
      escapeHtml(candidate.source_url) +
      '" target="_blank" rel="noopener noreferrer">Open source ↗</a>'
    : "";
  visualRightsDetail.innerHTML =
    '<div class="concept-detail-card"><h4>SELECTED CREATOR / EDITORIAL FOOTAGE</h4>' +
    '<h3>' + escapeHtml(candidate.title || candidate.candidate_id || entry.shot_id || "") + '</h3>' +
    '<p><strong>Shot:</strong> ' + escapeHtml(entry.shot_id || "") +
    '<br><strong>Creator:</strong> ' + escapeHtml(candidate.creator || "Unknown") +
    '<br><strong>Source tier:</strong> ' + escapeHtml(candidate.source_tier || "") +
    '<br><strong>Licence:</strong> ' + escapeHtml(candidate.license || "Requires human context review") +
    '</p>' + source +
    '<p class="muted">Approval records the intended editorial transformation/context. It does not make a legal fair-use determination.</p></div>';

  visualRightsPurpose.value =
    decision && decision.transformative_purpose
      ? decision.transformative_purpose
      : "";
  visualRightsNote.value =
    decision && decision.context_note ? decision.context_note : "";
  visualRightsPrev.disabled = visualRightsCursor === 0;
  visualRightsNext.disabled = visualRightsCursor >= items.length - 1;
}

async function submitVisualRightsDecision(decision) {
  const items = visualRightsItems(latestVisualRightsSnapshot || {});
  const current = items[visualRightsCursor];
  if (!current) return;
  try {
    await api("/api/visual-rights-review", {
      method: "POST",
      body: JSON.stringify({
        candidate_review_file: current.packet.candidate_review_file,
        shot_id: current.entry.shot_id,
        decision: decision,
        transformative_purpose: visualRightsPurpose.value,
        context_note: visualRightsNote.value
      })
    });
    const refreshed = await api("/api/visual-rights-review");
    latestVisualRightsSnapshot = refreshed;
    const refreshedItems = visualRightsItems(refreshed);
    const nextPending = refreshedItems.findIndex(function (item) {
      return !item.entry.decision;
    });
    if (nextPending >= 0) visualRightsCursor = nextPending;
    renderVisualRightsReview(refreshed);
    showToast(
      decision === "APPROVE_CONTEXT_USE"
        ? "Context use approved for this selected footage."
        : "Creator footage rejected for this shot.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function managedVisualKey(item) {
  return [
    String((item && item.concept_id) || ""),
    String((item && item.format) || ""),
    String((item && item.shot_id) || "")
  ].join("::");
}

function managedVisualPendingItems(acquisition, assets) {
  const registered = new Set(
    (((assets && assets.items) || [])).map(managedVisualKey)
  );
  return (((acquisition && acquisition.manual_items) || [])).filter(
    function (item) {
      return !registered.has(managedVisualKey(item));
    }
  );
}

function renderManagedVisualImport(acquisition, assets) {
  latestManagedVisualAcquisition = acquisition || {};
  latestManagedVisualAssets = assets || {};
  const items = managedVisualPendingItems(
    latestManagedVisualAcquisition,
    latestManagedVisualAssets
  );

  managedVisualImportPanel.hidden = items.length === 0;
  if (!items.length) return;

  managedVisualCursor = Math.max(
    0,
    Math.min(managedVisualCursor, items.length - 1)
  );
  const item = items[managedVisualCursor] || {};

  managedVisualImportTitle.textContent =
    "Supply approved visual — " + (item.shot_id || "");
  managedVisualImportSummary.textContent =
    (managedVisualCursor + 1) + " of " + items.length +
    " local assets required";
  managedVisualImportStatus.textContent = "LOCAL FILE REQUIRED";
  managedVisualImportStatus.className = "status-chip running";

  managedVisualImportDetail.innerHTML =
    '<div class="concept-detail-card"><h4>APPROVED EXISTING VISUAL</h4>' +
    '<h3>' + escapeHtml(item.shot_id || "") + '</h3>' +
    '<p><strong>Concept:</strong> ' + escapeHtml(item.concept_id || "") +
    '<br><strong>Format:</strong> ' +
    escapeHtml(humanizeToken(item.format || "")) +
    '<br><strong>Candidate:</strong> ' +
    escapeHtml(item.candidate_id || "") +
    '<br><strong>Creator:</strong> ' + escapeHtml(item.creator || "—") +
    '<br><strong>License/context:</strong> ' +
    escapeHtml(item.license || "Human context approval required") +
    '<br><strong>Source:</strong> ' +
    escapeHtml(item.source_url || "") +
    '</p><p class="muted">' +
    escapeHtml(humanizeToken(item.reason || "")) +
    '</p></div>';

  managedVisualAssetPath.value = "";
  managedVisualNote.value = "";
  managedVisualPrev.disabled = managedVisualCursor === 0;
  managedVisualNext.disabled = managedVisualCursor >= items.length - 1;
}

async function registerManagedVisualAsset() {
  const items = managedVisualPendingItems(
    latestManagedVisualAcquisition || {},
    latestManagedVisualAssets || {}
  );
  const item = items[managedVisualCursor];
  if (!item) return;

  const assetPath = managedVisualAssetPath.value.trim();
  if (!assetPath) {
    showToast("Enter the local approved visual file path.", true);
    return;
  }

  try {
    const payload = await api("/api/managed-visual-asset", {
      method: "POST",
      body: JSON.stringify({
        candidate_review_file: item.candidate_review_file,
        shot_id: item.shot_id,
        asset_file: assetPath,
        note: managedVisualNote.value
      })
    });
    latestManagedVisualAssets = payload.managed_visual_assets || {};
    const remaining = managedVisualPendingItems(
      latestManagedVisualAcquisition || {},
      latestManagedVisualAssets
    );
    if (managedVisualCursor >= remaining.length) {
      managedVisualCursor = Math.max(0, remaining.length - 1);
    }
    renderManagedVisualImport(
      latestManagedVisualAcquisition || {},
      latestManagedVisualAssets
    );
    showToast(
      "Approved visual registered. Current assembly can now use the local asset.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function visualRoughCutItems(snapshot) {
  return (snapshot && snapshot.items || []).filter(function (item) {
    return item && item.review_current !== false;
  });
}

function renderVisualRoughCutReview(snapshot) {
  latestVisualRoughCutSnapshot = snapshot || {};
  const items = visualRoughCutItems(latestVisualRoughCutSnapshot);
  visualRoughCutReviewPanel.hidden = items.length === 0;
  if (!items.length) return;

  visualRoughCutCursor = Math.max(
    0,
    Math.min(visualRoughCutCursor, items.length - 1)
  );
  const item = items[visualRoughCutCursor];
  const decision = item.decision || null;
  const summary = item.summary || {};
  const scenes = item.scenes || [];

  visualRoughCutReviewTitle.textContent =
    "Rough cut — " + humanizeToken(item.format || "");
  visualRoughCutReviewSummary.textContent =
    (visualRoughCutCursor + 1) + " of " + items.length +
    " branches · " + scenes.length + " scenes · " +
    Number(summary.placeholders || summary.unresolved_visual_gaps || 0) +
    " unresolved visual gaps";
  visualRoughCutReviewStatus.textContent = decision
    ? humanizeToken(decision.decision || "DECIDED")
    : "PENDING";
  visualRoughCutReviewStatus.className =
    "status-chip " +
    (decision && decision.approved_for_gap_planning
      ? "success"
      : decision
        ? "running"
        : "running");

  const sceneHtml = scenes.map(function (scene) {
    const assignment = scene.visual_assignment || {};
    return '<div class="concept-detail-card">' +
      '<h4>' + escapeHtml(scene.shot_id || scene.scene_id || "SHOT") + '</h4>' +
      '<p><strong>Purpose:</strong> ' + escapeHtml(scene.story_purpose || "") +
      '<br><strong>Visual:</strong> ' + escapeHtml(scene.desired_visual || "") +
      '<br><strong>Assignment:</strong> ' + escapeHtml(humanizeToken(assignment.status || "PLACEHOLDER")) +
      (assignment.reason
        ? '<br><strong>Reason:</strong> ' + escapeHtml(humanizeToken(assignment.reason))
        : "") +
      '</p></div>';
  }).join("");

  visualRoughCutDetail.innerHTML =
    '<div class="concept-detail-card"><h4>BRANCH</h4><h3>' +
    escapeHtml(item.concept_id || "") + ' · ' +
    escapeHtml(humanizeToken(item.format || "")) +
    '</h3><p class="muted">This is the structural rough cut. Missing visuals may remain as placeholders; paid generation is still locked.</p></div>' +
    sceneHtml;

  visualRoughCutShotSelect.innerHTML = scenes.map(function (scene) {
    const shotId = String(scene.shot_id || scene.scene_id || "");
    return '<option value="' + escapeHtml(shotId) + '">' +
      escapeHtml(shotId || "Unnamed shot") + '</option>';
  }).join("");
  visualRoughCutShotSelect.disabled = scenes.length === 0;

  visualRoughCutNote.value =
    decision && decision.note ? decision.note : "";
  visualRoughCutPrev.disabled = visualRoughCutCursor === 0;
  visualRoughCutNext.disabled = visualRoughCutCursor >= items.length - 1;
}

async function submitVisualRoughCutDecision(decision) {
  const items = visualRoughCutItems(latestVisualRoughCutSnapshot || {});
  const item = items[visualRoughCutCursor];
  if (!item) return;
  try {
    await api("/api/visual-rough-cut-review", {
      method: "POST",
      body: JSON.stringify({
        rough_cut_file: item.rough_cut_file,
        shot_id: visualRoughCutShotSelect.value || null,
        decision: decision,
        note: visualRoughCutNote.value
      })
    });
    const refreshed = await api("/api/visual-rough-cut-review");
    latestVisualRoughCutSnapshot = refreshed;
    const refreshedItems = visualRoughCutItems(refreshed);
    const nextPending = refreshedItems.findIndex(function (value) {
      return !value.decision;
    });
    if (nextPending >= 0) visualRoughCutCursor = nextPending;
    renderVisualRoughCutReview(refreshed);
    showToast(
      decision === "APPROVE_WITH_GAPS"
        ? "Rough cut approved. Unresolved gaps can now be planned."
        : "Rough cut sent back for " +
          humanizeToken(decision).replace("Rework ", "").toLowerCase() +
          " rework.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function visualSpendItems(snapshot) {
  const items = [];
  (snapshot && snapshot.items || []).forEach(function (packet) {
    (packet.hero_candidates || []).forEach(function (gap) {
      items.push({ packet: packet, gap: gap });
    });
  });
  return items;
}

function renderVisualSpendReview(snapshot) {
  latestVisualSpendSnapshot = snapshot || {};
  const items = visualSpendItems(latestVisualSpendSnapshot);
  visualSpendReviewPanel.hidden = items.length === 0;
  if (!items.length) return;

  visualSpendCursor = Math.max(
    0,
    Math.min(visualSpendCursor, items.length - 1)
  );
  const current = items[visualSpendCursor];
  const packet = current.packet;
  const gap = current.gap || {};
  const decision = (packet.decisions || {})[gap.shot_id] || null;
  const score = gap.visual_value_score || {};

  visualSpendReviewTitle.textContent =
    "Premium gap — " + (gap.shot_id || "");
  visualSpendReviewSummary.textContent =
    (visualSpendCursor + 1) + " of " + items.length +
    " premium candidates · authorized max so far $" +
    Number(snapshot.authorized_max_total_usd || 0).toFixed(2) +
    " " + String(snapshot.currency || "USD");
  visualSpendReviewStatus.textContent = decision
    ? humanizeToken(decision.decision || "DECIDED")
    : "PENDING";
  visualSpendReviewStatus.className =
    "status-chip " +
    (decision && decision.paid_generation_authorized
      ? "success"
      : decision
        ? "neutral"
        : "running");

  visualSpendDetail.innerHTML =
    '<div class="concept-detail-card"><h4>LAST-RESORT GENERATION CANDIDATE</h4>' +
    "<h3>" + escapeHtml(gap.shot_id || "") + "</h3>" +
    "<p><strong>Desired visual:</strong> " + escapeHtml(gap.desired_visual || "") +
    "<br><strong>Story purpose:</strong> " + escapeHtml(gap.story_purpose || "") +
    "<br><strong>Visual value score:</strong> " + escapeHtml(score.total == null ? "—" : score.total) +
    "<br><strong>Resolution class:</strong> " + escapeHtml(humanizeToken(gap.resolution_class || "")) +
    '</p><p class="muted">Per-shot hard cap: $' +
    Number(snapshot.per_shot_hard_cap_usd || 0).toFixed(2) +
    " · Workflow hard cap: $" +
    Number(snapshot.workflow_hard_cap_usd || 0).toFixed(2) +
    ". Authorizing here sets a ceiling only.</p></div>";

  visualSpendMaxCost.max = String(
    Number(snapshot.per_shot_hard_cap_usd || 0)
  );
  visualSpendMaxCost.value = decision
    ? Number(decision.max_cost_usd || 0).toFixed(2)
    : "0";
  visualSpendNote.value = decision && decision.note ? decision.note : "";
  visualSpendPrev.disabled = visualSpendCursor === 0;
  visualSpendNext.disabled = visualSpendCursor >= items.length - 1;
}

async function submitVisualSpendDecision(decision) {
  const items = visualSpendItems(latestVisualSpendSnapshot || {});
  const current = items[visualSpendCursor];
  if (!current) return;
  try {
    await api("/api/visual-spend-review", {
      method: "POST",
      body: JSON.stringify({
        gap_plan_file: current.packet.gap_plan_file,
        shot_id: current.gap.shot_id,
        decision: decision,
        max_cost_usd: Number(visualSpendMaxCost.value || 0),
        note: visualSpendNote.value
      })
    });
    const refreshed = await api("/api/visual-spend-review");
    latestVisualSpendSnapshot = refreshed;
    const refreshedItems = visualSpendItems(refreshed);
    const nextPending = refreshedItems.findIndex(function (item) {
      return !(item.packet.decisions || {})[item.gap.shot_id];
    });
    if (nextPending >= 0) visualSpendCursor = nextPending;
    renderVisualSpendReview(refreshed);
    showToast(
      decision === "AUTHORIZE_GENERATION"
        ? "Generation ceiling authorized for this shot. No provider call has been made."
        : decision === "RETRY_EXISTING"
          ? "Shot returned to existing-visual search."
          : "Shot will remain a placeholder.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function editPreviewItems(snapshot) {
  return (snapshot && snapshot.items) || [];
}

function renderEditPreviewReview(snapshot) {
  latestEditPreviewSnapshot = snapshot || {};
  const items = editPreviewItems(latestEditPreviewSnapshot);

  editPreviewReviewPanel.hidden = items.length === 0;
  if (!items.length) {
    editPreviewVideo.removeAttribute("src");
    return;
  }

  editPreviewCursor = Math.max(
    0,
    Math.min(editPreviewCursor, items.length - 1)
  );
  const item = items[editPreviewCursor] || {};
  const decision = item.decision || "PENDING";

  editPreviewReviewTitle.textContent =
    "Review structural edit — " +
    humanizeToken(item.format || "") +
    " · " + (item.concept_id || "");
  editPreviewReviewSummary.textContent =
    (editPreviewCursor + 1) + " of " + items.length +
    " · " + Number(item.duration_seconds || 0).toFixed(1) + " sec" +
    " · " + Number(item.placeholder_segments || 0) + " placeholder segment(s)";
  editPreviewReviewStatus.textContent = decision;
  editPreviewReviewStatus.className =
    "status-chip " +
    (decision === "APPROVE_EDIT_DIRECTION"
      ? "success"
      : decision === "PENDING"
        ? "running"
        : "failed");

  const url =
    "/api/edit-preview-video?concept_id=" +
    encodeURIComponent(item.concept_id || "") +
    "&format=" +
    encodeURIComponent(item.format || "");
  if (editPreviewVideo.dataset.previewUrl !== url) {
    editPreviewVideo.dataset.previewUrl = url;
    editPreviewVideo.src = url;
    editPreviewVideo.load();
  }

  editPreviewDetail.innerHTML =
    '<div class="concept-detail-card"><h4>STRUCTURAL PREVIEW</h4>' +
    '<p><strong>Duration:</strong> ' +
    Number(item.duration_seconds || 0).toFixed(1) + ' sec' +
    '<br><strong>Placeholders:</strong> ' +
    Number(item.placeholder_segments || 0) +
    '<br><strong>Purpose:</strong> Judge pacing, sequence and narration-to-picture rhythm before final visual spending/export.</p>' +
    (Number(item.placeholder_segments || 0) > 0
      ? '<p class="muted">Dark placeholder frames are expected. They represent unresolved visual slots, not missing render output.</p>'
      : '<p class="muted">All preview visual slots currently have local assets.</p>') +
    '</div>';

  editPreviewNote.value = item.note || "";
  editPreviewPrev.disabled = editPreviewCursor <= 0;
  editPreviewNext.disabled = editPreviewCursor >= items.length - 1;

  const decided = decision !== "PENDING";
  editPreviewVisuals.disabled = decided;
  editPreviewNarration.disabled = decided;
  editPreviewSound.disabled = decided;
  editPreviewApprove.disabled = decided;
}

async function submitEditPreviewDecision(decision) {
  const items = editPreviewItems(latestEditPreviewSnapshot || {});
  const item = items[editPreviewCursor];
  if (!item) return;

  try {
    const payload = await api("/api/edit-preview-review", {
      method: "POST",
      body: JSON.stringify({
        result_file: item.result_file,
        decision: decision,
        note: editPreviewNote.value
      })
    });
    latestEditPreviewSnapshot = payload;
    const refreshed = editPreviewItems(payload);
    const nextPending = refreshed.findIndex(function (entry) {
      return (entry.decision || "PENDING") === "PENDING";
    });
    if (nextPending >= 0) editPreviewCursor = nextPending;
    renderEditPreviewReview(payload);
    showToast(
      decision === "APPROVE_EDIT_DIRECTION"
        ? "Edit direction approved."
        : "Edit preview returned for rework.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function generatedVisualKey(item) {
  return [
    String((item && item.concept_id) || ""),
    String((item && item.format) || ""),
    String((item && item.shot_id) || "")
  ].join("::");
}

function generatedVisualPendingItems(handoff, assets) {
  const registered = new Set(
    (((assets && assets.items) || [])).map(generatedVisualKey)
  );
  return (((handoff && handoff.requests) || [])).filter(function (item) {
    return !registered.has(generatedVisualKey(item));
  });
}

function renderGeneratedVisualImport(handoff, assets) {
  latestGeneratedVisualHandoff = handoff || {};
  latestGeneratedVisualAssets = assets || {};
  const items = generatedVisualPendingItems(
    latestGeneratedVisualHandoff,
    latestGeneratedVisualAssets
  );

  generatedVisualImportPanel.hidden = items.length === 0;
  if (!items.length) return;

  generatedVisualCursor = Math.max(
    0,
    Math.min(generatedVisualCursor, items.length - 1)
  );
  const item = items[generatedVisualCursor] || {};
  const brief = item.generation_brief || {};
  const provider = item.provider_handoff || {};

  generatedVisualImportTitle.textContent =
    "Register generated visual — " + (item.shot_id || "");
  generatedVisualImportSummary.textContent =
    (generatedVisualCursor + 1) + " of " + items.length +
    " waiting · max USD " + Number(item.max_cost_usd || 0).toFixed(2);
  generatedVisualImportStatus.textContent = "WAITING FOR ASSET";
  generatedVisualImportStatus.className = "status-chip running";

  generatedVisualImportDetail.innerHTML =
    '<div class="concept-detail-card"><h4>AUTHORIZED PREMIUM SHOT</h4>' +
    '<h3>' + escapeHtml(item.shot_id || "") + '</h3>' +
    '<p><strong>Concept:</strong> ' + escapeHtml(item.concept_id || "") +
    '<br><strong>Format:</strong> ' + escapeHtml(humanizeToken(item.format || "")) +
    '<br><strong>Story purpose:</strong> ' + escapeHtml(item.story_purpose || "") +
    '<br><strong>Desired visual:</strong> ' + escapeHtml(item.desired_visual || "") +
    '<br><strong>Authorized ceiling:</strong> USD ' +
    Number(item.max_cost_usd || 0).toFixed(2) + '</p></div>' +
    '<div class="concept-detail-card"><h4>CINEMATIC BRIEF</h4><p>' +
    '<strong>Subject/action:</strong> ' + escapeHtml(brief.subject_and_action || "") +
    '<br><strong>Narrative intent:</strong> ' + escapeHtml(brief.narrative_intent || "") +
    '<br><strong>Camera:</strong> ' +
    escapeHtml([
      brief.camera_angle,
      brief.framing,
      brief.camera_movement
    ].filter(Boolean).join(" · ")) +
    '<br><strong>Lens:</strong> ' + escapeHtml(brief.lens_feel || "") +
    '<br><strong>Lighting:</strong> ' + escapeHtml(brief.lighting || "") +
    '<br><strong>Motion:</strong> ' + escapeHtml(brief.motion_speed || "") +
    '</p><p class="muted">Preferred provider: ' +
    escapeHtml(provider.preferred_provider || "higgsfield") +
    '. The app has not called the provider.</p></div>';

  generatedVisualActualCost.max = String(Number(item.max_cost_usd || 0));
  generatedVisualActualCost.value = "0";
  generatedVisualProvider.value =
    provider.preferred_provider || generatedVisualProvider.value || "higgsfield";
  generatedVisualAssetPath.value = "";
  generatedVisualProviderJobId.value = "";
  generatedVisualNote.value = "";
  generatedVisualPrev.disabled = generatedVisualCursor === 0;
  generatedVisualNext.disabled = generatedVisualCursor >= items.length - 1;
}

async function registerGeneratedVisualAsset() {
  const items = generatedVisualPendingItems(
    latestGeneratedVisualHandoff || {},
    latestGeneratedVisualAssets || {}
  );
  const item = items[generatedVisualCursor];
  if (!item) return;

  const assetPath = generatedVisualAssetPath.value.trim();
  if (!assetPath) {
    showToast("Enter the local generated file path.", true);
    return;
  }

  try {
    const payload = await api("/api/generated-visual-asset", {
      method: "POST",
      body: JSON.stringify({
        request_file: item.request_file,
        asset_file: assetPath,
        actual_cost_usd: Number(generatedVisualActualCost.value || 0),
        provider: generatedVisualProvider.value || "higgsfield",
        provider_job_id: generatedVisualProviderJobId.value,
        note: generatedVisualNote.value
      })
    });
    latestGeneratedVisualAssets = payload.generated_visual_assets || {};
    const remaining = generatedVisualPendingItems(
      latestGeneratedVisualHandoff || {},
      latestGeneratedVisualAssets
    );
    if (generatedVisualCursor >= remaining.length) {
      generatedVisualCursor = Math.max(0, remaining.length - 1);
    }
    renderGeneratedVisualImport(
      latestGeneratedVisualHandoff || {},
      latestGeneratedVisualAssets
    );
    showToast(
      "Generated visual registered. Assembly plan will rebuild from the current asset.",
      false
    );
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function formatElapsed(milliseconds) {
  const totalSeconds = Math.max(
    0,
    Math.floor(Number(milliseconds || 0) / 1000)
  );
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return hours + "h " + minutes + "m " + seconds + "s";
  if (minutes) return minutes + "m " + seconds + "s";
  return seconds + "s";
}

function updateRunningActivity(job) {
  const running = Boolean(
    job && (job.status === "RUNNING" || job.status === "STOPPING")
  );

  analysisCurrentPanel.classList.toggle("is-running", running);
  analysisRunningActivity.hidden = !running;

  if (!running) {
    runningJobId = null;
    runningJobStartedAt = null;
    runningLastPollAt = null;
    runningLastOutputAt = null;
    runningLastLogSignature = "";
    if (runningUiTimer) {
      clearInterval(runningUiTimer);
      runningUiTimer = null;
    }
    return;
  }

  if (runningJobId !== job.id) {
    runningJobId = job.id || null;
    const parsed = Date.parse(job.started_at || "");
    runningJobStartedAt = Number.isFinite(parsed) ? parsed : Date.now();
    runningLastOutputAt = null;
    runningLastLogSignature = "";
  }

  runningLastPollAt = Date.now();
  analysisRunningLabel.textContent =
    (job.status === "STOPPING" ? "Stopping: " : "Running: ") +
    (job.label || job.action_id || "workflow job");

  const paint = function () {
    const now = Date.now();
    analysisRunningElapsed.textContent =
      "Elapsed " + formatElapsed(now - (runningJobStartedAt || now));

    const pollAge = runningLastPollAt == null ? null : now - runningLastPollAt;
    const outputAge = runningLastOutputAt == null ? null : now - runningLastOutputAt;
    let message = "Process active";
    if (outputAge == null) {
      message = "Process active · waiting for first log output";
    } else if (outputAge < 15000) {
      message = "Live · new output " + formatElapsed(outputAge) + " ago";
    } else {
      message =
        "Process still running · no new log output for " +
        formatElapsed(outputAge);
    }
    if (pollAge != null) {
      message += " · checked " + formatElapsed(pollAge) + " ago";
    }
    analysisRunningHeartbeat.textContent = message;
  };

  paint();
  if (!runningUiTimer) {
    runningUiTimer = setInterval(paint, 1000);
  }
}

function noteJobLogActivity(job, log) {
  if (!job || (job.status !== "RUNNING" && job.status !== "STOPPING")) return;
  if (log === undefined || log === null) return;
  const value = String(log || "");
  const signature = value.length + ":" + value.slice(-180);
  if (value && signature !== runningLastLogSignature) {
    runningLastOutputAt = Date.now();
  }
  runningLastLogSignature = signature;
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
    "HUMAN_PERFORMANCE_GATE",
    "HUMAN_NARRATION_PREVIEW_GATE",
    "HUMAN_NARRATION_SPEND_GATE",
    "WAITING_NARRATION_PROVIDER_QUOTE",
    "NARRATION_PROVIDER_SETUP_REQUIRED",
    "HUMAN_VISUAL_CANDIDATE_GATE",
    "HUMAN_VISUAL_RIGHTS_GATE",
    "HUMAN_ROUGH_CUT_GATE",
    "HUMAN_VISUAL_SPEND_GATE",
    "HUMAN_EDIT_PREVIEW_GATE"
  ].includes(workflow.state);

  const opportunityApproved =
    Boolean(data.opportunity_gate && data.opportunity_gate.ready_for_experiment_02);
  const hasWorkflowTitle =
    Boolean(workflow.current_title) &&
    workflow.current_action_id !== "opportunity_research";

  analysisCurrentTitle.textContent =
    opportunityApproved && (humanCreateGate || hasWorkflowTitle)
      ? workflow.current_title
      : opportunityApproved
        ? "Prepare the approved source evidence"
        : "Waiting for opportunity approval";

  analysisCurrentDetail.textContent =
    opportunityApproved
      ? (
        workflow.current_detail ||
        "The next available analysis step is highlighted."
      )
      : "Approve an opportunity before Experiment 02 can begin.";

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
  renderPreviewReview(data.narration_preview_gate || {});
  renderNarrationSpendReview(data.narration_spend_gate || {});
  renderNarrationReturn(
    data.narration_render_return || {},
    data.narration || {},
    workflow
  );
  renderVisualCandidateReview(data.visual_candidate_gate || {});
  renderVisualRightsReview(data.visual_rights_gate || {});
  renderManagedVisualImport(
    data.visual_asset_acquisition || {},
    data.managed_visual_assets || {}
  );
  renderVisualRoughCutReview(data.visual_rough_cut_gate || {});
  renderVisualSpendReview(
    ["HUMAN_VISUAL_SPEND_GATE", "VISUAL_GENERATION_AUTHORIZED"].includes(
      workflow.state
    )
      ? (data.visual_spend_gate || {})
      : {}
  );
  renderGeneratedVisualImport(
    data.visual_generation_handoff || {},
    data.generated_visual_assets || {}
  );
  renderEditPreviewReview(data.edit_preview_gate || {});
  api("/api/narration-performance-review").then(function(x){latestNarrationPerformanceSnapshot=x;fillNarrationSegmentEditor();}).catch(function(){});
  api("/api/storyboard-review").then(function (value) {
    latestStoryboardSnapshot = value;
    renderVisualCandidateReview(latestVisualCandidateSnapshot || {});
  }).catch(function () {});

  let activeIndex = 0;
  const exp2 = data.experiment_02_artifacts || {};
  const transform = data.transformation || {};
  const packaging = data.packaging || {};
  const research = data.research || {};
  const story = data.story_script || {};
  const fmt = data.format || {};
  const voice = data.voice_performance || {};

  if (
    [
      "HUMAN_PERFORMANCE_GATE",
      "HUMAN_NARRATION_PREVIEW_GATE",
      "HUMAN_NARRATION_SPEND_GATE",
      "WAITING_NARRATION_PROVIDER_QUOTE",
      "NARRATION_PROVIDER_SETUP_REQUIRED",
      "WAITING_NARRATION_RENDER_RETURN",
      "NARRATION_AUDIO_QC_FAILED",
      "NARRATION_AUDIO_READY",
      "HUMAN_VISUAL_CANDIDATE_GATE",
      "HUMAN_VISUAL_RIGHTS_GATE",
      "HUMAN_ROUGH_CUT_GATE",
      "HUMAN_VISUAL_SPEND_GATE",
      "HUMAN_EDIT_PREVIEW_GATE",
      "WAITING_FOR_FINAL_VISUAL_ASSETS",
      "FINAL_EDIT_DIRECTION_APPROVED"
    ].includes(workflow.state) ||
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
  noteJobLogActivity(job, log);
  updateRunningActivity(job);
  if (!hasJob) {
    updateRunningActivity(null);
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

  const scriptSelectionButton = event.target.closest("[data-script-section-selection]");
  if (scriptSelectionButton) {
    submitScriptSectionAction("SELECT_ALTERNATIVE", {
      selection_id: scriptSelectionButton.dataset.scriptSectionSelection
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
packagingSaveIdea.addEventListener("click", function () {
  submitPackagingDecision("SAVE_IDEA");
});
packagingAccept.addEventListener("click", function () {
  submitPackagingDecision("ACCEPT");
});
researchNote.addEventListener("input", function () {
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
scriptSectionTarget.addEventListener("change", function () {
  if (scriptSectionBusy) return;
  scriptSectionTargetId = scriptSectionTarget.value;
  scriptSectionRenderedTargetId = null;
  renderScriptSectionReview(latestScriptSectionSnapshot || {});
});
scriptSectionNextPending.addEventListener("click", function () {
  if (scriptSectionBusy) return;
  const targets = (latestScriptSectionSnapshot && latestScriptSectionSnapshot.targets) || [];
  const nextTarget = nextUnresolvedScriptSectionTarget(
    targets,
    scriptSectionTargetId
  );
  if (!nextTarget) return;
  scriptSectionTargetId = nextTarget.target_id;
  scriptSectionRenderedTargetId = null;
  renderScriptSectionReview(latestScriptSectionSnapshot || {});
});
scriptSectionPrepare.addEventListener("click", function () {
  submitScriptSectionAction("PREPARE");
});
scriptSectionSaveManual.addEventListener("click", function () {
  submitScriptSectionAction("MANUAL_EDIT");
});
scriptSectionAccept.addEventListener("click", function () {
  submitScriptSectionAction("ACCEPT");
});
scriptSectionLock.addEventListener("click", function () {
  submitScriptSectionAction("LOCK");
});
scriptSectionUnlock.addEventListener("click", function () {
  submitScriptSectionAction("UNLOCK");
});
scriptSectionRework.addEventListener("click", function () {
  submitScriptSectionAction("REWORK");
});
scriptSectionCancelRework.addEventListener("click", function () {
  submitScriptSectionAction("CANCEL_REWORK");
});
scriptSectionPrepareRework.addEventListener("click", function () {
  submitScriptSectionAction("PREPARE_REWORK_REQUEST");
});
scriptSectionGenerate.addEventListener("click", function () {
  submitScriptSectionAction("GENERATE_ALTERNATIVES");
});
formatNote.addEventListener("input", function () {
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
previewScript.addEventListener("click", function () {
  submitPreviewDecision("REWORK_SCRIPT");
});
previewPerformance.addEventListener("click", function () {
  submitPreviewDecision("REWORK_PERFORMANCE");
});
previewSound.addEventListener("click", function () {
  submitPreviewDecision("REWORK_MUSIC_SFX");
});
narrationSpendPrev.addEventListener("click", function () {
  moveNarrationSpendCursor(-1);
});
narrationSpendNext.addEventListener("click", function () {
  moveNarrationSpendCursor(1);
});
narrationSpendReject.addEventListener("click", function () {
  submitNarrationSpendDecision("REJECT");
});
narrationSpendRework.addEventListener("click", function () {
  submitNarrationSpendDecision("REWORK");
});
narrationSpendAccept.addEventListener("click", function () {
  submitNarrationSpendDecision("ACCEPT");
});
narrationReturnPrev.addEventListener("click", function () {
  moveNarrationReturnCursor(-1);
});
narrationReturnNext.addEventListener("click", function () {
  moveNarrationReturnCursor(1);
});
narrationReturnRegister.addEventListener("click", submitNarrationReturn);
storyboardSaveRevision.addEventListener("click", saveStoryboardRevision);
visualShotPrev.addEventListener("click", function () { visualShotCursor = Math.max(0, visualShotCursor - 1); renderVisualCandidateReview(latestVisualCandidateSnapshot); });
visualShotNext.addEventListener("click", function () { visualShotCursor = Math.min(visualReviewItems().length - 1, visualShotCursor + 1); renderVisualCandidateReview(latestVisualCandidateSnapshot); });
visualRejectAll.addEventListener("click", function () { submitVisualCandidateDecision("REJECT_ALL"); });
visualNeedsBetter.addEventListener("click", function () { submitVisualCandidateDecision("NEEDS_BETTER_VISUAL"); });
visualRightsPrev.addEventListener("click", function () {
  visualRightsCursor = Math.max(0, visualRightsCursor - 1);
  renderVisualRightsReview(latestVisualRightsSnapshot);
});
visualRightsNext.addEventListener("click", function () {
  visualRightsCursor = Math.min(
    visualRightsItems(latestVisualRightsSnapshot || {}).length - 1,
    visualRightsCursor + 1
  );
  renderVisualRightsReview(latestVisualRightsSnapshot);
});
visualRightsReject.addEventListener("click", function () {
  submitVisualRightsDecision("REJECT_USE");
});
visualRightsApprove.addEventListener("click", function () {
  submitVisualRightsDecision("APPROVE_CONTEXT_USE");
});
managedVisualPrev.addEventListener("click", function () {
  managedVisualCursor = Math.max(0, managedVisualCursor - 1);
  renderManagedVisualImport(
    latestManagedVisualAcquisition || {},
    latestManagedVisualAssets || {}
  );
});
managedVisualNext.addEventListener("click", function () {
  const items = managedVisualPendingItems(
    latestManagedVisualAcquisition || {},
    latestManagedVisualAssets || {}
  );
  managedVisualCursor = Math.min(
    Math.max(0, items.length - 1),
    managedVisualCursor + 1
  );
  renderManagedVisualImport(
    latestManagedVisualAcquisition || {},
    latestManagedVisualAssets || {}
  );
});
managedVisualRegister.addEventListener("click", registerManagedVisualAsset);

visualRoughCutPrev.addEventListener("click", function () {
  visualRoughCutCursor = Math.max(0, visualRoughCutCursor - 1);
  renderVisualRoughCutReview(latestVisualRoughCutSnapshot);
});
visualRoughCutNext.addEventListener("click", function () {
  visualRoughCutCursor = Math.min(
    visualRoughCutItems(latestVisualRoughCutSnapshot || {}).length - 1,
    visualRoughCutCursor + 1
  );
  renderVisualRoughCutReview(latestVisualRoughCutSnapshot);
});
visualRoughCutVisual.addEventListener("click", function () {
  submitVisualRoughCutDecision("REWORK_VISUAL");
});
visualRoughCutPacing.addEventListener("click", function () {
  submitVisualRoughCutDecision("REWORK_PACING");
});
visualRoughCutAudio.addEventListener("click", function () {
  submitVisualRoughCutDecision("REWORK_AUDIO");
});
visualRoughCutApprove.addEventListener("click", function () {
  submitVisualRoughCutDecision("APPROVE_WITH_GAPS");
});
visualSpendPrev.addEventListener("click", function () {
  visualSpendCursor = Math.max(0, visualSpendCursor - 1);
  renderVisualSpendReview(latestVisualSpendSnapshot);
});
visualSpendNext.addEventListener("click", function () {
  visualSpendCursor = Math.min(
    visualSpendItems(latestVisualSpendSnapshot || {}).length - 1,
    visualSpendCursor + 1
  );
  renderVisualSpendReview(latestVisualSpendSnapshot);
});
visualSpendRetry.addEventListener("click", function () {
  submitVisualSpendDecision("RETRY_EXISTING");
});
visualSpendKeep.addEventListener("click", function () {
  submitVisualSpendDecision("KEEP_PLACEHOLDER");
});
visualSpendAuthorize.addEventListener("click", function () {
  submitVisualSpendDecision("AUTHORIZE_GENERATION");
});

editPreviewPrev.addEventListener("click", function () {
  editPreviewCursor = Math.max(0, editPreviewCursor - 1);
  renderEditPreviewReview(latestEditPreviewSnapshot || {});
});
editPreviewNext.addEventListener("click", function () {
  const items = editPreviewItems(latestEditPreviewSnapshot || {});
  editPreviewCursor = Math.min(
    Math.max(0, items.length - 1),
    editPreviewCursor + 1
  );
  renderEditPreviewReview(latestEditPreviewSnapshot || {});
});
editPreviewVisuals.addEventListener("click", function () {
  submitEditPreviewDecision("RETURN_TO_VISUALS");
});
editPreviewNarration.addEventListener("click", function () {
  submitEditPreviewDecision("RETURN_TO_NARRATION");
});
editPreviewSound.addEventListener("click", function () {
  submitEditPreviewDecision("RETURN_TO_SOUND");
});
editPreviewApprove.addEventListener("click", function () {
  submitEditPreviewDecision("APPROVE_EDIT_DIRECTION");
});

generatedVisualPrev.addEventListener("click", function () {
  generatedVisualCursor = Math.max(0, generatedVisualCursor - 1);
  renderGeneratedVisualImport(
    latestGeneratedVisualHandoff || {},
    latestGeneratedVisualAssets || {}
  );
});
generatedVisualNext.addEventListener("click", function () {
  const items = generatedVisualPendingItems(
    latestGeneratedVisualHandoff || {},
    latestGeneratedVisualAssets || {}
  );
  generatedVisualCursor = Math.min(
    Math.max(0, items.length - 1),
    generatedVisualCursor + 1
  );
  renderGeneratedVisualImport(
    latestGeneratedVisualHandoff || {},
    latestGeneratedVisualAssets || {}
  );
});
generatedVisualRegister.addEventListener("click", registerGeneratedVisualAsset);

narrationSegmentSelect.addEventListener("change", fillNarrationSegmentEditor);
narrationSaveRevision.addEventListener("click", saveNarrationSegmentRevision);
previewApprove.addEventListener("click", function () {
  submitPreviewDecision("APPROVE_FINAL");
});

renderRoute({ scroll: true });
loadStatus();
setInterval(loadStatus, 5000);
