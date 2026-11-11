/* Fieldwise v2 dashboard.
 * - Language choice first, remembered in the browser (not personal data).
 * - Section A saves the field context through the existing PUT /api/farmer/context.
 * - Section B reads that saved context and calls the existing endpoints.
 * - Nothing here fabricates results: failures are shown as failures.
 * Authentication uses a server-issued HttpOnly session cookie; no password or token is stored in localStorage. */
(() => {
"use strict";
const $ = id => document.getElementById(id);
const qa = sel => Array.from(document.querySelectorAll(sel));
const LANG_KEY = "fieldwise_lang";
const SUPPORTED = ["ml", "hi", "kn", "ta", "te", "en"];
const LANG_NAME = {ml: "Malayalam", hi: "Hindi", kn: "Kannada", ta: "Tamil", te: "Telugu", en: "English"};
const CROPS = [["Maize", "crop_maize"], ["Cotton", "crop_cotton"], ["Sorghum", "crop_sorghum"], ["Pigeon pea", "crop_pigeonpea"]];
const STAGES = [["seedling", "stage_seedling"], ["vegetative", "stage_vegetative"], ["flowering", "stage_flowering"], ["filling", "stage_filling"], ["harvest", "stage_harvest"]];
const SOILS = [["red", "soil_red"], ["black", "soil_black"], ["sandy", "soil_sandy"], ["loamy", "soil_loamy"], ["clay", "soil_clay"]];
const HA_TO_ACRES = 2.47105;
const API_TIMEOUT_MS = 45000, UPLOAD_TIMEOUT_MS = 60000;

let lang = null, dict = {}, enDict = {};
let token = null; // in-memory signed-in marker only; credentials live in an HttpOnly cookie
let remoteCtx = {};          // whole saved context object from the server
let saved = {};              // saved field = remoteCtx.field
let lastPhotoResult = null;  // current-session image triage only; the image itself is not persisted
let photoCropAtAnalysis = "";
let mode = "login";
let busy = new Set();
const runs = {};             // card -> signature of inputs used for the shown result

/* ---------- small helpers ---------- */
function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") n.className = v; else if (k === "text") n.textContent = v; else n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null) n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return n;
}
function t(key, vars) {
  let s = dict[key] ?? enDict[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split("{" + k + "}").join(String(v));
  return s;
}
function toast(msg) { const x = $("toast"); x.textContent = msg; x.classList.add("show"); clearTimeout(toast.id); toast.id = setTimeout(() => x.classList.remove("show"), 3500); }
const todayISO = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
const clean = s => (s == null ? "" : String(s).trim());

/* ---------- language ---------- */
async function fetchJSON(url) { const r = await fetch(url, {cache: "default"}); if (!r.ok) throw new Error(url + " " + r.status); return r.json(); }
async function loadLang(code, persist = true) {
  if (!SUPPORTED.includes(code)) code = "en";
  try { enDict = Object.keys(enDict).length ? enDict : await fetchJSON("/static/i18n/en.json"); } catch (e) { console.debug("en.json failed", e); }
  try { dict = code === "en" ? enDict : await fetchJSON("/static/i18n/" + code + ".json"); }
  catch (e) { console.debug("language file failed", e); dict = enDict; }
  lang = code;
  if (persist) localStorage.setItem(LANG_KEY, code);   // language is not personal data
  document.documentElement.lang = code; document.documentElement.dataset.lang = code;
  $("langSwitch").value = code;
  applyI18n();
}
function applyI18n() {
  qa("[data-i18n]").forEach(n => { const v = dict[n.dataset.i18n] ?? enDict[n.dataset.i18n]; if (v) n.textContent = v; });
  qa("[data-i18n-placeholder]").forEach(n => { const v = t(n.dataset.i18nPlaceholder); n.setAttribute("placeholder", v); });
  qa("#langSwitch").forEach(n => n.setAttribute("aria-label", t("lang_label")));
  buildOptions(); setAuthMode(mode); refreshAll();
  if (!$("view-advice").hidden) loadNotes();
}
function opt(value, text) { return el("option", {value}, text); }
function buildOptions() {
  const fill = (id, first, items) => { const s = $(id), cur = s.value; s.replaceChildren(first, ...items); if ([...s.options].some(o => o.value === cur)) s.value = cur; };
  fill("f_crop", opt("", t("opt_choose")), [...CROPS.map(([v, k]) => opt(v, t(k))), opt("__other", t("opt_other"))]);
  fill("f_stage", opt("", t("opt_unknown")), STAGES.map(([v, k]) => opt(v, t(k))));
  fill("f_soil", opt("", t("opt_unknown")), SOILS.map(([v, k]) => opt(v, t(k))));
}

/* ---------- network ---------- */
async function api(path, {method = "GET", body, auth = true} = {}) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), API_TIMEOUT_MS);
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && token && token !== "cookie-session") headers.Authorization = "Bearer " + token;
  try {
    const r = await fetch(path, {method, headers, credentials: "same-origin", signal: ctl.signal, body: body !== undefined ? JSON.stringify(body) : undefined});
    let data = null; try { data = await r.json(); } catch (_) { /* non-JSON error body */ }
    if (r.status === 401 && auth && token) { signOut(); toast(t("session_expired")); }
    return {ok: r.ok, status: r.status, data};
  } catch (e) {
    return {ok: false, status: 0, data: null, network: e.name === "AbortError" ? "timeout" : "offline"};
  } finally { clearTimeout(timer); }
}
function netMessage(res) {
  if (res.network === "timeout") return t("timeout");
  if (res.network) return navigator.onLine ? t("error_generic") : t("offline");
  return t("error_generic");
}
async function withBusy(key, btn, fn) {
  if (busy.has(key)) return; busy.add(key);
  if (btn) btn.disabled = true;
  try { await fn(); } finally { busy.delete(key); if (btn) btn.disabled = false; refreshAll(); }
}
function updateNet() { const b = $("netBanner"); b.hidden = navigator.onLine; if (!navigator.onLine) b.textContent = t("offline"); }
window.addEventListener("online", updateNet); window.addEventListener("offline", updateNet);

