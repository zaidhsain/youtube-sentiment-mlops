// Logique du popup : extraction (via content script) -> API -> affichage.

// ⚠️ Après le déploiement (Phase 6), remplacer par l'URL du Space Hugging Face,
// ex. "https://<utilisateur>-youtube-sentiment-api.hf.space"
const DEFAULT_API_URL = "http://localhost:8000";
const BATCH_SIZE = 100;          // taille des lots envoyés à l'API
const REQUEST_TIMEOUT_MS = 30000; // un Space HF "endormi" peut mettre ~20 s à redémarrer

const LABELS = { "1": "Positif", "0": "Neutre", "-1": "Négatif" };
const COLORS = { "1": "--pos", "0": "--neu", "-1": "--neg" };

const $ = (id) => document.getElementById(id);
const state = { predictions: [], stats: null, filter: "all", query: "", title: "", url: "" };

// ---------- Paramètres & thème (chrome.storage) ----------
async function loadSettings() {
  const s = await chrome.storage.local.get({
    apiUrl: DEFAULT_API_URL, maxComments: "100", includeReplies: false, theme: "light",
  });
  $("apiUrl").value = s.apiUrl;
  $("maxComments").value = s.maxComments;
  $("includeReplies").checked = s.includeReplies;
  document.body.classList.toggle("dark", s.theme === "dark");
  return s;
}

async function saveSettings() {
  const apiUrl = $("apiUrl").value.trim().replace(/\/+$/, "") || DEFAULT_API_URL;
  $("apiUrl").value = apiUrl;
  await chrome.storage.local.set({
    apiUrl, maxComments: $("maxComments").value, includeReplies: $("includeReplies").checked,
  });
  $("apiStatus").textContent = "Enregistré ✓";
}

async function toggleTheme() {
  const dark = document.body.classList.toggle("dark");
  await chrome.storage.local.set({ theme: dark ? "dark" : "light" });
}

// ---------- Appels API ----------
async function fetchJson(url, options = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(url, { ...options, signal: ctrl.signal });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body);
      throw new Error(`API ${res.status} : ${detail}`);
    }
    return body;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("L'API ne répond pas (délai dépassé).");
    if (e instanceof TypeError) throw new Error("Impossible de joindre l'API. Vérifiez l'URL dans ⚙.");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

async function testApi() {
  const s = $("apiStatus");
  s.textContent = "Test…";
  try {
    const h = await fetchJson(`${$("apiUrl").value.trim().replace(/\/+$/, "")}/health`);
    s.textContent = h.model_loaded ? `OK ✓ (modèle v${h.model_version})` : "API joignable, modèle absent";
  } catch (e) {
    s.textContent = e.message;
  }
}

