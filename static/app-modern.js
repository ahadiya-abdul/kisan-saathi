const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
}[character]));

let token = null; // in-memory marker only; session credential is an HttpOnly cookie
let authMode = "login";
let cameraStream;
let toastTimer;

function setAuthenticated(accessToken) {
  token = accessToken ? "cookie-session" : null;
  $("auth").hidden = Boolean(token);
  $("app").hidden = !token;
  $("logout").hidden = !token;
  if (token) loadConversationHistory();
}

function notify(message, kind = "success") {
  const toast = $("toast");
  toast.textContent = message;
  toast.className = `toast visible ${kind}`;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 3200);
}

async function readResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "The request failed. Please try again.");
  return data;
}

async function post(url, body) {
  return readResponse(await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token && token !== "cookie-session" ? { Authorization: `Bearer ${token}` } : {})
    },
    credentials: "same-origin",
    body: JSON.stringify(body)
  }));
}

function showResult(id, message, kind = "success") {
  const panel = $(id);
  panel.classList.remove("empty-result", "result-error", "result-success", "result-loading");
  panel.classList.toggle("result-risk-high", typeof message === "object" && message?.title?.includes("HIGH"));
  panel.classList.toggle("result-risk-watch", typeof message === "object" && message?.title?.includes("WATCH"));
  panel.classList.add(kind === "error" ? "result-error" : kind === "loading" ? "result-loading" : "result-success");
  panel.setAttribute("aria-busy", kind === "loading" ? "true" : "false");
  if (typeof message === "object" && message !== null) {
    panel.innerHTML = `<strong class="result-title">${escapeHtml(message.title)}</strong>
      <p class="result-detail">${escapeHtml(message.detail)}</p>
      ${message.items?.length ? `<ul class="result-items">${message.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
      ${message.note ? `<span class="result-note">${escapeHtml(message.note)}</span>` : ""}`;
  } else {
    panel.textContent = message;
  }
}

async function runTool(buttonId, resultId, action, render) {
  const button = $(buttonId);
  const originalContent = button.innerHTML;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.innerHTML = '<span class="button-spinner" aria-hidden="true"></span> Working…';
  showResult(resultId, "Working on it…", "loading");
  try {
    const data = await action();
    showResult(resultId, render(data));
    notify("Done — your result is ready.");
    return data;
  } catch (error) {
    showResult(resultId, error.message, "error");
    notify(error.message, "error");
    return null;
  } finally {
    button.innerHTML = originalContent;
    button.removeAttribute("aria-busy");
    button.disabled = false;
  }
}

function validateNumber(inputId, resultId, label, { min = 0, exclusive = false, integer = false } = {}) {
  const input = $(inputId);
  const value = input.value.trim() === "" ? Number.NaN : Number(input.value);
  const invalid = !Number.isFinite(value) || (exclusive ? value <= min : value < min) || (integer && !Number.isInteger(value));
  input.setAttribute("aria-invalid", String(invalid));
  if (invalid) {
    const comparator = exclusive ? "greater than" : "at least";
    showResult(resultId, `${label} must be ${comparator} ${min}${integer ? " and a whole number" : ""}.`, "error");
    input.focus();
    return null;
  }
  input.setAttribute("aria-invalid", "false");
  return value;
}

function appendConversation(question, answer, recommendation, explanation, { prepend = false, saved = false } = {}) {
  const item = document.createElement("article");
  item.className = "conversation-item";
  const sourceList = recommendation?.sources?.length
    ? recommendation.sources.map((source) => `<span class="info-badge">Demo source · ${escapeHtml(source)}</span>`).join("")
    : '<span class="info-badge">Source details unavailable</span>';
  const cost = recommendation?.cost
    ? `<span class="info-badge">${escapeHtml(recommendation.cost)} · sample</span>`
    : '<span class="warning-badge">Cost not verified</span>';
  const why = explanation?.why || (saved
    ? "Saved answer; no separate rationale was stored for this conversation."
    : "This demo response does not include a separate evidence rationale.");
  item.innerHTML = `<div class="farmer-message"><span class="message-label">${saved ? "SAVED QUESTION" : "YOUR QUESTION"}</span><p>${escapeHtml(question)}</p></div>
    <div class="advisor-message"><span class="message-label">FIELDWISE RECOMMENDS</span>
      <h3>${escapeHtml(recommendation?.primary || "Advice")}</h3>
      <p>${escapeHtml(answer)}</p>
      <div class="conversation-badges">${cost}${sourceList}</div>
      <p class="conversation-why"><strong>Why:</strong> ${escapeHtml(why)}</p>
    </div>`;
  if (prepend) $("conversation").prepend(item);
  else $("conversation").append(item);
}

async function loadConversationHistory() {
  if (!token) return false;
  const list = $("dashboardHistory");
  list.innerHTML = '<p class="history-loading">Loading saved conversations…</p>';
  try {
    const data = await readResponse(await fetch("/api/farmer/dashboard", {
      credentials: "same-origin"
    }));
    const chats = data.chat_history || [];
    $("dashboardResult").textContent = chats.length
      ? `${chats.length} saved conversation${chats.length === 1 ? "" : "s"}.`
      : "No saved conversations yet. Ask a question to start your field notes.";
    list.innerHTML = chats.map((chat, index) => `<button class="history-item" type="button" data-index="${index}">
      <span class="history-copy"><strong>${escapeHtml(chat.question)}</strong><span>${escapeHtml(chat.answer)}</span></span>
      <time datetime="${escapeHtml(chat.created_at)}">${escapeHtml(new Date(chat.created_at).toLocaleDateString())}</time>
    </button>`).join("");
    list.querySelectorAll(".history-item").forEach((item) => {
      item.addEventListener("click", () => {
        const chat = chats[Number(item.dataset.index)];
        if (!chat) return;
        $("conversation").replaceChildren();
        appendConversation(chat.question, chat.answer, {}, {}, { saved: true });
        $("conversation").scrollIntoView({ behavior: "smooth", block: "start" });
        notify("Saved conversation opened.");
      });
    });
    return true;
  } catch (error) {
    list.replaceChildren();
    $("dashboardResult").textContent = error.message;
    return false;
  }
}

document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    authMode = button.dataset.tab;
    document.querySelectorAll("[data-tab]").forEach((item) => {
      const selected = item === button;
      item.classList.toggle("active", selected);
      item.setAttribute("aria-selected", String(selected));
    });
    $("name").hidden = authMode === "login";
    $("nameLabel").hidden = authMode === "login";
    $("name").required = authMode === "register";
    $("password").autocomplete = authMode === "login" ? "current-password" : "new-password";
    $("authMsg").textContent = "";
  });
});

$("authForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector(".button-primary");
  button.disabled = true;
  button.classList.add("is-loading");
  $("authMsg").textContent = "";
  const body = { identifier: $("email").value.trim(), password: $("password").value };
  if (authMode === "register") body.name = $("name").value.trim();
  try {
    const data = await readResponse(await fetch(`/api/auth/${authMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }));
    setAuthenticated("cookie-session");
    form.reset();
    notify(authMode === "login" ? "Welcome back." : "Your account is ready.");
  } catch (error) {
    $("authMsg").textContent = error.message;
    notify(error.message, "error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
  }
});

