// === Глобальная защита API-токеном ===
// Все запросы к /api/* автоматически получают X-API-Token из window.API_TOKEN,
// который подставляет сервер при отдаче index.html.
const _originalFetch = window.fetch;
window.fetch = async function (url, options = {}) {
  if (typeof url === "string" && url.startsWith("/api/") && url !== "/api/health") {
    options = { ...options };
    options.headers = options.headers || {};
    if (typeof options.headers === "object" && !options.headers["X-API-Token"]) {
      options.headers["X-API-Token"] = window.API_TOKEN || "";
    }
  }
  return _originalFetch.call(this, url, options);
};

// === Элементы загрузочного экрана ===
const loadingScreen = document.getElementById("loading-screen");
const presetSetupPanel = document.getElementById("preset-setup-panel");
const presetLaunchPanel = document.getElementById("preset-launch-panel");
const presetSetupForm = document.getElementById("preset-setup-form");
const presetSetupBackBtn = document.getElementById("preset-setup-back-btn");
const presetSetupError = document.getElementById("preset-setup-error");
const presetSetupHint = document.getElementById("preset-setup-hint");
const presetNameInput = document.getElementById("preset-name-input");
const presetBackendWrap = document.getElementById("preset-backend-wrap");
const presetBackendSelect = document.getElementById("preset-backend-select");
const presetLlamaFields = document.getElementById("preset-llama-fields");
const presetLlamaInput = document.getElementById("preset-llama-input");
const presetLlamaHint = document.getElementById("preset-llama-hint");
const presetModelInput = document.getElementById("preset-model-input");
const presetScanModelsBtn = document.getElementById("preset-scan-models-btn");
const presetLocalModelsSelect = document.getElementById("preset-local-models-select");
const presetHfRepoInput = document.getElementById("preset-hf-repo-input");
const presetHfTokenInput = document.getElementById("preset-hf-token-input");
const presetDownloadBtn = document.getElementById("preset-download-btn");
const downloadProgressWrap = document.getElementById("download-progress-wrap");
const downloadProgressBar = document.getElementById("download-progress-bar");
const downloadProgressText = document.getElementById("download-progress-text");
const downloadProgressMeta = document.getElementById("download-progress-meta");
const downloadProgressHint = document.getElementById("download-progress-hint");
const presetMlxFields = document.getElementById("preset-mlx-fields");
const presetMtplxFields = document.getElementById("preset-mtplx-fields");
const presetLlamaExtraFields = document.getElementById("preset-llama-extra-fields");
const presetTemperatureInput = document.getElementById("preset-temperature-input");
const presetMaxTokensInput = document.getElementById("preset-max-tokens-input");
const presetMtplxTemperatureInput = document.getElementById("preset-mtplx-temperature-input");
const presetMtplxMaxTokensInput = document.getElementById("preset-mtplx-max-tokens-input");
const presetMtplxPortInput = document.getElementById("preset-mtplx-port-input");
const presetMtplxContextInput = document.getElementById("preset-mtplx-context-input");
const presetMtplxDepthInput = document.getElementById("preset-mtplx-depth-input");
const presetMtplxMtpEnabledInput = document.getElementById("preset-mtplx-mtp-enabled-input");
const presetPortInputLlama = document.getElementById("preset-port-input-llama");
const presetMmprojInput = document.getElementById("preset-mmproj-input");
const presetMtpInput = document.getElementById("preset-mtp-input");
const presetMtpEnabledInput = document.getElementById("preset-mtp-enabled-input");
const presetContextInput = document.getElementById("preset-context-input");
const presetNglInput = document.getElementById("preset-ngl-input");
const presetPortInput = document.getElementById("preset-port-input");
const presetSaveBtn = document.getElementById("preset-save-btn");
const presetSetupLead = document.getElementById("preset-setup-lead");
const presetCardList = document.getElementById("preset-card-list");
const presetAddBtn = document.getElementById("preset-add-btn");
const toolsList = document.getElementById("tools-list");
const toolsHint = document.getElementById("tools-hint");
const loadingModelSelect = document.getElementById("loading-model-select");
const loadingModelDescription = document.getElementById("loading-model-description");
const loadingAsrSelect = document.getElementById("loading-asr-select");
const loadingAsrDescription = document.getElementById("loading-asr-description");
const loadingStartBtn = document.getElementById("loading-start-btn");
const loadingStatusText = document.getElementById("loading-status-text");

// === Элементы основного интерфейса ===
const ttsToggle = document.getElementById("tts-toggle");
const ttsToggleHint = document.getElementById("tts-toggle-hint");
const voiceToggle = document.getElementById("voice-toggle");
const voiceToggleHint = document.getElementById("voice-toggle-hint");
const voiceAsrSelect = document.getElementById("voice-asr-select");
const voiceAsrDescription = document.getElementById("voice-asr-description");
const heroBadge = document.getElementById("hero-badge");
const heroChatTitle = document.getElementById("hero-chat-title");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const pastePreview = document.getElementById("paste-preview");
const sendBtn = document.getElementById("send-btn");
const voiceMessageBtn = document.getElementById("voice-message-btn");
const voskDownloadBanner = document.getElementById("vosk-download-banner");
const voskDownloadBtn = document.getElementById("vosk-download-btn");
const voskDownloadStatus = document.getElementById("vosk-download-status");
const contextIndicator = document.getElementById("context-indicator");
const contextIndicatorText = document.getElementById("context-indicator-text");
const chatLog = document.getElementById("chat-log");
const template = document.getElementById("message-template");
const liveStatus = document.getElementById("live-status");
const liveStatusText = document.getElementById("live-status-text");
const liveStatusTimer = document.getElementById("live-status-timer");
const liveStatusProgress = document.getElementById("live-status-progress");
const liveStatusProgressBar = document.getElementById("live-status-progress-bar");
const liveStatusProgressText = document.getElementById("live-status-progress-text");
const voiceOverlay = document.getElementById("voice-overlay");
const voiceOverlayStatus = document.getElementById("voice-overlay-status");
const voiceOverlayTranscript = document.getElementById("voice-overlay-transcript");
const chatList = document.getElementById("chat-list");
const chatListEmpty = document.getElementById("chat-list-empty");
const newChatBtn = document.getElementById("new-chat-btn");
const settingsToggleBtn = document.getElementById("settings-toggle-btn");
const settingsCloseBtn = document.getElementById("settings-close-btn");
const settingsDrawer = document.getElementById("settings-drawer");
const settingsBackdrop = document.getElementById("settings-backdrop");

// Telegram account settings
const telegramAccountStatus = document.getElementById("telegram-account-status");
const telegramAccountSetupBtn = document.getElementById("telegram-account-setup-btn");
const telegramAccountDisconnectBtn = document.getElementById("telegram-account-disconnect-btn");

// User prompt modal
const userPromptModal = document.getElementById("user-prompt-modal");
const userPromptQuestion = document.getElementById("user-prompt-question");
const userPromptInput = document.getElementById("user-prompt-input");
const userPromptSubmitBtn = document.getElementById("user-prompt-submit-btn");
const userPromptCancelBtn = document.getElementById("user-prompt-cancel-btn");

// Telegram setup modal
const telegramSetupModal = document.getElementById("telegram-setup-modal");
const telegramSetupCloseBtn = document.getElementById("telegram-setup-close-btn");
const telegramSetupForm = document.getElementById("telegram-setup-form");
const telegramApiIdInput = document.getElementById("telegram-api-id");
const telegramApiHashInput = document.getElementById("telegram-api-hash");
const telegramPhoneInput = document.getElementById("telegram-phone");
const telegramSetupError = document.getElementById("telegram-setup-error");
const telegramCodeForm = document.getElementById("telegram-code-form");
const telegramCodeInput = document.getElementById("telegram-code");
const telegramCodeError = document.getElementById("telegram-code-error");
const telegram2faForm = document.getElementById("telegram-2fa-form");
const telegram2faPasswordInput = document.getElementById("telegram-2fa-password");
const telegram2faError = document.getElementById("telegram-2fa-error");
const telegramSetupFinishBtn = document.getElementById("telegram-setup-finish-btn");
const telegramSetupStepCredentials = document.getElementById("telegram-setup-step-credentials");
const telegramSetupStepCode = document.getElementById("telegram-setup-step-code");
const telegramSetupStep2fa = document.getElementById("telegram-setup-step-2fa");
const telegramSetupStepSuccess = document.getElementById("telegram-setup-step-success");
const telegramSetupSuccessText = document.getElementById("telegram-setup-success-text");

// Update modal
const updateModal = document.getElementById("update-modal");
const updateCurrentVersion = document.getElementById("update-current-version");
const updateLatestVersion = document.getElementById("update-latest-version");
const updateError = document.getElementById("update-error");
const updateLaterBtn = document.getElementById("update-later-btn");
const updateNowBtn = document.getElementById("update-now-btn");

// System check banner
const systemCheckBanner = document.getElementById("system-check-banner");
const systemCheckIcon = document.getElementById("system-check-icon");
const systemCheckTitle = document.getElementById("system-check-title");
const systemCheckMessage = document.getElementById("system-check-message");
const systemCheckList = document.getElementById("system-check-list");
const systemCheckClose = document.getElementById("system-check-close");
const backgroundTaskList = document.getElementById("background-task-list");
const backgroundTaskCount = document.getElementById("background-task-count");
const activePlanPanel = document.getElementById("active-plan-panel");
const activePlanToggle = document.getElementById("active-plan-toggle");
const activePlanTitle = document.getElementById("active-plan-title");
const activePlanList = document.getElementById("active-plan-list");
const activePlanStepCount = document.getElementById("active-plan-step-count");
const activePlanProgressFill = document.getElementById("active-plan-progress-fill");

const TOOL_COLLAPSE_LIMIT = 480;
let modelsCache = [];
let configCache = null;
let toolsCache = [];
let asrBackendsCache = [];
let presetSaveInFlight = false;
let chatsCache = [];
let ttsRequestInFlight = false;
let activePlanCollapsed = false;
let voiceRequestInFlight = false;
let asrRequestInFlight = false;
let pendingImages = [];
let serverIsOnline = false;
let currentModelKey = null; // Хранит ключ текущей выбранной модели
let currentModelSupportsImages = false;
let lastVoiceCommandId = 0;
let pendingVoiceSubmit = false;
let lastVoiceEnabled = false;
let voiceSubmitRequested = false;
let liveStatusTimerId = null;
let liveStatusTimerStartedAt = 0;
let liveStatusTimerBaseText = "";
let contextRefreshTimerId = null;
let contextRefreshInFlight = false;
let isGeneratingResponse = false;
let stopRequestInFlight = false;
let isRecordingVoiceMessage = false;
let isMacOs = false;
let downloadEventSource = null;
let localModelsCache = [];
let currentChatId = null;
let chatSaveTimerId = null;
let chatSaveInFlight = false;
let openChatMenuId = null;
const pendingAutoTitleChatIds = new Set();
const recentAutoTitleUpdates = new Map();
const activeImageGenPlaceholders = new Map();
const activeStreamingToolCalls = new Map();

// ─── Smart auto-scroll / follow-mode ────────────────────────────────
let streamFollowMode = true;
let streamFollowButton = null;
let streamFollowIgnoreScroll = false;
const STREAM_FOLLOW_THRESHOLD = 80;

function isChatLogNearBottom() {
  if (!chatLog) return true;
  const distance = chatLog.scrollHeight - chatLog.scrollTop - chatLog.clientHeight;
  return distance <= STREAM_FOLLOW_THRESHOLD;
}

function scrollToBottomIfFollowing() {
  if (!chatLog) return;
  if (streamFollowMode) {
    streamFollowIgnoreScroll = true;
    chatLog.scrollTop = chatLog.scrollHeight;
  }
}

function updateStreamFollowButton() {
  if (!streamFollowButton) return;
  const nearBottom = isChatLogNearBottom();
  if (nearBottom && streamFollowMode) {
    streamFollowButton.classList.add("hidden");
  } else {
    streamFollowButton.classList.remove("hidden");
  }
}

function createStreamFollowButton() {
  if (streamFollowButton || !document.querySelector(".chat-frame")) return;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "stream-follow-btn hidden";
  btn.setAttribute("aria-label", "Следить за генерацией");
  btn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12l7 7 7-7"/></svg>
    <span>Следить</span>
  `;
  btn.addEventListener("click", () => {
    streamFollowMode = true;
    scrollToBottomIfFollowing();
    updateStreamFollowButton();
  });
  document.querySelector(".chat-frame").appendChild(btn);
  streamFollowButton = btn;
}

function initStreamFollow() {
  createStreamFollowButton();
  if (!chatLog) return;
  chatLog.addEventListener("scroll", () => {
    if (streamFollowIgnoreScroll) {
      streamFollowIgnoreScroll = false;
      updateStreamFollowButton();
      return;
    }
    const nearBottom = isChatLogNearBottom();
    if (nearBottom) {
      streamFollowMode = true;
    } else {
      streamFollowMode = false;
    }
    updateStreamFollowButton();
  }, { passive: true });
}

function isChatBusy() {
  return isGeneratingResponse;
}

function setSendButtonMode(mode) {
  if (!sendBtn) {
    return;
  }

  const isStopMode = mode === "stop";
  sendBtn.classList.toggle("is-stop", isStopMode);
  sendBtn.setAttribute("aria-label", isStopMode ? "Остановить генерацию" : "Отправить");
  sendBtn.innerHTML = isStopMode
    ? `
      <span class="send-btn-stop" aria-hidden="true">
        <span class="send-btn-stop-ring"></span>
        <span class="send-btn-stop-square"></span>
      </span>
    `
    : `<span class="send-btn-arrow" aria-hidden="true">➜</span>`;
}

function setGeneratingState(nextState, estimatedTokens = 0) {
  isGeneratingResponse = Boolean(nextState);
  if (!isGeneratingResponse) {
    liveStatus?.classList.remove("is-compacting");
    liveStatusProgress?.classList.remove("is-indeterminate");
    stopRequestInFlight = false;
    stopGenerationProgress();
    stopContextRefreshTimer();
  } else {
    startGenerationProgress(estimatedTokens);
    startContextRefreshTimer();
  }
  setSendButtonMode(isGeneratingResponse ? "stop" : "send");
}

function startContextRefreshTimer() {
  stopContextRefreshTimer();
  contextRefreshTimerId = setInterval(() => {
    if (contextRefreshInFlight) return;
    contextRefreshInFlight = true;
    refreshContext().finally(() => {
      contextRefreshInFlight = false;
    });
  }, 5000);
}

function stopContextRefreshTimer() {
  if (contextRefreshTimerId) {
    clearInterval(contextRefreshTimerId);
    contextRefreshTimerId = null;
  }
}

let generationProgressInterval = null;
let generationProgressPercent = 0;
let generationProgressPhase = "thinking"; // thinking | generating
let hasRealPromptProgress = false;
let lastRealPromptProgressAt = 0;
let hasRealDecodeProgress = false;
let estimatedPromptTokens = 0;
let promptProgressStartTime = 0;
let estimatedPrefillSpeed = parseFloat(localStorage.getItem("jarvis_estimated_prefill_speed")) || 150; // tokens/sec

function startGenerationProgress(estimatedTokens = 0) {
  generationProgressPercent = 0;
  generationProgressPhase = "thinking";
  hasRealPromptProgress = false;
  hasRealDecodeProgress = false;
  lastRealPromptProgressAt = 0;
  estimatedPromptTokens = Math.max(0, estimatedTokens);
  promptProgressStartTime = Date.now();
  if (liveStatusProgress) {
    liveStatusProgress.classList.remove("hidden");
  }
  updateGenerationProgressUI();
  if (generationProgressInterval) {
    clearInterval(generationProgressInterval);
  }
  generationProgressInterval = setInterval(() => {
    if (generationProgressPhase === "thinking") {
      // Prefer real prefill progress from llama-server when available.
      if (!hasRealPromptProgress && estimatedPromptTokens > 0) {
        const elapsedSec = (Date.now() - promptProgressStartTime) / 1000;
        const expectedSec = estimatedPromptTokens / Math.max(1, estimatedPrefillSpeed);
        generationProgressPercent = Math.min(99, (elapsedSec / expectedSec) * 100);
      }
    } else if (generationProgressPhase === "generating") {
      // If real decode progress arrives, don't fake-advance the bar.
      if (hasRealDecodeProgress) {
        return;
      }
      generationProgressPercent = Math.min(92, generationProgressPercent + 0.3);
    }
    updateGenerationProgressUI();
  }, 100);
}

function markGenerationProgressGenerating() {
  if (generationProgressPhase !== "generating") {
    generationProgressPhase = "generating";
    // Не сбрасываем прогресс назад; если prefill дошёл до 100%, генерация стартует с 100% и пойдёт дальше.
    generationProgressPercent = Math.max(generationProgressPercent, 0);
  }
}

function bumpGenerationProgress(delta = 2) {
  if (generationProgressPhase === "generating") {
    generationProgressPercent = Math.min(95, generationProgressPercent + delta);
    updateGenerationProgressUI();
  }
}

function finishGenerationProgress() {
  generationProgressPercent = 100;
  generationProgressPhase = "done";
  updateGenerationProgressUI();
  setTimeout(stopGenerationProgress, 600);
}

function stopGenerationProgress() {
  if (generationProgressInterval) {
    clearInterval(generationProgressInterval);
    generationProgressInterval = null;
  }
  generationProgressPercent = 0;
  generationProgressPhase = "thinking";
  hasRealPromptProgress = false;
  hasRealDecodeProgress = false;
  lastRealPromptProgressAt = 0;
  if (liveStatusProgress) {
    liveStatusProgress.classList.add("hidden");
  }
  updateGenerationProgressUI();
}

function updateGenerationProgressUI() {
  if (!liveStatusProgressBar || !liveStatusProgressText) {
    return;
  }
  const pct = Math.round(Math.max(0, Math.min(100, generationProgressPercent)));
  liveStatusProgressBar.style.width = `${pct}%`;
  liveStatusProgressText.textContent = `${pct}%`;
}

async function requestStopGeneration() {
  if (!isGeneratingResponse || stopRequestInFlight) {
    return;
  }

  // If a user prompt modal is open, treat stop as cancellation of the prompt.
  if (userPromptModal && !userPromptModal.classList.contains("hidden")) {
    cancelUserPrompt();
  }

  stopRequestInFlight = true;
  setLiveStatus("Останавливаю ответ...", true);

  try {
    await fetch("/api/chat/stop", { method: "POST" });
  } catch (error) {
    stopRequestInFlight = false;
    addMessage("system", `Не удалось остановить ответ: ${error.message}`);
    setLiveStatus("Ошибка остановки", false);
  }
}

function autoResizeMessageInput() {
  if (!messageInput) {
    return;
  }
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 320)}px`;
}

function setSettingsDrawerOpen(open) {
  if (!settingsDrawer || !settingsBackdrop) {
    return;
  }

  settingsDrawer.classList.toggle("hidden", !open);
  settingsBackdrop.classList.toggle("hidden", !open);
  settingsDrawer.setAttribute("aria-hidden", open ? "false" : "true");
}

function setVoiceOverlayVisible(visible) {
  if (!voiceOverlay) {
    return;
  }
  voiceOverlay.classList.toggle("hidden", !visible);
  voiceOverlay.setAttribute("aria-hidden", visible ? "false" : "true");
}

// === ask_user modal ===
let activeUserPromptId = null;

function setUserPromptModalOpen(open, { promptId, question } = {}) {
  if (!userPromptModal) {
    return;
  }
  if (open) {
    activeUserPromptId = promptId || null;
    if (userPromptQuestion) {
      userPromptQuestion.textContent = question || "Вопрос агента...";
    }
    if (userPromptInput) {
      userPromptInput.value = "";
      setTimeout(() => userPromptInput.focus(), 50);
    }
  }
  userPromptModal.classList.toggle("hidden", !open);
  userPromptModal.setAttribute("aria-hidden", open ? "false" : "true");
  if (!open) {
    activeUserPromptId = null;
    if (messageInput) {
      messageInput.focus();
    }
  }
}

async function submitUserPrompt(answer) {
  if (!activeUserPromptId) {
    return;
  }
  try {
    await fetch("/api/user-response", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt_id: activeUserPromptId, answer }),
    });
  } catch (error) {
    console.error("Failed to send user response:", error);
  } finally {
    setUserPromptModalOpen(false);
  }
}

function cancelUserPrompt() {
  submitUserPrompt("__cancelled__");
}

// === Telegram account setup modal ===
function setTelegramSetupModalOpen(open) {
  if (!telegramSetupModal) {
    return;
  }
  telegramSetupModal.classList.toggle("hidden", !open);
  telegramSetupModal.setAttribute("aria-hidden", open ? "false" : "true");
  if (open) {
    showTelegramSetupStep("credentials");
    if (telegramSetupForm) {
      telegramSetupForm.reset();
    }
    if (telegramCodeForm) {
      telegramCodeForm.reset();
    }
    if (telegram2faForm) {
      telegram2faForm.reset();
    }
    [telegramSetupError, telegramCodeError, telegram2faError].forEach((el) => {
      if (el) {
        el.classList.add("hidden");
        el.textContent = "";
      }
    });
  }
}

function showTelegramSetupStep(step) {
  const steps = {
    credentials: telegramSetupStepCredentials,
    code: telegramSetupStepCode,
    "2fa": telegramSetupStep2fa,
    success: telegramSetupStepSuccess,
  };
  Object.entries(steps).forEach(([key, el]) => {
    if (el) {
      el.classList.toggle("hidden", key !== step);
    }
  });
}

function showTelegramSetupError(el, message) {
  if (!el) {
    return;
  }
  el.textContent = message;
  el.classList.remove("hidden");
}

