/**
 * Main application script for Avatar AI Exam System
 * 
 * Features:
 * - Voice chat with AI agent (record and analyze)
 * - File upload and analysis
 * - Gaze tracking (eye movement monitoring)
 * 
 * Used on: index.html, exam.html
 */

// ============================================================================
// Constants and State
// ============================================================================

const API_ENDPOINTS = {
  RECORD: "/record/",
  ANALYZE_FILE: "/anylizefile/",
  GAZE_FRAME: "/gaze/frame/",
  GAZE_RESET: "/api/gaze/reset/"
};

const GAZE_CONFIG = {
  VIDEO_WIDTH: 640,
  VIDEO_HEIGHT: 360,
  CAPTURE_INTERVAL: 350,  // ms
  JPEG_QUALITY: 0.6,
  DEFAULT_THRESHOLD: 170
};

let gazeState = {
  sessionId: null,
  timerId: null,
  manualMode: false,
  manualThreshold: GAZE_CONFIG.DEFAULT_THRESHOLD,
  showPreview: true
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Display error message to user
 */
function showError(message) {
  console.error(message);
  alert(message);
}

/**
 * Safe fetch with error handling
 */
async function safeFetch(url, options = {}) {
  try {
    const response = await fetch(url, options);
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    
    return { success: true, data };
  } catch (error) {
    console.error(`Fetch error (${url}):`, error);
    return { success: false, error: error.message };
  }
}

/**
 * Update text content of element if it exists
 */
function updateElement(id, text) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = text;
  }
}

/**
 * Update text and color of element
 */
function updateElementWithStyle(id, text, color) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = text;
    if (color) {
      element.style.color = color;
    }
  }
}

// ============================================================================
// Voice Chat Features
// ============================================================================

/**
 * Record audio on server and get AI response
 */
async function sendRequest() {
  const questionEl = document.getElementById("question");
  const answerEl = document.getElementById("answer");
  
  if (!questionEl || !answerEl) {
    return;
  }

  questionEl.innerText = "Йде запис та відповідь...";

  const result = await safeFetch(API_ENDPOINTS.RECORD, {
    method: "POST"
  });

  if (result.success) {
    answerEl.innerText = `Відповідь: ${result.data.answer}`;
    questionEl.innerText = `Питання: ${result.data.question}`;
  } else {
    questionEl.innerText = "Сталася помилка";
    answerEl.innerText = `Помилка: ${result.error}`;
  }
}

// ============================================================================
// File Upload and Analysis
// ============================================================================

/**
 * Initialize file upload handlers
 */
function initFileUploadHandlers() {
  const fileInput = document.getElementById("fileInput");
  const fileForm = document.getElementById("fileForm");
  const fileNameSpan = document.getElementById("fileName");

  if (fileInput && fileNameSpan) {
    fileInput.addEventListener("change", function() {
      if (this.files.length > 0) {
        fileNameSpan.textContent = this.files[0].name;
        fileNameSpan.style.backgroundColor = "var(--green-subtle)";
        fileNameSpan.style.borderColor = "var(--green)";
        fileNameSpan.style.color = "var(--green)";
        fileNameSpan.style.fontWeight = "bold";
      } else {
        fileNameSpan.textContent = "Оберіть файл для аналізу";
        fileNameSpan.style.backgroundColor = "";
        fileNameSpan.style.borderColor = "";
        fileNameSpan.style.color = "";
        fileNameSpan.style.fontWeight = "";
      }
    });
  }

  if (fileForm) {
    fileForm.addEventListener("submit", handleFileSubmit);
  }
}

/**
 * Handle file form submission
 */
async function handleFileSubmit(event) {
  event.preventDefault();

  const formData = new FormData(event.target);
  const result = await safeFetch(API_ENDPOINTS.ANALYZE_FILE, {
    method: "POST",
    body: formData
  });

  if (result.success) {
    updateElement("answer", `Відповідь: ${result.data.answer}`);
    updateElement("question", `Питання: ${result.data.question}`);
  } else {
    showError(`Помилка аналізу файлу: ${result.error}`);
  }
}

// ============================================================================
// Gaze Tracking
// ============================================================================

/**
 * Initialize and start gaze tracking
 */
async function startGaze() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showError("Камера недоступна в цьому браузері");
    return;
  }

  const video = document.getElementById("cam");
  if (!video) {
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ 
      video: true, 
      audio: false 
    });
    video.srcObject = stream;
    await video.play();
  } catch (error) {
    showError(`Не вдалося отримати доступ до камери: ${error.message}`);
    return;
  }

  // Update UI indicators
  const indicatorDot = document.getElementById("camIndicatorDot");
  if (indicatorDot) indicatorDot.classList.add("active");
  updateElement("camIndicatorText", "Камера активна");

  setElementDisabled("gazeStartBtn", true);
  setElementDisabled("gazeStopBtn", false);
  setElementDisabled("gazeResetBtn", false);

  // Initialize session ID
  if (!gazeState.sessionId) {
    const sidInput = document.getElementById("gazeSid");
    gazeState.sessionId = sidInput && sidInput.value 
      ? sidInput.value 
      : generateSessionId();
  }

  startGazeCapture(video);
}

