// Commentomètre : popup
// Récupère les commentaires via content.js, les envoie à l'API, affiche le bilan.

// API locale (le port 8000 est déjà pris sur ma machine). À remplacer par
// l'adresse du Space Hugging Face une fois déployé.
const DEFAULT_API_URL = "http://127.0.0.1:8001";
const BATCH_SIZE = 100;
// Un Space HF en veille met parfois ~20 s à se réveiller, d'où ce délai large.
const REQUEST_TIMEOUT_MS = 30000;

const LABELS = { "1": "😊 positif", "0": "😐 neutre", "-1": "😞 négatif" };

// Humeur globale affichée en haut des résultats, selon le score (de −1 à +1).
function moodFor(score) {
  if (score >= 0.4) return ["🤩", "Le public adore"];
  if (score >= 0.15) return ["😊", "Accueil plutôt positif"];
  if (score > -0.15) return ["😐", "Accueil mitigé"];
  if (score > -0.4) return ["😕", "Accueil plutôt négatif"];
  return ["😡", "Le public n'aime pas"];
}

const $ = (id) => document.getElementById(id);
const state = { predictions: [], stats: null, filter: "all", query: "", title: "", url: "", latency: 0, apiMs: 0 };

const pct = (x) => `${x.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
const signed = (x) => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });


/* ---------- réglages ---------- */

async function loadSettings() {
  const s = await chrome.storage.local.get({
    apiUrl: DEFAULT_API_URL, maxComments: "100", includeReplies: false, theme: "light",
  });
  $("apiUrl").value = s.apiUrl;
  $("maxComments").value = s.maxComments;
  $("includeReplies").checked = s.includeReplies;
  applyTheme(s.theme === "dark");
  return s;
}

function applyTheme(dark) {
  document.body.classList.toggle("dark", dark);
  $("themeBtn").textContent = dark ? "☀️" : "🌙";
}

function cleanUrl(raw) {
  return raw.trim().replace(/\/+$/, "") || DEFAULT_API_URL;
}

async function saveSettings() {
  $("apiUrl").value = cleanUrl($("apiUrl").value);
  await chrome.storage.local.set({
    apiUrl: $("apiUrl").value,
    maxComments: $("maxComments").value,
    includeReplies: $("includeReplies").checked,
  });
  $("apiStatus").textContent = "Réglages enregistrés.";
}

async function toggleTheme() {
  const dark = !document.body.classList.contains("dark");
  applyTheme(dark);
  await chrome.storage.local.set({ theme: dark ? "dark" : "light" });
}


/* ---------- appels à l'API ---------- */

async function fetchJson(url, options = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(url, { ...options, signal: ctrl.signal });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body);
      throw new Error(`L'API a répondu ${res.status} : ${detail}`);
    }
    return body;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("L'API met trop de temps à répondre. Réessayez dans un instant.");
    if (e instanceof TypeError) throw new Error("Impossible de joindre l'API. Vérifiez son adresse dans les réglages.");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

async function testApi() {
  const out = $("apiStatus");
  out.textContent = "Connexion…";
  try {
    const h = await fetchJson(`${cleanUrl($("apiUrl").value)}/health`);
    out.textContent = h.model_loaded
      ? `Connexion établie, modèle v${h.model_version} chargé.`
      : "L'API répond, mais le modèle n'est pas chargé.";
  } catch (e) {
    out.textContent = e.message;
  }
}

