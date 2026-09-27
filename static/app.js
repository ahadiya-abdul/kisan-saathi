/* Served Fieldwise frontend bundle. Keep in sync with frontend/app.js. */
let token = localStorage.getItem("fieldwise_token");
let mode = "login";
const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
function setAuthenticated(value){token=value;if(value)localStorage.setItem("fieldwise_token",value);else localStorage.removeItem("fieldwise_token");$("auth").hidden=!!value;$("app").hidden=!value;$("logout").hidden=!value;}
async function readResponse(response){const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||"Something went wrong");return data;}
document.querySelectorAll("[data-tab]").forEach(button=>button.addEventListener("click",()=>{mode=button.dataset.tab;document.querySelectorAll("[data-tab]").forEach(item=>item.classList.toggle("active",item===button));$("name").hidden=mode==="login";$("name").required=mode==="register";$("authMsg").textContent="";}));
$("authForm").addEventListener("submit",async event=>{event.preventDefault();const submit=event.currentTarget.querySelector("button[type=submit], .primary");submit.disabled=true;$("authMsg").textContent="";const body={email:$("email").value.trim(),password:$("password").value};if(mode==="register")body.name=$("name").value.trim();try{const data=await readResponse(await fetch(`/api/auth/${mode}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}));setAuthenticated(data.access_token);$("authForm").reset();}catch(error){$("authMsg").textContent=error.message;}finally{submit.disabled=false;}});
$("logout").addEventListener("click",()=>setAuthenticated(null));
$("ask").addEventListener("click",async()=>{const question=$("question").value.trim();if(!question){$("question").focus();return;}$("ask").disabled=true;$("result").innerHTML='<div class="card"><p class="muted">Checking local evidence…</p></div>';try{const data=await readResponse(await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:JSON.stringify({question,context:{}})}));const recommendation=data.recommendation||{};$("result").innerHTML=`<div class="card answer"><p class="eyebrow">YOUR FIELDWISE PLAN</p><h2>${escapeHtml(recommendation.primary)} <small>PRIMARY</small></h2><p>${escapeHtml(data.answer)}</p><div class="chips"><span>Confidence ${Math.round((data.confidence||0)*100)}%</span><span>${escapeHtml(recommendation.cost||"Local budget")}</span><span>${escapeHtml((recommendation.sources||[]).join(" · "))}</span></div><h3>Why this recommendation</h3><p class="muted">${escapeHtml((data.reasoning_path||[]).join("  →  "))}</p></div>`;}catch(error){if(error.message.toLowerCase().includes("token")||error.message.toLowerCase().includes("authentication"))setAuthenticated(null);$("result").innerHTML=`<div class="card"><p>${escapeHtml(error.message)}</p></div>`;}finally{$("ask").disabled=false;}});
$("question").addEventListener("keydown",event=>{if((event.ctrlKey||event.metaKey)&&event.key==="Enter")$("ask").click();});$("name").hidden=true;setAuthenticated(token);

const post = async (url, body) => readResponse(await fetch(url, {
  method: "POST", headers: {"Content-Type": "application/json", ...(token ? {Authorization: `Bearer ${token}`} : {})},
  body: JSON.stringify(body)
}));
const show = (id, value) => { $(id).textContent = typeof value === "string" ? value : JSON.stringify(value); };

$("analyze").addEventListener("click", async () => {
  const file = $("photo").files[0];
  if (!file) return show("imageResult", "Choose a photo or use your camera first.");
  const form = new FormData(); form.append("file", file);
  try { const d = await readResponse(await fetch("/api/image-analyze", {method:"POST", body:form})); show("imageResult", `${d.label}: ${d.analysis} Confidence: ${Math.round((d.confidence || 0) * 100)}%. ${d.needs_human_verification === false ? "" : "Human verification is required."}`); }
  catch (e) { show("imageResult", e.message); }
});
let cameraStream;
$("startCamera").addEventListener("click", async () => {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({video: {facingMode: {ideal: "environment"}}, audio: false});
    $("cameraPreview").srcObject = cameraStream;
    $("cameraPreview").hidden = false;
    $("capturePhoto").hidden = false;
    show("imageResult", "Camera enabled. Frame the affected plant and capture a clear, well-lit photo.");
  } catch (error) {
    show("imageResult", "Camera permission was denied or is unavailable. Use Choose File instead.");
  }
});
$("capturePhoto").addEventListener("click", () => {
  const video = $("cameraPreview");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  canvas.toBlob(blob => {
    if (!blob) return show("imageResult", "Could not capture the camera frame.");
    const file = new File([blob], "camera-capture.jpg", {type: "image/jpeg"});
    const transfer = new DataTransfer();
    transfer.items.add(file);
    $("photo").files = transfer.files;
    show("imageResult", "Photo captured. Click Analyze image.");
  }, "image/jpeg", 0.9);
});
$("optimize").addEventListener("click", async () => {
  try { const d = await post("/api/budget-optimize", {budget:Number($("budget").value),area_acres:Number($("area").value),crop:"Maize",pest:"Fall Armyworm"}); show("budgetResult", `${d.estimated_total} estimated; within budget: ${d.within_budget} (sample values)`); } catch(e) { show("budgetResult",e.message); }
});
$("outbreak").addEventListener("click", async () => {
  try { const d = await post("/api/outbreak-warning", {district:"Dharwad",crop:"Maize",pest:"Fall Armyworm",reports_last_7_days:Number($("reports").value)}); show("outbreakResult", `Risk: ${d.risk_level}. ${d.warning}`); } catch(e) { show("outbreakResult",e.message); }
});
$("planner").addEventListener("click", async () => {
  try { const d = await post("/api/pest-planner", {crop:"Maize",pest:"Fall Armyworm",start_date:new Date().toISOString().slice(0,10),duration_days:28}); show("plannerResult", d.plan.map(x=>`Day ${x.day}: ${x.task}`).join(" | ")); } catch(e) { show("plannerResult",e.message); }
});
$("compatibility").addEventListener("click", async () => {
  try { const d = await post("/api/treatment-compatibility", {products:$("products").value.split(",").map(x=>x.trim()).filter(Boolean)}); show("compatibilityResult", `${d.compatible ? "Compatible" : "Review needed"} (offline demo)`); } catch(e) { show("compatibilityResult",e.message); }
});
$("suppliers").addEventListener("click", async () => {
  try { const d = await post("/api/local-suppliers", {district:"Dharwad",product:$("supplier").value}); show("supplierResult", `${d.suppliers[0].name}: ${d.note}`); } catch(e) { show("supplierResult",e.message); }
});
$("dashboard").addEventListener("click", async () => {
  try { const d = await readResponse(await fetch("/api/farmer/dashboard", {headers:{Authorization:`Bearer ${token}`} })); show("dashboardResult", `${d.chat_history.length} saved chats; context: ${JSON.stringify(d.context)}`); } catch(e) { show("dashboardResult",e.message); }
});
