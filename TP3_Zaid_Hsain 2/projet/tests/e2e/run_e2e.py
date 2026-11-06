"""Test E2E : Chromium + extension non empaquetée + page YouTube simulée + API réelle.

Pour un test reproductible, indépendant du contenu de YouTube, on sert à l'URL
https://www.youtube.com/watch?v=demo une page qui reproduit la structure DOM des
commentaires (voir youtube_fixture.py). Tout autre trafic vers YouTube est bloqué.

Prérequis : pip install playwright && playwright install chromium
Usage     : python tests/e2e/run_e2e.py [url_api] [dossier_sortie]
            (API lancée au préalable, ex. uvicorn src.api.main:app --port 8001)
"""
import hashlib
import shutil
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from youtube_fixture import render  # noqa: E402

EXT = (HERE.parent.parent / "chrome-extension").resolve()
API = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001").rstrip("/")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/screenshots"); OUT.mkdir(parents=True, exist_ok=True)
VIDEO = "demo"


def ext_id(path: Path) -> str:
    h = hashlib.sha256(str(path).encode()).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in h)


def wait_until(cond, timeout_s):
    end = time.time() + timeout_s
    while time.time() < end:
        if cond():
            return
        time.sleep(0.3)
    raise TimeoutError("condition non atteinte")


profile = tempfile.mkdtemp()
vid_dir = Path(tempfile.mkdtemp())
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        profile, channel="chromium", headless=True,
        args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
        viewport={"width": 1280, "height": 860}, locale="en-US",
        record_video_dir=str(vid_dir), record_video_size={"width": 1280, "height": 860},
    )
    eid = ext_id(EXT)
    print("Extension ID:", eid)

    ctx.route("**/*youtube.com/**", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=render())
              if "/watch" in r.request.url else r.abort())
    yt = ctx.pages[0] if ctx.pages else ctx.new_page()
    yt.goto(f"https://www.youtube.com/watch?v={VIDEO}", wait_until="domcontentloaded")
    yt.wait_for_timeout(3000)
    yt.wait_for_timeout(2000)
    yt.screenshot(path=OUT / "01_youtube_video.png")

    popup = ctx.new_page()
    popup.set_viewport_size({"width": 400, "height": 760})
    popup.goto(f"chrome-extension://{eid}/popup.html")
    popup.wait_for_timeout(500)
    tab_id = popup.evaluate(
        "async () => (await chrome.tabs.query({url: 'https://www.youtube.com/watch*'}))[0]?.id")
    print("YouTube tab id:", tab_id)
    popup.evaluate(f"chrome.storage.local.set({{apiUrl: '{API}', maxComments: '100', theme: 'light'}})")
    popup.goto(f"chrome-extension://{eid}/popup.html?tabId={tab_id}")
    popup.wait_for_timeout(500)

    # Paramètres + test API
    popup.click("#settingsBtn"); popup.click("#testApi")
    wait_until(lambda: "OK" in popup.inner_text("#apiStatus") or len(popup.inner_text("#apiStatus")) > 12, 60)
    print("API status:", popup.inner_text("#apiStatus"))
    popup.screenshot(path=OUT / "02_popup_settings.png", full_page=True)
    popup.click("#settingsBtn")

    # Analyse
    t0 = time.time()
    popup.click("#analyzeBtn")
    popup.wait_for_timeout(1200)
    popup.screenshot(path=OUT / "03_popup_loading.png")
    wait_until(lambda: popup.is_visible("#results") or popup.is_visible("#error"), 120)
    print(f"Analyse terminée en {time.time() - t0:.1f}s")
    if popup.is_visible("#error"):
        print("ERREUR:", popup.inner_text("#error"))
        popup.screenshot(path=OUT / "99_error.png", full_page=True)
    else:
        print("Total:", popup.inner_text("#total"), "| +", popup.inner_text("#posPct"),
              "| =", popup.inner_text("#neuPct"), "| -", popup.inner_text("#negPct"),
              "| latence", popup.inner_text("#latency"), "ms")
        popup.screenshot(path=OUT / "04_popup_results_light.png", full_page=True)
        popup.click(".filter[data-filter='-1']"); popup.wait_for_timeout(600)
        popup.screenshot(path=OUT / "05_filter_negative.png", full_page=True)
        popup.click(".filter[data-filter='1']"); popup.wait_for_timeout(600)
        popup.click("#themeBtn"); popup.wait_for_timeout(600)
        popup.screenshot(path=OUT / "06_popup_dark_positive.png", full_page=True)
        popup.click(".filter[data-filter='all']")
        popup.fill("#search", "love"); popup.wait_for_timeout(600)
        popup.screenshot(path=OUT / "07_search_dark.png", full_page=True)
        popup.fill("#search", ""); popup.click("#themeBtn"); popup.wait_for_timeout(600)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        popup.click("#copyBtn"); popup.wait_for_timeout(400)
        clip = popup.evaluate("navigator.clipboard.readText()")
        (OUT / "copied_results.txt").write_text(clip)
        print("Presse-papiers (début):", clip[:200].replace("\n", " | "))
        with popup.expect_download() as dl:
            popup.click("#csvBtn")
        dl.value.save_as(OUT / "export.csv")
        print("CSV exporté:", (OUT / "export.csv").stat().st_size, "octets")

    # Inclure les réponses (threads)
    popup.click("#settingsBtn"); popup.check("#includeReplies"); popup.click("#saveSettings"); popup.click("#settingsBtn")
    popup.click("#analyzeBtn"); popup.wait_for_timeout(300)
    wait_until(lambda: popup.is_visible("#results") and not popup.is_disabled("#analyzeBtn"), 120)
    print("Avec réponses -> total:", popup.inner_text("#total"))
    popup.fill("#search", "réponse"); popup.fill("#search", "")
    popup.screenshot(path=OUT / "08b_with_replies.png", full_page=True)

    # Erreur réseau : API injoignable
    popup.evaluate("chrome.storage.local.set({apiUrl: 'http://127.0.0.1:9'})")
    popup.click("#analyzeBtn")
    wait_until(lambda: popup.is_visible("#error") and "API" in popup.inner_text("#error"), 120)
    print("Erreur réseau affichée:", popup.inner_text("#error"))
    popup.screenshot(path=OUT / "08_network_error.png")
    popup.evaluate(f"chrome.storage.local.set({{apiUrl: '{API}'}})")

    yt.bring_to_front(); yt.wait_for_timeout(500)
    yt.screenshot(path=OUT / "09_youtube_comments_loaded.png")
    popup_video = popup.video
    ctx.close()
    if popup_video:
        shutil.copy(popup_video.path(), OUT / "demo_popup.webm")
shutil.rmtree(profile, ignore_errors=True)
shutil.rmtree(vid_dir, ignore_errors=True)
print("OK")