/**
 * Generate random session ID
 */
function generateSessionId() {
  return Math.random().toString(36).slice(2);
}

/**
 * Start periodic gaze frame capture
 */
function startGazeCapture(video) {
  const canvas = document.createElement("canvas");
  canvas.width = GAZE_CONFIG.VIDEO_WIDTH;
  canvas.height = GAZE_CONFIG.VIDEO_HEIGHT;
  const ctx = canvas.getContext("2d");

  gazeState.timerId = setInterval(async () => {
    ctx.drawImage(video, 0, 0, GAZE_CONFIG.VIDEO_WIDTH, GAZE_CONFIG.VIDEO_HEIGHT);
    
    canvas.toBlob(async (blob) => {
      await processGazeFrame(blob);
    }, "image/jpeg", GAZE_CONFIG.JPEG_QUALITY);
  }, GAZE_CONFIG.CAPTURE_INTERVAL);
}

/**
 * Send frame to server and update UI
 */
async function processGazeFrame(blob) {
  const queryParams = buildGazeQueryParams();
  const url = `${API_ENDPOINTS.GAZE_FRAME}?${queryParams}`;

  const result = await safeFetch(url, {
    method: "POST",
    headers: { "Content-Type": "image/jpeg" },
    body: blob
  });

  if (result.success) {
    updateGazeUI(result.data);
  }
}

/**
 * Build query parameters for gaze request
 */
function buildGazeQueryParams() {
  const params = new URLSearchParams({ 
    sid: gazeState.sessionId 
  });

  if (gazeState.manualMode) {
    params.set("manual", "1");
    params.set("thresh", String(gazeState.manualThreshold));
  } else {
    params.set("manual", "0");
  }

  // Request eye preview images when preview element exists or manual mode
  if (gazeState.manualMode || gazeState.showPreview || document.getElementById("leftPrev")) {
    params.set("preview", "1");
  }

  return params.toString();
}

/**
 * Update gaze tracking UI with server response
 */
function updateGazeUI(data) {
  // Update gaze status with colorblind-friendly classes and SVG icons
  const gazeStatusEl = document.getElementById("gazeStatus");
  if (gazeStatusEl) {
    if (data.isLooking) {
      gazeStatusEl.innerHTML = `<svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Фокус на екрані</span>`;
      gazeStatusEl.classList.remove("gaze-status--not-looking");
      gazeStatusEl.classList.add("gaze-status--looking");
      gazeStatusEl.style.color = "";
    } else {
      const statusText = data.face ? "Погляд відведено" : "Обличчя не знайдено";
      gazeStatusEl.innerHTML = `<svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg> <span>${statusText}</span>`;
      gazeStatusEl.classList.remove("gaze-status--looking");
      gazeStatusEl.classList.add("gaze-status--not-looking");
      gazeStatusEl.style.color = "";
    }
  }

  // Update cheat percentage
  updateElement("cheatPct", `Час неуваги: ${data.notLookingPct}%`);
  updateElement("cheatPctMetric", `${data.notLookingPct}%`);

  // Update proctoring gauge bar (35% penalty threshold)
  const gaugeFill = document.getElementById("proctoringGaugeFill");
  if (gaugeFill) {
    const pct = Math.min(100, Math.max(0, data.notLookingPct || 0));
    gaugeFill.style.width = `${pct}%`;
    gaugeFill.classList.remove("warning", "danger");
    if (pct >= 35) {
      gaugeFill.classList.add("danger");
    } else if (pct >= 20) {
      gaugeFill.classList.add("warning");
    }
  }

  // Update threshold controls
  const currentThresh = data?.thresh ?? gazeState.manualThreshold;
  if (!gazeState.manualMode) {
    gazeState.manualThreshold = currentThresh;
  }

  updateElement("threshVal", String(currentThresh));
  updateElement("threshValMetric", String(currentThresh));

  const threshSlider = document.getElementById("threshSlider");
  if (threshSlider && !threshSlider.matches(":active")) {
    threshSlider.value = String(currentThresh);
  }

  // Update directional metrics
  const DIR_MAP = {
    "center": "По центру",
    "left": "Вліво",
    "right": "Вправо",
    "off": "Поза зоною",
    "unknown": "Не визначено"
  };

  updateElement("leftEyeBadge", DIR_MAP[data.left] || (data.left ?? "—"));
  updateElement("rightEyeBadge", DIR_MAP[data.right] || (data.right ?? "—"));
  updateElement("centerPctVal", data.centerPct != null ? `${data.centerPct}%` : "—");

  // Update face detection badge
  const faceBadge = document.getElementById("faceDetectBadge");
  if (faceBadge) {
    if (data.face) {
      faceBadge.textContent = "Виявлено";
      faceBadge.style.color = "var(--green)";
    } else {
      faceBadge.textContent = "Не знайдено";
      faceBadge.style.color = "var(--red)";
    }
  }

  // Update calibration status
  const calibStatus = data.manual 
    ? "Ручний режим" 
    : (data.calibrated ? "Відкалібровано" : "Калібрування...");
  updateElement("calibStatusMetric", calibStatus);

  // Update elapsed time
  if (data.elapsedSec != null) {
    updateElement("elapsedMetric", `${data.elapsedSec} с`);
  }

  // Fetch or estimate frame metrics if stats are requested
  if (data.sid) {
    fetchSessionStats(data.sid);
  }

  // Update preview images
  updatePreviewImage("leftPrev", data.previewLeft);
  updatePreviewImage("rightPrev", data.previewRight);
}