async function refreshTelegramAccountStatus() {
  if (!telegramAccountStatus) {
    return;
  }
  try {
    const response = await fetch("/api/telegram-account/status");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      telegramAccountStatus.textContent = "Не удалось загрузить статус";
      telegramAccountStatus.classList.remove("is-connected");
      return;
    }
    if (!data.available) {
      telegramAccountStatus.textContent = "Telethon не установлен";
      telegramAccountStatus.classList.remove("is-connected");
      return;
    }
    if (data.connected && (data.username || data.phone)) {
      telegramAccountStatus.textContent = `Подключено: ${data.username ? "@" + data.username : data.phone}`;
      telegramAccountStatus.classList.add("is-connected");
    } else if (data.configured) {
      telegramAccountStatus.textContent = "Настроено, но не подключено";
      telegramAccountStatus.classList.remove("is-connected");
    } else {
      telegramAccountStatus.textContent = "Аккаунт не подключён";
      telegramAccountStatus.classList.remove("is-connected");
    }

    if (telegramAccountSetupBtn) {
      telegramAccountSetupBtn.classList.toggle("hidden", data.connected || data.configured);
    }
    if (telegramAccountDisconnectBtn) {
      telegramAccountDisconnectBtn.classList.toggle("hidden", !(data.connected || data.configured));
    }
  } catch (error) {
    telegramAccountStatus.textContent = "Ошибка загрузки статуса";
    telegramAccountStatus.classList.remove("is-connected");
  }
}

// === System check banner ===
async function runSystemCheck() {
  try {
    const response = await fetch("/api/system-check");
    if (!response.ok) return;
    const data = await response.json();
    const dismissed = getDismissedSystemCheckIssues();
    renderSystemCheckBanner((data.issues || []).filter((issue) => !dismissed.has(issue.id)));
  } catch (error) {
    // Тихо игнорируем: баннер — необязательная подсказка
  }
}

function getDismissedSystemCheckIssues() {
  try {
    return new Set(JSON.parse(localStorage.getItem("jarvis.dismissedSystemChecks") || "[]"));
  } catch {
    return new Set();
  }
}

function renderSystemCheckBanner(issues) {
  if (!systemCheckBanner || !systemCheckTitle || !systemCheckMessage || !systemCheckList) return;

  if (!issues.length) {
    systemCheckBanner.classList.add("hidden");
    return;
  }

  const hasError = issues.some((i) => i.severity === "error");
  systemCheckBanner.classList.remove("hidden", "warning", "error");
  systemCheckBanner.classList.add(hasError ? "error" : "warning");
  systemCheckIcon.textContent = hasError ? "🚫" : "⚠️";

  if (issues.length === 1) {
    systemCheckTitle.textContent = issues[0].title;
    systemCheckMessage.textContent = issues[0].message;
  } else {
    systemCheckTitle.textContent = hasError ? "Обнаружены критические проблемы" : "Нужно настроить несколько разрешений";
    systemCheckMessage.textContent = `Найдено проблем: ${issues.length}. Разверните карточки ниже, чтобы увидеть пошаговое решение.`;
  }

  systemCheckList.innerHTML = "";
  issues.forEach((issue) => {
    const issueEl = document.createElement("div");
    issueEl.className = `system-check-issue ${issue.severity === "error" ? "error" : "warning"}`;
    issueEl.dataset.issueId = issue.id || issue.title;

    const header = document.createElement("div");
    header.className = "system-check-issue-header";

    const title = document.createElement("div");
    title.className = "system-check-issue-title";
    title.textContent = issue.title;

    const badge = document.createElement("span");
    badge.className = `system-check-issue-badge ${issue.severity === "error" ? "error" : "warning"}`;
    badge.textContent = issue.severity === "error" ? "Критично" : "Важно";

    header.appendChild(title);
    header.appendChild(badge);
    issueEl.appendChild(header);

    const message = document.createElement("div");
    message.className = "system-check-issue-message";
    message.textContent = issue.message;
    issueEl.appendChild(message);

    const actions = document.createElement("div");
    actions.className = "system-check-issue-actions";

    const solutionBtn = document.createElement("button");
    solutionBtn.type = "button";
    solutionBtn.textContent = "Как исправить";
    actions.appendChild(solutionBtn);

    if (issue.fix_action) {
      const fixBtn = document.createElement("button");
      fixBtn.type = "button";
      fixBtn.className = "primary";
      fixBtn.textContent = issue.fix_action === "open_presets" ? "Настроить пресет" : "Исправить";
      fixBtn.addEventListener("click", () => handleSystemCheckFix(issue));
      actions.appendChild(fixBtn);
    }

    issueEl.appendChild(actions);

    const solutionEl = document.createElement("div");
    solutionEl.className = "system-check-solution hidden";

    const solutionTitle = document.createElement("div");
    solutionTitle.className = "system-check-solution-title";
    solutionTitle.textContent = "Пошаговое решение";
    solutionEl.appendChild(solutionTitle);

    const solutionSteps = issue.solution || [];
    if (solutionSteps.length) {
      const ol = document.createElement("ol");
      solutionSteps.forEach((step) => {
        const li = document.createElement("li");
        li.innerHTML = escapeHtml(step)
          .replace(/`([^`]+)`/g, '<code>$1</code>')
          .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
        ol.appendChild(li);
      });
      solutionEl.appendChild(ol);
    } else {
      const hint = document.createElement("p");
      hint.style.cssText = "margin:0;color:var(--muted);font-size:0.82rem;";
      hint.textContent = "Дополнительная информация отсутствует.";
      solutionEl.appendChild(hint);
    }

    issueEl.appendChild(solutionEl);

    solutionBtn.addEventListener("click", () => {
      solutionEl.classList.toggle("hidden");
      solutionBtn.textContent = solutionEl.classList.contains("hidden") ? "Как исправить" : "Скрыть решение";
    });
    systemCheckList.appendChild(issueEl);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function handleSystemCheckFix(issue) {
  if (issue.fix_action === "open_url" && issue.fix_url) {
    window.open(issue.fix_url, "_blank");
  } else if (issue.fix_action === "open_presets") {
    loadingScreen?.classList.remove("hidden");
    document.querySelector(".shell")?.classList.add("hidden");
    setLoadingMode("launch");
  } else if (issue.fix_action === "env_hint") {
    const steps = (issue.solution || []).join("\n");
    const text = steps ? `${issue.title}\n\n${issue.message}\n\n${steps}` : `${issue.title}\n\n${issue.message}`;
    alert(text);
  }
  // Не закрываем баннер автоматически — пусть пользователь сам закроет
}

if (systemCheckClose) {
  systemCheckClose.addEventListener("click", () => {
    try {
      const ids = getDismissedSystemCheckIssues();
      document.querySelectorAll(".system-check-issue").forEach((node) => {
        if (node.dataset.issueId) ids.add(node.dataset.issueId);
      });
      localStorage.setItem("jarvis.dismissedSystemChecks", JSON.stringify([...ids]));
    } catch {}
    systemCheckBanner.classList.add("hidden");
  });
}

// === Self-update ===
function setUpdateModalOpen(open) {
  if (!updateModal) return;
  updateModal.classList.toggle("hidden", !open);
  updateModal.setAttribute("aria-hidden", open ? "false" : "true");
}

async function checkForUpdate() {
  try {
    const response = await fetch("/api/update/check");
    const data = await response.json();
    if (!response.ok || !data.ok) return;
    if (!data.available) return;

    if (updateCurrentVersion) updateCurrentVersion.textContent = (data.current || "").slice(0, 12);
    if (updateLatestVersion) updateLatestVersion.textContent = (data.latest || "").slice(0, 12);
    if (updateError) {
      updateError.textContent = "";
      updateError.classList.add("hidden");
    }
    setUpdateModalOpen(true);
  } catch {
    // Silently ignore update check failures.
  }
}

async function applyUpdate() {
  if (!updateNowBtn || !updateError) return;
  updateNowBtn.disabled = true;
  updateNowBtn.textContent = "Обновление...";
  try {
    const response = await fetch("/api/update/apply", { method: "POST" });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.detail || "Не удалось обновить приложение");
    }
    if (!data.restarted) {
      setUpdateModalOpen(false);
      return;
    }
    updateNowBtn.textContent = "Перезапуск...";
    // The backend will terminate the process; the updater will relaunch the app.
  } catch (error) {
    updateError.textContent = error.message;
    updateError.classList.remove("hidden");
    updateNowBtn.disabled = false;
    updateNowBtn.textContent = "Обновить";
  }
}

if (updateLaterBtn) {
  updateLaterBtn.addEventListener("click", () => setUpdateModalOpen(false));
}
if (updateNowBtn) {
  updateNowBtn.addEventListener("click", applyUpdate);
}

function updateVoiceOverlay(state) {
  if (!voiceOverlay || !voiceOverlayStatus || !voiceOverlayTranscript) {
    return;
  }

  const visible = Boolean(state.overlay_visible) && Boolean(state.enabled);
  setVoiceOverlayVisible(visible);
  voiceOverlayStatus.textContent = state.status || "Слушаю...";
  voiceOverlayTranscript.textContent = state.live_text || "Слушаю...";
}

async function resetVoiceOverlayState() {
  try {
    await fetch("/api/voice/reset", { method: "POST" });
  } catch {}
  setVoiceOverlayVisible(false);
}

function trySubmitQueuedVoiceCommand() {
  if (!pendingVoiceSubmit || isChatBusy()) {
    return;
  }
  pendingVoiceSubmit = false;
  chatForm.requestSubmit();
}

function queueVoiceSubmission(commandText) {
  messageInput.value = commandText;
  autoResizeMessageInput();
  messageInput.focus();
  voiceSubmitRequested = true;

  if (isChatBusy()) {
    pendingVoiceSubmit = true;
    setLiveStatus("Голосовая команда ждёт завершения текущего ответа...", true);
    return;
  }

  pendingVoiceSubmit = false;
  chatForm.requestSubmit();
}

async function toggleVoiceMessageRecording() {
  if (!voiceMessageBtn) {
    return;
  }

  if (isRecordingVoiceMessage) {
    voiceMessageBtn.disabled = true;
    voiceMessageBtn.setAttribute("aria-label", "Расшифровываю запись...");
    setLiveStatus("📝 Расшифровываю всю запись...", true);

    try {
      const response = await fetch("/api/voice/record_message/stop", { method: "POST" });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.detail || data.error || "Ошибка расшифровки");
      }

      const text = String(data.text || "").trim();
      if (text) {
        const prefix = messageInput.value ? `${messageInput.value}\n` : "";
        messageInput.value = prefix + text;
        autoResizeMessageInput();
        messageInput.focus();
        setLiveStatus("Голосовое сообщение расшифровано", false);
      } else {
        setLiveStatus("Ничего не распознано", false);
      }
    } catch (error) {
      setLiveStatus(`Ошибка расшифровки: ${error.message}`, false);
    } finally {
      isRecordingVoiceMessage = false;
      voiceMessageBtn.disabled = false;
      voiceMessageBtn.classList.remove("recording");
      voiceMessageBtn.setAttribute("aria-label", "Записать голосовое сообщение");
    }
    return;
  }

  if (isChatBusy()) {
    setLiveStatus("Дождитесь окончания текущего ответа", false);
    return;
  }

  isRecordingVoiceMessage = true;
  voiceMessageBtn.classList.add("recording");
  voiceMessageBtn.setAttribute("aria-label", "Идёт запись...");
  setLiveStatus("🔴 Записываю голосовое сообщение. Нажмите ещё раз для остановки", true);

  try {
    const response = await fetch("/api/voice/record_message/start", { method: "POST" });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.detail || "Ошибка распознавания");
    }
  } catch (error) {
    isRecordingVoiceMessage = false;
    voiceMessageBtn.classList.remove("recording");
    voiceMessageBtn.setAttribute("aria-label", "Записать голосовое сообщение");
    setLiveStatus(`Ошибка записи: ${error.message}`, false);
  }
}

async function pollVoiceState() {
  try {
    const response = await fetch("/api/voice/state", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      return;
    }

    lastVoiceEnabled = Boolean(data.enabled);
    updateVoiceOverlay(data);

    if (
      data.enabled &&
      data.overlay_visible &&
      typeof data.live_text === "string" &&
      data.live_text.trim() &&
      !isChatBusy()
    ) {
      messageInput.value = data.live_text;
      autoResizeMessageInput();
    }

    if (voiceToggle) {
      voiceToggle.checked = Boolean(data.enabled);
    }
    if (voiceToggleHint) {
      const wakeWord = data.wake_word || "пятница";
      voiceToggleHint.textContent = data.enabled
        ? `Слушает wake word: "${wakeWord}"`
        : `Wake word: "${wakeWord}"`;
    }

    if (data.final_command_id && data.final_command_id > lastVoiceCommandId) {
      lastVoiceCommandId = data.final_command_id;
      const finalText = String(data.final_text || data.live_text || "").trim();
      if (finalText) {
        queueVoiceSubmission(finalText);
      }
    }

    if (voskDownloadBanner) {
      const missing = Boolean(data.model_missing) && !Boolean(data.model_downloading);
      voskDownloadBanner.classList.toggle("hidden", !missing);
      if (voskDownloadBtn) {
        voskDownloadBtn.disabled = Boolean(data.model_downloading);
      }
      if (voskDownloadStatus && data.model_downloading) {
        voskDownloadStatus.textContent = "Скачивание…";
      } else if (voskDownloadStatus) {
        voskDownloadStatus.textContent = "";
      }
    }
  } catch {}
}

function canUsePastedImages() {
  const selected = modelsCache.find((model) => model.key === currentModelKey);
  if (selected) {
    return Boolean(selected.supports_images);
  }
  return currentModelSupportsImages;
}

function renderPendingImages() {
  if (!pastePreview) {
    return;
  }

  if (!pendingImages.length) {
    pastePreview.innerHTML = "";
    pastePreview.classList.add("is-empty");
    return;
  }

  pastePreview.classList.remove("is-empty");
  pastePreview.innerHTML = pendingImages
    .map((src, index) => `
      <div class="paste-chip">
        <img src="${src}" alt="attachment ${index + 1}" class="paste-chip-image">
        <button type="button" class="paste-chip-remove" data-image-index="${index}" aria-label="Удалить изображение">x</button>
      </div>
    `)
    .join("");
}

function clearPendingImages() {
  pendingImages = [];
  renderPendingImages();
}

async function fileToDataUrl(file) {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Не удалось прочитать изображение"));
    reader.readAsDataURL(file);
  });
}

async function addClipboardImages(files) {
  if (!files.length) {
    return;
  }

  if (!canUsePastedImages()) {
    addMessage("system", "Текущая модель не поддерживает прикрепление изображений.");
    return;
  }

  const nextImages = [];
  for (const file of files) {
    const dataUrl = await fileToDataUrl(file);
    if (dataUrl.startsWith("data:image/")) {
      nextImages.push(dataUrl);
    }
  }

  if (!nextImages.length) {
    return;
  }

  pendingImages = [...pendingImages, ...nextImages].slice(0, 6);
  renderPendingImages();
  setLiveStatus(`Прикреплено изображений: ${pendingImages.length}`, false);
}

function formatContextTitle(data) {
  const used = Number(data.used || 0);
  const capacity = Number(data.capacity || 0);
  const free = Number(data.free || 0);
  return `Заполнено: ${used} из ${capacity}. Свободно: ${free}.`;
}

function updateContextIndicator(data) {
  if (!contextIndicator || !contextIndicatorText) {
    return;
  }

  const capacity = Math.max(Number(data.capacity || 0), 1);
  const used = Math.min(Math.max(Number(data.used || 0), 0), capacity);
  const free = Math.max(capacity - used, 0);
  const percent = Math.max(0, Math.min((used / capacity) * 100, 100));

  contextIndicator.style.setProperty("--context-fill", `${percent}%`);
  contextIndicatorText.textContent = `${Math.round(percent)}%`;
  contextIndicator.title = formatContextTitle({ used, capacity, free });
  contextIndicator.setAttribute("aria-label", contextIndicator.title);
}

function setLiveStatus(text, busy = false) {
  stopLiveStatusTimer();
  liveStatusText.textContent = text;
  liveStatus.classList.toggle("is-busy", busy);
  liveStatus.classList.toggle("is-idle", !busy);
}

function stopLiveStatusTimer() {
  if (liveStatusTimerId) {
    clearInterval(liveStatusTimerId);
    liveStatusTimerId = null;
  }
  liveStatusTimerStartedAt = 0;
  liveStatusTimerBaseText = "";
  if (liveStatusTimer) {
    liveStatusTimer.textContent = "";
    liveStatusTimer.classList.add("hidden");
  }
}

function startLiveStatusTimer(text, busy = true) {
  stopLiveStatusTimer();
  liveStatusTimerBaseText = text;
  liveStatusTimerStartedAt = Date.now();

  const render = () => {
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - liveStatusTimerStartedAt) / 1000));
    liveStatusText.textContent = liveStatusTimerBaseText;
    if (liveStatusTimer) {
      liveStatusTimer.textContent = `${elapsedSeconds}s`;
      liveStatusTimer.classList.remove("hidden");
    }
    liveStatus.classList.toggle("is-busy", busy);
    liveStatus.classList.toggle("is-idle", !busy);
  };

  render();
  liveStatusTimerId = window.setInterval(render, 1000);
}

function getTimeBasedGreetingOptions() {
  const hour = new Date().getHours();

  if (hour < 6 || hour >= 19) {
    return [
      "Доброго вечера, Сэр.",
      "Тихий вечер, Сэр. Jarvis на связи.",
      "Вечер в порядке, Сэр. Можем начинать.",
    ];
  }

  if (hour < 14) {
    return [
      "Доброе утро, Сэр.",
      "С добрым утром, Сэр. Jarvis готов.",
      "Утро началось, Сэр. Чем займемся?",
    ];
  }

  return [
    "Добрый день, Сэр.",
    "Хорошего дня, Сэр. Jarvis к вашим услугам.",
    "День в разгаре, Сэр. Готов помочь.",
  ];
}

function createEmptyChatState() {
  const greetingOptions = getTimeBasedGreetingOptions();
  const greeting =
    greetingOptions[Math.floor(Math.random() * greetingOptions.length)] ||
    "Добрый день, Сэр.";

  const node = document.createElement("div");
  node.className = "chat-empty-state";
  node.innerHTML = `
    <div class="chat-empty-brand">Jarvis</div>
    <div class="chat-empty-greeting">${greeting}</div>
  `;
  return node;
}

function syncEmptyChatState() {
  if (!chatLog) {
    return;
  }

  const hasMessages = Boolean(chatLog.querySelector(".message"));
  const emptyState = chatLog.querySelector(".chat-empty-state");

  if (hasMessages) {
    emptyState?.remove();
    chatLog.classList.remove("is-empty");
    return;
  }

  if (!emptyState) {
    chatLog.appendChild(createEmptyChatState());
  }

  chatLog.classList.add("is-empty");
}

function formatRelativeChatTime(timestamp) {
  if (!timestamp) {
    return "сейчас";
  }

  const value = Date.parse(timestamp);
  if (Number.isNaN(value)) {
    return "сейчас";
  }

  const diffSeconds = Math.max(0, Math.floor((Date.now() - value) / 1000));
  if (diffSeconds < 60) {
    return "сейчас";
  }

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes} ${pluralizeRu(diffMinutes, "минуту", "минуты", "минут")} назад`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} ${pluralizeRu(diffHours, "час", "часа", "часов")} назад`;
  }

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return `${diffDays} ${pluralizeRu(diffDays, "день", "дня", "дней")} назад`;
  }

  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 5) {
    return `${diffWeeks} ${pluralizeRu(diffWeeks, "неделю", "недели", "недель")} назад`;
  }

  const date = new Date(value);
  return date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function pluralizeRu(value, one, few, many) {
  const abs = Math.abs(Number(value)) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) {
    return many;
  }
  if (last > 1 && last < 5) {
    return few;
  }
  if (last === 1) {
    return one;
  }
  return many;
}

function summarizeChatPreview(preview) {
  const normalized = String(preview || "").replace(/\s+/g, " ").trim();
  return normalized || "Пока без сообщений";
}

function getChatDisplayTitle(chat) {
  return String(chat?.title || "").trim() || summarizeChatPreview(chat?.preview) || "Новый чат";
}

function updateHeroChatTitle() {
  if (!heroChatTitle) {
    return;
  }
  const activeChat = currentChatId
    ? chatsCache.find((chat) => chat.id === currentChatId)
    : null;
  heroChatTitle.textContent = getChatDisplayTitle(activeChat);
}

function countTitleCandidateMessages(messages) {
  return (messages || []).filter((entry) => {
    const role = String(entry?.role || "").trim().toLowerCase();
    return (role === "user" || role === "assistant") && String(entry?.body || "").trim();
  }).length;
}

function shouldAttemptAutoTitle(messages) {
  return countTitleCandidateMessages(messages) > 2;
}

function markAutoTitleUpdated(chatId) {
  if (!chatId) {
    return;
  }
  recentAutoTitleUpdates.set(chatId, Date.now() + 2400);
}

function isAutoTitleRecentlyUpdated(chatId) {
  const expiresAt = recentAutoTitleUpdates.get(chatId);
  if (!expiresAt) {
    return false;
  }
  if (expiresAt <= Date.now()) {
    recentAutoTitleUpdates.delete(chatId);
    return false;
  }
  return true;
}

function renderChatList() {
  if (!chatList || !chatListEmpty) {
    return;
  }

  const sortedChats = [...chatsCache].sort((left, right) => {
    return String(right.updated_at || "").localeCompare(String(left.updated_at || ""));
  });

  chatList.innerHTML = sortedChats.map((chat) => `
    <div class="chat-list-row ${chat.id === currentChatId ? "active" : ""} ${isAutoTitleRecentlyUpdated(chat.id) ? "title-updated" : ""}" data-chat-id="${chat.id}">
      <button
        type="button"
        class="chat-list-item ${chat.id === currentChatId ? "active" : ""}"
        data-chat-id="${chat.id}"
        aria-label="Открыть чат ${escapeHtml(chat.title || "Новый чат")}"
      >
        <span class="chat-list-title">
          <span class="chat-list-text">${escapeHtml((chat.title || "").trim() || summarizeChatPreview(chat.preview))}</span>
          ${pendingAutoTitleChatIds.has(chat.id) ? '<span class="chat-title-spinner" aria-hidden="true"></span>' : ""}
        </span>
        <span class="chat-list-meta">${escapeHtml(formatRelativeChatTime(chat.last_message_at || chat.updated_at))}</span>
      </button>
      <div class="chat-menu-wrap">
        <button
          type="button"
          class="chat-menu-trigger"
          data-chat-menu-trigger="${chat.id}"
          aria-label="Действия для чата ${escapeHtml(chat.title || "Новый чат")}"
        >...</button>
        <div class="chat-menu ${openChatMenuId === chat.id ? "" : "hidden"}" data-chat-menu="${chat.id}">
          <button type="button" class="chat-menu-item" data-chat-action="summarize" data-chat-id="${chat.id}">Сжать контекст</button>
          <button type="button" class="chat-menu-item" data-chat-action="rename" data-chat-id="${chat.id}">Переименовать</button>
          <button type="button" class="chat-menu-item danger" data-chat-action="delete" data-chat-id="${chat.id}">Удалить</button>
        </div>
      </div>
    </div>
  `).join("");

  chatListEmpty.classList.toggle("hidden", sortedChats.length > 0);
  requestAnimationFrame(positionOpenChatMenu);
}

function positionOpenChatMenu() {
  if (!chatList || !openChatMenuId) {
    return;
  }

  const menu = Array.from(chatList.querySelectorAll("[data-chat-menu]"))
    .find((node) => node.getAttribute("data-chat-menu") === openChatMenuId);
  if (!menu || menu.classList.contains("hidden")) {
    return;
  }

  const trigger = chatList.querySelector(`[data-chat-menu-trigger="${openChatMenuId}"]`);
  if (!trigger) {
    return;
  }

  const triggerRect = trigger.getBoundingClientRect();
  const viewportGap = 10;
  menu.classList.remove("open-up");
  menu.style.left = "auto";
  menu.style.right = `${Math.max(viewportGap, window.innerWidth - triggerRect.right)}px`;
  menu.style.top = `${triggerRect.bottom + 8}px`;
  menu.style.bottom = "auto";

  const menuRect = menu.getBoundingClientRect();
  const overflowBottom = menuRect.bottom - window.innerHeight + viewportGap;

  if (overflowBottom > 0) {
    menu.classList.add("open-up");
    menu.style.top = "auto";
    menu.style.bottom = `${Math.max(viewportGap, window.innerHeight - triggerRect.top + 8)}px`;
  }

  const positionedRect = menu.getBoundingClientRect();
  if (positionedRect.left < viewportGap) {
    menu.style.left = `${viewportGap}px`;
    menu.style.right = "auto";
  }
}

function upsertChatSummary(chat) {
  if (!chat?.id) {
    return;
  }

  const index = chatsCache.findIndex((item) => item.id === chat.id);
  if (index >= 0) {
    chatsCache[index] = { ...chatsCache[index], ...chat };
  } else {
    chatsCache.push(chat);
  }
  updateHeroChatTitle();
  renderChatList();
}

async function loadChats() {
  const response = await fetch("/api/chats");
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.detail || "Не удалось загрузить список чатов");
  }

  chatsCache = Array.isArray(data.chats) ? data.chats : [];
  if (!currentChatId) {
    // Don't auto-select the most recent chat on startup: an empty UI must
    // mean a truly new/empty context, not a hidden long history.
    currentChatId = data.active_chat_id || null;
  }
  updateHeroChatTitle();
  renderChatList();
}

function clearChatLog() {
  thinkingStates.clear();
  chatLog.innerHTML = "";
  syncEmptyChatState();
}

function cloneSerializable(value, fallback) {
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return fallback;
  }
}

function serializeThinkingState(state) {
  return {
    expanded: Boolean(state?.expanded),
    buffer: String(state?.buffer || ""),
    timeline: Array.isArray(state?.timeline) ? cloneSerializable(state.timeline, []) : [],
    activeThoughtId: state?.activeThoughtId || null,
    activeToolName: String(state?.activeToolName || ""),
    toolCount: Number(state?.toolCount || 0),
    thoughtCount: Number(state?.thoughtCount || 0),
    startedAt: Number(state?.startedAt || Date.now()),
    mode: String(state?.mode || "done"),
    activityLabel: String(state?.activityLabel || ""),
    lastEventKind: String(state?.lastEventKind || "thinking"),
  };
}

function captureChatUiState() {
  const articles = Array.from(chatLog.querySelectorAll(".message"));
  return articles.map((article) => {
    if (article.classList.contains("thinking")) {
      const thinkingStateId = article.dataset.thinkingStateId;
      const thinkingState = thinkingStateId ? thinkingStates.get(thinkingStateId) : null;
      return {
        role: "thinking",
        ...serializeThinkingState(thinkingState),
      };
    }

    const bodyNode = article.querySelector(".message-body");
    let role = "system";
    if (article.classList.contains("user")) {
      role = "user";
    } else if (article.classList.contains("assistant")) {
      role = "assistant";
    } else if (article.classList.contains("tool")) {
      role = "tool";
    }

    let images = [];
    try {
      images = JSON.parse(article.dataset.images || "[]");
    } catch {
      images = [];
    }

    return {
      role,
      body: String(bodyNode?.dataset?.rawText || ""),
      images,
    };
  });
}

async function persistCurrentChatState({ immediate = false } = {}) {
  if (!currentChatId || chatSaveInFlight) {
    return;
  }

  const save = async () => {
    chatSaveInFlight = true;
    try {
      const uiMessages = captureChatUiState();
      const previousTitle = currentChatId
        ? (chatsCache.find((chat) => chat.id === currentChatId)?.title || "")
        : "";
      const shouldShowAutoTitleSpinner = shouldAttemptAutoTitle(uiMessages);
      if (shouldShowAutoTitleSpinner && currentChatId) {
        pendingAutoTitleChatIds.add(currentChatId);
        renderChatList();
      }
      const response = await fetch(`/api/chats/${encodeURIComponent(currentChatId)}/state`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ui_messages: uiMessages,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.detail || "Не удалось сохранить чат");
      }
      if (shouldShowAutoTitleSpinner && currentChatId) {
        pendingAutoTitleChatIds.delete(currentChatId);
      }
      upsertChatSummary(data.chat);
      if (shouldShowAutoTitleSpinner && data.chat?.id && data.chat?.title && data.chat.title !== previousTitle) {
        markAutoTitleUpdated(data.chat.id);
        renderChatList();
      }
    } catch (error) {
      console.error(error);
    } finally {
      if (currentChatId && pendingAutoTitleChatIds.has(currentChatId)) {
        pendingAutoTitleChatIds.delete(currentChatId);
        renderChatList();
      }
      chatSaveInFlight = false;
    }
  };

  if (immediate) {
    if (chatSaveTimerId) {
      clearTimeout(chatSaveTimerId);
      chatSaveTimerId = null;
    }
    await save();
    return;
  }

  if (chatSaveTimerId) {
    clearTimeout(chatSaveTimerId);
  }
  chatSaveTimerId = window.setTimeout(() => {
    chatSaveTimerId = null;
    save();
  }, 260);
}

function restoreThinkingMessage(snapshot) {
  const node = createMessage("thinking", "");
  const state = node.thinkingStateId ? thinkingStates.get(node.thinkingStateId) : null;
  if (!state) {
    return;
  }

  Object.assign(state, {
    expanded: Boolean(snapshot.expanded),
    buffer: String(snapshot.buffer || ""),
    timeline: Array.isArray(snapshot.timeline) ? cloneSerializable(snapshot.timeline, []) : [],
    activeThoughtId: snapshot.activeThoughtId || null,
    activeToolName: String(snapshot.activeToolName || ""),
    toolCount: Number(snapshot.toolCount || 0),
    thoughtCount: Number(snapshot.thoughtCount || 0),
    startedAt: Number(snapshot.startedAt || Date.now()),
    mode: String(snapshot.mode || "done"),
    activityLabel: String(snapshot.activityLabel || ""),
    lastEventKind: String(snapshot.lastEventKind || "thinking"),
  });

  node.article.dataset.thinkingStateId = node.thinkingStateId;
  state.expanded = true;
  node.thinkingContent.classList.remove("collapsed");
  updateThinkingToggle(state);
  renderThinkingTimeline(state);
}

function restoreChatUiState(messages = []) {
  clearChatLog();
  for (const entry of messages) {
    if (!entry || typeof entry !== "object") {
      continue;
    }

    if (entry.role === "thinking") {
      restoreThinkingMessage(entry);
      continue;
    }

    createMessage(entry.role || "system", entry.body || entry.content || entry.text || "", { images: entry.images || [] });
  }
  syncEmptyChatState();
}

async function openChat(chatId) {
  if (!chatId || isChatBusy()) {
    return;
  }

  const previousChatId = currentChatId;
  if (previousChatId && previousChatId !== chatId) {
    await persistCurrentChatState({ immediate: true });
  }

  const response = await fetch(`/api/chats/${encodeURIComponent(chatId)}`);
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.detail || "Не удалось открыть чат");
  }

  currentChatId = chatId;
  openChatMenuId = null;
  restoreChatUiState(data.chat?.ui_messages || []);
  upsertChatSummary(data.chat);
  updateHeroChatTitle();
  renderChatList();
  await refreshContext();
}

async function renameChat(chatId) {
  const current = chatsCache.find((chat) => chat.id === chatId);
  const nextTitle = window.prompt("Новое название чата", current?.title || "Новый чат");
  if (nextTitle == null) {
    return;
  }

  const response = await fetch(`/api/chats/${encodeURIComponent(chatId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: nextTitle }),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.detail || "Не удалось переименовать чат");
  }

  openChatMenuId = null;
  upsertChatSummary(data.chat);
  renderChatList();
}

async function summarizeChat(chatId) {
  if (isChatBusy()) {
    return;
  }

  const current = chatsCache.find((chat) => chat.id === chatId);
  const ok = window.confirm(
    `Сжать контекст чата "${current?.title || "Новый чат"}"? Последние сообщения и цепочка текущих инструментов сохранятся.`
  );
  if (!ok) {
    return;
  }

  setLiveStatus("Сжимаю контекст через активную модель...", true);
  try {
    const response = await fetch(`/api/chats/${encodeURIComponent(chatId)}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keep_last_n: 12, max_summary_tokens: 2048 }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.detail || "Не удалось сжать контекст");
    }

    openChatMenuId = null;
    upsertChatSummary(data.chat);
    await openChat(chatId);
    await refreshContext();
    setLiveStatus("Контекст сжат", false);
  } catch (error) {
    setLiveStatus(`Ошибка сжатия контекста: ${error.message}`, false);
  }
}

async function deleteChat(chatId) {
  const current = chatsCache.find((chat) => chat.id === chatId);
  const ok = window.confirm(`Удалить чат "${current?.title || "Новый чат"}"?`);
  if (!ok) {
    return;
  }

  if (currentChatId === chatId) {
    currentChatId = null;
  }

  const response = await fetch(`/api/chats/${encodeURIComponent(chatId)}`, {
    method: "DELETE",
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.detail || "Не удалось удалить чат");
  }

  chatsCache = chatsCache.filter((chat) => chat.id !== chatId);
  openChatMenuId = null;

  const fallbackChatId = chatsCache[0]?.id || null;
  if (fallbackChatId) {
    await openChat(fallbackChatId);
  } else {
    clearChatLog();
    updateHeroChatTitle();
    renderChatList();
    await refreshContext();
  }
}

async function createNewChat() {
  if (isChatBusy()) {
    return;
  }

  await persistCurrentChatState({ immediate: true });

  const response = await fetch("/api/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.detail || "Не удалось создать чат");
  }

  currentChatId = data.active_chat_id || data.chat?.id || null;
  clearChatLog();
  upsertChatSummary(data.chat);
  updateHeroChatTitle();
  renderChatList();
  await refreshContext();
  messageInput.focus();
}

const thinkingStates = new Map();
const MODEL_ACTIVITY_IDLE_MS = 900;

function formatElapsedSeconds(startedAt) {
  if (!startedAt) {
    return "0s";
  }
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  return `${elapsedSeconds}s`;
}

window.setInterval(() => {
  for (const state of thinkingStates.values()) {
    if (state && state.mode !== "done") {
      updateThinkingToggle(state);
    }
  }
}, 1000);

function appendMessageImages(node, images = []) {
  const validImages = getValidImageSources(images);
  if (!validImages.length) {
    return;
  }

  const gallery = document.createElement("div");
  gallery.className = "message-attachments";

  for (const [index, src] of validImages.entries()) {
    const link = document.createElement("a");
    link.className = "message-attachment-link";
    link.href = src;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("aria-label", `Открыть изображение ${index + 1}`);

    const image = document.createElement("img");
    image.className = "message-attachment-image";
    image.src = src;
    image.alt = `attachment ${index + 1}`;
    image.loading = "lazy";

    link.appendChild(image);
    gallery.appendChild(link);
  }

  node.appendChild(gallery);
}

function addImageGenPlaceholder(toolCallId, width, height, article) {
  removeImageGenPlaceholder(toolCallId);
  const wrap = document.createElement("div");
  wrap.className = "image-gen-preview-wrap";
  wrap.dataset.imageGenId = toolCallId;

  const preview = document.createElement("div");
  preview.className = "image-gen-preview";
  const w = Math.max(64, Math.min(2048, Number(width) || 512));
  const h = Math.max(64, Math.min(2048, Number(height) || 512));
  preview.style.setProperty("--ig-width", String(w));
  preview.style.setProperty("--ig-height", String(h));

  wrap.appendChild(preview);
  article.appendChild(wrap);
  activeImageGenPlaceholders.set(toolCallId, wrap);
  scrollToBottomIfFollowing();
  return wrap;
}

function resolveImageGenPlaceholder(toolCallId, src) {
  const wrap = activeImageGenPlaceholders.get(toolCallId);
  if (!wrap) {
    return;
  }
  const preview = wrap.querySelector(".image-gen-preview");
  if (!preview) {
    return;
  }
  preview.innerHTML = "";
  const img = document.createElement("img");
  img.src = src;
  img.alt = "generated image";
  preview.appendChild(img);
  activeImageGenPlaceholders.delete(toolCallId);
  scrollToBottomIfFollowing();
}

function updateImageGenPlaceholderProgress(toolCallId, percent) {
  const pct = Math.max(0, Math.min(100, Math.round(percent || 0)));
  let wrap = activeImageGenPlaceholders.get(toolCallId);
  if (!wrap) {
    // Fallback: update the most recent placeholder if id was not provided or mismatched.
    const entries = Array.from(activeImageGenPlaceholders.entries());
    if (!entries.length) {
      return;
    }
    wrap = entries[entries.length - 1][1];
  }
  const preview = wrap.querySelector(".image-gen-preview");
  if (!preview) {
    return;
  }
  let track = preview.querySelector(".image-gen-progress-track");
  let bar = preview.querySelector(".image-gen-progress-bar");
  let label = preview.querySelector(".image-gen-progress-label");
  if (!track) {
    label = document.createElement("div");
    label.className = "image-gen-progress-label";
    label.textContent = "Генерация… ";
    const pctSpan = document.createElement("span");
    pctSpan.className = "image-gen-progress-text";
    pctSpan.textContent = `${pct}%`;
    label.appendChild(pctSpan);

    bar = document.createElement("div");
    bar.className = "image-gen-progress-bar";
    track = document.createElement("div");
    track.className = "image-gen-progress-track";
    track.appendChild(bar);

    preview.appendChild(label);
    preview.appendChild(track);
  }
  bar.style.width = `${pct}%`;
  const pctSpan = label.querySelector(".image-gen-progress-text");
  if (pctSpan) {
    pctSpan.textContent = `${pct}%`;
  }
}

function removeImageGenPlaceholder(toolCallId) {
  const wrap = activeImageGenPlaceholders.get(toolCallId);
  if (wrap) {
    wrap.remove();
    activeImageGenPlaceholders.delete(toolCallId);
  }
}

function clearImageGenPlaceholders() {
  for (const wrap of activeImageGenPlaceholders.values()) {
    wrap.remove();
  }
  activeImageGenPlaceholders.clear();
}

function getValidImageSources(images = []) {
  return images.filter((src) => typeof src === "string" && src.startsWith("data:image/"));
}

function buildImageGalleryHtml(images = [], galleryClassName = "message-attachments") {
  const validImages = getValidImageSources(images);
  if (!validImages.length) {
    return "";
  }

  return `
    <div class="${galleryClassName}">
      ${validImages.map((src, index) => `
        <a
          class="message-attachment-link"
          href="${escapeHtml(src)}"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Открыть изображение ${index + 1}"
        >
          <img
            class="message-attachment-image"
            src="${escapeHtml(src)}"
            alt="attachment ${index + 1}"
            loading="lazy"
          >
        </a>
      `).join("")}
    </div>
  `;
}

function createMessage(role, body = "", options = {}) {
  const fragment = template.content.cloneNode(true);
  const article = fragment.querySelector(".message");
  const roleNode = fragment.querySelector(".message-role");
  const bodyNode = fragment.querySelector(".message-body");
  const actionsNode = fragment.querySelector(".message-actions");
  const images = getValidImageSources(options.images || []);

  article.classList.add(role);
  article.dataset.role = role;
  article.dataset.images = JSON.stringify(images);
  roleNode.textContent =
    role === "user" ? "" :
    role === "assistant" ? "Jarvis" :
    role === "thinking" ? "" :
    role === "tool" ? "" :
    "System";

  if (actionsNode) {
    if (role === "user") {
      const copyBtn = actionsNode.querySelector(".copy-action");
      const editBtn = actionsNode.querySelector(".edit-action");
      if (copyBtn) {
        copyBtn.addEventListener("click", () => copyMessageText(article));
      }
      if (editBtn) {
        editBtn.addEventListener("click", () => editMessageText(article));
      }
    } else {
      actionsNode.style.display = "none";
    }
  }

  if (role === "thinking") {
    bodyNode.innerHTML = '';
    const toggle = document.createElement('div');
    toggle.className = 'thinking-toggle';
    toggle.innerHTML = `
      <span class="thinking-mode-indicator" aria-hidden="true"></span>
      <span class="thinking-toggle-copy">
        <span class="toggle-text">Думаю</span>
        <span class="thinking-activity-text">Модель анализирует запрос…</span>
      </span>
      <span class="timeline-count"></span>
    `;

    const content = document.createElement('div');
    content.className = 'thinking-content';
    const stateId = `thinking-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    bodyNode.appendChild(toggle);
    bodyNode.appendChild(content);

    toggle.setAttribute("role", "button");
    toggle.setAttribute("tabindex", "0");
    const toggleThinking = () => {
      const state = thinkingStates.get(stateId);
      if (!state) return;
      state.expanded = !state.expanded;
      content.classList.toggle("collapsed", !state.expanded);
      updateThinkingToggle(state);
      if (state.expanded) {
        renderThinkingTimeline(state);
      }
    };
    toggle.addEventListener("click", toggleThinking);
    toggle.addEventListener("mousedown", (event) => {
      // Не даём браузеру начать выделение заголовка вместо раскрытия блока.
      event.preventDefault();
    });
    toggle.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleThinking();
      }
    });

    thinkingStates.set(stateId, {
      expanded: true,
      buffer: body || "",
      timeline: [],
      activeThoughtId: null,
      activeToolName: "",
      toolCount: 0,
      thoughtCount: 0,
      startedAt: Date.now(),
      mode: "thinking",
      activityLabel: "Модель анализирует запрос…",
      lastEventKind: "thinking",
      idleTimer: null,
      contentNode: content,
      toggleNode: toggle
    });

    updateThinkingToggle(thinkingStates.get(stateId));

    chatLog.appendChild(fragment);
    article.dataset.thinkingStateId = stateId;
    syncEmptyChatState();
    scrollToBottomIfFollowing();
    return { article, bodyNode, roleNode, thinkingStateId: stateId, thinkingContent: content };
  }

  setMessageBody(bodyNode, body, options);
  chatLog.appendChild(fragment);
  syncEmptyChatState();
  scrollToBottomIfFollowing();
  return { article, bodyNode, roleNode };
}