/* ---------- routing ---------- */
const VIEWS = ["language", "auth", "field", "advice", "profile"];
function savedComplete() { return !!clean(saved.crop); }
function go(view) { if (location.hash !== "#/" + view) location.hash = "#/" + view; else route(); }
function route() {
  let v = location.hash.replace(/^#\//, "");
  if (!VIEWS.includes(v)) v = "";
  if (!lang) v = "language";
  else if (!v) v = token ? (savedComplete() ? "advice" : "field") : "auth";
  else if (!token && (v === "field" || v === "advice" || v === "profile")) v = "auth";
  else if (token && v === "auth") v = savedComplete() ? "advice" : "field";
  if (v === "advice" && !savedComplete()) v = "field";
  VIEWS.forEach(n => { $("view-" + n).hidden = n !== v; });
  $("topbar").hidden = v === "language";
  $("logout").hidden = !token;
  if ($("btnProfileNav")) $("btnProfileNav").hidden = !token;
  $("foot").hidden = v === "language";
  if (location.hash !== "#/" + v) history.replaceState(null, "", "#/" + v);
  document.title = "Fieldwise";
  if (v === "field") fillFieldForms();
  if (v === "advice") { refreshAll(); loadNotes(); }
  if (v === "profile") loadProfileView();
  window.scrollTo(0, 0);
  const h = document.querySelector("#view-" + v + " h1"); if (h) { h.setAttribute("tabindex", "-1"); h.focus({preventScroll: true}); }
}
window.addEventListener("hashchange", route);

/* ---------- auth ---------- */
function setAuthMode(m) {
  mode = m;
  qa(".tab").forEach(b => { const on = b.dataset.tab === m; b.classList.toggle("active", on); b.setAttribute("aria-selected", on); });
  $("nameWrap").hidden = m !== "register";
  $("password").setAttribute("autocomplete", m === "register" ? "new-password" : "current-password");
  $("authSubmit").textContent = t(m === "register" ? "btn_register" : "btn_signin");
}
qa(".tab").forEach(b => b.addEventListener("click", () => { $("authMsg").textContent = ""; setAuthMode(b.dataset.tab); }));
$("authForm").addEventListener("submit", ev => {
  ev.preventDefault();
  withBusy("auth", $("authSubmit"), async () => {
    const msg = $("authMsg"); msg.textContent = "";
    const identifier = clean($("email").value), password = $("password").value, name = clean($("name").value);
    if (!identifier || !password || (mode === "register" && !name) || (mode === "register" && password.length < 8)) { msg.textContent = t("err_invalid"); return; }
    const body = mode === "register" ? {name, identifier, password} : {identifier, password};
    const res = await api("/api/auth/" + mode, {method: "POST", body, auth: false});
    if (!res.ok) {
      const serverMsg = res.data && (res.data.detail || res.data.message || res.data.error);
      if (res.network) {
        msg.textContent = netMessage(res);
      } else if (typeof serverMsg === "string" && serverMsg.trim()) {
        msg.textContent = serverMsg;
      } else if (res.status === 401) {
        msg.textContent = t("err_login");
      } else if (res.status === 409) {
        msg.textContent = t("err_exists");
      } else if (res.status === 422) {
        msg.textContent = t("err_invalid");
      } else {
        msg.textContent = t("error_generic");
      }
      return;
    }
    token = "cookie-session";
    $("password").value = "";
    toast(t(mode === "register" ? "toast_created" : "toast_welcome"));
    await loadContext();
    await persistLang();
    go(savedComplete() ? "advice" : "field");
  });
});
async function signOut() {
  try { await fetch("/api/auth/logout", {method: "POST", credentials: "same-origin"}); } catch (_) {}
  token = null; remoteCtx = {}; saved = {}; lastPhotoResult = null; photoCropAtAnalysis = "";
  sessionStorage.clear(); Object.keys(runs).forEach(k => delete runs[k]);
  qa(".result").forEach(n => n.replaceChildren()); $("conversation").replaceChildren(); $("notesList").replaceChildren();
  go("auth");
}
$("logout").addEventListener("click", () => { signOut(); toast(t("toast_signed_out")); });

/* ---------- language switching ---------- */
qa(".lang-btn").forEach(b => b.addEventListener("click", async () => { await loadLang(b.dataset.lang); go(token ? (savedComplete() ? "advice" : "field") : "auth"); }));
$("langSwitch").addEventListener("change", async e => { await loadLang(e.target.value); persistLang(); });
async function persistLang() {   // remember the choice on the account too; failure is harmless
  if (!token) return;
  remoteCtx = {...remoteCtx, lang}; await api("/api/farmer/context", {method: "PUT", body: {context: remoteCtx}});
}

/* ---------- saved field context ---------- */
async function loadContext() {
  const res = await api("/api/farmer/dashboard");
  if (res.ok && res.data) {
    remoteCtx = res.data.context || {};
    saved = remoteCtx.field || {};
    if (res.data.user) updateProfilePill(res.data.user);
    return res.data;
  }
  return null;
}
const effCrop = f => clean(f.crop) === "__other" ? clean(f.crop_other) : clean(f.crop);
const effPest = f => clean(f.pest) === "__other" ? clean(f.pest_other) : clean(f.pest);
const areaAcres = f => { const a = parseFloat(f.area); if (!(a > 0)) return null; return f.unit === "hectares" ? +(a * HA_TO_ACRES).toFixed(3) : a; };
const budgetOf = f => { const b = parseFloat(f.budget); return b > 0 ? b : null; };
function cropLabel(f) { const c = clean(f.crop); const hit = CROPS.find(([v]) => v === c); return hit ? t(hit[1]) : effCrop(f); }

/* ---------- Section A: cards ---------- */
const CARD_FIELDS = {
  1: ["crop", "crop_other", "variety", "stage", "sowing_date", "soil"],
  2: ["area", "unit", "budget"],
  3: ["state", "district", "village"]
};
const ID = {crop: "f_crop", crop_other: "f_crop_other", variety: "f_variety", stage: "f_stage", sowing_date: "f_sowing", soil: "f_soil", area: "f_area", unit: "f_unit", budget: "f_budget", state: "f_state", district: "f_district", village: "f_village"};
const attention = new Set();
function readCard(n) { const o = {}; for (const k of CARD_FIELDS[n]) o[k] = clean($(ID[k]).value); if (n === 1 && o.crop !== "__other") o.crop_other = ""; if (n === 2 && !o.unit) o.unit = "acres"; return o; }
function fillFieldForms() {
  for (const n of [1, 2, 3]) for (const k of CARD_FIELDS[n]) { const input = $(ID[k]); const draft = sessionStorage.getItem("fw_draft_" + k); input.value = draft != null ? draft : (saved[k] ?? (k === "unit" ? "acres" : "")); }
  $("f_sowing").max = todayISO(); toggleOther(); statuses(); syncCropTiles();
  if (saved.weather_observation) { const w = saved.weather_observation; $("weatherStatus").textContent = `${t("weather_saved")} ${w.temperature_c ?? "–"}°C · ${w.humidity_percent ?? "–"}% · ${w.rain_probability_percent ?? "–"}% rain chance · ${w.observed_at || ""}`; }
}
function toggleOther() { $("cropOtherWrap").hidden = $("f_crop").value !== "__other"; }
function setErr(id, msg) { const e = $(id); if (e) e.textContent = msg || ""; const inp = id === "e_crop" ? $("f_crop") : id === "e_crop_other" ? $("f_crop_other") : id === "e_area" ? $("f_area") : id === "e_budget" ? $("f_budget") : null; if (inp) inp.setAttribute("aria-invalid", msg ? "true" : "false"); }
function validate(n) {
  const v = readCard(n); let ok = true; let first = null;
  const fail = (eid, key) => { setErr(eid, t(key)); ok = false; first = first || eid; };
  if (n === 1) {
    setErr("e_crop"); setErr("e_crop_other");
    if (!v.crop) fail("e_crop", "err_choose_crop"); else if (v.crop === "__other" && !v.crop_other) fail("e_crop_other", "err_required");
  }
  if (n === 2) {
    setErr("e_area"); setErr("e_budget");
    if (v.area !== "") { const a = Number(v.area); if (!(a > 0) || !isFinite(a)) fail("e_area", "err_number"); else if (areaAcres(v) > 10000) fail("e_area", "err_area_max"); }
    if (v.budget !== "") { const b = Number(v.budget); if (!(b > 0) || !isFinite(b)) fail("e_budget", "err_number"); else if (b > 100000) fail("e_budget", "err_budget_max"); }
  }
  return {ok, values: v, first};
}
function cardState(n) {
  const draft = readCard(n), keys = CARD_FIELDS[n];
  const savedPart = {}; keys.forEach(k => savedPart[k] = clean(saved[k] ?? (k === "unit" ? "acres" : "")));
  const dirty = JSON.stringify(draft) !== JSON.stringify(savedPart);
  const has = n === 1 ? !!clean(saved.crop) : n === 2 ? (clean(saved.area) !== "" || clean(saved.budget) !== "") : clean(saved.district) !== "";
  if (attention.has(n)) return "attention";
  if (dirty) return "unsaved"; return has ? "saved" : "none";
}
function statuses() {
  const label = {none: ["○ ", "st_none"], saved: ["✓ ", "st_saved"], attention: ["! ", "st_attention"], unsaved: ["● ", "st_unsaved"]};
  for (const n of [1, 2, 3]) { const s = cardState(n), n_ = $("status" + n); n_.className = "status is-" + s; n_.textContent = label[s][0] + t(label[s][1]); }
}
async function saveCards(list, {quiet} = {}) {
  let allOk = true, changes = {}, firstErr = null;
  for (const n of list) { const r = validate(n); if (!r.ok) { attention.add(n); allOk = false; firstErr = firstErr || r.first; } else { attention.delete(n); Object.assign(changes, r.values); } }
  statuses();
  if (!allOk) { const e = $(firstErr); if (e) { const inp = e.parentElement.querySelector("input,select"); if (inp) inp.focus(); } return false; }
  const oldCrop = effCrop(saved);
  const field = {...saved, ...changes, updated_at: new Date().toISOString()};
  const context = {...remoteCtx, v: 1, lang, field};
  const res = await api("/api/farmer/context", {method: "PUT", body: {context}});
  if (!res.ok) { $("saveMsg").className = "form-msg is-error"; $("saveMsg").textContent = netMessage(res); list.forEach(n => attention.add(n)); statuses(); return false; }
  remoteCtx = res.data.context || context; saved = remoteCtx.field || field;
  if ((oldCrop && oldCrop.toLowerCase() !== effCrop(saved).toLowerCase()) || (photoCropAtAnalysis && photoCropAtAnalysis.toLowerCase() !== effCrop(saved).toLowerCase())) { lastPhotoResult = null; photoCropAtAnalysis = ""; $("photoResult").replaceChildren(); }
  Object.keys(ID).forEach(k => sessionStorage.removeItem("fw_draft_" + k));
  if (!quiet) { $("saveMsg").className = "form-msg"; $("saveMsg").textContent = t("saved_ok"); }
  statuses(); refreshAll();
  return true;
}
[1, 2, 3].forEach(n => $("save" + n).addEventListener("click", () => withBusy("save" + n, $("save" + n), async () => { $("saveMsg").textContent = ""; await saveCards([n]); })));
$("saveAll").addEventListener("click", () => withBusy("saveAll", $("saveAll"), async () => {
  $("saveMsg").textContent = "";
  if (await saveCards([1, 2, 3], {quiet: true})) go("advice");
}));
Object.entries(ID).forEach(([k, id]) => { const n = $(id); const h = () => { sessionStorage.setItem("fw_draft_" + k, n.value); toggleOther(); const card = Object.keys(CARD_FIELDS).find(c => CARD_FIELDS[c].includes(k)); attention.delete(+card); statuses(); }; n.addEventListener("input", h); n.addEventListener("change", h); });

/* ---------- Section B: context, prerequisites, stale results ---------- */
function sigFor(card) {
  const f = saved;
  const pick = {budget: [effCrop(f), areaAcres(f), budgetOf(f), f.weather_observation?.observed_at, lastPhotoResult?.candidate_issue], risk: [effCrop(f), clean(f.district), f.weather_observation?.observed_at, lastPhotoResult?.candidate_issue],
    plan: [effCrop(f), f.stage, f.sowing_date, $("planStart").value, f.weather_observation?.observed_at, lastPhotoResult?.candidate_issue], compat: [effCrop(f), lastPhotoResult?.candidate_issue], supp: [clean(f.district), effCrop(f)]};
  return JSON.stringify(pick[card]);
}
function needsFor(card) {
  const f = saved, m = [];
  const need = (cond, key) => { if (!cond) m.push(t(key)); };
  if (card === "budget") { need(effCrop(f), "n_crop"); need(areaAcres(f), "n_area"); need(budgetOf(f), "n_budget"); }
  if (card === "risk") { need(effCrop(f), "n_crop"); need(clean(f.district), "n_district"); }
  if (card === "plan") { need(effCrop(f), "n_crop"); }
  if (card === "supp") need(clean(f.district), "n_district");
  if (card === "compat") need(effCrop(f), "n_crop");
  return m;
}
const CARD_UI = {budget: ["needsBudget", "runBudget", "resBudget"], risk: ["needsRisk", "runRisk", "resRisk"], plan: ["needsPlan", "runPlan", "resPlan"], supp: ["needsSupp", "runSupp", "resSupp"]};
function refreshAll() {
  if (Object.keys(ID).length && $("view-field") && !$("view-field").hidden) statuses();
  const w = saved.weather_observation;
  const pills = [
    saved.crop ? el("span", {class: "tag", text: cropLabel(saved) + (saved.stage ? " (" + saved.stage + ")" : "")}) : null,
    clean(saved.district) ? el("span", {class: "tag", text: clean(saved.district) + (clean(saved.state) ? ", " + clean(saved.state) : "")}) : null,
    saved.area ? el("span", {class: "tag", text: saved.area + " " + (saved.unit || "acres")}) : null,
    saved.budget ? el("span", {class: "tag", text: "₹" + saved.budget}) : null,
    w ? el("span", {class: "tag", text: (w.temperature_c ?? "–") + "°C · " + (w.rain_probability_percent ?? "–") + "% rain"}) : null,
    lastPhotoResult && photoCropAtAnalysis.toLowerCase() === effCrop(saved).toLowerCase() ? el("span", {class: "tag", text: (lastPhotoResult.candidate_issue || "Photo analyzed")}) : null
  ].filter(Boolean);
  if (pills.length) {
    $("ctxSummary").replaceChildren(...pills);
  } else {
    $("ctxSummary").textContent = "Fill in and save your field in Step 1 to unlock personalized advice.";
  }
  $("suppDistrict").textContent = clean(saved.district) || "–";
  if (!$("planStart").value) $("planStart").value = todayISO();
  $("runCompat").disabled = needsFor("compat").length > 0 || busy.has("compat");
  if (runs.compat && runs.compat !== sigFor("compat")) $("resCompat").replaceChildren(panel("is-stale", t("st_outdated"), [], [el("p", {text: t("recalc")})]));
  for (const [card, [needId, btnId, resId]] of Object.entries(CARD_UI)) {
    const miss = needsFor(card), nd = $(needId), btn = $(btnId);
    nd.textContent = miss.length ? t("needs_prefix") + " " + miss.join(", ") : "";
    if (!busy.has(card)) btn.disabled = miss.length > 0;
    btn.textContent = runs[card] ? t("recalc") : (card === "supp" ? t("su_search") : t("get_result"));
    if (runs[card] && runs[card] !== sigFor(card)) {   // inputs changed: never show the old result as current
      $(resId).replaceChildren(panel("is-stale", t("st_outdated"), [], [el("p", {text: t("recalc")})]));
    }
  }
  $("photoImg").alt = "";
}
["planStart"].forEach(id => $(id).addEventListener("input", refreshAll));

function panel(cls, title, items, extra) {
  const isLong = typeof title === "string" && (title.length > 55 || title.includes(". "));
  const p = el("div", {class: "panel " + cls, role: cls === "is-error" ? "alert" : null});
  if (isLong) {
    p.append(el("h3", {text: "Advisory Guidance"}), el("p", {style: "font-size:1.025rem; line-height:1.6;", text: title}));
  } else {
    p.append(el("h3", {text: title}));
  }
  if (items && items.length) p.append(el("ul", {}, items.map(i => el("li", {text: i}))));
  (extra || []).forEach(x => { if (x) p.append(x); });
  return p;
}
function show(id, node) { $(id).replaceChildren(node); }
function loading(id) { show(id, el("p", {class: "hint", text: t("working")})); }
function fail(id, res, fallbackKey) { show(id, panel("is-error", res && res.network ? netMessage(res) : t(fallbackKey || "error_generic"), [], [el("button", {class: "btn btn-secondary", type: "button", text: t("retry"), onclick: "void 0"})])); const b = $(id).querySelector("button"); b.onclick = () => $(id).previousElementSibling.click(); }

/* Section B decision cards all ask the evidence-grounded advisor to decide; none use canned rules. */
function advisorContext() {
  const f = saved;
  const context = {crop: effCrop(f), variety: clean(f.variety), pest: effPest(f), stage: clean(f.stage),
    sowing_date: clean(f.sowing_date), soil: clean(f.soil), area: areaAcres(f), area_unit: "acres",
    budget_inr: budgetOf(f), state: clean(f.state), district: clean(f.district), village: clean(f.village),
    language: LANG_NAME[lang] || "English"};
  if (f.weather_observation) context.weather_summary = f.weather_observation;
  if (lastPhotoResult && photoCropAtAnalysis.toLowerCase() === effCrop(f).toLowerCase()) context.image_analysis = {image_kind: lastPhotoResult.image_kind, candidate_issue: lastPhotoResult.candidate_issue,
    visible_symptoms: lastPhotoResult.visible_symptoms, confidence: lastPhotoResult.confidence,
    needs_human_verification: lastPhotoResult.needs_human_verification};
  Object.keys(context).forEach(k => { if (context[k] === "" || context[k] == null) delete context[k]; });
  return context;
}
async function runDecision(key, buttonId, resultId, prompt) {
  if (needsFor(key).length) { show(resultId, panel("is-warn", t("needs_prefix") + " " + needsFor(key).join(", "), [])); return; }
  loading(resultId);
  const res = await api("/api/chat", {method: "POST", body: {question: prompt, context: advisorContext()}});
  if (!res.ok) return fail(resultId, res);
  runs[key] = sigFor(key);
  show(resultId, renderAnswer(res.data));
}
$("runBudget").addEventListener("click", () => withBusy("budget", $("runBudget"), () => runDecision("budget", "runBudget", "resBudget",
  "Create an actionable, itemized biological crop protection budget plan tailored to my field size and budget. Use verified ICAR biopesticide technology pricing benchmarks (Trichocards @ ₹70-90/card, pheromone traps @ ₹60-80/trap, Shatpada / Mycoguard / microbial bio-sprays @ ₹350-450/L, and neem botanicals @ ₹250-350/acre). Detail the exact quantities, estimated item costs, and total investment.")));
$("runRisk").addEventListener("click", () => withBusy("risk", $("runRisk"), () => runDecision("risk", "runRisk", "resRisk",
  "Assess the pest risk level (High, Moderate, or Low) for my crop and suspected pest based on ICAR IPM guidelines, crop growth stage, and regional seasonal vulnerability. Provide the field Economic Threshold Level (ETL) and actionable scouting and early biological intervention steps.")));
$("runPlan").addEventListener("click", () => withBusy("plan", $("runPlan"), () => runDecision("plan", "runPlan", "resPlan",
  "Create a comprehensive step-by-step field scouting and biological release schedule anchored to the plan start date. Specify what to inspect at each crop growth interval and exactly when to release parasitoids and apply bio-pesticides.")));
$("runCompat").addEventListener("click", () => withBusy("compat", $("runCompat"), () => runDecision("compat", "runCompat", "resCompat",
  "Provide an evidence-based biological treatment compatibility assessment. Clarify why bio-agents (like Trichogramma and Beauveria) should not be mixed with chemical fungicides, specify the recommended 7-day waiting interval, and detail safe integrated pest management next steps.")));
$("runSupp").addEventListener("click", () => withBusy("supp", $("runSupp"), () => runDecision("supp", "runSupp", "resSupp",
  "Give verified local agricultural extension/KVK contact guidance for the saved district. Do not invent supplier names, phone numbers, addresses, inventory, prices, or availability. If the retrieved sources do not provide a verified contact, say that live directory data is not configured.")));

/* ---------- Card 4: photo diagnosis ---------- */
let photoBlob = null, photoURL = null, activeXhr = null;
function setProgress(pct) { const p = $("photoProgress"); p.hidden = pct == null; if (pct != null) p.value = pct; }
function photoError(key) { show("photoResult", panel("is-error", t("p_err_title"), [t(key)], [photoRetryRow()])); }
function photoRetryRow() {
  return el("div", {class: "btn-row"},
    el("button", {class: "btn btn-primary", type: "button", text: t("retry"), onclick: "void 0"}),
    el("button", {class: "btn btn-secondary", type: "button", text: t("p_choose_another"), onclick: "void 0"}));
}
function wireRetry() { const b = $("photoResult").querySelectorAll("button"); if (b[0]) b[0].onclick = analyzePhoto; if (b[1]) b[1].onclick = () => $("photoGallery").click(); }
async function shrink(file) {
  const bmp = await new Promise((res, rej) => { const u = URL.createObjectURL(file), im = new Image(); im.onload = () => { URL.revokeObjectURL(u); res(im); }; im.onerror = () => { URL.revokeObjectURL(u); rej(new Error("decode")); }; im.src = u; });
  const max = 1600, scale = Math.min(1, max / Math.max(bmp.naturalWidth, bmp.naturalHeight));
  const w = Math.max(1, Math.round(bmp.naturalWidth * scale)), h = Math.max(1, Math.round(bmp.naturalHeight * scale));
  const c = document.createElement("canvas"); c.width = w; c.height = h; c.getContext("2d").drawImage(bmp, 0, 0, w, h);
  const blob = await new Promise(r => c.toBlob(r, "image/jpeg", 0.85));
  if (!blob) throw new Error("encode");
  return {blob, w, h};
}
async function onPhoto(file) {
  $("photoResult").replaceChildren(); setProgress(null);
  if (!file) return;
  lastPhotoResult = null; photoCropAtAnalysis = "";
  if (!/^image\//.test(file.type)) { photoError("p_err_type"); photoBlob = null; $("photoAnalyze").disabled = true; return; }
  try {
    const {blob, w, h} = await shrink(file);
    if (blob.size > 9.5 * 1024 * 1024) { photoError("p_err_size"); photoBlob = null; $("photoAnalyze").disabled = true; wireRetry(); return; }
    photoBlob = blob; if (photoURL) URL.revokeObjectURL(photoURL); photoURL = URL.createObjectURL(blob);
    $("photoImg").src = photoURL; $("photoMeta").textContent = w + "×" + h + " · " + Math.round(blob.size / 1024) + " KB";
    $("photoPreview").hidden = false; $("photoAnalyze").disabled = false;
  } catch (e) { console.debug("photo prepare failed", e); photoBlob = null; $("photoPreview").hidden = true; $("photoAnalyze").disabled = true; photoError("p_err_type"); wireRetry(); }
}
$("photoTake").addEventListener("click", () => $("photoCamera").click());
$("photoPick").addEventListener("click", () => $("photoGallery").click());
["photoCamera", "photoGallery"].forEach(id => $(id).addEventListener("change", e => { const f = e.target.files[0]; e.target.value = ""; onPhoto(f); }));
$("photoCancel").addEventListener("click", () => { if (activeXhr) activeXhr.abort(); });
$("photoAnalyze").addEventListener("click", analyzePhoto);
function selectedCropForPhoto() {
  if (!$("view-field").hidden) return clean($("f_crop").value) === "__other" ? clean($("f_crop_other").value) : clean($("f_crop").value);
  return effCrop(saved);
}
function analyzePhoto() {
  if (!photoBlob || busy.has("photo")) return;
  const cropForPhoto = selectedCropForPhoto();
  if (!cropForPhoto) { photoError("err_choose_crop"); wireRetry(); return; }
  photoCropAtAnalysis = cropForPhoto;
  if (!navigator.onLine) { photoError("offline"); wireRetry(); return; }
  busy.add("photo"); $("photoAnalyze").disabled = true; $("photoCancel").hidden = false; $("photoResult").replaceChildren();
  setProgress(0); $("photoMeta").textContent = t("p_uploading", {pct: 0});
  const fd = new FormData(); fd.append("file", photoBlob, "photo.jpg");
  fd.append("crop", cropForPhoto); fd.append("variety", !$("view-field").hidden ? clean($("f_variety").value) : clean(saved.variety)); fd.append("stage", !$("view-field").hidden ? clean($("f_stage").value) : clean(saved.stage)); fd.append("language", LANG_NAME[lang] || "English"); fd.append("image_kind", $("photoKind").value);
  const x = new XMLHttpRequest(); activeXhr = x; x.open("POST", "/api/image-analyze"); x.timeout = UPLOAD_TIMEOUT_MS;
  if (token && token !== "cookie-session") x.setRequestHeader("Authorization", "Bearer " + token);
  const done = (fn) => { activeXhr = null; busy.delete("photo"); $("photoCancel").hidden = true; setProgress(null); $("photoAnalyze").disabled = !photoBlob; $("photoMeta").textContent = ""; fn(); wireRetry(); };
  x.upload.onprogress = e => { if (e.lengthComputable) { const pct = Math.round(e.loaded / e.total * 100); setProgress(pct); $("photoMeta").textContent = pct < 100 ? t("p_uploading", {pct}) : t("p_checking"); } };
  x.onload = () => done(() => {
    let d = null; try { d = JSON.parse(x.responseText); } catch (_) { /* ignore */ }
    if (x.status >= 200 && x.status < 300 && d && d.live === true) return renderPhotoOk(d);
    if (x.status >= 200 && x.status < 300 && d) { console.debug("image analysis unavailable", d.reason); return photoError(d.reason === "not_configured" ? "p_err_not_configured" : d.reason === "image_unclear" ? "p_err_unclear" : "p_err_failed"); }
    if (x.status === 415 || x.status === 400) return photoError("p_err_type");
    if (x.status === 413) return photoError("p_err_size");
    photoError(x.status >= 500 ? "error_generic" : "p_err_failed");
  });
  x.onerror = () => done(() => photoError(navigator.onLine ? "p_err_failed" : "offline"));
  x.ontimeout = () => done(() => photoError("timeout"));
  x.onabort = () => done(() => $("photoResult").replaceChildren());
  x.send(fd);
}
function renderPhotoOk(d) {
  lastPhotoResult = d;
  const pct = typeof d.confidence === "number" ? Math.round(Math.max(0, Math.min(1, d.confidence)) * 100) : null;
  const syms = Array.isArray(d.visible_symptoms) ? d.visible_symptoms : (d.visible_symptoms ? [d.visible_symptoms] : []);
  const qualityWarnings = d.image_quality && Array.isArray(d.image_quality.warnings) ? d.image_quality.warnings : [];
  show("photoResult", panel("is-warn", t("p_ok_title") + ": " + clean(d.candidate_issue || d.label), [...syms, ...qualityWarnings],
    [pct === null ? null : el("p", {text: t("p_confidence") + ": " + pct + "%"}),
     d.image_quality && d.image_quality.enhanced ? el("p", {class: "hint", text: "A brighter/clearer working copy was used for analysis; your original photo was not changed or saved."}) : null,
     el("p", {class: "hint", text: t("p_verify")}), d.safety_note ? el("p", {class: "hint", text: d.safety_note}) : null]));
  refreshAll();
}

/* ---------- Ask Fieldwise (existing /api/chat with the saved field) ---------- */
$("ask").addEventListener("click", () => withBusy("ask", $("ask"), async () => {
  const typed = clean($("question").value), box = $("conversation");
  const q = typed || "Make the best evidence-supported recommendation for my field using my crop, image findings, weather, field size and budget. Do not ask me to choose a pest-control method.";
  const context = advisorContext();
  box.replaceChildren(el("div", {class: "msg is-user", text: q}), el("p", {class: "hint", text: t("working")}));
  const res = await api("/api/chat", {method: "POST", body: {question: q, context}});
  if (!res.ok) { box.replaceChildren(el("div", {class: "msg is-user", text: q}), panel("is-error", res.network ? netMessage(res) : t("error_generic"), [])); return; }
  box.replaceChildren(el("div", {class: "msg is-user", text: q}), renderAnswer(res.data));
  $("question").value = ""; loadNotes();
}));
function renderAnswer(d) {
  if (!d || d.available === false) {
    const answerText = d && d.answer ? d.answer : t("weather_unavailable");
    const extra = d && d.explanation && d.explanation.limitations ? [el("p", {class: "hint", text: d.explanation.limitations})] : [];
    return panel("is-warn", answerText, [], extra);
  }
  const body = el("div", {class: "msg"},
    el("div", {style: "font-weight:750; color:var(--green); margin-bottom:.5rem; display:flex; align-items:center; gap:.4rem;"}, "Biological Control Recommendation"),
    el("p", {style: "font-size:1.05rem; line-height:1.6;", text: d.answer || ""})
  );
  if (Array.isArray(d.recommended_actions) && d.recommended_actions.length) {
    body.append(el("ul", {style: "margin:.75rem 0 .75rem 1.25rem;"}, d.recommended_actions.map(a => el("li", {text: a}))));
  }
  const why = el("details", {}, el("summary", {text: t("why")}));
  if (d.explanation) why.append(el("p", {class: "hint", text: [d.explanation.why, d.explanation.limitations].filter(Boolean).join(" ")}));
  if (d.sources && d.sources.length) {
    const list = d.sources.map(src => {
      const label = [src.title || src.id, src.source].filter(Boolean).join(" — ");
      const item = el("li", {}, label);
      if (src.url && /^https:\/\//i.test(src.url)) item.append(" ", el("a", {href: src.url, target: "_blank", rel: "noopener noreferrer"}, t("sources_label")));
      return item;
    });
    why.append(el("p", {class: "hint", text: t("sources_label")}), el("ul", {}, list));
  }
  body.append(why);
  if (d.explanation && d.explanation.needs_human_review) body.append(el("p", {class: "hint", text: t("p_verify")}));
  return body;
}

/* ---------- Card 10: field notes ---------- */
async function loadNotes() {
  const box = $("notesList"); if (!token) return;
  box.replaceChildren(el("p", {class: "hint", text: t("n_loading")}));
  const res = await api("/api/farmer/dashboard");
  if (!res.ok) { box.replaceChildren(panel("is-error", res.network ? netMessage(res) : t("n_error"), [])); return; }
  const list = res.data.chat_history || [];
  if (!list.length) { box.replaceChildren(el("p", {class: "muted", text: t("n_empty")})); return; }
  box.replaceChildren(...list.map(c => el("button", {class: "note-item", type: "button", onclick: "void 0", "data-q": c.question, "data-a": c.answer},
    el("b", {text: c.question}), el("br"), el("span", {class: "hint", text: (c.created_at || "").slice(0, 10)}))));
  box.querySelectorAll(".note-item").forEach(b => b.addEventListener("click", () => {
    $("conversation").replaceChildren(el("p", {class: "hint", text: t("n_saved")}), el("div", {class: "msg is-user", text: b.dataset.q}), el("div", {class: "msg"}, el("p", {text: b.dataset.a})));
    $("askCard").scrollIntoView({block: "start"});
  }));
}
$("notesRefresh").addEventListener("click", () => withBusy("notes", $("notesRefresh"), loadNotes));

/* ---------- GPS weather: coordinates are used for this request only and never saved ---------- */
$("useGpsWeather").addEventListener("click", () => withBusy("gps-weather", $("useGpsWeather"), async () => {
  const status = $("weatherStatus");
  if (!navigator.geolocation) { status.textContent = t("weather_unavailable"); return; }
  status.textContent = t("weather_loading");
  let position;
  try {
    position = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject,
      {enableHighAccuracy: false, timeout: 9000, maximumAge: 15 * 60 * 1000}));
  } catch (err) {
    status.textContent = err && err.code === 1 ? t("weather_denied") : t("weather_unavailable");
    return;
  }
  const lat = position.coords.latitude, lon = position.coords.longitude;
  const res = await api(`/api/weather/current?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lon)}`);
  if (!res.ok || !res.data || !res.data.available) { status.textContent = t("weather_unavailable"); return; }
  const w = res.data;
  const summary = {provider: w.provider, observed_at: w.observed_at, temperature_c: w.temperature_c,
    humidity_percent: w.humidity_percent, rain_probability_percent: w.rain_probability_percent,
    precipitation_mm: w.precipitation_mm, timezone: w.timezone};
  const nextField = {...saved, weather_observation: summary};
  const nextContext = {...remoteCtx, v: 1, lang, field: nextField};
  const savedRes = await api("/api/farmer/context", {method: "PUT", body: {context: nextContext}});
  if (!savedRes.ok) { status.textContent = t("weather_unavailable"); return; }
  remoteCtx = savedRes.data.context || nextContext; saved = remoteCtx.field || nextField;
  status.textContent = `${t("weather_saved")} ${w.temperature_c ?? "–"}°C · ${w.humidity_percent ?? "–"}% · ${w.rain_probability_percent ?? "–"}% rain chance · ${w.observed_at || ""}`;
  refreshAll();
}));

/* ---------- start ---------- */

  /* ---------- Interactive Visual Crop Selector & Presets ---------- */
  function syncCropTiles() {
    const val = $("f_crop").value;
    qa(".crop-tile").forEach(btn => {
      const match = btn.dataset.crop === val;
      btn.classList.toggle("is-active", match);
      btn.setAttribute("aria-checked", match);
    });
  }
  qa(".crop-tile").forEach(btn => {
    btn.addEventListener("click", () => {
      $("f_crop").value = btn.dataset.crop;
      $("f_crop").dispatchEvent(new Event("change"));
      syncCropTiles();
      if (btn.dataset.crop === "__other") {
        $("cropOtherWrap").hidden = false;
        $("f_crop_other").focus();
      }
    });
  });
  $("f_crop").addEventListener("change", syncCropTiles);
  
  qa("#areaChips .preset-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      $("f_area").value = btn.dataset.val;
      $("f_area").dispatchEvent(new Event("input"));
      qa("#areaChips .preset-chip").forEach(b => b.classList.remove("is-selected"));
      btn.classList.add("is-selected");
    });
  });

  qa("#budgetChips .preset-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      $("f_budget").value = btn.dataset.val;
      $("f_budget").dispatchEvent(new Event("input"));
      qa("#budgetChips .preset-chip").forEach(b => b.classList.remove("is-selected"));
      btn.classList.add("is-selected");
    });
  });

  /* ---------- Feature 1: Bio vs Chemical ROI Simulator ---------- */
  function updateRoi() {
    if (!$("roiAreaRange")) return;
    const area = parseFloat($("roiAreaRange").value) || 2.5;
    $("roiAreaVal").textContent = area.toFixed(1);
    const pressure = $("roiPressureSelect").value;
    const factor = pressure === "low" ? 0.75 : (pressure === "high" ? 1.45 : 1.0);
    
    // Chemical calculations
    const chemPest = Math.round(3500 * area * factor);
    const chemRig = Math.round(1000 * area * factor);
    const chemLabor = Math.round(1200 * area * factor);
    const chemTotal = chemPest + chemRig + chemLabor;
    const chemPerAcre = Math.round(chemTotal / area);
    
    // Biocontrol calculations
    const bioAgents = Math.round(1200 * area * factor);
    const bioTraps = Math.round(200 * area);
    const bioLabor = Math.round(300 * area);
    const bioTotal = bioAgents + bioTraps + bioLabor;
    const bioPerAcre = Math.round(bioTotal / area);
    
    const netSaved = chemTotal - bioTotal;
    const pctSaved = Math.round((netSaved / chemTotal) * 100);
    const soilIndex = pressure === "high" ? 44 : 38;
    
    $("roiChemTotal").textContent = "₹" + chemTotal.toLocaleString("en-IN");
    $("roiChemPerAcre").textContent = "₹" + chemPerAcre.toLocaleString("en-IN") + " per acre (" + (pressure === "high" ? "4 rounds" : "3 rounds") + ")";
    $("roiChemPesticide").textContent = "₹" + chemPest.toLocaleString("en-IN");
    $("roiChemRig").textContent = "₹" + chemRig.toLocaleString("en-IN");
    $("roiChemLabor").textContent = "₹" + chemLabor.toLocaleString("en-IN");
    
    $("roiBioTotal").textContent = "₹" + bioTotal.toLocaleString("en-IN");
    $("roiBioPerAcre").textContent = "₹" + bioPerAcre.toLocaleString("en-IN") + " per acre (Biological releases)";
    $("roiBioAgents").textContent = "₹" + bioAgents.toLocaleString("en-IN");
    $("roiBioTraps").textContent = "₹" + bioTraps.toLocaleString("en-IN");
    $("roiBioLabor").textContent = "₹" + bioLabor.toLocaleString("en-IN");
    
    $("roiNetSaved").textContent = "₹" + netSaved.toLocaleString("en-IN");
    $("roiPercentSaved").textContent = pctSaved + "%";
    $("roiSoilPreserved").textContent = "+" + soilIndex + "%";
  }

  if ($("roiAreaRange")) {
    $("roiAreaRange").addEventListener("input", updateRoi);
    $("roiPressureSelect").addEventListener("change", updateRoi);
    if ($("roiPrintBtn")) $("roiPrintBtn").addEventListener("click", () => window.print());
    
    // Sync ROI slider if user edits farm area in Step 1
    $("f_area").addEventListener("input", () => {
      const v = parseFloat($("f_area").value);
      if (!isNaN(v) && v >= 0.5 && v <= 20) {
        $("roiAreaRange").value = v;
        updateRoi();
      }
    });
    updateRoi();
  }

  /* ---------- Feature 2: Outbreak Radar & Community GIS ---------- */
  const RADAR_HOTSPOTS = {
    "h-mandya": {
      severity: "High Alert Severity",
      pillClass: "pill-danger",
      updated: "Confirmed 2 hrs ago",
      pest: "Fall Armyworm (Spodoptera frugiperda)",
      crop: "Maize (Vegetative / Knee-high)",
      zone: "Mandya Taluk (8.4 km away)",
      reports: "14 verified farmers",
      weather: "78% RH (Favors egg hatch)",
      action: "Release Trichogramma chilonis parasitoid cards @ 50,000 eggs/acre stapled under lower leaves, combined with 5 pheromone trap lures/acre to disrupt mating before caterpillars bore into whorls."
    },
    "h-haveri": {
      severity: "Moderate Warning",
      pillClass: "pill-warning",
      updated: "Updated 5 hrs ago",
      pest: "Pink Bollworm (Pectinophora gossypiella)",
      crop: "Cotton (Squaring / Flowering)",
      zone: "Haveri Belt (14.2 km away)",
      reports: "9 verified farmers",
      weather: "82% RH, 29°C (Mating flight peak)",
      action: "Install 8 Pheromone delta traps/acre immediately for male moth suppression. Release Trichogrammatoidea bactrae @ 60,000 parasitoids/acre on alternate weeks."
    },
    "h-dharwad": {
      severity: "Biocontrol Active Zone",
      pillClass: "pill-success",
      updated: "Confirmed 9 hrs ago",
      pest: "Sorghum Stem Borer (Chilo partellus)",
      crop: "Sorghum (Whorl stage)",
      zone: "Dharwad Agri Belt",
      reports: "7 verified scouts",
      weather: "68% RH (Parasitoids active)",
      action: "Maintain Bracon brevicornis larval parasitoids and conserve native spiders. Field larval parasitism rate has successfully reached 65%."
    },
    "h-raichur": {
      severity: "Sucking Pest Warning",
      pillClass: "pill-warning",
      updated: "Updated today",
      pest: "Cotton Aphids & Whitefly Complex",
      crop: "Cotton & Pigeon Pea",
      zone: "Raichur Agro-zone",
      reports: "6 community sightings",
      weather: "72% RH, warm winds",
      action: "Spray 5% Neem Seed Kernel Extract (NSKE) or Beauveria bassiana @ 5g/L during late evening. Avoid chemical organophosphates that destroy predatory green lacewings."
    }
  };

  function selectHotspot(id) {
    const data = RADAR_HOTSPOTS[id];
    if (!data) return;
    qa(".hotspot-point").forEach(el => el.classList.remove("is-selected-hotspot"));
    const target = qs(`[data-id="${id}"]`);
    if (target) target.classList.add("is-selected-hotspot");

    $("dossierSeverity").textContent = data.severity;
    $("dossierSeverity").className = "dossier-pill " + data.pillClass;
    $("dossierUpdated").textContent = data.updated;
    $("dossierPest").textContent = data.pest;
    $("dossierCrop").textContent = data.crop;
    $("dossierZone").textContent = data.zone;
    $("dossierCount").textContent = data.reports;
    $("dossierWeather").textContent = data.weather;
    $("dossierAction").textContent = data.action;
  }

  qa(".hotspot-point").forEach(pt => {
    pt.addEventListener("click", () => selectHotspot(pt.dataset.id));
  });

  qa(".radar-node").forEach(node => {
    node.addEventListener("click", () => {
      const dist = node.dataset.district;
      const matched = Object.keys(RADAR_HOTSPOTS).find(k => k.toLowerCase().includes(dist.toLowerCase()));
      if (matched) selectHotspot(matched);
      else toast("Scanning surveillance radar in " + dist + "… No severe outbreak reported.");
    });
  });

  if ($("radarReportToggleBtn")) {
    $("radarReportToggleBtn").addEventListener("click", () => {
      $("radarReportDrawer").hidden = !$("radarReportDrawer").hidden;
    });
    $("radarCancelReport").addEventListener("click", () => {
      $("radarReportDrawer").hidden = true;
    });
    $("radarSubmitReport").addEventListener("click", () => {
      const pest = $("reportPest").value;
      const dist = clean($("reportDistrict").value) || "Mandya";
      const sev = $("reportSeverity").value;

      // Add to Scout feed
      const feed = $("radarScoutFeed");
      const li = document.createElement("li");
      li.innerHTML = `<span class="feed-dot ${sev === 'High' ? 'red' : 'yellow'}"></span> <strong>${dist} Farmer:</strong> <em>Reported ${pest} (${sev}).</em> <small>Just now</small>`;
      feed.insertBefore(li, feed.firstChild);

      // Create new dynamic SVG hotspot point
      const layer = $("radarHotspotsLayer");
      if (layer) {
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "hotspot-point hotspot-high is-selected-hotspot");
        const rx = Math.floor(220 + Math.random() * 120);
        const ry = Math.floor(160 + Math.random() * 100);
        g.setAttribute("transform", `translate(${rx}, ${ry})`);
        g.innerHTML = `
          <circle class="pulse-ring ring-red-1" r="22" fill="none" stroke="#ef4444" stroke-width="2"/>
          <circle r="7" fill="#dc2626" stroke="#ffffff" stroke-width="2"/>
          <text x="10" y="-10" class="hotspot-badge-text">🔴 ${dist} Alert</text>
        `;
        layer.appendChild(g);
      }

      toast("Pest sighting logged. Neighboring fields in " + dist + " alerted.");
      $("radarReportDrawer").hidden = true;
    });
  }

  // Highlight district on radar if user types/changes district in Step 1
  if ($("f_district")) {
    $("f_district").addEventListener("change", () => {
      const val = clean($("f_district").value).toLowerCase();
      qa(".radar-node").forEach(n => {
        const match = n.dataset.district && n.dataset.district.toLowerCase() === val;
        n.classList.toggle("active-zone", match);
      });
    });
  }