async function predictAll(apiUrl, texts) {
  const predictions = [];
  let apiMs = 0;
  for (let i = 0; i < texts.length; i += BATCH_SIZE) {
    setLoading(`Analyse : ${Math.min(i + BATCH_SIZE, texts.length)} sur ${texts.length}…`);
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

// Avec plusieurs lots, l'API ne voit jamais l'ensemble : on refait le bilan ici.
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


/* ---------- extraction ---------- */

async function extractComments(tabId, options) {
  const ask = () => chrome.tabs.sendMessage(tabId, { type: "EXTRACT_COMMENTS", options });
  try {
    return await ask();
  } catch {
    // Onglet ouvert avant l'installation : content.js n'y est pas encore.
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
    return await ask();
  }
}

async function findTargetTab() {
  // popup.html?tabId=… : utilisé uniquement par le test Playwright.
  const forced = new URLSearchParams(location.search).get("tabId");
  if (forced) return chrome.tabs.get(Number(forced));
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function analyze() {
  hide("error");
  hide("results");
  $("analyzeBtn").disabled = true;
  try {
    const settings = await loadSettings();
    const tab = await findTargetTab();
    if (!tab?.url?.startsWith("https://www.youtube.com/watch")) {
      throw new Error("Ouvrez d'abord une vidéo YouTube, puis relancez l'analyse.");
    }

    setLoading("Lecture des commentaires, la page va défiler…");
    const data = await extractComments(tab.id, {
      max: Number(settings.maxComments),
      includeReplies: settings.includeReplies,
      autoScroll: true,
    });
    if (!data?.ok) throw new Error(data?.error || "Impossible de lire les commentaires.");
    if (!data.comments.length) throw new Error("Aucun commentaire trouvé. Ils sont peut-être désactivés sur cette vidéo.");

    const t0 = performance.now();
    const { predictions, apiMs } = await predictAll(settings.apiUrl, data.comments.map((c) => c.text));

    state.latency = Math.round(performance.now() - t0);
    state.apiMs = apiMs;
    state.predictions = predictions.map((p, i) => ({ ...p, ...data.comments[i] }));
    state.stats = computeStats(state.predictions);
    state.title = data.title;
    state.url = data.url;
    render();
  } catch (e) {
    showError(e.message);
  } finally {
    hide("loading");
    $("analyzeBtn").disabled = false;
  }
}


/* ---------- affichage ---------- */

function render() {
  const st = state.stats;
  $("videoTitle").textContent = state.title;
  $("score").textContent = signed(st.sentiment_score);
  const [emoji, label] = moodFor(st.sentiment_score);
  $("mood").textContent = emoji;
  $("moodLabel").textContent = label;
  $("total").textContent = st.total;
  $("conf").textContent = `${Math.round(100 * st.average_confidence)} %`;
  $("latency").textContent = state.latency;
  $("latency").title = `dont ${state.apiMs.toFixed(1)} ms de calcul côté serveur`;

  $("posN").textContent = st.positive;
  $("neuN").textContent = st.neutral;
  $("negN").textContent = st.negative;
  $("posPct").textContent = pct(st.positive_pct);
  $("neuPct").textContent = pct(st.neutral_pct);
  $("negPct").textContent = pct(st.negative_pct);

  $("segPos").style.width = `${st.positive_pct}%`;
  $("segNeu").style.width = `${st.neutral_pct}%`;
  $("segNeg").style.width = `${st.negative_pct}%`;

  renderList();
  show("results");
}

function visibleComments() {
  const q = state.query.toLowerCase();
  return state.predictions.filter((p) =>
    (state.filter === "all" || String(p.sentiment) === state.filter) &&
    (!q || p.text.toLowerCase().includes(q) || (p.author || "").toLowerCase().includes(q)));
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text; // jamais innerHTML : le texte vient de YouTube
  return node;
}

function renderList() {
  const list = $("commentList");
  list.replaceChildren();
  const items = visibleComments();
  if (!items.length) {
    list.append(el("li", "empty", "Aucun commentaire ne correspond."));
    return;
  }
  const frag = document.createDocumentFragment();
  for (const p of items) {
    const li = el("li");
    const meta = el("div", "c-meta");
    meta.append(
      el("span", p.isReply ? "reply" : "", (p.author || "anonyme") + (p.isReply ? ", en réponse" : "")),
      el("span", `tag s${p.sentiment}`, `${LABELS[p.sentiment]} · ${Math.round(100 * p.confidence)} %`),
    );
    li.append(meta, el("div", "c-text", p.text));
    frag.append(li);
  }
  list.append(frag);
}


/* ---------- export ---------- */

async function copyResults() {
  const st = state.stats;
  const lines = [
    `Commentomètre : ${state.title}`,
    state.url,
    `${st.total} commentaires : ${pct(st.positive_pct)} positifs, ${pct(st.neutral_pct)} neutres, ${pct(st.negative_pct)} négatifs`,
    `Score global : ${signed(st.sentiment_score)}`,
    "",
    ...visibleComments().map((p) => `[${LABELS[p.sentiment]}, ${Math.round(100 * p.confidence)} %] ${p.text.replace(/\s+/g, " ")}`),
  ];
  await navigator.clipboard.writeText(lines.join("\n"));
  flash($("copyBtn"), "Copié");
}

function exportCsv() {
  const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const rows = ["auteur;reponse;sentiment;etiquette;confiance;texte"];
  for (const p of visibleComments()) {
    rows.push([q(p.author), p.isReply ? 1 : 0, p.sentiment, p.label, String(p.confidence).replace(".", ","), q(p.text)].join(";"));
  }
  // Point-virgule et BOM : le fichier s'ouvre directement dans un Excel en français.
  const blob = new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `commentometre_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
  flash($("csvBtn"), "Téléchargé");
}


/* ---------- petites aides ---------- */

function show(id) { $(id).classList.remove("hidden"); }
function hide(id) { $(id).classList.add("hidden"); }
function setLoading(text) { $("loadingText").textContent = text; show("loading"); }
function showError(msg) { $("error").textContent = msg; show("error"); }
function flash(btn, text) {
  const before = btn.textContent;
  btn.textContent = text;
  setTimeout(() => { btn.textContent = before; }, 1200);
}

document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  $("analyzeBtn").addEventListener("click", analyze);
  $("themeBtn").addEventListener("click", toggleTheme);
  $("settingsBtn").addEventListener("click", () => $("settings").classList.toggle("hidden"));
  $("saveSettings").addEventListener("click", saveSettings);
  $("testApi").addEventListener("click", testApi);
  $("copyBtn").addEventListener("click", copyResults);
  $("csvBtn").addEventListener("click", exportCsv);
  $("search").addEventListener("input", (e) => { state.query = e.target.value; renderList(); });
  for (const btn of document.querySelectorAll(".filter")) {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.filter = btn.dataset.filter;
      renderList();
    });
  }
});