function addMessage(role, body, options = {}) {
  return createMessage(role, body, options);
}

async function copyMessageText(articleNode) {
  if (!articleNode) return;
  const bodyNode = articleNode.querySelector(".message-body");
  if (!bodyNode) return;
  const text = bodyNode.textContent || "";
  try {
    await navigator.clipboard.writeText(text);
    const copyBtn = articleNode.querySelector(".copy-action span");
    if (copyBtn) {
      const original = copyBtn.textContent;
      copyBtn.textContent = "Скопировано";
      setTimeout(() => {
        copyBtn.textContent = original;
      }, 1200);
    }
  } catch (error) {
    console.error("Failed to copy message:", error);
  }
}

function editMessageText(articleNode) {
  if (!articleNode) return;
  if (isGeneratingResponse) {
    setLiveStatus("Нельзя изменить сообщение во время генерации", false);
    return;
  }
  startMessageEdit(articleNode);
}

function startMessageEdit(articleNode) {
  if (!articleNode) return;
  const bodyNode = articleNode.querySelector(".message-body");
  const actionsNode = articleNode.querySelector(".message-actions");
  if (!bodyNode || bodyNode.querySelector(".message-edit-textarea")) return;

  const originalText = bodyNode.dataset.rawText || bodyNode.textContent || "";
  bodyNode.dataset.editOriginal = originalText;

  const wrapper = document.createElement("div");
  wrapper.className = "message-edit-wrapper";
  wrapper.innerHTML = `
    <textarea class="message-edit-textarea" rows="3">${escapeHtml(originalText)}</textarea>
    <div class="message-edit-actions">
      <button type="button" class="message-edit-btn save">Сохранить</button>
      <button type="button" class="message-edit-btn cancel">Отмена</button>
    </div>
  `;

  bodyNode.innerHTML = "";
  bodyNode.appendChild(wrapper);
  bodyNode.classList.add("is-editing");
  if (actionsNode) actionsNode.style.display = "none";

  const textarea = wrapper.querySelector(".message-edit-textarea");
  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  autoResizeEditTextarea(textarea);
  textarea.addEventListener("input", () => autoResizeEditTextarea(textarea));

  wrapper.querySelector(".save").addEventListener("click", () => saveMessageEdit(articleNode));
  wrapper.querySelector(".cancel").addEventListener("click", () => cancelMessageEdit(articleNode));
  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      saveMessageEdit(articleNode);
    } else if (event.key === "Escape") {
      event.preventDefault();
      cancelMessageEdit(articleNode);
    }
  });
}