async function predictAll(apiUrl, texts) {
  const predictions = [];
  let apiMs = 0;
  for (let i = 0; i < texts.length; i += BATCH_SIZE) {
    setLoading(`Analyse ${Math.min(i + BATCH_SIZE, texts.length)}/${texts.length}…`);
    const r = await fetchJson(`${apiUrl}/predict_batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comments: texts.slice(i, i + BATCH_SIZE) }),
    });
    predictions.push(...r.predictions);
    apiMs += r.processing_time_ms;
  }
  return { predictions, apiMs };
}

// Les stats globales sont recalculées côté client quand il y a plusieurs lots.
function computeStats(preds) {
  const n = preds.length;
  const count = (s) => preds.filter((p) => p.sentiment === s).length;
  const pos = count(1), neu = count(0), neg = count(-1);
  return {
    total: n, positive: pos, neutral: neu, negative: neg,
    positive_pct: (100 * pos) / n, neutral_pct: (100 * neu) / n, negative_pct: (100 * neg) / n,
    average_confidence: preds.reduce((a, p) => a + p.confidence, 0) / n,
    sentiment_score: (pos - neg) / n,
  };
}

// ---------- Extraction des commentaires ----------
async function extractComments(tabId, options) {
  const send = () => chrome.tabs.sendMessage(tabId, { type: "EXTRACT_COMMENTS", options });
  try {
    return await send();
  } catch {
    // Onglet ouvert avant l'installation de l'extension : on injecte le content script.
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
    return await send();
  }
}

async function analyze() {
  hide("error"); hide("results");
  $("analyzeBtn").disabled = true;
  try {
    const settings = await loadSettings();
    // Mode test : popup.html?tabId=<id> cible un onglet précis (tests automatisés Playwright).
    const testTabId = new URLSearchParams(location.search).get("tabId");
    const tab = testTabId
      ? await chrome.tabs.get(Number(testTabId))
      : (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
    if (!tab?.url?.startsWith("https://www.youtube.com/watch")) {
      throw new Error("Ouvrez une vidéo YouTube puis relancez l'analyse.");
    }

    setLoading("Extraction des commentaires (défilement automatique)…");
    const data = await extractComments(tab.id, {
      max: Number(settings.maxComments), includeReplies: settings.includeReplies, autoScroll: true,
    });
    if (!data?.ok) throw new Error(data?.error || "Extraction impossible.");
    if (!data.comments.length) throw new Error("Aucun commentaire trouvé (commentaires désactivés ?).");

    const t0 = performance.now();
    const { predictions, apiMs } = await predictAll(settings.apiUrl, data.comments.map((c) => c.text));
    const roundTrip = performance.now() - t0;

    state.predictions = predictions.map((p, i) => ({ ...p, ...data.comments[i], text: data.comments[i].text }));
    state.stats = computeStats(state.predictions);
    state.title = data.title;
    state.url = data.url;
    state.latency = Math.round(roundTrip);
    state.apiMs = apiMs;
    render();
  } catch (e) {
    showError(e.message);
  } finally {
    hide("loading");
    $("analyzeBtn").disabled = false;
  }
}

// ---------- Rendu ----------
function renderDonut(st) {
  const svg = $("donut");
  const css = getComputedStyle(document.body);
  const r = 15.915; // circonférence = 100 -> les % se lisent directement
  const parts = [["1", st.positive_pct], ["0", st.neutral_pct], ["-1", st.negative_pct]];
  let offset = 25; // départ à 12h
  let html = `<circle cx="21" cy="21" r="${r}" fill="none" stroke="${css.getPropertyValue("--border")}" stroke-width="5"/>`;
  for (const [k, pct] of parts) {
    if (pct <= 0) continue;
    html += `<circle cx="21" cy="21" r="${r}" fill="none" stroke="${css.getPropertyValue(COLORS[k])}"
      stroke-width="5" stroke-dasharray="${pct} ${100 - pct}" stroke-dashoffset="${offset}"/>`;
    offset -= pct;
  }
  const score = st.sentiment_score;
  html += `<text x="21" y="22" text-anchor="middle">${score > 0 ? "+" : ""}${score.toFixed(2)}</text>
           <text x="21" y="27" text-anchor="middle" class="sub">score</text>`;
  svg.innerHTML = html; // contenu 100 % numérique, aucune donnée utilisateur
}

function render() {
  const st = state.stats;
  $("videoTitle").textContent = state.title;
  $("posPct").textContent = `${st.positive_pct.toFixed(1)}%`;
  $("neuPct").textContent = `${st.neutral_pct.toFixed(1)}%`;
  $("negPct").textContent = `${st.negative_pct.toFixed(1)}%`;
  $("posN").textContent = `${st.positive} commentaires`;
  $("neuN").textContent = `${st.neutral} commentaires`;
  $("negN").textContent = `${st.negative} commentaires`;
  $("total").textContent = st.total;
  $("score").textContent = st.sentiment_score.toFixed(2);
  $("conf").textContent = `${(100 * st.average_confidence).toFixed(0)}%`;
  $("latency").textContent = state.latency;
  $("latency").parentElement.title = `Aller-retour réseau ; calcul côté API : ${state.apiMs.toFixed(1)} ms`;
  renderDonut(st);
  renderList();
  show("results");
}

function filtered() {
  const q = state.query.toLowerCase();
  return state.predictions.filter((p) =>
    (state.filter === "all" || String(p.sentiment) === state.filter) &&
    (!q || p.text.toLowerCase().includes(q) || (p.author || "").toLowerCase().includes(q)));
}

function renderList() {
  const list = $("commentList");
  list.replaceChildren();
  const items = filtered();
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "Aucun commentaire pour ce filtre.";
    list.append(li);
    return;
  }
  const frag = document.createDocumentFragment();
  for (const p of items) {
    // textContent uniquement : le texte des commentaires n'est jamais interprété comme du HTML (XSS).
    const li = document.createElement("li");
    li.className = `s${p.sentiment}`;
    const head = document.createElement("div");
    head.className = "c-head";
    const who = document.createElement("span");
    who.textContent = (p.author || "Anonyme") + (p.isReply ? " · réponse" : "");
    if (p.isReply) who.className = "reply-tag";
    const badge = document.createElement("span");
    badge.className = `badge s${p.sentiment}`;
    badge.textContent = `${LABELS[p.sentiment]} · ${(100 * p.confidence).toFixed(0)}%`;
    head.append(who, badge);
    const txt = document.createElement("div");
    txt.className = "c-text";
    txt.textContent = p.text;
    li.append(head, txt);
    frag.append(li);
  }
  list.append(frag);
}

// ---------- Export ----------
async function copyResults() {
  const st = state.stats;
  const lines = [
    `Analyse de sentiment — ${state.title}`,
    state.url,
    `Total : ${st.total} | Positif ${st.positive_pct.toFixed(1)}% | Neutre ${st.neutral_pct.toFixed(1)}% | Négatif ${st.negative_pct.toFixed(1)}%`,
    `Score global : ${st.sentiment_score.toFixed(2)}`,
    "",
    ...filtered().map((p) => `[${LABELS[p.sentiment]} ${(100 * p.confidence).toFixed(0)}%] ${p.text.replace(/\s+/g, " ")}`),
  ];
  await navigator.clipboard.writeText(lines.join("\n"));
  flash($("copyBtn"), "Copié ✓");
}

function exportCsv() {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const rows = [["author", "is_reply", "sentiment", "label", "confidence", "text"].join(",")];
  for (const p of filtered()) {
    rows.push([esc(p.author), p.isReply, p.sentiment, p.label, p.confidence, esc(p.text)].join(","));
  }
  const blob = new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `sentiment_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
  flash($("csvBtn"), "✓");
}

// ---------- Utilitaires UI ----------
function show(id) { $(id).classList.remove("hidden"); }
function hide(id) { $(id).classList.add("hidden"); }
function setLoading(text) { $("loadingText").textContent = text; show("loading"); }
function showError(msg) { $("error").textContent = msg; show("error"); }
function flash(btn, text) {
  const old = btn.textContent;
  btn.textContent = text;
  setTimeout(() => (btn.textContent = old), 1200);
}

// ---------- Événements ----------
document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  $("analyzeBtn").addEventListener("click", analyze);
  $("themeBtn").addEventListener("click", async () => {
    await toggleTheme();
    if (state.stats) renderDonut(state.stats); // les couleurs du donut dépendent du thème
  });
  $("settingsBtn").addEventListener("click", () => $("settings").classList.toggle("hidden"));
  $("saveSettings").addEventListener("click", saveSettings);
  $("testApi").addEventListener("click", testApi);
  $("copyBtn").addEventListener("click", copyResults);
  $("csvBtn").addEventListener("click", exportCsv);
  $("search").addEventListener("input", (e) => { state.query = e.target.value; renderList(); });
  document.querySelectorAll(".filter").forEach((btn) =>
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.filter = btn.dataset.filter;
      renderList();
    }));
});