$("logout").addEventListener("click", async () => {
  if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
  try { await fetch("/api/auth/logout", {method: "POST", credentials: "same-origin"}); } catch (_) {}
  setAuthenticated(null);
  $("conversation").replaceChildren();
  notify("You have been signed out.");
});

$("ask").addEventListener("click", async () => {
  const question = $("question").value.trim();
  if (!question) {
    $("question").setAttribute("aria-invalid", "true");
    $("question").focus();
    notify("Describe your crop or pest issue before requesting advice.", "error");
    return;
  }
  $("question").setAttribute("aria-invalid", "false");
  const button = $("ask");
  button.disabled = true;
  button.classList.add("is-loading");
  button.innerHTML = '<span class="spinner" aria-hidden="true"></span> Finding guidance…';
  const loading = document.createElement("div");
  loading.className = "conversation-loading";
  loading.innerHTML = "<span></span><span></span><span></span> Checking your question against available guidance";
  $("conversation").append(loading);
  try {
    const data = await readResponse(await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" }, credentials: "same-origin",
      body: JSON.stringify({ question, context: {} })
    }));
    loading.remove();
    appendConversation(question, data.answer, data.recommendation || {}, data.explanation || {});
    $("question").value = "";
    notify("Recommendation added to your field notes.");
    loadConversationHistory();
  } catch (error) {
    loading.remove();
    notify(error.message, "error");
    if (/token|authentication/i.test(error.message)) setAuthenticated(null);
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.innerHTML = 'Get a recommendation <span aria-hidden="true">→</span>';
  }
});