function autoResizeEditTextarea(textarea) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 60), 320)}px`;
}

function cancelMessageEdit(articleNode) {
  if (!articleNode) return;
  const bodyNode = articleNode.querySelector(".message-body");
  const actionsNode = articleNode.querySelector(".message-actions");
  if (!bodyNode) return;
  const originalText = bodyNode.dataset.editOriginal || "";
  setMessageBody(bodyNode, originalText);
  delete bodyNode.dataset.editOriginal;
  bodyNode.classList.remove("is-editing");
  if (actionsNode) actionsNode.style.display = "";
}

async function saveMessageEdit(articleNode) {
  if (!articleNode || !currentChatId || isGeneratingResponse) return;
  const bodyNode = articleNode.querySelector(".message-body");
  const actionsNode = articleNode.querySelector(".message-actions");
  if (!bodyNode) return;

  const textarea = bodyNode.querySelector(".message-edit-textarea");
  const newText = (textarea?.value || "").trim();
  if (!newText) return;

  const originalText = bodyNode.dataset.editOriginal || "";
  if (newText === originalText) {
    cancelMessageEdit(articleNode);
    return;
  }

  const messageIndex = Array.from(chatLog.children).indexOf(articleNode);
  if (messageIndex < 0) return;

  let images = [];
  try {
    images = JSON.parse(articleNode.dataset.images || "[]");
  } catch {
    images = [];
  }

  bodyNode.classList.remove("is-editing");
  delete bodyNode.dataset.editOriginal;
  setMessageBody(bodyNode, newText);
  if (actionsNode) actionsNode.style.display = "";

  // Remove everything after the edited message from DOM.
  const children = Array.from(chatLog.children);
  for (let i = messageIndex + 1; i < children.length; i++) {
    const child = children[i];
    const stateId = child.dataset.thinkingStateId;
    if (stateId && thinkingStates.has(stateId)) {
      thinkingStates.delete(stateId);
    }
    child.remove();
  }
  syncEmptyChatState();

  await persistCurrentChatState({ immediate: true });

  try {
    const response = await fetch(`/api/chats/${encodeURIComponent(currentChatId)}/edit-message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_index: messageIndex, new_text: newText }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.detail || "Не удалось изменить сообщение");
    }
    upsertChatSummary(data.chat);
  } catch (error) {
    addMessage("system", `Ошибка изменения сообщения: ${error.message}`);
    setLiveStatus("Ошибка изменения сообщения", false);
    return;
  }

  // Start a new response for the edited message.
  messageInput.value = "";
  autoResizeMessageInput();
  clearPendingImages();
  setGeneratingState(true, 0);
  startLiveStatusTimer("Обработка контекста...");
  await runChatStream(newText, images, { skipUserAppend: true });
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

const CODE_BLOCK_PLACEHOLDER = "§§CODE_BLOCK_";

function extractCodeBlocks(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  const out = [];
  let i = 0;

  while (i < lines.length) {
    const openMatch = lines[i].match(/^(\s*)(`{3,}|~{3,})\s*(.*)$/);
    if (!openMatch) {
      out.push(lines[i]);
      i += 1;
      continue;
    }

    const fence = openMatch[2];
    const info = openMatch[3].trim();
    const lang = info.split(/\s+/)[0] || "";
    const codeLines = [];
    i += 1;

    while (i < lines.length) {
      const closeMatch = lines[i].match(/^(\s*)(`{3,}|~{3,})\s*$/);
      if (
        closeMatch &&
        closeMatch[2].startsWith(fence[0]) &&
        closeMatch[2].length >= fence.length
      ) {
        i += 1;
        break;
      }
      codeLines.push(lines[i]);
      i += 1;
    }

    blocks.push({ lang, code: codeLines.join("\n") });
    out.push(`${CODE_BLOCK_PLACEHOLDER}${blocks.length - 1}§§`);
  }

  return { text: out.join("\n"), blocks };
}

function renderCodeBlock(block) {
  const langClass = block.lang ? ` class="language-${escapeHtml(block.lang)}"` : "";
  return `<pre class="code-block"><code${langClass}>${escapeHtml(block.code)}</code></pre>`;
}

function renderTable(block) {
  const lines = block.trim().split("\n").map((line) => line.trim()).filter(Boolean);
  if (lines.length < 2 || !lines[1].includes("---")) {
    return null;
  }

  const parseRow = (line) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());

  const headers = parseRow(lines[0]);
  const rows = lines.slice(2).map(parseRow);

  const headHtml = headers.map((cell) => `<th>${renderInline(cell)}</th>`).join("");
  const bodyHtml = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${renderInline(cell)}</td>`).join("")}</tr>`)
    .join("");

  return `<table><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
}

function renderTablesInText(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const chunks = [];
  let index = 0;

  while (index < lines.length) {
    const current = lines[index].trim();
    const nextNonEmptyIndex = (() => {
      let probe = index + 1;
      while (probe < lines.length && !lines[probe].trim()) {
        probe += 1;
      }
      return probe;
    })();

    const nextLine = nextNonEmptyIndex < lines.length ? lines[nextNonEmptyIndex].trim() : "";
    const looksLikeTableStart =
      current.startsWith("|") &&
      nextLine.startsWith("|") &&
      nextLine.includes("---");

    if (!looksLikeTableStart) {
      chunks.push(lines[index]);
      index += 1;
      continue;
    }

    const tableLines = [current, nextLine];
    index = nextNonEmptyIndex + 1;

    while (index < lines.length) {
      const candidate = lines[index].trim();
      if (!candidate) {
        index += 1;
        continue;
      }
      if (!candidate.startsWith("|")) {
        break;
      }
      tableLines.push(candidate);
      index += 1;
    }

    const tableHtml = renderTable(tableLines.join("\n"));
    chunks.push(tableHtml || tableLines.join("\n"));
  }

  return chunks.join("\n");
}

function createTokenStore() {
  const tokens = [];
  return {
    stash(html) {
      const marker = `@@JARVIS_TOKEN_${tokens.length}@@`;
      tokens.push(html);
      return marker;
    },
    restore(text) {
      return text.replace(/@@JARVIS_TOKEN_(\d+)@@/g, (_, index) => tokens[Number(index)] ?? "");
    }
  };
}

function applyInlineFormatting(text) {
  let html = text;
  html = html.replace(/\*\*\*([^*]+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__([^_]+?)__/g, "<strong>$1</strong>");
  html = html.replace(/(^|[^\w])\*([^*\n]+?)\*(?=[^\w]|$)/g, "$1<em>$2</em>");
  html = html.replace(/(^|[^\w])_([^_\n]+?)_(?=[^\w]|$)/g, "$1<em>$2</em>");
  return html;
}

function skipMathWhitespace(source, startIndex) {
  let index = startIndex;
  while (index < source.length && /\s/.test(source[index])) {
    index += 1;
  }
  return index;
}

function readBalancedMathToken(source, startIndex) {
  const pairs = {
    "{": "}",
    "(": ")",
    "[": "]",
  };
  const opening = source[startIndex];
  const closing = pairs[opening];
  if (!closing) {
    return null;
  }

  let depth = 0;
  for (let index = startIndex; index < source.length; index += 1) {
    const char = source[index];
    if (char === opening) {
      depth += 1;
    } else if (char === closing) {
      depth -= 1;
      if (depth === 0) {
        return {
          value: source.slice(startIndex, index + 1),
          end: index + 1,
        };
      }
    }
  }

  return null;
}

function readMathToken(source, startIndex) {
  const index = skipMathWhitespace(source, startIndex);
  if (index >= source.length) {
    return null;
  }

  const char = source[index];

  if ("{([".includes(char)) {
    return readBalancedMathToken(source, index);
  }

  if (char === "\\") {
    const commandMatch = source.slice(index).match(/^\\[a-zA-Z]+/);
    if (commandMatch) {
      return {
        value: commandMatch[0],
        end: index + commandMatch[0].length,
      };
    }
  }

  if (char === "^" || char === "_") {
    const nextToken = readMathToken(source, index + 1);
    if (!nextToken) {
      return {
        value: char,
        end: index + 1,
      };
    }
    return {
      value: `${char}${nextToken.value}`,
      end: nextToken.end,
    };
  }

  const tokenMatch = source.slice(index).match(/^[^\s\\{}()[\]^_+=\-*/<>≤≥≠±×·,.;:!?|]+/);
  if (!tokenMatch) {
    return {
      value: char,
      end: index + 1,
    };
  }

  return {
    value: tokenMatch[0],
    end: index + tokenMatch[0].length,
  };
}

function shouldJoinMathTokens(parts, nextValue) {
  if (!parts.length) {
    return false;
  }

  const lastPart = parts[parts.length - 1];
  if (!nextValue) {
    return false;
  }

  if (/^[_^]/.test(nextValue) || /^[{([]/.test(nextValue)) {
    return true;
  }

  if (parts.length === 1 && /^[A-Za-zА-Яа-я]$/.test(lastPart) && /^[0-9]/.test(nextValue)) {
    return true;
  }

  return false;
}

function readMathAtom(source, startIndex) {
  const firstToken = readMathToken(source, startIndex);
  if (!firstToken) {
    return null;
  }

  const parts = [firstToken.value];
  let end = firstToken.end;

  while (true) {
    const nextStart = skipMathWhitespace(source, end);
    const nextToken = readMathToken(source, nextStart);
    if (!nextToken || !shouldJoinMathTokens(parts, nextToken.value)) {
      break;
    }
    parts.push(nextToken.value);
    end = nextToken.end;
  }

  return {
    value: parts.join(" ").trim(),
    end,
  };
}

function normalizeBareFracCommands(source) {
  let normalized = "";
  let index = 0;

  while (index < source.length) {
    if (!source.startsWith("\\frac", index)) {
      normalized += source[index];
      index += 1;
      continue;
    }

    const fracStart = index;
    const afterFrac = skipMathWhitespace(source, index + 5);
    if (afterFrac >= source.length || "{([".includes(source[afterFrac])) {
      normalized += "\\frac";
      index += 5;
      continue;
    }

    const numerator = readMathAtom(source, afterFrac);
    const denominator = numerator ? readMathAtom(source, numerator.end) : null;
    if (!numerator || !denominator) {
      normalized += "\\frac";
      index += 5;
      continue;
    }

    normalized += `\\frac{${numerator.value}}{${denominator.value}}`;
    index = denominator.end;

    if (index <= fracStart) {
      normalized += source[index] || "";
      index += 1;
    }
  }

  return normalized;
}

function normalizeMathSource(source) {
  let normalized = normalizeBareFracCommands(String(source || "").trim());

  const malformedFracPattern = /\\frac\s*[\(\[]\s*(.+?)\s*([XxHh\/])\s*(.+?)\s*[\)\}]/g;
  let previous = "";
  while (normalized !== previous) {
    previous = normalized;
    normalized = normalized.replace(malformedFracPattern, (_, numerator, separator, denominator) => {
      const cleanNumerator = String(numerator || "").trim();
      const cleanDenominator = String(denominator || "").trim();
      if (!cleanNumerator || !cleanDenominator) {
        return `\\frac{${cleanNumerator}}{${cleanDenominator}}`;
      }
      return `\\frac{${cleanNumerator}}{${cleanDenominator}}`;
    });
  }

  normalized = normalized
    .replace(/\\text\s*\{([^{}]*)\}/g, "$1")
    .replace(/\\text\s+([A-Za-zА-Яа-яЁё]+)/g, "$1")
    .replace(/\\text([A-Za-zА-Яа-яЁё]+)/g, "$1")
    .replace(/\\,/g, " ")
    .replace(/\\left/g, "")
    .replace(/\\right/g, "")
    .replace(/([A-Za-zА-Яа-я0-9)\]}])\s*X\s*(?=[A-Za-zА-Яа-я0-9(\\[{])/g, "$1 \\times ")
    .replace(/([A-Za-zА-Яа-я0-9)\]}])\s*H\s*(?=[A-Za-zА-Яа-я0-9(\\[{])/g, "$1 / ")
    .replace(/\s+/g, " ")
    .trim();

  return normalized;
}

function renderMathExpression(source) {
  const greekMap = {
    alpha: "α",
    beta: "β",
    gamma: "γ",
    delta: "δ",
    eta: "η",
    theta: "θ",
    lambda: "λ",
    mu: "μ",
    pi: "π",
    rho: "ρ",
    sigma: "σ",
    tau: "τ",
    phi: "φ",
    psi: "ψ",
    omega: "ω",
  };

  let html = escapeHtml(normalizeMathSource(source));

  const renderFracHtml = (numerator, denominator) => {
    return `<span class="math-frac"><span class="math-frac-top">${renderMathExpression(numerator)}</span><span class="math-frac-bottom">${renderMathExpression(denominator)}</span></span>`;
  };

  let previous = "";
  while (html !== previous) {
    previous = html;
    html = html.replace(/\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}/g, (_, numerator, denominator) => {
      return renderFracHtml(numerator, denominator);
    });
  }

  html = html.replace(/\\([a-zA-Z]+)/g, (match, command) => {
    if (greekMap[command]) {
      return greekMap[command];
    }

    const commandMap = {
      approx: "≈",
      cdot: "·",
      circ: "°",
      times: "×",
      pm: "±",
      neq: "≠",
      leq: "≤",
      geq: "≥",
      to: "→",
      infty: "∞",
    };

    return commandMap[command] ?? match;
  });

  html = html.replace(/\^(\{([^{}]+)\}|([A-Za-zА-Яа-я0-9+\-]))/g, (_, _token, grouped, single) => {
    return `<sup>${grouped ?? single ?? ""}</sup>`;
  });

  html = html.replace(/_(\{([^{}]+)\}|([A-Za-zА-Яа-я0-9+\-]))/g, (_, _token, grouped, single) => {
    return `<sub>${grouped ?? single ?? ""}</sub>`;
  });

  html = html
    .replace(/\\?([=+\-*/<>≤≥≠±×·]+)/g, "$1")
    .replace(/[{}]/g, "");

  return html;
}

function renderInlineMathSegments(text, tokenStore) {
  return text.replace(/\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g, (_, blockMath, inlineMath) => {
    const mathSource = blockMath ?? inlineMath ?? "";
    const className = blockMath != null ? "math-block" : "math-inline";
    return tokenStore.stash(`<span class="${className}">${renderMathExpression(mathSource)}</span>`);
  });
}

function normalizeLooseLatexText(text) {
  return String(text || "")
    .replace(/\\text\s*\{([^{}]*)\}/g, "$1")
    .replace(/\\text\s+([A-Za-zА-Яа-яЁё]+)/g, "$1")
    .replace(/\\text([A-Za-zА-Яа-яЁё]+)/g, "$1")
    .replace(/\\,/g, " ")
    .replace(/\\\^/g, "^")
    .replace(/\^?\\circ(?=\s|[)}\].,;:!?]|[A-Za-zА-Яа-яЁё]|$)/g, "°")
    .replace(/\\([()])/g, "$1");
}

function isStandaloneMathLine(text) {
  const raw = String(text || "").trim();
  if (!raw || raw.length < 3) {
    return false;
  }

  const normalized = normalizeLooseLatexText(raw);
  const longWordCount = (normalized.match(/[A-Za-zА-Яа-яЁё]{4,}/g) || []).length;
  const mathMarkerPattern = /\\[A-Za-z]+|[_^]|=|[0-9]\s*[+\-*/=]|[+\-*/]\s*[0-9(]|≈|≤|≥|≠|±|×|·/;

  if (!mathMarkerPattern.test(raw)) {
    return false;
  }

  if (longWordCount > 2) {
    return false;
  }

  return true;
}

function renderInline(text) {
  const tokenStore = createTokenStore();
  let html = normalizeLooseLatexText(text).replace(/---/g, "—");

  html = renderInlineMathSegments(html, tokenStore);
  html = html.replace(/`([^`]+)`/g, (_, code) => tokenStore.stash(`<code>${escapeHtml(code)}</code>`));
  html = escapeHtml(html);
  html = applyInlineFormatting(html);

  return tokenStore.restore(html);
}

function renderImageTags(text) {
  if (typeof text !== "string") return text;
  return text.replace(/\(image\)\[([^\]]+)\]/g, (_, rawPath) => {
    const path = rawPath.trim();
    const filename = path.split("/").pop() || path.split("\\").pop() || path;
    const safeFilename = encodeURIComponent(filename);
    return `\n<img src="/images/${safeFilename}" class="chat-image" alt="image" loading="lazy">\n`;
  });
}