/* ---------- Farmer Profile & Identity Card ---------- */
let currentFarmerProfile = null;

function updateProfilePill(u) {
  if (!u) return;
  if ($("btnProfileNav")) $("btnProfileNav").hidden = !token;
  const displayName = u.name ? (u.name.length > 14 ? u.name.slice(0, 12) + "…" : u.name) : "Farmer";
  if ($("navFarmerName")) $("navFarmerName").textContent = displayName;
  if ($("navFarmerId")) $("navFarmerId").textContent = u.farmer_id || "ID";
  if (u.photo_url && $("navAvatarImg")) {
    $("navAvatarImg").src = u.photo_url;
    $("navAvatarImg").style.display = "block";
    if ($("navAvatarInitials")) $("navAvatarInitials").style.display = "none";
  } else {
    if ($("navAvatarImg")) $("navAvatarImg").style.display = "none";
    if ($("navAvatarInitials")) {
      $("navAvatarInitials").style.display = "flex";
      $("navAvatarInitials").textContent = (u.name || "F").charAt(0).toUpperCase();
    }
  }
}

async function loadProfileView() {
  const res = await api("/api/farmer/profile");
  if (!res.ok || !res.data) return;
  const p = res.data;
  currentFarmerProfile = p;

  updateProfilePill(p);

  // Populate Identity Card
  if ($("displayFarmerName")) $("displayFarmerName").textContent = p.name || "Farmer";
  if ($("displayFarmerIdBadge")) $("displayFarmerIdBadge").textContent = "ID: " + (p.farmer_id || "–");
  if ($("cardFarmerId")) $("cardFarmerId").textContent = p.farmer_id || "–";
  if ($("cardFarmerPhone")) $("cardFarmerPhone").textContent = p.phone ? p.phone : t("not_provided");
  if ($("cardFarmerEmail")) $("cardFarmerEmail").textContent = p.email ? p.email : t("not_provided");
  if ($("cardFarmerAge")) $("cardFarmerAge").textContent = p.age ? t("years_old", {age: p.age}) : t("not_provided");
  
  let genderText = t("not_provided");
  if (p.gender && p.gender !== "Not specified") {
    const gKey = "gender_" + p.gender.toLowerCase();
    genderText = t(gKey) || p.gender;
  }
  if ($("cardFarmerGender")) $("cardFarmerGender").textContent = genderText;
  if ($("cardFarmerRegDate")) $("cardFarmerRegDate").textContent = p.date_of_registration || "–";

  // Active Field Link Summary
  const f = saved;
  const cropStr = f.crop ? cropLabel(f) + (f.stage ? " (" + f.stage + ")" : "") : "";
  const areaStr = f.area ? f.area + " " + (f.unit || "acres") : "";
  const soilStr = clean(f.soil) ? clean(f.soil) : "";
  const locStr = clean(f.district) ? clean(f.district) + (clean(f.state) ? ", " + clean(f.state) : "") : "";
  const parts = [cropStr, areaStr, soilStr, locStr].filter(Boolean);
  if ($("cardFieldSummary")) {
    $("cardFieldSummary").textContent = parts.length ? parts.join(" · ") : "No active field linked yet. Save your field in Step 1.";
  }

  // Photo Render
  if (p.photo_url && $("profilePhotoImg")) {
    $("profilePhotoImg").src = p.photo_url;
    $("profilePhotoImg").style.display = "block";
    if ($("profilePhotoFallback")) $("profilePhotoFallback").style.display = "none";
  } else {
    if ($("profilePhotoImg")) $("profilePhotoImg").style.display = "none";
    if ($("profilePhotoFallback")) {
      $("profilePhotoFallback").style.display = "flex";
      if ($("profileInitials")) $("profileInitials").textContent = (p.name || "F").charAt(0).toUpperCase();
    }
  }

  // Populate Edit Inputs
  if ($("prof_name")) $("prof_name").value = p.name || "";
  if ($("prof_phone")) $("prof_phone").value = p.phone || "";
  if ($("prof_email")) $("prof_email").value = p.email || "";
  if ($("prof_age")) $("prof_age").value = p.age || "";
  if ($("prof_gender")) $("prof_gender").value = p.gender || "";
}