$("question").addEventListener("input", () => $("question").setAttribute("aria-invalid", "false"));
$("question").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") $("ask").click();
});

$("photo").addEventListener("change", () => {
  const file = $("photo").files[0];
  $("photoName").textContent = file ? file.name : "Choose image from device";
  if (file && !["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    showResult("imageResult", "Choose a JPG, PNG, or WebP image.", "error");
    notify("Unsupported image format.", "error");
    $("photo").value = "";
    $("photoName").textContent = "Choose image from device";
    return;
  }
  if (file && file.size > 10 * 1024 * 1024) {
    showResult("imageResult", "Image must be smaller than 10 MB.", "error");
    notify("Image is larger than 10 MB.", "error");
    $("photo").value = "";
    $("photoName").textContent = "Choose image from device";
    return;
  }
  if (file) showResult("imageResult", "Photo ready. Select Analyze photo when you’re ready.", "success");
});

document.querySelector(".file-picker").addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    $("photo").click();
  }
});

$("startCamera").addEventListener("click", async () => {
  const button = $("startCamera");
  const originalContent = button.innerHTML;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.innerHTML = '<span class="button-spinner" aria-hidden="true"></span> Opening camera…';
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
    $("cameraPreview").srcObject = cameraStream;
    $("cameraPreview").hidden = false;
    $("capturePhoto").hidden = false;
    showResult("imageResult", "Camera ready. Frame the affected part of the plant.", "success");
  } catch {
    showResult("imageResult", "Camera access is unavailable or denied. Choose an image from your device instead.", "error");
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.innerHTML = originalContent;
  }
});

$("capturePhoto").addEventListener("click", () => {
  const button = $("capturePhoto");
  const originalContent = button.innerHTML;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.innerHTML = '<span class="button-spinner" aria-hidden="true"></span> Capturing…';
  const video = $("cameraPreview");
  if (!video.videoWidth || !video.videoHeight) {
    showResult("imageResult", "Wait for the camera preview, then capture again.", "error");
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.innerHTML = originalContent;
    return;
  }
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  canvas.toBlob((blob) => {
    if (!blob) {
      showResult("imageResult", "Could not capture the camera frame.", "error");
      button.disabled = false;
      button.removeAttribute("aria-busy");
      button.innerHTML = originalContent;
      return;
    }
    const transfer = new DataTransfer();
    const captured = new File([blob], "camera-capture.jpg", { type: "image/jpeg" });
    transfer.items.add(captured);
    $("photo").files = transfer.files;
    $("photoName").textContent = captured.name;
    showResult("imageResult", "Photo captured. You can analyze it now.", "success");
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.innerHTML = originalContent;
  }, "image/jpeg", 0.9);
});

$("analyze").addEventListener("click", () => {
  const file = $("photo").files[0];
  if (!file) {
    showResult("imageResult", "Choose or capture a photo first.", "error");
    notify("Choose or capture a photo first.", "error");
    document.querySelector(".file-picker").focus();
    return;
  }
  runTool("analyze", "imageResult", async () => {
    const form = new FormData();
    form.append("file", file);
    return readResponse(await fetch("/api/image-analyze", { method: "POST", body: form }));
  }, (data) => ({
    title: data.label || "Image review",
    detail: data.visible_symptoms || data.analysis || "No visible symptoms could be summarized.",
    items: [`Visual confidence: ${Math.round((data.confidence || 0) * 100)}%`],
    note: data.safety_note || data.suggested_next_step || "Have a local agronomist verify the issue before treating."
  }));
});

$("optimize").addEventListener("click", () => {
  const budget = validateNumber("budget", "budgetResult", "Budget", { min: 0, exclusive: true });
  if (budget === null) return;
  const area = validateNumber("area", "budgetResult", "Field size", { min: 0, exclusive: true });
  if (area === null) return;
  runTool("optimize", "budgetResult", () => post("/api/budget-optimize", {
    budget, area_acres: area, crop: "Maize", pest: "Fall Armyworm"
  }), (data) => ({
    title: data.within_budget ? "Plan fits your budget" : "Plan exceeds your budget",
    detail: `Estimated sample total: ₹${data.estimated_total} for ${data.area_acres} acre(s).`,
    items: data.plan.map((item) => `${item.product}: ${item.quantity} acre(s)`),
    note: data.note
  }));
});

