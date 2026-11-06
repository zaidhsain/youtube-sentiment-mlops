// Content script : s'exécute DANS la page YouTube et extrait les commentaires du DOM.
// YouTube charge les commentaires dynamiquement (lazy loading au scroll) :
// on fait défiler la page jusqu'à atteindre le nombre voulu ou jusqu'à stagnation.

(() => {
  if (window.__ytSentimentLoaded) return; // évite une double injection
  window.__ytSentimentLoaded = true;

  const THREAD_SEL = "ytd-comment-thread-renderer";
  const TEXT_SEL = "#content-text";
  const AUTHOR_SEL = "#author-text";
  const REPLY_SEL = "ytd-comment-replies-renderer";

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function collect(includeReplies) {
    const out = [];
    const seen = new Set();
    for (const thread of document.querySelectorAll(THREAD_SEL)) {
      // Tous les blocs de texte du thread : le 1er est le commentaire principal,
      // les suivants (dans ytd-comment-replies-renderer) sont des réponses déjà dépliées.
      for (const node of thread.querySelectorAll(TEXT_SEL)) {
        const isReply = !!node.closest(REPLY_SEL);
        if (isReply && !includeReplies) continue;
        const text = node.innerText.trim();
        if (!text || seen.has(text)) continue;
        seen.add(text);
        const container = node.closest("ytd-comment-view-model, ytd-comment-renderer") || thread;
        const author = container.querySelector(AUTHOR_SEL)?.innerText.trim() || "";
        out.push({ text, author, isReply });
      }
    }
    return out;
  }

  // YouTube ne demande les commentaires qu'à l'approche de leur section, et la réponse
  // peut tarder : sans cette attente, on conclurait à tort qu'il n'y en a aucun.
  async function waitForFirstComments(timeoutMs = 12000) {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      if (document.querySelector(THREAD_SEL)) return true;
      document.querySelector("ytd-comments#comments")?.scrollIntoView();
      await sleep(400);
    }
    return false;
  }

  async function extract({ max = 100, includeReplies = false, autoScroll = true } = {}) {
    if (!location.pathname.startsWith("/watch")) {
      throw new Error("Ouvrez une vidéo YouTube (URL /watch).");
    }
    const startY = window.scrollY;
    if (autoScroll) {
      await waitForFirstComments();
      let last = -1, stale = 0;
      while (stale < 4) {
        const n = document.querySelectorAll(THREAD_SEL).length;
        if (n >= max) break;
        stale = n === last ? stale + 1 : 0;
        last = n;
        window.scrollTo(0, document.documentElement.scrollHeight);
        await sleep(900);
      }
      window.scrollTo(0, startY);
    }
    const comments = collect(includeReplies).slice(0, max);
    const title = document.querySelector("h1.ytd-watch-metadata, h1.title")?.innerText.trim() || document.title;
    return { comments, title, url: location.href };
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type !== "EXTRACT_COMMENTS") return;
    extract(msg.options)
      .then((data) => sendResponse({ ok: true, ...data }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // réponse asynchrone
  });
})();