/**
 * Periodically or optionally fetch comprehensive session stats
 */
let lastStatsFetchTime = 0;
async function fetchSessionStats(sid) {
  const now = Date.now();
  if (now - lastStatsFetchTime < 1500) return;
  lastStatsFetchTime = now;

  try {
    const res = await safeFetch(`/api/gaze/stats/${sid}/`);
    if (res.success && res.data) {
      updateElement("totalFramesMetric", String(res.data.frames ?? 0));
      updateElement("notLookingFramesMetric", String(res.data.not_looking ?? 0));
    }
  } catch (e) {
    console.debug("fetchSessionStats error:", e);
  }
}

/**
 * Update preview image element
 */
function updatePreviewImage(elementId, dataUrl) {
  const imgElement = document.getElementById(elementId);
  if (!imgElement) {
    return;
  }

  if (dataUrl) {
    imgElement.src = dataUrl;
  } else {
    imgElement.removeAttribute("src");
  }
}

/**
 * Stop gaze tracking and release camera
 */
function stopGaze() {
  clearInterval(gazeState.timerId);
  gazeState.timerId = null;

  const video = document.getElementById("cam");
  if (video && video.srcObject) {
    const stream = video.srcObject;
    stream.getTracks().forEach(track => track.stop());
    video.srcObject = null;
  }

  // Update UI indicators
  const indicatorDot = document.getElementById("camIndicatorDot");
  if (indicatorDot) indicatorDot.classList.remove("active");
  updateElement("camIndicatorText", "Камера вимкнена");

  setElementDisabled("gazeStartBtn", false);
  setElementDisabled("gazeStopBtn", true);
}

/**
 * Reset gaze frame counters for session
 */
async function resetGaze() {
  if (!gazeState.sessionId) {
    const sidInput = document.getElementById("gazeSid");
    if (sidInput && sidInput.value) {
      gazeState.sessionId = sidInput.value;
    }
  }

  if (!gazeState.sessionId) return;

  const url = `${API_ENDPOINTS.GAZE_RESET}${gazeState.sessionId}/`;
  const result = await safeFetch(url, { method: "POST" });
  if (result.success) {
    updateElement("cheatPct", "Час неуваги: 0%");
    updateElement("cheatPctMetric", "0%");
    updateElement("totalFramesMetric", "0");
    updateElement("notLookingFramesMetric", "0");
    updateElement("elapsedMetric", "0 с");
    
    const gaugeFill = document.getElementById("proctoringGaugeFill");
    if (gaugeFill) {
      gaugeFill.style.width = "0%";
      gaugeFill.classList.remove("warning", "danger");
    }
  }
}

/**
 * Enable manual threshold calibration mode
 */
function enableManual() {
  gazeState.manualMode = true;
  
  setElementDisabled("threshSlider", false);
  setElementDisabled("manualOnBtn", true);
  setElementDisabled("manualOffBtn", false);
  
  updateElement("calibModeBadge", "Ручний поріг");
  updateElement("calibStatusMetric", "Ручний режим");

  const panel = document.getElementById("previewPanel");
  if (panel) {
    panel.classList.add("active");
  }
}

/**
 * Disable manual threshold calibration mode
 */
function disableManual() {
  gazeState.manualMode = false;
  
  setElementDisabled("threshSlider", true);
  setElementDisabled("manualOnBtn", false);
  setElementDisabled("manualOffBtn", true);
  
  updateElement("calibModeBadge", "Автоматичний");

  const panel = document.getElementById("previewPanel");
  if (panel && !gazeState.showPreview) {
    panel.classList.remove("active");
  }
}

