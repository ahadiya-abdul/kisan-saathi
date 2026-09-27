/* Fieldwise frontend controller. The served page uses /static/app.js; this
   copy keeps the frontend bundle functional when opened from a static host. */
let token = localStorage.getItem("fieldwise_token");
let mode = "login";
const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
  "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
}[c]));

function setAuthenticated(value) {
  token = value;
  if (value) localStorage.setItem("fieldwise_token", value);
  else localStorage.removeItem("fieldwise_token");
  $("auth").hidden = !!value;
  $("app").hidden = !value;
  $("logout").hidden = !value;
}

async function readResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    mode = button.dataset.tab;
    document.querySelectorAll("[data-tab]").forEach((item) => item.classList.toggle("active", item === button));
    $("name").hidden = mode === "login";
    $("name").required = mode === "register";
    $("authMsg").textContent = "";
  });
});

$("authForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = event.currentTarget.querySelector("button[type=submit], .primary");
  submit.disabled = true;
  $("authMsg").textContent = "";
  const body = { email: $("email").value.trim(), password: $("password").value };
  if (mode === "register") body.name = $("name").value.trim();
  try {
    const data = await readResponse(await fetch(`/api/auth/${mode}`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)
    }));
    setAuthenticated(data.access_token);
    $("authForm").reset();
  } catch (error) {
    $("authMsg").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

$("logout").addEventListener("click", () => setAuthenticated(null));

$("ask").addEventListener("click", async () => {
  const question = $("question").value.trim();
  if (!question) { $("question").focus(); return; }
  $("ask").disabled = true;
  $("result").innerHTML = '<div class="card"><p class="muted">Checking local evidence…</p></div>';
  try {
    const data = await readResponse(await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json", Authorization: `Bearer ${token}`},
      body: JSON.stringify({question, context: {}})
    }));
    const recommendation = data.recommendation || {};
    $("result").innerHTML = `<div class="card answer">
      <p class="eyebrow">RECOMMENDED ACTION</p>
      <h2>${escapeHtml(recommendation.primary)} <small>PRIMARY</small></h2>
      <p>${escapeHtml(data.answer)}</p>
      <p class="muted"><strong>Why:</strong> ${escapeHtml(data.explanation?.why || "Based on the available advisory evidence.")}</p>
      <div class="chips">
      <span>${escapeHtml(recommendation.cost || "Cost not verified")}</span>
      <span>${escapeHtml((recommendation.sources || []).join(" · "))}</span></div>
    </div>`;
  } catch (error) {
    if (error.message.toLowerCase().includes("token") || error.message.toLowerCase().includes("authentication")) setAuthenticated(null);
    $("result").innerHTML = `<div class="card"><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    $("ask").disabled = false;
  }
});

$("question").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") $("ask").click();
});

$("name").hidden = true;
setAuthenticated(token);