function renderRichText(text) {
  text = renderImageTags(text);
  const { text: textWithoutCode, blocks: codeBlocks } = extractCodeBlocks(text);
  const normalized = renderTablesInText(textWithoutCode);

  if (normalized.includes("<table>")) {
    return normalized
      .split("\n")
      .map((line) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return "";
        }
        if (trimmed.startsWith("<table>")) {
          return trimmed;
        }
        const codeMatch = trimmed.match(/^§§CODE_BLOCK_(\d+)§§$/);
        if (codeMatch) {
          return renderCodeBlock(codeBlocks[Number(codeMatch[1])]);
        }
        return `<p>${renderInline(trimmed)}</p>`;
      })
      .filter(Boolean)
      .join("");
  }

  const lines = normalized.split("\n");
  let html = "";
  let inList = false;
  let inMathBlock = false;
  let mathBlockLines = [];

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const trimmed = line.trim();

    const codeMatch = trimmed.match(/^§§CODE_BLOCK_(\d+)§§$/);
    if (codeMatch) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      if (inMathBlock) {
        html += `<div class="math-display">${renderMathExpression(mathBlockLines.join(" "))}</div>`;
        mathBlockLines = [];
        inMathBlock = false;
      }
      html += renderCodeBlock(codeBlocks[Number(codeMatch[1])]);
      continue;
    }

    if (trimmed === "$$") {
      if (inList) {
        html += "</ul>";
        inList = false;
      }

      if (inMathBlock) {
        html += `<div class="math-display">${renderMathExpression(mathBlockLines.join(" "))}</div>`;
        mathBlockLines = [];
        inMathBlock = false;
      } else {
        inMathBlock = true;
      }
      continue;
    }

    if (inMathBlock) {
      if (trimmed) {
        mathBlockLines.push(trimmed);
      }
      continue;
    }

    if (!trimmed) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      continue;
    }

    if (trimmed.startsWith("$$") && trimmed.endsWith("$$") && trimmed.length > 4) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += `<div class="math-display">${renderMathExpression(trimmed.slice(2, -2))}</div>`;
      continue;
    }

    if (isStandaloneMathLine(trimmed)) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += `<div class="math-display">${renderMathExpression(trimmed)}</div>`;
      continue;
    }

    const thematicBreakMatch = trimmed.match(/^(?:#{3,}|-{3,}|\*{3,}|_{3,})$/);
    if (thematicBreakMatch) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += "<hr>";
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})(?:\s+|$)(.*)$/);
    if (headingMatch) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }

      const level = Math.min(headingMatch[1].length, 3);
      const headingText = headingMatch[2].trim();
      if (!headingText) {
        html += "<hr>";
        continue;
      }
      html += `<h${level}>${renderInline(headingText)}</h${level}>`;
      continue;
    }

    if (/^[-•·]$/.test(trimmed)) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      continue;
    }

    const bulletMatch = trimmed.match(/^[-•·]\s+(.*)$/);
    if (bulletMatch) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${renderInline(bulletMatch[1])}</li>`;
      continue;
    }

    if (inList) {
      html += "</ul>";
      inList = false;
    }

    html += `<p>${renderInline(trimmed)}</p>`;
  }

  if (inList) {
    html += "</ul>";
  }

  if (inMathBlock && mathBlockLines.length) {
    html += `<div class="math-display">${renderMathExpression(mathBlockLines.join(" "))}</div>`;
  }

  return html || "<p></p>";
}

function animateNewTokens(node) {
  if (!node) {
    return;
  }

  const excludedSelector = "code, pre, table, .math-inline, .math-block, .math-display";
  const collectWalker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
    acceptNode(textNode) {
      const parent = textNode.parentElement;
      if (!parent || parent.closest(excludedSelector)) {
        return NodeFilter.FILTER_REJECT;
      }
      if (!textNode.nodeValue || !textNode.nodeValue.trim()) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  const textNodes = [];
  let currentNode = collectWalker.nextNode();
  while (currentNode) {
    textNodes.push(currentNode);
    currentNode = collectWalker.nextNode();
  }

  let totalTokens = 0;
  for (const textNode of textNodes) {
    const pieces = String(textNode.nodeValue || "").match(/\S+|\s+/g) || [];
    for (const piece of pieces) {
      if (piece.trim()) {
        totalTokens += 1;
      }
    }
  }

  const fadeWindow = 4;
  const fadeStepMs = 80;

  let tokenIndex = 0;
  for (const textNode of textNodes) {
    const parent = textNode.parentNode;
    if (!parent) {
      continue;
    }

    const pieces = String(textNode.nodeValue || "").match(/\S+|\s+/g);
    if (!pieces) {
      continue;
    }

    const fragment = document.createDocumentFragment();
    for (const piece of pieces) {
      if (!piece.trim()) {
        fragment.appendChild(document.createTextNode(piece));
        continue;
      }

      const span = document.createElement("span");
      span.textContent = piece;
      const distanceFromEnd = totalTokens - tokenIndex - 1;
      if (distanceFromEnd >= 0 && distanceFromEnd < fadeWindow) {
        span.className = "stream-token";
        span.style.animationDelay = `${-distanceFromEnd * fadeStepMs}ms`;
      } else {
        span.className = "stream-token-static";
      }
      fragment.appendChild(span);
      tokenIndex += 1;
    }

    parent.replaceChild(fragment, textNode);
  }
}

const STREAM_TOKEN_FADE_MS = 320;

function readTokenBirths(node) {
  if (!node?.dataset?.tokenBirths) {
    return [];
  }

  try {
    const parsed = JSON.parse(node.dataset.tokenBirths);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function animateStreamingTokens(node, previousBirths = []) {
  if (!node) {
    return;
  }

  const excludedSelector = "code, pre, table, .math-inline, .math-block, .math-display";
  const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
    acceptNode(textNode) {
      const parent = textNode.parentElement;
      if (!parent || parent.closest(excludedSelector)) {
        return NodeFilter.FILTER_REJECT;
      }
      if (!textNode.nodeValue || !textNode.nodeValue.trim()) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  const textNodes = [];
  let currentNode = walker.nextNode();
  while (currentNode) {
    textNodes.push(currentNode);
    currentNode = walker.nextNode();
  }

  const now = performance.now();
  const nextBirths = [];
  let tokenIndex = 0;

  for (const textNode of textNodes) {
    const parent = textNode.parentNode;
    if (!parent) {
      continue;
    }

    const pieces = String(textNode.nodeValue || "").match(/\S+|\s+/g);
    if (!pieces) {
      continue;
    }

    const fragment = document.createDocumentFragment();
    for (const piece of pieces) {
      if (!piece.trim()) {
        fragment.appendChild(document.createTextNode(piece));
        continue;
      }

      const birth = Number.isFinite(previousBirths[tokenIndex])
        ? previousBirths[tokenIndex]
        : now;
      nextBirths.push(birth);

      const elapsed = Math.max(0, now - birth);
      const span = document.createElement("span");
      span.textContent = piece;

      if (elapsed < STREAM_TOKEN_FADE_MS) {
        span.className = "stream-token";
        span.style.animationDelay = `-${elapsed}ms`;
      } else {
        span.className = "stream-token-static";
      }

      fragment.appendChild(span);
      tokenIndex += 1;
    }

    parent.replaceChild(fragment, textNode);
  }

  node.dataset.tokenBirths = JSON.stringify(nextBirths);
}

function getComparableBlockHtml(node) {
  if (!node) {
    return "";
  }

  const clone = node.cloneNode(true);
  if (clone.querySelectorAll) {
    for (const animatedToken of clone.querySelectorAll(".stream-token, .stream-token-static")) {
      animatedToken.replaceWith(document.createTextNode(animatedToken.textContent || ""));
    }
  }

  return clone.outerHTML || clone.textContent || "";
}

function patchStreamingRichText(node, text) {
  const renderedHtml = renderRichText(text);
  const temp = document.createElement("div");
  temp.innerHTML = renderedHtml;

  const currentBlocks = Array.from(node.children).filter(
    (child) => !child.classList.contains("message-attachments")
  );
  const incomingBlocks = Array.from(temp.children);

  let sharedPrefix = 0;
  while (
    sharedPrefix < currentBlocks.length &&
    sharedPrefix < incomingBlocks.length &&
    getComparableBlockHtml(currentBlocks[sharedPrefix]) === getComparableBlockHtml(incomingBlocks[sharedPrefix])
  ) {
    sharedPrefix += 1;
  }

  const previousBirths = sharedPrefix < currentBlocks.length
    ? readTokenBirths(currentBlocks[sharedPrefix])
    : [];

  for (let index = currentBlocks.length - 1; index >= sharedPrefix; index -= 1) {
    currentBlocks[index].remove();
  }

  for (let index = sharedPrefix; index < incomingBlocks.length; index += 1) {
    node.appendChild(incomingBlocks[index].cloneNode(true));
  }

  const lastUpdatedBlock = node.lastElementChild;
  if (lastUpdatedBlock && sharedPrefix < incomingBlocks.length) {
    animateStreamingTokens(lastUpdatedBlock, previousBirths);
  }
}

function highlightCodeBlocks(root) {
  if (!window.hljs || !root) {
    return;
  }
  root.querySelectorAll("pre.code-block code").forEach((block) => {
    try {
      hljs.highlightElement(block);
    } catch {
      // Подсветка не критична — оставляем как есть.
    }
  });
}

function setMessageBody(node, text, options = {}) {
  node.dataset.rawText = String(text ?? "");
  if (options.stream) {
    patchStreamingRichText(node, text);
  } else {
    node.innerHTML = renderRichText(text);
    appendMessageImages(node, options.images || []);
    if (options.animate) {
      animateNewTokens(node);
    }
    highlightCodeBlocks(node);
  }
  node.dataset.renderedVisibleText = node.textContent || "";
}

function renderMessageSpeed(articleNode, timings) {
  const existing = articleNode?.querySelector(".message-speed");
  if (existing) {
    existing.remove();
  }
  if (!timings || !timings.predicted_per_second) {
    return;
  }
  const tps = parseFloat(timings.predicted_per_second);
  if (!Number.isFinite(tps) || tps <= 0) {
    return;
  }
  const el = document.createElement("div");
  el.className = "message-speed";
  el.textContent = `⚡ ~${tps.toFixed(1)} tok/s`;

  const promptN = Number(timings.prompt_n) || 0;
  const promptMs = Number(timings.prompt_ms) || 0;
  const promptSpeed = Number(timings.prompt_per_second) || 0;
  const predictedN = Number(timings.predicted_n) || 0;
  const predictedMs = Number(timings.predicted_ms) || 0;
  const lines = [
    `decode: ${predictedN} tok / ${(predictedMs / 1000).toFixed(2)} s = ${tps.toFixed(1)} tok/s`,
  ];
  if (promptN > 0 && promptMs > 0) {
    lines.push(
      `prefill: ${promptN} tok / ${(promptMs / 1000).toFixed(2)} s = ${promptSpeed.toFixed(1)} tok/s`
    );
  }
  if (timings.cache_n) {
    lines.push(`cache: ${timings.cache_n} tok`);
  }
  el.title = lines.join("\n");

  articleNode.appendChild(el);
}

function setServerState(isOnline) {
  serverIsOnline = isOnline;
  heroBadge.textContent = isOnline ? "online" : "offline";
  heroBadge.classList.toggle("online", isOnline);
}

function updateModelDescription(selectEl, descEl) {
  const selected = modelsCache.find((model) => model.key === selectEl.value);
  descEl.textContent = selected ? selected.description : "";
  if (!canUsePastedImages() && pendingImages.length) {
    clearPendingImages();
  }
}

function updateAsrDescription(selectEl, descEl) {
  if (!selectEl || !descEl) {
    return;
  }
  const selected = asrBackendsCache.find((backend) => backend.key === selectEl.value);
  if (!selected) {
    descEl.textContent = "";
    return;
  }
  const suffix = selected.available ? "" : ` Недоступно: ${selected.reason || "нет данных"}`;
  descEl.textContent = `${selected.description || ""}${suffix}`.trim();
}

function formatToolPayload(payload) {
  if (payload == null) {
    return "";
  }
  if (typeof payload === "string") {
    return payload;
  }
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

function createTimelineId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getThinkingEventCount(state) {
  if (!state?.timeline?.length) {
    return 0;
  }
  return state.timeline.filter((entry) => {
    if (entry.type === "tool" || entry.type === "tool_streaming") {
      return true;
    }
    if (entry.type === "thought") {
      return Boolean(String(entry.content || "").trim());
    }
    return false;
  }).length;
}

function finalizeActiveThoughtEntry(state) {
  if (!state?.activeThoughtId) {
    return;
  }

  const entry = state.timeline.find((item) => item.type === "thought" && item.id === state.activeThoughtId);
  if (!entry) {
    state.activeThoughtId = null;
    return;
  }

  if (String(entry.content || "").trim()) {
    entry.completed = true;
  }
  state.activeThoughtId = null;
}

function updateThinkingToggle(state) {
  if (!state?.toggleNode) {
    return;
  }

  const toggle = state.toggleNode;
  const toggleText = toggle.querySelector(".toggle-text");
  const activityNode = toggle.querySelector(".thinking-activity-text");
  const countNode = toggle.querySelector(".timeline-count");

  toggle.classList.toggle("still-thinking", state.mode !== "done");
  toggle.classList.toggle("mode-tool", state.mode === "tool" || state.mode === "tool_writing");

  if (toggleText) {
    if (state.mode === "tool_writing" && state.activeToolName) {
      toggleText.textContent = `Пишет ${state.activeToolName}`;
    } else if (state.mode === "tool_writing") {
      toggleText.textContent = "Пишет инструмент";
    } else if (state.mode === "tool" && state.activeToolName) {
      toggleText.textContent = `Жду ${state.activeToolName}`;
    } else if (state.toolCount > 0) {
      toggleText.textContent = "Мысли и инструменты";
    } else if (state.thoughtCount > 0 || getThinkingEventCount(state) > 0) {
      toggleText.textContent = "Мысли";
    } else if (state.mode === "thinking") {
      toggleText.textContent = "Думаю";
    } else {
      toggleText.textContent = "Мысли";
    }
  }

  if (activityNode) {
    activityNode.textContent = state.activityLabel || "";
    activityNode.classList.toggle("hidden", !state.activityLabel);
  }

  if (countNode) {
    const eventCount = getThinkingEventCount(state);
    if (eventCount > 0) {
      if (state.toolCount > 0) {
        countNode.textContent = `${state.toolCount} инстр. · ${eventCount} событ.`;
      } else {
        countNode.textContent = `${eventCount} событ.`;
      }
    } else if (state.mode !== "done") {
      countNode.textContent = formatElapsedSeconds(state.startedAt);
    } else {
      countNode.textContent = "";
    }
  }
}

function clearThinkingIdleTimer(state) {
  if (state?.idleTimer) {
    clearTimeout(state.idleTimer);
    state.idleTimer = null;
  }
}

function setThinkingActivity(state, label, options = {}) {
  if (!state) {
    return;
  }

  state.activityLabel = label || "";
  if (options.mode) {
    state.mode = options.mode;
  }
  if (options.lastEventKind) {
    state.lastEventKind = options.lastEventKind;
  }
  updateThinkingToggle(state);
}

function scheduleThinkingIdleActivity(state) {
  if (!state || state.mode === "done") {
    return;
  }

  clearThinkingIdleTimer(state);
  state.idleTimer = window.setTimeout(() => {
    if (!state || state.mode === "done") {
      return;
    }

    if (state.mode === "tool_writing" && state.activeToolName) {
      setThinkingActivity(state, `Модель пишет инструмент ${state.activeToolName}…`);
      return;
    }

    if (state.mode === "tool" && state.activeToolName) {
      setThinkingActivity(state, `Инструмент ${state.activeToolName} выполняется…`);
      return;
    }

    if (state.lastEventKind === "content") {
      setThinkingActivity(state, "Модель продолжает писать ответ…");
      return;
    }

    if (state.lastEventKind === "tool_result") {
      setThinkingActivity(state, "Модель анализирует результат инструмента…");
      return;
    }

    if (state.thoughtCount > 0 || String(state.buffer || "").trim()) {
      setThinkingActivity(state, "Модель готовит следующий шаг…");
      return;
    }

    setThinkingActivity(state, "Модель анализирует запрос…");
  }, MODEL_ACTIVITY_IDLE_MS);
}

function ensureThoughtTimelineEntry(state) {
  const existing = state.timeline.find((entry) => entry.id === state.activeThoughtId);
  if (existing) {
    return existing;
  }

  const entry = {
    id: createTimelineId("thought"),
    type: "thought",
    content: state.buffer || "",
    completed: false
  };
  state.activeThoughtId = entry.id;
  state.timeline.push(entry);
  return entry;
}

function syncThoughtTimeline(state, content) {
  state.buffer = content || state.buffer || "";
  state.mode = "thinking";
  state.activeToolName = "";
  state.lastEventKind = "thinking";
  state.activityLabel = "Модель пишет мысли…";

  if (!state.buffer.trim()) {
    updateThinkingToggle(state);
    scheduleThinkingIdleActivity(state);
    return;
  }

  const entry = ensureThoughtTimelineEntry(state);
  entry.content = state.buffer;
  updateThinkingToggle(state);
  scheduleThinkingIdleActivity(state);
  if (state.expanded) {
    const row = state.contentNode?.querySelector(
      `.timeline-row[data-entry-id="${CSS.escape(entry.id)}"]`
    );
    const thoughtBody = row?.querySelector(".timeline-thought-body");
    const preview = row?.querySelector(".timeline-row-preview");
    if (thoughtBody) {
      patchStreamingRichText(thoughtBody, entry.content);
      thoughtBody.dataset.entryId = entry.id;
      if (preview) {
        preview.textContent = makeTimelinePreview(entry.content);
      }
    } else {
      renderThinkingTimeline(state, { animate: true });
    }
  }
}

function completeThoughtTimelineEntry(state) {
  const entry = state.timeline.find((item) => item.type === "thought" && item.id === state.activeThoughtId);
  if (!entry || !String(entry.content || "").trim()) {
    return;
  }

  if (!entry.completed) {
    entry.completed = true;
    state.thoughtCount += 1;
  }
  state.activeThoughtId = null;
  updateThinkingToggle(state);
  if (state.expanded) {
    renderThinkingTimeline(state, { animate: true });
  }
}

function addToolTimelineEntry(state, toolName, args, toolCallId) {
  completeThoughtTimelineEntry(state);
  state.mode = "tool";
  state.activeToolName = toolName || "";
  state.lastEventKind = "tool_call";
  state.activityLabel = toolName
    ? `Модель вызывает ${toolName}…`
    : "Модель вызывает инструмент…";

  const entry = {
    id: toolCallId || createTimelineId(`tool-${toolName || "call"}`),
    type: "tool",
    name: toolName || "tool",
    argsFormatted: formatToolPayload(args || {}),
    resultFormatted: "",
    images: [],
    success: null,
    status: "working"
  };
  state.timeline.push(entry);
  state.toolCount += 1;
  updateThinkingToggle(state);
  scheduleThinkingIdleActivity(state);
  if (state.expanded) {
    renderThinkingTimeline(state);
  }
}

function updateToolTimelineEntry(state, toolCallId, result, success, images = []) {
  const entry = state.timeline.find((item) => item.type === "tool" && item.id === toolCallId);
  if (!entry) {
    return;
  }

  entry.success = Boolean(success);
  entry.status = success ? "success" : "error";
  entry.resultFormatted = formatToolPayload(result);
  entry.images = getValidImageSources(images);
  state.mode = "thinking";
  state.activeToolName = "";
  state.lastEventKind = "tool_result";
  state.activityLabel = entry.success
    ? `Модель анализирует результат ${entry.name}…`
    : `Модель разбирает ошибку ${entry.name}…`;
  updateThinkingToggle(state);
  scheduleThinkingIdleActivity(state);
  if (state.expanded) {
    renderThinkingTimeline(state);
  }
}

function formatStreamingToolArgs(argumentsJson) {
  if (!argumentsJson) {
    return "";
  }
  try {
    const parsed = JSON.parse(argumentsJson);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return String(argumentsJson);
  }
}

function upsertStreamingToolTimelineEntry(state, toolCallId, toolName, argumentsJson, stage) {
  completeThoughtTimelineEntry(state);
  state.mode = "tool_writing";
  state.activeToolName = toolName || "";
  state.lastEventKind = "tool_call";
  state.activityLabel = toolName
    ? `Модель пишет инструмент ${toolName}…`
    : "Модель пишет инструмент…";

  const existing = state.timeline.find((item) => item.type === "tool_streaming" && item.id === toolCallId);
  if (existing) {
    existing.name = toolName || existing.name || "tool";
    existing.argsFormatted = formatStreamingToolArgs(argumentsJson);
    existing.stage = stage;
  } else {
    state.timeline.push({
      id: toolCallId,
      type: "tool_streaming",
      name: toolName || "tool",
      argsFormatted: formatStreamingToolArgs(argumentsJson),
      resultFormatted: "",
      images: [],
      success: null,
      status: "streaming",
      stage: stage,
    });
    state.toolCount += 1;
  }
  updateThinkingToggle(state);
  scheduleThinkingIdleActivity(state);
  if (state.expanded) {
    const row = state.contentNode?.querySelector(
      `.timeline-row[data-entry-id="${CSS.escape(toolCallId)}"]`
    );
    if (existing && row) {
      const nameNode = row.querySelector(".timeline-row-name");
      const argsNode = row.querySelector(".tool-args");
      if (nameNode) nameNode.textContent = existing.name;
      if (argsNode) argsNode.textContent = existing.argsFormatted;
    } else {
      renderThinkingTimeline(state);
    }
  }
}

function finalizeStreamingToolTimelineEntry(state, toolCallId) {
  const entry = state.timeline.find((item) => item.type === "tool_streaming" && item.id === toolCallId);
  if (!entry) {
    return;
  }
  entry.stage = "finish";
  entry.status = "queued";
  state.activityLabel = entry.name
    ? `Модель закончила писать ${entry.name}, жду выполнения…`
    : "Модель закончила писать инструмент, жду выполнения…";
  updateThinkingToggle(state);
  scheduleThinkingIdleActivity(state);
  if (state.expanded) {
    renderThinkingTimeline(state);
  }
}

function cancelStreamingToolTimelineEntry(state, toolCallId, reason = "Поток вызова инструмента прерван") {
  const entry = state.timeline.find((item) => item.id === toolCallId);
  if (!entry) {
    return;
  }

  entry.type = "tool";
  entry.status = "error";
  entry.success = false;
  entry.stage = "cancelled";
  entry.resultFormatted = reason || "Поток вызова инструмента прерван";
  state.mode = "thinking";
  state.activeToolName = "";
  state.lastEventKind = "tool_result";
  state.activityLabel = "Модель продолжает после ошибки инструмента…";
  updateThinkingToggle(state);
  scheduleThinkingIdleActivity(state);
  if (state.expanded) {
    renderThinkingTimeline(state);
  }
}

function promoteStreamingToolToWorking(state, toolCallId, toolName, args) {
  const index = state.timeline.findIndex((item) => item.type === "tool_streaming" && item.id === toolCallId);
  if (index >= 0) {
    const wasExpanded = Boolean(state.timeline[index].expanded);
    state.timeline[index] = {
      id: toolCallId,
      type: "tool",
      name: toolName || state.timeline[index].name || "tool",
      argsFormatted: formatToolPayload(args || {}),
      resultFormatted: "",
      images: [],
      success: null,
      status: "working",
      expanded: wasExpanded,
    };
  } else {
    addToolTimelineEntry(state, toolName, args, toolCallId);
    return;
  }
  state.mode = "tool";
  state.activeToolName = toolName || "";
  state.lastEventKind = "tool_call";
  state.activityLabel = toolName
    ? `Модель вызывает ${toolName}…`
    : "Модель вызывает инструмент…";
  updateThinkingToggle(state);
  scheduleThinkingIdleActivity(state);
  if (state.expanded) {
    renderThinkingTimeline(state);
  }
}

function stripHtmlForPreview(html) {
  const tmp = document.createElement("div");
  tmp.innerHTML = String(html || "").replace(/<br\s*\/?>/gi, " ");
  return (tmp.textContent || tmp.innerText || "").replace(/\s+/g, " ").trim();
}

function formatTimelinePreview(text, maxLen = 90) {
  const plain = stripHtmlForPreview(text);
  if (!plain) return "(пусто)";
  if (plain.length <= maxLen) return plain;
  return plain.slice(0, maxLen).trimEnd() + "…";
}

function getTimelineRowStatus(entry) {
  if (entry.type === "tool_streaming") {
    const isFinished = entry.stage === "finish" || entry.status === "queued";
    return {
      class: isFinished ? "queued" : "streaming",
      text: isFinished ? "готов" : "пишет",
      dotClass: isFinished ? "queued" : "streaming",
    };
  }
  if (entry.type === "tool") {
    const map = {
      working: { class: "working", text: "выполняется", dotClass: "working" },
      success: { class: "success", text: "готово", dotClass: "success" },
      error:   { class: "error",   text: "ошибка",    dotClass: "error" },
    };
    return map[entry.status] || { class: entry.status, text: entry.status, dotClass: entry.status };
  }
  // thought
  return {
    class: "thought",
    text: entry.completed ? "завершена" : "пишет",
    dotClass: entry.completed ? "completed" : "streaming",
  };
}

function makeTimelinePreview(content, maxLength = 90) {
  const text = String(content || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "…";
  return text.length > maxLength ? text.slice(0, maxLength) + "…" : text;
}

function renderThinkingTimeline(state, options = {}) {
  if (!state?.contentNode) {
    return;
  }

  // Remember which rows the user has expanded.
  const expandedIds = new Set();
  if (state.contentNode.querySelectorAll) {
    for (const row of state.contentNode.querySelectorAll(".timeline-row")) {
      if (row.classList.contains("expanded") && row.dataset.entryId) {
        expandedIds.add(row.dataset.entryId);
      }
    }
  }

  // Preserve animation token-birth state across re-renders.
  const previousThoughtBirths = new Map();
  if (state.contentNode.querySelectorAll) {
    for (const thoughtBody of state.contentNode.querySelectorAll(".timeline-thought-body[data-entry-id]")) {
      previousThoughtBirths.set(thoughtBody.dataset.entryId, readTokenBirths(thoughtBody));
    }
  }

  const timelineHtml = state.timeline
    .map((entry) => {
      const status = getTimelineRowStatus(entry);
      const entryId = escapeHtml(entry.id || "");
      const expandState = expandedIds.has(entry.id) ? "expanded" : "collapsed";

      if (entry.type === "tool_streaming") {
        return `
          <div class="timeline-row tool-row streaming ${expandState}" data-entry-id="${entryId}" data-entry-type="tool_streaming">
            <div class="timeline-row-header">
              <span class="timeline-row-chevron" aria-hidden="true">▸</span>
              <span class="timeline-row-dot streaming"></span>
              <span class="timeline-row-name">${escapeHtml(entry.name)}</span>
              <span class="timeline-row-status streaming">пишет…</span>
            </div>
            <div class="timeline-row-body">
              <pre class="tool-block tool-args">${escapeHtml(entry.argsFormatted)}</pre>
            </div>
          </div>
        `;
      }

      if (entry.type === "tool") {
        const resultImagesHtml = buildImageGalleryHtml(entry.images || [], "timeline-tool-images");
        return `
          <div class="timeline-row tool-row ${entry.status} ${expandState}" data-entry-id="${entryId}" data-entry-type="tool">
            <div class="timeline-row-header">
              <span class="timeline-row-chevron" aria-hidden="true">▸</span>
              <span class="timeline-row-dot ${status.dotClass}"></span>
              <span class="timeline-row-name">${escapeHtml(entry.name)}</span>
              <span class="timeline-row-status ${status.class}">${escapeHtml(status.text)}</span>
            </div>
            <div class="timeline-row-body">
              <pre class="tool-block tool-args">${escapeHtml(entry.argsFormatted)}</pre>
              ${entry.resultFormatted ? `
                <pre class="tool-block tool-result ${entry.status}">${escapeHtml(entry.resultFormatted)}</pre>
                ${resultImagesHtml}
              ` : ""}
            </div>
          </div>
        `;
      }

      const thoughtHtml = renderRichText(entry.content || "");
      const thoughtPreview = makeTimelinePreview(entry.content || "");
      return `
        <div class="timeline-row thought-row ${entry.completed ? "completed" : "streaming"} ${expandState}" data-entry-id="${entryId}" data-entry-type="thought">
          <div class="timeline-row-header">
            <span class="timeline-row-chevron" aria-hidden="true">▸</span>
            <span class="timeline-row-dot ${status.dotClass}"></span>
            <span class="timeline-row-name">Мысль</span>
            <span class="timeline-row-preview">${escapeHtml(thoughtPreview)}</span>
          </div>
          <div class="timeline-row-body" data-entry-id="${entryId}">
            <div class="timeline-thought-body">${thoughtHtml || "<p>(пусто)</p>"}</div>
          </div>
        </div>
      `;
    })
    .join("");

  state.contentNode.innerHTML = `<div class="thinking-timeline codex-timeline">${timelineHtml}</div>`;

  // Click header to expand/collapse a single row.
  if (state.contentNode.querySelectorAll) {
    for (const row of state.contentNode.querySelectorAll(".timeline-row")) {
      const header = row.querySelector(".timeline-row-header");
      if (header) {
        header.addEventListener("mousedown", (event) => {
          // Клик по строке должен работать даже во время потокового обновления.
          event.preventDefault();
        });
        header.addEventListener("click", () => {
          row.classList.toggle("collapsed");
          row.classList.toggle("expanded");
        });
      }
    }
  }

  if (options.animate && state.contentNode.querySelectorAll) {
    for (const entry of state.timeline) {
      if (entry.type !== "thought") {
        continue;
      }
      const thoughtBody = state.contentNode.querySelector(`.timeline-row[data-entry-id="${entry.id}"] .timeline-thought-body`);
      if (!thoughtBody) {
        continue;
      }
      thoughtBody.dataset.entryId = entry.id;
      animateStreamingTokens(thoughtBody, previousThoughtBirths.get(entry.id) || []);
    }
  }
}

function finalizeThinkingState(state) {
  clearThinkingIdleTimer(state);
  completeThoughtTimelineEntry(state);
  finalizeActiveThoughtEntry(state);
  state.mode = "done";
  state.activeToolName = "";
  state.activeThoughtId = null;
  state.activityLabel = "";
  updateThinkingToggle(state);
  if (state.expanded) {
    renderThinkingTimeline(state);
  }
}

function shouldSuppressSystemErrorMessage(message) {
  const normalized = String(message || "").trim().toLowerCase();
  return (
    normalized.includes("http ошибка: 400") ||
    normalized.includes("htтр ошибка: 400")
  );
}

function showSetupError(message) {
  if (!presetSetupError) {
    return;
  }
  if (!message) {
    presetSetupError.textContent = "";
    presetSetupError.classList.add("hidden");
    return;
  }
  presetSetupError.textContent = message;
  presetSetupError.classList.remove("hidden");
}

function setLoadingMode(mode) {
  const isSetup = mode === "setup";
  presetSetupPanel?.classList.toggle("hidden", !isSetup);
  presetLaunchPanel?.classList.toggle("hidden", isSetup);
  presetSetupBackBtn?.classList.toggle("hidden", !configCache || configCache.needs_setup);
}

function fillPresetSetupDefaults(status) {
  if (!status) {
    return;
  }
  isMacOs = Boolean(status.is_macos);
  if (presetBackendWrap) {
    presetBackendWrap.classList.toggle("hidden", !isMacOs);
  }
  if (isMacOs) {
    if (presetBackendSelect) {
      presetBackendSelect.value = "mtplx";
    }
    updatePresetFormVisibility();
    if (presetSetupLead) {
      presetSetupLead.innerHTML = `Укажите параметры MTPLX-пресета. Native multi-token speculative decoding на Apple Silicon. Пресет сохранится в <code>jarvis_config.json</code>.`;
    }
    if (presetSetupHint) {
      const configPath = status.config_path || "jarvis_config.json";
      presetSetupHint.textContent = `Конфиг: ${configPath}. MTPLX-модели: huggingface.co/Youssofal`;
    }
  } else {
    updatePresetFormVisibility();
    if (presetLlamaInput && !presetLlamaInput.value && status.detected_llama_server) {
      presetLlamaInput.value = status.detected_llama_server;
    }
    if (presetSetupHint) {
      const configPath = status.config_path || "jarvis_config.json";
      presetSetupHint.textContent = `Конфиг: ${configPath}. llama-server: github.com/ggerganov/llama.cpp/releases`;
    }
  }
}

function updatePresetFormVisibility() {
  const backend = presetBackendSelect?.value || "llama-server";
  const isMlx = backend === "mlx-vlm";
  const isMtplx = backend === "mtplx";
  const isLlama = !isMlx && !isMtplx;

  if (presetLlamaFields) {
    presetLlamaFields.classList.toggle("hidden", !isLlama);
  }
  if (presetLlamaExtraFields) {
    presetLlamaExtraFields.classList.toggle("hidden", !isLlama);
  }
  if (presetMlxFields) {
    presetMlxFields.classList.toggle("hidden", !isMlx);
  }
  if (presetMtplxFields) {
    presetMtplxFields.classList.toggle("hidden", !isMtplx);
  }

  const llamaPort = presetPortInputLlama?.value || "8080";
  const mlxPort = presetPortInput?.value || "8080";
  const mtplxPort = presetMtplxPortInput?.value || "8080";
  if (isMlx && presetPortInput && !presetPortInput.value) {
    presetPortInput.value = llamaPort || mtplxPort;
  } else if (isMtplx && presetMtplxPortInput && !presetMtplxPortInput.value) {
    presetMtplxPortInput.value = llamaPort || mlxPort;
  } else if (isLlama && presetPortInputLlama && !presetPortInputLlama.value) {
    presetPortInputLlama.value = mlxPort || mtplxPort;
  }

  if (presetModelInput) {
    presetModelInput.placeholder = isMlx
      ? "/Users/roma/Models/mlx-community/Qwen2.5-0.5B-Instruct-MLX-8bit"
      : (isMtplx
        ? "/Users/roma/models/Qwen3.6-27B-MTPLX-Optimized-Speed"
        : "C:\\models\\qwen.gguf");
  }
  if (presetLlamaInput) {
    presetLlamaInput.required = isLlama;
  }

  if (isMacOs && presetSetupLead) {
    if (isMlx) {
      presetSetupLead.innerHTML = `Укажите параметры MLX-пресета. На macOS сервер поднимается через <strong>mlx-vlm</strong>. Пресет сохранится в <code>jarvis_config.json</code>.`;
    } else if (isMtplx) {
      presetSetupLead.innerHTML = `Укажите параметры MTPLX-пресета. Native multi-token speculative decoding на Apple Silicon. Пресет сохранится в <code>jarvis_config.json</code>.`;
    } else {
      presetSetupLead.innerHTML = `Укажите параметры пресета <strong>llama-server</strong>. Поля mmproj/MTP ниже — опциональные. Пресет сохранится в <code>jarvis_config.json</code>.`;
    }
  }
  if (presetSetupHint) {
    const configPath = configCache?.config_path || "jarvis_config.json";
    if (isMlx) {
      presetSetupHint.textContent = `Конфиг: ${configPath}. MLX-модели: huggingface.co/mlx-community`;
    } else if (isMtplx) {
      presetSetupHint.textContent = `Конфиг: ${configPath}. MTPLX-модели: huggingface.co/Youssofal`;
    } else {
      presetSetupHint.textContent = `Конфиг: ${configPath}. llama-server: github.com/ggerganov/llama.cpp/releases`;
    }
  }
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes === 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatEta(seconds) {
  const s = Math.max(0, Math.ceil(Number(seconds) || 0));
  if (s < 60) {
    return `${s} с`;
  }
  if (s < 3600) {
    return `${Math.ceil(s / 60)} мин`;
  }
  return `${Math.floor(s / 3600)} ч ${Math.ceil((s % 3600) / 60)} мин`;
}

async function loadLocalModels() {
  if (!presetLocalModelsSelect) {
    return;
  }
  try {
    const response = await fetch("/api/models/local");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.detail || "Не удалось загрузить список локальных моделей");
    }
    localModelsCache = Array.isArray(data.models) ? data.models : [];
    presetLocalModelsSelect.innerHTML = '<option value="">— выберите найденную модель —</option>';
    for (const model of localModelsCache) {
      const option = document.createElement("option");
      option.value = model.path;
      option.textContent = model.name;
      presetLocalModelsSelect.appendChild(option);
    }
    presetLocalModelsSelect.classList.toggle("hidden", localModelsCache.length === 0);
  } catch (error) {
    console.error("Failed to load local models:", error);
    if (presetLocalModelsSelect) {
      presetLocalModelsSelect.classList.add("hidden");
    }
  }
}

function stopDownload() {
  if (downloadEventSource) {
    downloadEventSource.close();
    downloadEventSource = null;
  }
}

async function startModelDownload(repoId) {
  if (!repoId) {
    return;
  }
  stopDownload();
  if (downloadProgressWrap) {
    downloadProgressWrap.classList.remove("hidden");
  }
  if (downloadProgressBar) {
    downloadProgressBar.style.width = "0%";
  }
  if (downloadProgressText) {
    downloadProgressText.textContent = "0%";
  }
  if (downloadProgressMeta) {
    downloadProgressMeta.textContent = "—";
  }
  if (downloadProgressHint) {
    downloadProgressHint.textContent = "Подключение к HuggingFace...";
  }
  if (presetDownloadBtn) {
    presetDownloadBtn.disabled = true;
    presetDownloadBtn.textContent = "Скачивается...";
  }

  try {
    const hfToken = presetHfTokenInput?.value?.trim() || "";
    const response = await fetch("/api/models/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, local_dir: "", hf_token: hfToken }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || "Не удалось начать скачивание");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";

      for (const chunk of chunks) {
        const line = chunk.split("\n").find((entry) => entry.startsWith("data: "));
        if (!line) {
          continue;
        }
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "progress") {
            const percent = Math.max(0, Math.min(100, Number(data.percent) || 0));
            if (downloadProgressBar) {
              downloadProgressBar.style.width = `${percent}%`;
            }
            if (downloadProgressText) {
              downloadProgressText.textContent = `${percent.toFixed(1)}%`;
            }
            const speed = data.speed ? `${formatBytes(data.speed)}/с` : "—";
            const eta = data.eta ? `≈ ${formatEta(data.eta)}` : "—";
            const downloaded = formatBytes(data.downloaded || 0);
            const total = formatBytes(data.total || 0);
            if (downloadProgressMeta) {
              downloadProgressMeta.textContent = `${downloaded} / ${total} · ${speed} · ${eta}`;
            }
            if (downloadProgressHint) {
              downloadProgressHint.textContent = data.message || "Скачивание...";
            }
          } else if (data.type === "done") {
            if (presetModelInput && data.path) {
              presetModelInput.value = data.path;
            }
            if (downloadProgressHint) {
              downloadProgressHint.textContent = `Готово: ${data.path || ""}`;
            }
          } else if (data.type === "error") {
            throw new Error(data.error || "Ошибка скачивания");
          }
        } catch (parseError) {
          console.error("Invalid download progress event:", parseError);
        }
      }
    }
  } catch (error) {
    if (downloadProgressHint) {
      downloadProgressHint.textContent = `Ошибка: ${error.message}`;
    }
  } finally {
    if (presetDownloadBtn) {
      presetDownloadBtn.disabled = false;
      presetDownloadBtn.textContent = "Скачать";
    }
  }
}

function renderPresetCards() {
  if (!presetCardList || !configCache) {
    return;
  }

  presetCardList.innerHTML = "";
  for (const preset of configCache.presets || []) {
    const backendBadge = preset.backend === "mlx-vlm"
      ? '<span class="preset-card-badge">MLX</span>'
      : (preset.backend === "mtplx"
        ? '<span class="preset-card-badge">MTPLX</span>'
        : "");
    const card = document.createElement("div");
    card.className = `preset-card${preset.selected ? " is-selected" : ""}`;
    card.dataset.presetIndex = String(preset.index);
    card.innerHTML = `
      <button type="button" class="preset-card-body" aria-label="Выбрать пресет ${escapeHtml(preset.name)}">
        <div class="preset-card-title">${escapeHtml(preset.name)} ${backendBadge}</div>
        <div class="preset-card-meta">${escapeHtml(preset.description)}</div>
        <div class="preset-card-path">${escapeHtml(preset.model_path)}</div>
      </button>
      <button type="button" class="preset-card-delete" aria-label="Удалить пресет ${escapeHtml(preset.name)}">×</button>
    `;

    const selectBtn = card.querySelector(".preset-card-body");
    selectBtn.addEventListener("click", async () => {
      try {
        await selectPresetByIndex(preset.index);
      } catch (error) {
        loadingStatusText.textContent = `Ошибка выбора пресета: ${error.message}`;
      }
    });

    const deleteBtn = card.querySelector(".preset-card-delete");
    deleteBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      await deletePresetByIndex(preset.index);
    });

    presetCardList.appendChild(card);
  }
}

async function loadConfigStatus() {
  const response = await fetch("/api/config");
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Не удалось загрузить конфигурацию");
  }
  configCache = data;
  return data;
}

async function loadToolsCatalog() {
  try {
    const response = await fetch("/api/tools");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.detail || "Не удалось загрузить список инструментов");
    }
    toolsCache = Array.isArray(data.tools) ? data.tools : [];
  } catch (error) {
    toolsCache = [];
    console.error(error);
  }
}

function renderActivePlan(plan) {
  if (!activePlanPanel || !activePlanToggle || !activePlanTitle || !activePlanList || !activePlanStepCount || !activePlanProgressFill) {
    return;
  }
  if (!plan || !plan.title || !Array.isArray(plan.steps) || !plan.steps.length) {
    activePlanPanel.classList.add("hidden");
    activePlanPanel.classList.add("is-collapsed");
    activePlanToggle.setAttribute("aria-expanded", "false");
    activePlanTitle.textContent = "";
    activePlanList.innerHTML = '<div class="active-plan-empty">Нет активного плана</div>';
    activePlanStepCount.textContent = "0";
    activePlanProgressFill.style.width = "0%";
    return;
  }

  activePlanPanel.classList.remove("hidden");
  activePlanPanel.classList.toggle("is-collapsed", activePlanCollapsed);
  activePlanToggle.setAttribute("aria-expanded", String(!activePlanCollapsed));
  activePlanTitle.textContent = plan.title;
  const doneCount = plan.steps.filter((step) => step.status === "done").length;
  const progress = Math.round((doneCount / plan.steps.length) * 100);
  activePlanStepCount.textContent = `${doneCount}/${plan.steps.length}`;
  activePlanProgressFill.style.width = `${progress}%`;

  const statusSvgs = {
    done: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
    in_progress: `<svg class="plan-spinner" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><path d="M12 18v4"/><path d="M4.93 4.93 7.76 7.76"/><path d="M16.24 16.24 19.07 19.07"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="M4.93 19.07 7.76 16.24"/><path d="M16.24 7.76 19.07 4.93"/></svg>`,
    pending: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/></svg>`,
  };

  activePlanList.innerHTML = plan.steps.map((step, index) => {
    const status = step.status || "pending";
    const markerClass = status === "done" ? "done" : status === "in_progress" ? "in-progress" : "pending";
    const statusLabel = status === "done" ? "Готово" : status === "in_progress" ? "В работе" : "Не сделано";
    const desc = String(step.description || "").trim();
    const markerSvg = statusSvgs[status] || statusSvgs.pending;
    return `
      <div class="active-plan-step ${markerClass}" style="--step-index: ${index}" type="button" aria-expanded="false">
        <span class="active-plan-step-marker" aria-hidden="true">${markerSvg}</span>
        <span class="active-plan-step-text" title="${escapeHtml(statusLabel)}: ${escapeHtml(desc)}">${escapeHtml(desc)}</span>
      </div>
    `;
  }).join("");

  activePlanList.querySelectorAll(".active-plan-step").forEach((stepEl) => {
    stepEl.addEventListener("click", () => {
      const expanded = stepEl.classList.toggle("expanded");
      stepEl.setAttribute("aria-expanded", String(expanded));
    });
  });
}