/**
 * Set preset threshold value
 */
function setThresholdPreset(val) {
  enableManual();
  gazeState.manualThreshold = val;
  updateElement("threshVal", String(val));
  updateElement("threshValMetric", String(val));
  const slider = document.getElementById("threshSlider");
  if (slider) {
    slider.value = String(val);
  }
}

/**
 * Handle threshold slider change
 */
function onThreshChange(event) {
  gazeState.manualThreshold = parseInt(event.target.value || String(GAZE_CONFIG.DEFAULT_THRESHOLD), 10);
  updateElement("threshVal", String(gazeState.manualThreshold));
  updateElement("threshValMetric", String(gazeState.manualThreshold));
}

/**
 * Set disabled state of element
 */
function setElementDisabled(id, disabled) {
  const element = document.getElementById(id);
  if (element) {
    element.disabled = disabled;
  }
}

// ============================================================================
// Responsive Burger Menu
// ============================================================================

/**
 * Initialize responsive burger menu navigation
 */
function initBurgerMenu() {
  const burgerBtn = document.getElementById("burgerBtn");
  const nav = document.getElementById("headerNav");
  if (!burgerBtn || !nav) return;

  burgerBtn.addEventListener("click", function(e) {
    e.stopPropagation();
    const isOpen = nav.classList.toggle("open");
    burgerBtn.classList.toggle("active", isOpen);
    burgerBtn.setAttribute("aria-expanded", String(isOpen));
  });

  // Close menu when clicking outside
  document.addEventListener("click", function(e) {
    if (nav.classList.contains("open") && !nav.contains(e.target) && !burgerBtn.contains(e.target)) {
      nav.classList.remove("open");
      burgerBtn.classList.remove("active");
      burgerBtn.setAttribute("aria-expanded", "false");
    }
  });

  // Close menu on Escape key
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && nav.classList.contains("open")) {
      nav.classList.remove("open");
      burgerBtn.classList.remove("active");
      burgerBtn.setAttribute("aria-expanded", "false");
      burgerBtn.focus();
    }
  });

  // Close menu when clicking on any navigation link
  nav.querySelectorAll("a").forEach(function(link) {
    link.addEventListener("click", function() {
      nav.classList.remove("open");
      burgerBtn.classList.remove("active");
      burgerBtn.setAttribute("aria-expanded", "false");
    });
  });
}

// ============================================================================
// Navigation Dropdown
// ============================================================================

/**
 * Initialize navigation dropdown menu (e.g. "Про нас")
 */
function initNavDropdown() {
  const dropdown = document.querySelector(".nav-dropdown");
  if (!dropdown) return;

  const btn = dropdown.querySelector(".nav-dropdown__btn");
  const menu = dropdown.querySelector(".nav-dropdown__menu");
  if (!btn || !menu) return;

  function setDropdownState(open) {
    dropdown.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", String(open));
  }

  function toggleDropdown() {
    const isCurrentlyOpen = dropdown.classList.contains("is-open");
    setDropdownState(!isCurrentlyOpen);
  }

  btn.addEventListener("click", function(e) {
    e.stopPropagation();
    toggleDropdown();
  });

  // Keyboard navigation on button
  btn.addEventListener("keydown", function(e) {
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setDropdownState(true);
      const firstLink = menu.querySelector("a");
      if (firstLink) firstLink.focus();
    } else if (e.key === "Escape") {
      setDropdownState(false);
      btn.focus();
    }
  });

  // Keyboard navigation inside dropdown menu
  menu.addEventListener("keydown", function(e) {
    const links = Array.from(menu.querySelectorAll("a"));
    const currentIndex = links.indexOf(document.activeElement);

    if (e.key === "Escape") {
      e.preventDefault();
      setDropdownState(false);
      btn.focus();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const nextIndex = (currentIndex + 1) % links.length;
      links[nextIndex].focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const prevIndex = (currentIndex - 1 + links.length) % links.length;
      links[prevIndex].focus();
    }
  });

  // Close when clicking outside
  document.addEventListener("click", function(e) {
    if (dropdown.classList.contains("is-open") && !dropdown.contains(e.target)) {
      setDropdownState(false);
    }
  });

  // Close on Escape key globally if open
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && dropdown.classList.contains("is-open")) {
      setDropdownState(false);
      btn.focus();
    }
  });
}

// ============================================================================
// Initialization
// ============================================================================

// Initialize handlers when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", function() {
    initFileUploadHandlers();
    initBurgerMenu();
    initNavDropdown();
  });
} else {
  initFileUploadHandlers();
  initBurgerMenu();
  initNavDropdown();
}