$("outbreak").addEventListener("click", () => {
  const reports = validateNumber("reports", "outbreakResult", "Report count", { min: 0, integer: true });
  if (reports === null) return;
  runTool("outbreak", "outbreakResult", () => post("/api/outbreak-warning", {
    district: "Dharwad", crop: "Maize", pest: "Fall Armyworm", reports_last_7_days: reports
  }), (data) => ({
    title: `${data.risk_level.toUpperCase()} sample risk`,
    detail: `Based on ${data.reports_last_7_days} report(s) in the last 7 days.`,
    items: data.actions,
    note: data.warning
  }));
});

$("planner").addEventListener("click", () => {
  const crop = $("plannerCrop").value.trim();
  const pest = $("plannerPest").value.trim();
  if (!crop || !pest) {
    showResult("plannerResult", "Enter both a crop and a pest to build the plan.", "error");
    $("plannerCrop").setAttribute("aria-invalid", String(!crop));
    $("plannerPest").setAttribute("aria-invalid", String(!pest));
    (!crop ? $("plannerCrop") : $("plannerPest")).focus();
    notify("Enter both a crop and a pest.", "error");
    return;
  }
  $("plannerCrop").setAttribute("aria-invalid", "false");
  $("plannerPest").setAttribute("aria-invalid", "false");
  runTool("planner", "plannerResult", () => post("/api/pest-planner", {
    crop, pest, start_date: new Date().toISOString().slice(0, 10), duration_days: 28
  }), (data) => ({
    title: `${data.crop} · ${data.pest}`,
    detail: `Sample 28-day plan starting ${data.start_date}.`,
    items: data.plan.map((item) => `Day ${item.day}: ${item.task}`),
    note: data.note
  }));
});

$("compatibility").addEventListener("click", () => {
  const products = $("products").value.split(",").map((product) => product.trim()).filter(Boolean);
  if (!products.length) {
    showResult("compatibilityResult", "Enter at least one treatment name, separated by commas.", "error");
    $("products").setAttribute("aria-invalid", "true");
    $("products").focus();
    notify("Enter at least one treatment.", "error");
    return;
  }
  $("products").setAttribute("aria-invalid", "false");
  runTool("compatibility", "compatibilityResult", () => post("/api/treatment-compatibility", { products }),
    (data) => ({
      title: data.compatible ? "No known conflict in this demo" : "Review needed",
      detail: `Treatments checked: ${data.products.join(", ")}.`,
      items: data.warnings,
      note: data.note
    }));
});

$("suppliers").addEventListener("click", () => {
  const product = $("supplier").value.trim();
  if (!product) {
    showResult("supplierResult", "Enter a product or treatment to search.", "error");
    $("supplier").setAttribute("aria-invalid", "true");
    $("supplier").focus();
    notify("Enter a product to search.", "error");
    return;
  }
  $("supplier").setAttribute("aria-invalid", "false");
  runTool("suppliers", "supplierResult", () => post("/api/local-suppliers", { district: "Dharwad", product }),
    (data) => ({
      title: `Results for ${data.product}`,
      detail: data.suppliers.map((supplier) => `${supplier.name} · ${supplier.availability}`).join("; "),
      note: data.note
    }));
});

$("dashboard").addEventListener("click", async () => {
  const button = $("dashboard");
  const originalContent = button.innerHTML;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.innerHTML = '<span class="button-spinner" aria-hidden="true"></span> Loading field notes…';
  $("dashboardHistory").innerHTML = '<p class="history-loading">Loading saved conversations…</p>';
  try {
    if (await loadConversationHistory()) notify("Field notes refreshed.");
    else notify($("dashboardResult").textContent, "error");
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.innerHTML = originalContent;
  }
});

document.querySelectorAll("input, textarea").forEach((input) => {
  input.addEventListener("input", () => input.setAttribute("aria-invalid", "false"));
});

(async () => {
  try {
    const response = await fetch("/api/auth/me", {credentials: "same-origin"});
    if (response.ok) { setAuthenticated("cookie-session"); await loadConversationHistory(); }
    else setAuthenticated(null);
  } catch (_) { setAuthenticated(null); }
})();