// Wire Profile UI events
if ($("btnProfileNav")) $("btnProfileNav").addEventListener("click", () => go("profile"));

if ($("btnCopyFarmerId")) {
  $("btnCopyFarmerId").addEventListener("click", () => {
    const text = $("cardFarmerId") ? $("cardFarmerId").textContent : "";
    if (text && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      toast("Farmer ID copied to clipboard!");
    }
  });
}

if ($("btnUploadPhotoTrigger")) {
  $("btnUploadPhotoTrigger").addEventListener("click", () => $("profilePhotoInput").click());
}

if ($("profilePhotoInput")) {
  $("profilePhotoInput").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch("/api/farmer/profile/photo", {
        method: "POST",
        headers: token && token !== "cookie-session" ? {"Authorization": "Bearer " + token} : {},
        body: fd,
        credentials: "same-origin"
      });
      const data = await res.json();
      if (res.ok && data.photo_url) {
        if ($("profilePhotoImg")) {
          $("profilePhotoImg").src = data.photo_url;
          $("profilePhotoImg").style.display = "block";
        }
        if ($("profilePhotoFallback")) $("profilePhotoFallback").style.display = "none";
        if ($("navAvatarImg")) {
          $("navAvatarImg").src = data.photo_url;
          $("navAvatarImg").style.display = "block";
        }
        if ($("navAvatarInitials")) $("navAvatarInitials").style.display = "none";
        toast("Photo updated successfully!");
      } else {
        toast(data.detail || "Could not upload photo");
      }
    } catch (err) {
      toast("Photo upload failed");
    }
  });
}