if (activePlanToggle && activePlanPanel) {
  activePlanToggle.addEventListener("click", () => {
    activePlanCollapsed = !activePlanCollapsed;
    activePlanPanel.classList.toggle("is-collapsed", activePlanCollapsed);
    activePlanToggle.setAttribute("aria-expanded", String(!activePlanCollapsed));
  });
}

async function refreshActivePlan() {
  try {
    const response = await fetch("/api/active-plan");
    const data = await response.json();
    if (response.ok && data.ok) {
      renderActivePlan(data.active_plan);
    }
  } catch (error) {
    console.debug("Active plan unavailable", error);
  }
}

function renderBackgroundTasks(tasks) {
  if (!backgroundTaskList || !backgroundTaskCount) {
    return;
  }
  const activeTasks = tasks.filter((task) => task.status === "running");
  backgroundTaskCount.textContent = String(activeTasks.length);
  if (!tasks.length) {
    backgroundTaskList.innerHTML = '<div class="background-task-empty">Нет запущенных задач</div>';
    return;
  }
  backgroundTaskList.innerHTML = tasks.slice(0, 8).map((task) => {
    const taskId = escapeHtml(task.task_id || "");
    const status = escapeHtml(task.status || "unknown");
    const label = escapeHtml(task.label || task.command || "Background task");
    const command = escapeHtml(task.command || "");
    const stopButton = task.status === "running"
      ? `<button class="background-task-stop" type="button" data-stop-background-task="${taskId}">Остановить</button>`
      : "";
    return `<div class="background-task">
      <div class="background-task-top"><span class="background-task-label" title="${command}">${label}</span>${stopButton}</div>
      <div class="background-task-command" title="${command}">${command}</div>
      <div class="background-task-meta"><span class="background-task-status ${status}">${status}</span><span>PID ${escapeHtml(task.pid)}</span></div>
    </div>`;
  }).join("");
  backgroundTaskList.querySelectorAll("[data-stop-background-task]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const response = await fetch("/api/background-tasks/stop", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: button.dataset.stopBackgroundTask })
        });
        if (!response.ok) {
          throw new Error("Не удалось остановить задачу");
        }
        await refreshBackgroundTasks();
      } catch (error) {
        button.disabled = false;
        console.error(error);
      }
    });
  });
}

async function refreshBackgroundTasks() {
  try {
    const response = await fetch("/api/background-tasks");
    const data = await response.json();
    if (response.ok && data.ok) {
      renderBackgroundTasks(Array.isArray(data.tasks) ? data.tasks : []);
    }
  } catch (error) {
    console.debug("Background task status unavailable", error);
  }
}

function getActivePreset() {
  if (!configCache) {
    return null;
  }
  const activeIndex = configCache.active_preset_index;
  return configCache.presets?.find((preset) => preset.index === activeIndex) || null;
}

function isToolEnabled(preset, tool) {
  const enabledTools = preset?.enabled_tools;
  if (!Array.isArray(enabledTools)) {
    return true;
  }
  return enabledTools.includes(tool.name);
}

function renderToolsList() {
  if (!toolsList || !toolsHint) {
    return;
  }

  const preset = getActivePreset();
  if (!preset) {
    toolsList.innerHTML = "";
    toolsHint.textContent = "Сначала создайте и выберите пресет.";
    return;
  }

  const supportsImages = Boolean(preset.supports_images);
  toolsHint.textContent = supportsImages
    ? `Инструменты для пресета "${escapeHtml(preset.name)}". Мультимодальные инструменты доступны.`
    : `Инструменты для пресета "${escapeHtml(preset.name)}". Мультимодальные инструменты отключены, т.к. в пресете не указан mmproj.`;

  toolsList.innerHTML = toolsCache.map((tool) => {
    const isMultimodal = Boolean(tool.multimodal);
    const disabled = isMultimodal && !supportsImages;
    const checked = disabled ? false : isToolEnabled(preset, tool);
    const checkboxId = `tool-toggle-${tool.name}`;
    return `
      <label class="tool-item ${disabled ? "is-disabled" : ""}" for="${checkboxId}">
        <span class="tool-info">
          <span class="tool-name">${escapeHtml(tool.name)}</span>
          <span class="tool-description">${escapeHtml(tool.description)}</span>
          ${isMultimodal ? '<span class="tool-badge">vision</span>' : ""}
        </span>
        <span class="toggle-switch">
          <input id="${checkboxId}" type="checkbox" data-tool-name="${escapeHtml(tool.name)}" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}>
          <span class="toggle-slider"></span>
        </span>
      </label>
    `;
  }).join("");

  toolsList.querySelectorAll("input[type=checkbox][data-tool-name]").forEach((checkbox) => {
    checkbox.addEventListener("change", async () => {
      await saveEnabledToolsFromUI();
    });
  });
}

