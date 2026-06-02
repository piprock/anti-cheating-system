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
  GAZE_FRAME: "/gaze/frame/"
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
  manualThreshold: GAZE_CONFIG.DEFAULT_THRESHOLD
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
        fileNameSpan.style.backgroundColor = "#3FA72F";
      } else {
        fileNameSpan.textContent = "Оберіть файл для аналізу";
        fileNameSpan.style.backgroundColor = "transparent";
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
    params.set("preview", "1");
  } else {
    params.set("manual", "0");
  }

  return params.toString();
}

/**
 * Update gaze tracking UI with server response
 */
function updateGazeUI(data) {
  // Update gaze status
  if (data.isLooking) {
    updateElementWithStyle("gazeStatus", "Погляд спрямований на екран", "lime");
  } else {
    const statusText = data.face ? "Погляд відведено" : "Обличчя не знайдено";
    updateElementWithStyle("gazeStatus", statusText, "tomato");
  }

  // Update cheat percentage
  updateElement("cheatPct", `Час неуваги: ${data.notLookingPct}%`);

  // Update threshold controls
  const currentThresh = data?.thresh ?? gazeState.manualThreshold;
  if (!gazeState.manualMode) {
    gazeState.manualThreshold = currentThresh;
  }

  updateElement("threshVal", String(currentThresh));

  const threshSlider = document.getElementById("threshSlider");
  if (threshSlider && !threshSlider.matches(":active")) {
    threshSlider.value = String(currentThresh);
  }

  // Update preview images in manual mode
  if (gazeState.manualMode) {
    updatePreviewImage("leftPrev", data.previewLeft);
    updatePreviewImage("rightPrev", data.previewRight);
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
}

/**
 * Enable manual threshold calibration mode
 */
function enableManual() {
  gazeState.manualMode = true;
  
  setElementDisabled("threshSlider", false);
  setElementDisabled("manualOnBtn", true);
  setElementDisabled("manualOffBtn", false);
  
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
  
  const panel = document.getElementById("previewPanel");
  if (panel) {
    panel.classList.remove("active");
  }
}

/**
 * Handle threshold slider change
 */
function onThreshChange(event) {
  gazeState.manualThreshold = parseInt(event.target.value || String(GAZE_CONFIG.DEFAULT_THRESHOLD), 10);
  updateElement("threshVal", String(gazeState.manualThreshold));
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
// Initialization
// ============================================================================

// Initialize file upload handlers when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initFileUploadHandlers);
} else {
  initFileUploadHandlers();
}