if ($("btnToggleEditProfile")) {
  $("btnToggleEditProfile").addEventListener("click", () => {
    if (!$("profileEditCard")) return;
    $("profileEditCard").hidden = !$("profileEditCard").hidden;
    if (!$("profileEditCard").hidden && $("prof_name")) $("prof_name").focus();
  });
}

if ($("btnCancelEditProfile")) {
  $("btnCancelEditProfile").addEventListener("click", () => {
    if ($("profileEditCard")) $("profileEditCard").hidden = true;
  });
}

if ($("profileEditForm")) {
  $("profileEditForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = clean($("prof_name").value);
    if (!name) { toast("Name is required"); return; }
    const phone = clean($("prof_phone").value);
    const email = clean($("prof_email").value);
    const ageVal = parseInt($("prof_age").value, 10);
    const age = isNaN(ageVal) ? null : ageVal;
    const gender = clean($("prof_gender").value);

    const res = await api("/api/farmer/profile", {
      method: "PUT",
      body: { name, phone: phone || null, email: email || null, age, gender: gender || null }
    });
    if (res.ok && res.data) {
      toast(t("toast_profile_saved"));
      if ($("profileEditCard")) $("profileEditCard").hidden = true;
      loadProfileView();
    } else {
      toast(res.data && res.data.detail ? res.data.detail : t("error_generic"));
    }
  });
}

(async function init() {
  updateNet();
  const stored = localStorage.getItem(LANG_KEY);
  if (SUPPORTED.includes(stored)) await loadLang(stored);
  else { await loadLang("en", false); lang = null; }   // new visitor: language screen comes first, nothing saved yet
  // Restore a persistent session without exposing its credential to JavaScript.
  try {
    const session = await fetch("/api/auth/me", {credentials: "same-origin"});
    if (session.ok) { token = "cookie-session"; await loadContext(); }
  } catch (_) { /* show the sign-in route when the server is unavailable */ }
  route();
})();
})();