async function saveEnabledToolsFromUI() {
  const preset = getActivePreset();
  if (!preset || !toolsList) {
    return;
  }

  const enabledTools = Array.from(toolsList.querySelectorAll("input[type=checkbox][data-tool-name]:checked"))
    .map((checkbox) => checkbox.dataset.toolName)
    .filter(Boolean);

  try {
    const response = await fetch("/api/config/presets/tools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset_index: preset.index, enabled_tools: enabledTools }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось сохранить инструменты");
    }
    configCache = data;
    renderToolsList();
  } catch (error) {
    if (toolsHint) {
      toolsHint.textContent = `Ошибка сохранения инструментов: ${error.message}`;
    }
  }
}

async function selectPresetByIndex(presetIndex) {
  const response = await fetch("/api/config/presets/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preset_index: presetIndex }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Не удалось выбрать пресет");
  }
  configCache = data;
  await loadModels();
  renderPresetCards();
  renderToolsList();
  return data;
}

async function deletePresetByIndex(presetIndex) {
  const preset = configCache?.presets?.find((item) => item.index === presetIndex);
  const name = preset?.name || "этот пресет";
  if (!window.confirm(`Удалить пресет "${name}"?`)) {
    return;
  }

  try {
    const response = await fetch("/api/config/presets/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset_index: presetIndex }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось удалить пресет");
    }

    configCache = data;
    if (configCache.needs_setup) {
      setLoadingMode("setup");
      loadingStatusText.textContent = "Создайте первый пресет, чтобы начать работу.";
      renderPresetCards();
      renderToolsList();
    } else {
      await loadModels();
      renderPresetCards();
      renderToolsList();
      setLoadingMode("launch");
      loadingStatusText.textContent = "Пресет удалён.";
    }
  } catch (error) {
    loadingStatusText.textContent = `Ошибка удаления пресета: ${error.message}`;
  }
}

async function savePresetFromForm(event) {
  event?.preventDefault();
  if (presetSaveInFlight) {
    return;
  }

  showSetupError("");
  presetSaveInFlight = true;
  if (presetSaveBtn) {
    presetSaveBtn.disabled = true;
  }
  loadingStatusText.textContent = "Сохраняю пресет...";

  try {
    const backend = isMacOs ? (presetBackendSelect?.value || "llama-server") : "llama-server";
    const isMlx = backend === "mlx-vlm";
    const isMtplx = backend === "mtplx";
    const isLlama = !isMlx && !isMtplx;

    let port;
    if (isMlx) {
      port = Number(presetPortInput?.value || 8080);
    } else if (isMtplx) {
      port = Number(presetMtplxPortInput?.value || 8080);
    } else {
      port = Number(presetPortInputLlama?.value || 8080);
    }

    const payload = {
      name: presetNameInput?.value?.trim() || "Default",
      backend,
      llama_server_path: isLlama ? (presetLlamaInput?.value?.trim() || "") : "",
      model_path: presetModelInput?.value?.trim() || "",
      mmproj_path: isLlama ? (presetMmprojInput?.value?.trim() || "") : "",
      mtp_path: isLlama ? (presetMtpInput?.value?.trim() || "") : "",
      mtp_enabled: isLlama ? Boolean(presetMtpEnabledInput?.checked) : (isMtplx ? Boolean(presetMtplxMtpEnabledInput?.checked) : false),
      mtp_n_max: isMtplx ? Number(presetMtplxDepthInput?.value || 3) : 0,
      context_size: isLlama ? Number(presetContextInput?.value || 18432) : (isMtplx ? Number(presetMtplxContextInput?.value || 32768) : 0),
      ngl: isLlama ? Number(presetNglInput?.value || 99) : 0,
      port,
      temperature: isMlx ? Number(presetTemperatureInput?.value || 0.7) : (isMtplx ? Number(presetMtplxTemperatureInput?.value || 0.6) : 0.7),
      max_tokens: isMlx ? Number(presetMaxTokensInput?.value || 512) : (isMtplx ? Number(presetMtplxMaxTokensInput?.value || 8192) : 512),
      make_active: true,
    };

    const response = await fetch("/api/config/presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось сохранить пресет");
    }

    configCache = data;
    await loadModels();
    await loadAsrBackends();
    await loadChats();
    await loadToolsCatalog();
    renderPresetCards();
    renderToolsList();
    setLoadingMode("launch");
    loadingStatusText.textContent = "Пресет сохранён. Теперь можно запустить сервер модели.";
  } catch (error) {
    showSetupError(error.message);
    loadingStatusText.textContent = "Проверьте пути и попробуйте снова.";
  } finally {
    presetSaveInFlight = false;
    if (presetSaveBtn) {
      presetSaveBtn.disabled = false;
    }
  }
}

async function loadModels() {
  const response = await fetch("/api/models");
  const data = await response.json();
  modelsCache = data.models || [];

  for (const selectEl of [loadingModelSelect].filter(Boolean)) {
    selectEl.innerHTML = "";
    for (const model of modelsCache) {
      const option = document.createElement("option");
      option.value = model.key;
      option.textContent = model.label;
      option.selected = Boolean(model.selected);
      selectEl.appendChild(option);
    }
  }

  if (loadingModelSelect && loadingModelDescription) {
    updateModelDescription(loadingModelSelect, loadingModelDescription);
  }
}

async function loadAsrBackends() {
  const response = await fetch("/api/asr/backends");
  const data = await response.json();
  asrBackendsCache = data.backends || [];

  for (const selectEl of [loadingAsrSelect, voiceAsrSelect].filter(Boolean)) {
    const previousValue = selectEl.value;
    selectEl.innerHTML = "";
    for (const backend of asrBackendsCache) {
      const option = document.createElement("option");
      option.value = backend.key;
      option.textContent = backend.label;
      option.selected = Boolean(backend.selected);
      option.disabled = !backend.available;
      selectEl.appendChild(option);
    }
    if (previousValue && [...selectEl.options].some((option) => option.value === previousValue)) {
      selectEl.value = previousValue;
    }
  }

  updateAsrDescription(loadingAsrSelect, loadingAsrDescription);
  updateAsrDescription(voiceAsrSelect, voiceAsrDescription);
}

async function refreshHealth() {
  const response = await fetch("/api/health");
  const data = await response.json();
  const isOnline = Boolean(data.llama_server_online);
  setServerState(isOnline);

  if (ttsToggle) {
    const ttsAvailable = Boolean(data.tts_available);
    const ttsEnabled = Boolean(data.tts_enabled);
    const ttsLoaded = Boolean(data.tts_model_loaded);
    const ttsDisableLocked = Boolean(data.tts_disable_locked);
    const ttsDevice = data.tts_device ? ` (${data.tts_device})` : "";
    const disableHint = "Перезапустите для отключения";

    ttsToggle.checked = ttsEnabled && ttsLoaded;
    ttsToggle.disabled = !ttsAvailable || ttsRequestInFlight || (ttsEnabled && ttsDisableLocked);

    if (ttsToggleHint) {
      if (!ttsAvailable) {
        ttsToggleHint.textContent = "Supertonic недоступен в этой сборке";
      } else if (ttsEnabled && ttsDisableLocked) {
        ttsToggleHint.textContent = disableHint;
      } else if (ttsLoaded) {
        ttsToggleHint.textContent = `Модель озвучки загружена${ttsDevice}`;
      } else {
        ttsToggleHint.textContent = "Голосовой вывод Jarvis через Supertonic 3 (CPU)";
      }
    }

    ttsToggle.title = ttsEnabled && ttsDisableLocked ? disableHint : "";
  }

  if (voiceToggle) {
    const voiceAvailable = Boolean(data.voice_available);
    const voiceEnabled = Boolean(data.voice_enabled);
    const wakeWord = data.voice_wake_word || "пятница";
    voiceToggle.checked = voiceEnabled;
    voiceToggle.disabled = !voiceAvailable || voiceRequestInFlight;

    if (voiceToggleHint) {
      const backendLabel = data.voice_backend_label ? ` | STT: ${data.voice_backend_label}` : "";
      voiceToggleHint.textContent = voiceAvailable
        ? (voiceEnabled ? `Слушает wake word: "${wakeWord}"${backendLabel}` : `Wake word: "${wakeWord}"${backendLabel}`)
        : "Vosk или микрофон недоступны";
    }
  }

  if (loadingAsrSelect && data.voice_backend_key) {
    loadingAsrSelect.value = data.voice_backend_key;
    loadingAsrSelect.disabled = asrRequestInFlight;
    if (loadingAsrDescription) {
      updateAsrDescription(loadingAsrSelect, loadingAsrDescription);
    }
  }

  if (voiceAsrSelect && data.voice_backend_key) {
    voiceAsrSelect.value = data.voice_backend_key;
    voiceAsrSelect.disabled = asrRequestInFlight || Boolean(data.voice_enabled);
    if (voiceAsrDescription) {
      updateAsrDescription(voiceAsrSelect, voiceAsrDescription);
    }
  }
  
  // Синхронизируем выбранные модели в обоих селектах, если они существуют
  if (loadingModelSelect && data.selected_model_key) {
    loadingModelSelect.value = data.selected_model_key;
    currentModelKey = data.selected_model_key; // Синхронизируем глобальную переменную
    currentModelSupportsImages = Boolean(data.selected_model_supports_images);
    if (loadingModelDescription) {
      updateModelDescription(loadingModelSelect, loadingModelDescription);
    }
  }
  
  return isOnline;
}

async function refreshContext() {
  if (!contextIndicator) {
    return null;
  }

  try {
    const response = await fetch("/api/context");
    const data = await response.json();
    if (!response.ok || !data.ok || !data.capacity) {
      throw new Error(data.detail || "Context unavailable");
    }
    updateContextIndicator(data);
    return data;
  } catch {
    contextIndicator.style.setProperty("--context-fill", "0%");
    contextIndicatorText.textContent = "ctx";
    contextIndicator.title = "Контекст недоступен";
    contextIndicator.setAttribute("aria-label", "Контекст недоступен");
    return null;
  }
}

async function updateTtsSetting(enabled) {
  if (!ttsToggle || ttsRequestInFlight) {
    return;
  }

  ttsRequestInFlight = true;
  ttsToggle.disabled = true;
  setLiveStatus(
    enabled ? "Загружаю модель озвучки на CPU..." : "Выгружаю модель озвучки из памяти...",
    true
  );

  try {
    const response = await fetch("/api/settings/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Не удалось обновить озвучку");
    }

    const ttsLoaded = Boolean(data.tts_model_loaded);
    const ttsDevice = data.tts_device ? ` (${data.tts_device})` : "";
    ttsToggle.checked = Boolean(data.tts_enabled) && ttsLoaded;

    if (ttsToggleHint) {
      ttsToggleHint.textContent = ttsLoaded
        ? "Перезапустите для отключения"
        : "Голосовой вывод Jarvis через Supertonic 3 (CPU)";
    }

    ttsToggle.title = ttsLoaded ? "Перезапустите для отключения" : "";
    setLiveStatus(enabled ? "Озвучка готова" : "Озвучка отключена", false);
  } catch (error) {
    ttsToggle.checked = !enabled;
    addMessage("system", `Ошибка переключения озвучки: ${error.message}`);
    setLiveStatus("Ошибка настройки озвучки", false);
  } finally {
    ttsRequestInFlight = false;
    await refreshHealth();
  }
}

async function updateAsrSetting(engineKey) {
  if (!engineKey || asrRequestInFlight) {
    return;
  }

  asrRequestInFlight = true;
  if (loadingAsrSelect) {
    loadingAsrSelect.disabled = true;
  }
  if (voiceAsrSelect) {
    voiceAsrSelect.disabled = true;
  }

  setLiveStatus(
    engineKey === "vosk_large"
      ? "Подготавливаю большую модель Vosk для распознавания команд..."
      : "Переключаю распознавание команд на Vosk...",
    true
  );

  try {
    const response = await fetch("/api/settings/asr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ engine_key: engineKey }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось переключить backend распознавания");
    }

    await loadAsrBackends();
    await refreshHealth();
    setLiveStatus(`Распознавание команд: ${data.backend?.label || engineKey}`, false);
  } catch (error) {
    addMessage("system", `Ошибка переключения ASR: ${error.message}`);
    setLiveStatus("Ошибка настройки распознавания команд", false);
    await loadAsrBackends();
    await refreshHealth();
  } finally {
    asrRequestInFlight = false;
  }
}

async function updateVoiceSetting(enabled) {
  if (!voiceToggle || voiceRequestInFlight) {
    return;
  }

  voiceRequestInFlight = true;
  voiceToggle.disabled = true;
  setLiveStatus(
    enabled ? "Включаю голосовую активацию..." : "Выключаю голосовую активацию...",
    true
  );

  try {
    const response = await fetch("/api/settings/voice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Не удалось обновить голосовую активацию");
    }

    voiceToggle.checked = Boolean(data.enabled);
    updateVoiceOverlay(data);
    setLiveStatus(
      enabled ? `Жду фразу "${data.wake_word || "пятница"}"` : "Голосовая активация выключена",
      false
    );
  } catch (error) {
    voiceToggle.checked = !enabled;
    addMessage("system", `Ошибка голосовой активации: ${error.message}`);
    setLiveStatus("Ошибка голосовой активации", false);
  } finally {
    voiceRequestInFlight = false;
    await refreshHealth();
  }
}

async function startModelFromLoadingScreen() {
  if (!loadingStartBtn || !loadingModelSelect) return;

  const selectedModelKey = loadingModelSelect.value;
  const selectedPreset = modelsCache.find((model) => model.key === selectedModelKey);
  currentModelKey = selectedModelKey;

  if (selectedPreset?.config_index !== undefined) {
    await selectPresetByIndex(selectedPreset.config_index);
  }

  if (loadingAsrSelect && loadingAsrSelect.value) {
    await updateAsrSetting(loadingAsrSelect.value);
  }

  loadingStartBtn.disabled = true;
  loadingStatusText.textContent = "Запускаю сервер модели...";

  try {
    const response = await fetch("/api/server/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_key: selectedModelKey }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось запустить модель");
    }

    // Ждём пока сервер действительно поднимется (поллинг)
    loadingStatusText.textContent = "Проверяю сервер...";
    for (let i = 0; i < 300; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      const isOnline = await refreshHealth();
      if (isOnline) {
        break;
      }
    }

    // Переходим в основной интерфейс только если сервер онлайн
    if (serverIsOnline) {
      loadingScreen.classList.add("hidden");
      document.querySelector(".shell")?.classList.remove("hidden");
      await refreshContext();
      setLiveStatus("Готов к работе", false);
      syncEmptyChatState();
    } else {
      loadingStatusText.textContent = "Сервер не отвечает. Попробуйте ещё раз.";
    }
  } catch (error) {
    loadingStatusText.textContent = `Ошибка: ${error.message}`;
  } finally {
    loadingStartBtn.disabled = false;
  }
}

async function readEventStream(response, handlers) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let lastTokenTs = performance.now();

  function logPerf(event, data) {
    try {
      fetch("/api/log_frontend_perf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ts: performance.now(), event, data }),
        keepalive: true,
      }).catch(() => {});
    } catch {
      // ignore
    }
  }

  while (true) {
    const readStart = performance.now();
    const { value, done } = await reader.read();
    const readMs = performance.now() - readStart;
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .find((entry) => entry.startsWith("data: "));

      if (!line) {
        continue;
      }

      const payload = JSON.parse(line.slice(6));
      const handler = handlers[payload.event];
      if (handler) {
        const handlerStart = performance.now();
        handler(payload);
        const handlerMs = performance.now() - handlerStart;
        const now = performance.now();
        const sinceLastToken = now - lastTokenTs;
        if (["content_delta", "thinking_delta"].includes(payload.event)) {
          logPerf("stream_event", {
            event_type: payload.event,
            read_ms: Math.round(readMs * 100) / 100,
            handler_ms: Math.round(handlerMs * 100) / 100,
            since_last_token_ms: Math.round(sinceLastToken * 100) / 100,
            delta_len: (payload.delta || "").length,
            total_len: (payload.content || "").length,
          });
          lastTokenTs = now;
        }
      }
    }
  }
}

async function runChatStream(message, images, options = {}) {
  const { skipUserAppend = false, isVoiceSubmission = false } = options;

  const thinkingNode = createMessage("thinking", "");
  let assistantNode = createMessage("assistant", "");
  let assistantReplyClosed = false;

  function getAssistantText() {
    return assistantNode?.bodyNode?.textContent?.trim() || "";
  }

  function ensureAssistantNode(nextText = "") {
    if (assistantReplyClosed && String(nextText || "").trim()) {
      assistantNode = createMessage("assistant", "");
      assistantReplyClosed = false;
    }
    return assistantNode;
  }

  function ensureAssistantNodeForFinal(finalText = "") {
    // При финальном событии всегда используем текущий узел, если ответ ещё
    // не закрыт. Раньше сравнивали видимый текст с сырым, из-за markdown
    // (жирный, списки и т.п.) это ошибочно создавало второй bubble.
    return ensureAssistantNode(finalText);
  }

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, images, chat_id: currentChatId }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "Ошибка ответа");
    }

    await readEventStream(response, {
      thinking_delta: (payload) => {
        if (thinkingNode.thinkingStateId) {
          const state = thinkingStates.get(thinkingNode.thinkingStateId);
          if (state) {
            syncThoughtTimeline(state, payload.content || state.buffer);
            scrollToBottomIfFollowing();
          }
        } else {
          setMessageBody(thinkingNode.bodyNode, payload.content || "");
          scrollToBottomIfFollowing();
        }
      },
      thinking_block: (payload) => {
        if (thinkingNode.thinkingStateId) {
          const state = thinkingStates.get(thinkingNode.thinkingStateId);
          if (state) {
            syncThoughtTimeline(state, payload.content || state.buffer);
            completeThoughtTimelineEntry(state);
            scrollToBottomIfFollowing();
          }
        } else {
          setMessageBody(thinkingNode.bodyNode, payload.content || "");
          scrollToBottomIfFollowing();
        }
      },
      content_delta: (payload) => {
        stopLiveStatusTimer();
        markGenerationProgressGenerating();
        bumpGenerationProgress(1.5);
        setLiveStatus("Печатает ответ...", true);
        if (thinkingNode.thinkingStateId) {
          const state = thinkingStates.get(thinkingNode.thinkingStateId);
          if (state) {
            setThinkingActivity(state, "Модель пишет ответ…", {
              mode: "thinking",
              lastEventKind: "content",
            });
            scheduleThinkingIdleActivity(state);
          }
        }
        const node = ensureAssistantNode(payload.content || "");
        setMessageBody(node.bodyNode, payload.content || "", { stream: true });
        scrollToBottomIfFollowing();
      },
      prompt_progress: (payload) => {
        if (typeof payload.percent === "number") {
          hasRealPromptProgress = true;
          lastRealPromptProgressAt = Date.now();
          generationProgressPercent = payload.percent;
          generationProgressPhase = "thinking";
          updateGenerationProgressUI();
          setLiveStatus(`Обработка контекста: ${Math.round(payload.percent)}%`, true);
        }
      },
      decode_progress: (payload) => {
        if (typeof payload.percent === "number") {
          hasRealDecodeProgress = true;
          markGenerationProgressGenerating();
          generationProgressPercent = payload.percent;
          updateGenerationProgressUI();
          setLiveStatus(`Генерация ответа: ${Math.round(payload.percent)}%`, true);
          if (payload.percent >= 100) {
            finishGenerationProgress();
          }
        }
      },
      plan_update: (payload) => {
        renderActivePlan(payload.plan);
      },
      image_progress: (payload) => {
        const pct = Math.round(payload.percent || 0);
        setLiveStatus(`Генерация изображения: ${pct}%`, true);
        updateImageGenPlaceholderProgress(payload.tool_call_id, pct);
      },
      tool_call_start: (payload) => {
        stopLiveStatusTimer();
        const toolId = payload.tool_call_id;
        if (!toolId || !thinkingNode.thinkingStateId) {
          return;
        }
        activeStreamingToolCalls.set(toolId, { toolName: payload.tool_name || "", stage: "start" });
        const state = thinkingStates.get(thinkingNode.thinkingStateId);
        if (state) {
          upsertStreamingToolTimelineEntry(state, toolId, payload.tool_name || "", "", "start");
          scrollToBottomIfFollowing();
        }
      },
      tool_call_delta: (payload) => {
        const toolId = payload.tool_call_id;
        if (!toolId || !thinkingNode.thinkingStateId) {
          return;
        }
        activeStreamingToolCalls.set(toolId, { toolName: payload.tool_name || "", stage: "delta" });
        const state = thinkingStates.get(thinkingNode.thinkingStateId);
        if (state) {
          upsertStreamingToolTimelineEntry(state, toolId, payload.tool_name || "", payload.arguments_json || "", "delta");
          scrollToBottomIfFollowing();
        }
      },
      tool_call_finish: (payload) => {
        const toolId = payload.tool_call_id;
        if (!toolId || !thinkingNode.thinkingStateId) {
          return;
        }
        activeStreamingToolCalls.set(toolId, { toolName: payload.tool_name || "", stage: "finish" });
        const state = thinkingStates.get(thinkingNode.thinkingStateId);
        if (state) {
          upsertStreamingToolTimelineEntry(state, toolId, payload.tool_name || "", payload.arguments_json || "", "finish");
          finalizeStreamingToolTimelineEntry(state, toolId);
          scrollToBottomIfFollowing();
        }
      },
      tool_call_cancel: (payload) => {
        const toolId = payload.tool_call_id;
        if (!toolId || !thinkingNode.thinkingStateId) {
          return;
        }
        activeStreamingToolCalls.delete(toolId);
        const state = thinkingStates.get(thinkingNode.thinkingStateId);
        if (state) {
          cancelStreamingToolTimelineEntry(
            state,
            toolId,
            payload.reason || "Поток вызова инструмента прерван сервером"
          );
          scrollToBottomIfFollowing();
        }
      },
      tool_call: (payload) => {
        stopLiveStatusTimer();
        const statusText = payload.tool_name === "generate_image"
          ? "Генерация изображения..."
          : `Вызов инструмента: ${payload.tool_name}`;
        setLiveStatus(statusText, true);
        if (getAssistantText()) {
          assistantReplyClosed = true;
        }
        const iter = payload.iteration ?? 0;
        const toolId = payload.tool_call_id || `tool-${payload.tool_name}-${iter}`;
        if (payload.tool_name === "generate_image") {
          const args = payload.args || {};
          const node = ensureAssistantNode("");
          addImageGenPlaceholder(toolId, args.width, args.height, node.article);
        }
        if (thinkingNode.thinkingStateId) {
          const state = thinkingStates.get(thinkingNode.thinkingStateId);
          if (state) {
            promoteStreamingToolToWorking(state, toolId, payload.tool_name, payload.args || {});
            scrollToBottomIfFollowing();
          }
        }
        activeStreamingToolCalls.delete(toolId);
      },
      tool_result: (payload) => {
        stopLiveStatusTimer();
        setLiveStatus("Ожидаем следующий шаг агента...", true);
        const iter = payload.iteration ?? 0;
        const toolId = payload.tool_call_id || `tool-${payload.tool_name}-${iter}`;
        if (payload.tool_name === "generate_image") {
          if (payload.success) {
            const images = payload.images || [];
            if (images.length) {
              resolveImageGenPlaceholder(toolId, images[0]);
            } else {
              // Backend reported success but no preview image arrived (file missing or unreadable).
              removeImageGenPlaceholder(toolId);
              addMessage("system", `Ошибка генерации изображения: ${payload.error || "файл не создан или недоступен"}`);
            }
          } else {
            removeImageGenPlaceholder(toolId);
            if (payload.error) {
              addMessage("system", `Ошибка генерации изображения: ${payload.error}`);
            }
          }
        }
        if (thinkingNode.thinkingStateId) {
          const state = thinkingStates.get(thinkingNode.thinkingStateId);
          if (state) {
            updateToolTimelineEntry(state, toolId, payload.success ? payload.data : payload.error, payload.success, payload.images || []);
            scrollToBottomIfFollowing();
          }
        }
        activeStreamingToolCalls.delete(toolId);
      },
      status: (payload) => {
        if (payload.message) {
          addMessage("system", payload.message);
        }
      },
      context_compaction_start: (payload) => {
        liveStatus?.classList.add("is-compacting");
        const used = Number(payload.used || 0).toLocaleString("ru-RU");
        const capacity = Number(payload.capacity || 0).toLocaleString("ru-RU");
        setLiveStatus(`Сжимаю контекст: ${used} из ${capacity} токенов…`, true);
        if (liveStatusProgress) {
          liveStatusProgress.classList.remove("hidden");
          liveStatusProgress.classList.add("is-indeterminate");
          liveStatusProgressBar.style.width = "42%";
          liveStatusProgressText.textContent = "…";
        }
      },
      context_compaction_done: async () => {
        liveStatus?.classList.remove("is-compacting");
        if (liveStatusProgress) {
          liveStatusProgress.classList.remove("is-indeterminate");
          liveStatusProgress.classList.add("hidden");
        }
        setLiveStatus("Контекст сжат, продолжаю задачу…", true);
        await refreshContext();
      },
      context_compaction_error: (payload) => {
        liveStatus?.classList.remove("is-compacting");
        if (liveStatusProgress) {
          liveStatusProgress.classList.remove("is-indeterminate");
          liveStatusProgress.classList.add("hidden");
        }
        setLiveStatus(`Сжатие контекста не выполнено: ${payload.message || "неизвестная ошибка"}`, true);
      },
      error: (payload) => {
        stopLiveStatusTimer();
        stopGenerationProgress();
        clearImageGenPlaceholders();
        const errorMessage = payload.message || "Неизвестная ошибка";
        if (!shouldSuppressSystemErrorMessage(errorMessage)) {
          addMessage("system", `Ошибка: ${errorMessage}`);
          setLiveStatus("Ошибка ответа", false);
        }
      },
      final: (payload) => {
        stopLiveStatusTimer();
        finishGenerationProgress();

        // Learn real prefill speed from server timings to improve the next
        // estimated progress bar.
        const timings = payload.timings || {};
        let promptSpeed = null;
        if (typeof timings.prompt_per_second === "number" && timings.prompt_per_second > 0) {
          promptSpeed = timings.prompt_per_second;
        } else if (timings.prompt_n && timings.prompt_ms) {
          promptSpeed = (timings.prompt_n / (timings.prompt_ms / 1000));
        }
        if (promptSpeed && isFinite(promptSpeed)) {
          estimatedPrefillSpeed = Math.max(10, Math.min(2000, promptSpeed));
          localStorage.setItem("jarvis_estimated_prefill_speed", String(estimatedPrefillSpeed));
        }

        const rawFinalContent = payload.content ?? "";
        const finalText = String(rawFinalContent).trim();
        const currentRawText = String(assistantNode?.bodyNode?.dataset?.rawText || "").trim();

        // Если сервер прислал пустой final, но ответ уже отрисован — не затираем
        // накопленный текст и не портим markdown-форматирование.
        if (!finalText && currentRawText) {
          assistantReplyClosed = true;
        } else if (!(assistantReplyClosed && currentRawText === finalText)) {
          const node = ensureAssistantNodeForFinal(rawFinalContent);
          setMessageBody(node.bodyNode, rawFinalContent);
          if (finalText) {
            assistantReplyClosed = true;
          }
        }

        if (thinkingNode.thinkingStateId) {
          const state = thinkingStates.get(thinkingNode.thinkingStateId);
          if (state) {
            finalizeThinkingState(state);
          }
        }

        let hasTimeline = false;
        if (thinkingNode.thinkingStateId) {
          const state = thinkingStates.get(thinkingNode.thinkingStateId);
          if (state && state.timeline.length > 0) {
            hasTimeline = true;
          }
        }

        if (!hasTimeline) {
          if (thinkingNode.thinkingStateId) {
            const state = thinkingStates.get(thinkingNode.thinkingStateId);
            if (!state?.expanded) {
              thinkingStates.delete(thinkingNode.thinkingStateId);
              thinkingNode.article.remove();
            }
          }
        }

        renderMessageSpeed(assistantNode.article, payload.timings);
      },
      user_prompt: (payload) => {
        setUserPromptModalOpen(true, {
          promptId: payload.prompt_id,
          question: payload.question,
        });
      },
      user_prompt_close: () => {
        setUserPromptModalOpen(false);
      },
      user_prompt_keepalive: () => {
        // No-op: the event keeps the SSE stream alive while the modal is open.
      },
      done: () => {
        stopLiveStatusTimer();
        clearImageGenPlaceholders();
        if (!assistantNode.bodyNode.textContent.trim() && !assistantReplyClosed) {
          setMessageBody(assistantNode.bodyNode, "(пустой ответ)");
        }
        if (thinkingNode.thinkingStateId) {
          const state = thinkingStates.get(thinkingNode.thinkingStateId);
          if (state) {
            finalizeThinkingState(state);
          }
        }
        setLiveStatus("Готов к работе", false);
        persistCurrentChatState();
      },
    });
  } catch (error) {
    stopLiveStatusTimer();
    thinkingNode.article.remove();
    assistantNode.article.remove();
    addMessage("system", `Ошибка чата: ${error.message}`);
    setLiveStatus("Ошибка чата", false);
    await persistCurrentChatState({ immediate: true });
  } finally {
    setGeneratingState(false);
    await persistCurrentChatState({ immediate: true });
    refreshContext();
    messageInput.focus();
    autoResizeMessageInput();
    trySubmitQueuedVoiceCommand();
  }
}

async function sendMessage(event) {
  event.preventDefault();
  if (userPromptModal && !userPromptModal.classList.contains("hidden")) {
    return;
  }
  if (isGeneratingResponse) {
    await requestStopGeneration();
    return;
  }

  const message = messageInput.value.trim();
  const images = [...pendingImages];
  const isVoiceSubmission = voiceSubmitRequested && !images.length;
  voiceSubmitRequested = false;
  if (!message && !images.length) {
    return;
  }

  // Проверяем системные разрешения при каждой отправке сообщения
  runSystemCheck();

  if (!currentChatId) {
    await createNewChat();
  }

  // Estimate prompt size so the prefill progress bar can advance even when
  // llama-server does not stream real slot progress.
  const contextData = await refreshContext();
  const estimatedTokens = contextData?.used || 0;

  addMessage("user", message, { images });
  await persistCurrentChatState({ immediate: true });
  messageInput.value = "";
  autoResizeMessageInput();
  clearPendingImages();
  setGeneratingState(true, estimatedTokens);
  startLiveStatusTimer("Обработка контекста...");
  if (isVoiceSubmission) {
    await resetVoiceOverlayState();
  }

  await runChatStream(message, images, { isVoiceSubmission });
}

// Обработчики для загрузочного экрана (если элементы существуют)
if (loadingModelSelect && loadingModelDescription) {
  loadingModelSelect.addEventListener("change", async () => {
    updateModelDescription(loadingModelSelect, loadingModelDescription);
    const selected = modelsCache.find((model) => model.key === loadingModelSelect.value);
    if (selected?.config_index !== undefined) {
      try {
        await selectPresetByIndex(selected.config_index);
      } catch (error) {
        loadingStatusText.textContent = `Ошибка выбора пресета: ${error.message}`;
      }
    }
  });
}
if (loadingAsrSelect && loadingAsrDescription) {
  loadingAsrSelect.addEventListener("change", () => {
    updateAsrDescription(loadingAsrSelect, loadingAsrDescription);
  });
}
if (presetBackendSelect) {
  presetBackendSelect.addEventListener("change", updatePresetFormVisibility);
}
if (presetScanModelsBtn) {
  presetScanModelsBtn.addEventListener("click", () => {
    loadLocalModels();
  });
}
if (presetLocalModelsSelect) {
  presetLocalModelsSelect.addEventListener("change", () => {
    if (presetLocalModelsSelect.value && presetModelInput) {
      presetModelInput.value = presetLocalModelsSelect.value;
    }
  });
}
if (presetDownloadBtn) {
  presetDownloadBtn.addEventListener("click", () => {
    const repoId = presetHfRepoInput?.value?.trim();
    if (!repoId) {
      showSetupError("Введите repo_id модели с HuggingFace.");
      return;
    }
    showSetupError("");
    startModelDownload(repoId);
  });
}
if (loadingStartBtn) {
  loadingStartBtn.addEventListener("click", startModelFromLoadingScreen);
}
if (presetSetupForm) {
  presetSetupForm.addEventListener("submit", savePresetFromForm);
}
if (presetAddBtn) {
  presetAddBtn.addEventListener("click", () => {
    showSetupError("");
    stopDownload();
    if (presetBackendSelect && isMacOs) {
      presetBackendSelect.value = "mlx-vlm";
    } else if (presetBackendSelect) {
      presetBackendSelect.value = "llama-server";
    }
    updatePresetFormVisibility();
    setLoadingMode("setup");
    loadingStatusText.textContent = "Создайте новый пресет.";
  });
}
if (presetSetupBackBtn) {
  presetSetupBackBtn.addEventListener("click", () => {
    showSetupError("");
    stopDownload();
    if (configCache?.needs_setup) {
      loadingStatusText.textContent = "Сначала создайте хотя бы один пресет.";
      return;
    }
    setLoadingMode("launch");
    loadingStatusText.textContent = "Выберите пресет и запустите сервер модели.";
  });
}

chatForm.addEventListener("submit", sendMessage);
if (voiceMessageBtn) {
  voiceMessageBtn.addEventListener("click", toggleVoiceMessageRecording);
}
if (voskDownloadBtn) {
  voskDownloadBtn.addEventListener("click", async () => {
    voskDownloadBtn.disabled = true;
    if (voskDownloadStatus) voskDownloadStatus.textContent = "Скачивание…";
    try {
      const response = await fetch("/api/voice/download_model", { method: "POST" });
      const data = await response.json();
      if (response.ok && data.ok) {
        if (voskDownloadStatus) voskDownloadStatus.textContent = "Готово!";
        if (voskDownloadBanner) voskDownloadBanner.classList.add("hidden");
      } else {
        throw new Error(data.detail || "Ошибка скачивания");
      }
    } catch (err) {
      if (voskDownloadStatus) voskDownloadStatus.textContent = `Ошибка: ${err.message}`;
    } finally {
      voskDownloadBtn.disabled = false;
    }
  });
}
if (newChatBtn) {
  newChatBtn.addEventListener("click", async () => {
    try {
      await createNewChat();
    } catch (error) {
      addMessage("system", `Ошибка создания чата: ${error.message}`);
    }
  });
}
if (chatList) {
  chatList.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-chat-action]");
    if (actionButton) {
      const action = actionButton.getAttribute("data-chat-action");
      const chatId = actionButton.getAttribute("data-chat-id");
      try {
        if (action === "rename") {
          await renameChat(chatId);
        } else if (action === "delete") {
          await deleteChat(chatId);
        } else if (action === "summarize") {
          await summarizeChat(chatId);
        }
      } catch (error) {
        addMessage("system", `Ошибка действия с чатом: ${error.message}`);
      }
      return;
    }

    const menuTrigger = event.target.closest("[data-chat-menu-trigger]");
    if (menuTrigger) {
      const chatId = menuTrigger.getAttribute("data-chat-menu-trigger");
      openChatMenuId = openChatMenuId === chatId ? null : chatId;
      renderChatList();
      return;
    }

    const button = event.target.closest(".chat-list-item[data-chat-id]");
    if (!button) {
      return;
    }

    try {
      await openChat(button.getAttribute("data-chat-id"));
    } catch (error) {
      addMessage("system", `Ошибка открытия чата: ${error.message}`);
    }
  });
}
document.addEventListener("click", (event) => {
  // Timeline rows are always expanded; no toggle behaviour needed.
  if (!event.target.closest(".chat-menu-wrap")) {
    if (openChatMenuId !== null) {
      openChatMenuId = null;
      renderChatList();
    }
  }
});

window.addEventListener("resize", () => {
  requestAnimationFrame(positionOpenChatMenu);
});

if (chatList) {
  chatList.addEventListener("scroll", () => {
    requestAnimationFrame(positionOpenChatMenu);
  }, { passive: true });
}
if (settingsToggleBtn) {
  settingsToggleBtn.addEventListener("click", () => {
    renderToolsList();
    refreshTelegramAccountStatus();
    setSettingsDrawerOpen(true);
  });
}
if (settingsCloseBtn) {
  settingsCloseBtn.addEventListener("click", () => setSettingsDrawerOpen(false));
}
if (settingsBackdrop) {
  settingsBackdrop.addEventListener("click", () => setSettingsDrawerOpen(false));
}
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    setSettingsDrawerOpen(false);
    if (userPromptModal && !userPromptModal.classList.contains("hidden")) {
      cancelUserPrompt();
    }
    if (telegramSetupModal && !telegramSetupModal.classList.contains("hidden")) {
      setTelegramSetupModalOpen(false);
    }
  }
});

// === ask_user modal events ===
if (userPromptSubmitBtn) {
  userPromptSubmitBtn.addEventListener("click", () => {
    const answer = userPromptInput?.value || "";
    submitUserPrompt(answer.trim());
  });
}
if (userPromptCancelBtn) {
  userPromptCancelBtn.addEventListener("click", cancelUserPrompt);
}
if (userPromptInput) {
  userPromptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const answer = userPromptInput.value || "";
      submitUserPrompt(answer.trim());
    }
  });
}

// === Telegram account setup events ===
if (telegramAccountSetupBtn) {
  telegramAccountSetupBtn.addEventListener("click", () => setTelegramSetupModalOpen(true));
}
if (telegramAccountDisconnectBtn) {
  telegramAccountDisconnectBtn.addEventListener("click", async () => {
    if (!window.confirm("Отключить Telegram-аккаунт и удалить сохранённые учётные данные?")) {
      return;
    }
    try {
      const response = await fetch("/api/telegram-account/disconnect", { method: "POST" });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.detail || "Ошибка");
      }
      await refreshTelegramAccountStatus();
    } catch (error) {
      addMessage("system", `Ошибка отключения Telegram: ${error.message}`);
    }
  });
}
if (telegramSetupCloseBtn) {
  telegramSetupCloseBtn.addEventListener("click", () => setTelegramSetupModalOpen(false));
}
if (telegramSetupFinishBtn) {
  telegramSetupFinishBtn.addEventListener("click", () => {
    setTelegramSetupModalOpen(false);
    refreshTelegramAccountStatus();
  });
}

if (telegramSetupForm) {
  telegramSetupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const apiId = Number(telegramApiIdInput?.value);
    const apiHash = telegramApiHashInput?.value?.trim();
    const phone = telegramPhoneInput?.value?.trim();
    if (!apiId || !apiHash || !phone) {
      showTelegramSetupError(telegramSetupError, "Заполните все поля");
      return;
    }
    try {
      const response = await fetch("/api/telegram-account/start-setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_id: apiId, api_hash: apiHash, phone }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.detail || "Ошибка отправки кода");
      }
      showTelegramSetupStep("code");
      setTimeout(() => telegramCodeInput?.focus(), 50);
    } catch (error) {
      showTelegramSetupError(telegramSetupError, error.message);
    }
  });
}

if (telegramCodeForm) {
  telegramCodeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const code = telegramCodeInput?.value?.trim();
    if (!code) {
      showTelegramSetupError(telegramCodeError, "Введите код");
      return;
    }
    try {
      const response = await fetch("/api/telegram-account/confirm-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.detail || "Ошибка подтверждения кода");
      }
      if (data.needs_2fa) {
        showTelegramSetupStep("2fa");
        setTimeout(() => telegram2faPasswordInput?.focus(), 50);
      } else {
        await saveTelegramSession();
      }
    } catch (error) {
      showTelegramSetupError(telegramCodeError, error.message);
    }
  });
}

if (telegram2faForm) {
  telegram2faForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = telegram2faPasswordInput?.value || "";
    try {
      const response = await fetch("/api/telegram-account/confirm-2fa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.detail || "Ошибка подтверждения 2FA");
      }
      await saveTelegramSession();
    } catch (error) {
      showTelegramSetupError(telegram2faError, error.message);
    }
  });
}

async function saveTelegramSession() {
  try {
    const response = await fetch("/api/telegram-account/save-session", { method: "POST" });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.detail || "Ошибка сохранения сессии");
    }
    if (telegramSetupSuccessText) {
      telegramSetupSuccessText.textContent = `Аккаунт подключён: ${data.username ? "@" + data.username : data.phone}`;
    }
    showTelegramSetupStep("success");
  } catch (error) {
    showTelegramSetupError(telegram2faError, error.message);
  }
}
if (ttsToggle) {
  ttsToggle.addEventListener("change", () => updateTtsSetting(ttsToggle.checked));
}
if (voiceToggle) {
  voiceToggle.addEventListener("change", () => updateVoiceSetting(voiceToggle.checked));
}
if (voiceAsrSelect) {
  voiceAsrSelect.addEventListener("change", () => updateAsrSetting(voiceAsrSelect.value));
}

messageInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey) {
    return;
  }
  event.preventDefault();
  if (!isChatBusy()) {
    chatForm.requestSubmit();
  }
});

messageInput.addEventListener("input", autoResizeMessageInput);

setLiveStatus("Готов к работе", false);
syncEmptyChatState();
autoResizeMessageInput();
setSendButtonMode("send");

messageInput.addEventListener("paste", async (event) => {
  const clipboardItems = Array.from(event.clipboardData?.items || []);
  const imageFiles = clipboardItems
    .filter((item) => item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter(Boolean);

  if (!imageFiles.length) {
    return;
  }

  event.preventDefault();

  try {
    await addClipboardImages(imageFiles);
  } catch (error) {
    addMessage("system", `Ошибка вставки изображения: ${error.message}`);
  }
});
if (pastePreview) {
  pastePreview.addEventListener("click", (event) => {
    const button = event.target.closest("[data-image-index]");
    if (!button) {
      return;
    }

    const index = Number(button.getAttribute("data-image-index"));
    if (Number.isNaN(index)) {
      return;
    }

    pendingImages = pendingImages.filter((_, itemIndex) => itemIndex !== index);
    renderPendingImages();
  });
}

// === Инициализация при загрузке ===
async function initApp() {
  try {
    const status = await loadConfigStatus();
    fillPresetSetupDefaults(status);
    updatePresetFormVisibility();
    loadLocalModels();

    if (status.needs_setup) {
      loadingScreen?.classList.remove("hidden");
      document.querySelector(".shell")?.classList.add("hidden");
      setLoadingMode("setup");
      loadingStatusText.textContent = "Создайте первый пресет, чтобы начать работу.";
      return;
    }

    await loadModels();
      await loadAsrBackends();
      await loadChats();
      await pollVoiceState();
      await loadToolsCatalog();
      await refreshBackgroundTasks();
      await refreshActivePlan();
      await refreshTelegramAccountStatus();
    renderPresetCards();
    renderToolsList();
    setLoadingMode("launch");

    // Check for updates from GitHub after the UI is ready.
    checkForUpdate();

    const isOnline = await refreshHealth();

    if (isOnline) {
      loadingScreen?.classList.add("hidden");
      document.querySelector(".shell")?.classList.remove("hidden");
      if (currentChatId) {
        await openChat(currentChatId);
      } else {
        clearChatLog();
      }
      await refreshContext();
      setLiveStatus("Готов к работе", false);
      syncEmptyChatState();
      runSystemCheck();
    } else {
      loadingScreen?.classList.remove("hidden");
      document.querySelector(".shell")?.classList.add("hidden");
      runSystemCheck();
      loadingStatusText.textContent = "Выберите пресет и запустите llama-server.";
    }
  } catch (error) {
    loadingScreen?.classList.remove("hidden");
    document.querySelector(".shell")?.classList.add("hidden");
    setLoadingMode(configCache?.needs_setup ? "setup" : "launch");
    loadingStatusText.textContent = `Ошибка инициализации: ${error.message}`;
  }
}

initStreamFollow();
initApp();
setInterval(pollVoiceState, 250);
setInterval(renderChatList, 60000);
setInterval(refreshBackgroundTasks, 2000);
setInterval(refreshActivePlan, 2000);
