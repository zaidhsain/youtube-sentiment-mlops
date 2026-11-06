"""Enregistre la vidéo de démonstration : uniquement YouTube et le système, sans texte ajouté.

Séquence : installation dans chrome://extensions, appel réel à l'API dans Swagger, analyses
de vraies vidéos YouTube, toutes les fonctions du popup, puis une API injoignable.

Limites de la capture : le dialogue natif de choix de dossier n'est pas filmable, l'extension
est donc chargée par la commande Extensions.loadUnpacked ; et le popup est ouvert dans sa propre
fenêtre (popup.html?tabId=…), car le popup de la barre d'outils n'est pas filmable non plus.
Le script s'arrête si une analyse échoue.

Prérequis : pip install playwright imageio-ffmpeg pillow, API accessible (variable API_URL).
Usage     : API_URL=<url> python tests/e2e/record_demo.py <video.mp4> <resultats.json> <dossier_captures>
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

OUT, RESULTS, SHOTS = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
ROOT = Path(__file__).resolve().parents[2]
EXT = str(ROOT / "chrome-extension")
EXT_ID = "cmipaanhhmabdagfjolahadjmdmddlee"
API = os.environ.get("API_URL", "http://127.0.0.1:8001")
APP = Path.home() / "Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app"
BIN = APP / "Contents/MacOS/Google Chrome for Testing"
PROFILE = Path.home() / ".commentometre-navigateur"
VIDEOS = {
    "rick": "https://www.youtube.com/watch?v=m85MeUJCYac",
    "gangnam": "https://www.youtube.com/watch?v=9bZkp7q19f0",
    "shape": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
}
W, H, FPS = 1920, 1080, 12
POPUP_W = 380
BG = "#000000"


class Recorder:
    def __init__(self):
        self.w = imageio_ffmpeg.write_frames(OUT, (W, H), fps=FPS, codec="libx264", quality=7,
                                             pix_fmt_out="yuv420p", macro_block_size=8)
        self.w.send(None)
        self.frames = 0
        self.left = self.right = None
        self.imgs = {"left": None, "right": None}
        self.place = {}                # panneau -> (x, y, échelle css vers image finale)
        self.cursor = (W // 2, H // 2)

    def shoot(self):
        if self.left is not None:
            self.imgs["left"] = Image.open(io.BytesIO(self.left.screenshot(type="jpeg", quality=80))).convert("RGB")
        if self.right is not None:
            img = Image.open(io.BytesIO(self.right.screenshot(type="jpeg", quality=90, full_page=True))).convert("RGB")
            dpr = self.right.evaluate("() => devicePixelRatio")
            self.imgs["right"] = img.crop((0, 0, min(int(POPUP_W * dpr), img.width), img.height))
            self.right_dpr = dpr

    def compose(self):
        img = Image.new("RGB", (W, H), BG)
        space = W
        if self.right is not None and self.imgs["right"] is not None:
            r = self.imgs["right"]
            k = min(470 / r.width, H / r.height)
            rs = r.resize((int(r.width * k), int(r.height * k)), Image.LANCZOS)
            x = W - rs.width
            img.paste(rs, (x, 0))
            self.place["right"] = (x, 0, k * self.right_dpr)
            space = x - 8
        if self.left is not None and self.imgs["left"] is not None:
            l = self.imgs["left"]
            k = min(space / l.width, H / l.height)
            ls = l.resize((int(l.width * k), int(l.height * k)), Image.LANCZOS)
            x, y = (space - ls.width) // 2, (H - ls.height) // 2
            img.paste(ls, (x, y))
            css_w = self.left.evaluate("() => innerWidth")
            self.place["left"] = (x, y, ls.width / css_w)
        self._draw_cursor(img)
        return img

    def _draw_cursor(self, img):
        x, y = self.cursor
        pts = [(x, y), (x, y + 26), (x + 7, y + 20), (x + 12, y + 31), (x + 17, y + 29), (x + 12, y + 18), (x + 21, y + 18)]
        ImageDraw.Draw(img).polygon(pts, fill="white", outline="black")

    def emit(self, img, count):
        raw = img.tobytes()
        for _ in range(count):
            self.w.send(raw)
        self.frames += count

    def live(self, seconds):
        start, base = time.time(), self.frames
        while time.time() - start < seconds:
            self.shoot()
            due = int((time.time() - start) * FPS)
            self.emit(self.compose(), max(1, due - (self.frames - base)))

    def still(self, seconds):
        self.shoot()
        self.emit(self.compose(), max(1, int(seconds * FPS)))

    def glide(self, target, seconds=0.5):
        x0, y0 = self.cursor
        steps = max(1, int(seconds * FPS))
        for i in range(1, steps + 1):
            t = i / steps
            t = t * t * (3 - 2 * t)
            self.cursor = (int(x0 + (target[0] - x0) * t), int(y0 + (target[1] - y0) * t))
            self.emit(self.compose(), 1)

    def point(self, panel, locator):
        box = locator.bounding_box()
        ox, oy, k = self.place[panel]
        self.glide((int(ox + (box["x"] + box["width"] / 2) * k), int(oy + (box["y"] + box["height"] / 2) * k)))

    def click(self, panel, locator):
        self.shoot()
        self.compose()
        self.point(panel, locator)
        self.emit(self.compose(), 4)
        locator.click()

    def close(self):
        self.w.close()


def install(rec):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            tempfile.mkdtemp(), channel="chromium", headless=False,
            args=["--enable-unsafe-extension-debugging", "--lang=fr"],
            ignore_default_args=["--disable-extensions"], viewport={"width": 1200, "height": 760})
        page = ctx.pages[0]
        page.goto("chrome://extensions")
        page.wait_for_timeout(1200)
        rec.left = page
        rec.still(5)
        rec.click("left", page.locator("#devMode"))
        rec.still(5)
        rec.shoot(); rec.compose()
        rec.point("left", page.locator("#loadUnpacked"))
        rec.still(5)
        ctx.browser.new_browser_cdp_session().send("Extensions.loadUnpacked", {"path": EXT})
        page.wait_for_timeout(1000)
        rec.still(9)
        rec.left = None
        ctx.close()


def launch_browser():
    subprocess.run(["pkill", "-f", "commentometre-navigateur"])
    time.sleep(2)
    subprocess.Popen([str(BIN), f"--user-data-dir={PROFILE}", f"--load-extension={EXT}", "--remote-debugging-port=9333",
                      "--no-first-run", "--no-default-browser-check", "--lang=fr",
                      "--window-position=0,30", "--window-size=1000,780", f"{API}/health"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(25):
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:9333/json/version", timeout=1)
            break
        except OSError:
            time.sleep(1)
    time.sleep(3)


def swagger(rec, ctx):
    page = ctx.pages[0]
    page.bring_to_front()
    page.wait_for_timeout(1500)
    warning = page.get_by_role("button", name="Continue")   # avertissement GitHub, une fois par session
    if warning.count():
        warning.click()
        page.wait_for_load_state("networkidle")
    page.goto(f"{API}/health")
    rec.left = page
    rec.still(7)
    page.goto(f"{API}/docs", wait_until="networkidle")
    page.wait_for_timeout(800)
    rec.still(6)
    rec.click("left", page.locator(".opblock-post .opblock-summary-control"))
    page.wait_for_timeout(600)
    rec.still(4)
    rec.click("left", page.locator(".try-out__btn"))
    page.wait_for_timeout(400)
    box = page.locator(".body-param__text")
    box.fill(json.dumps({"comments": ["I love this video, great work!", "This is the worst tutorial ever", "Posted on Monday"]}, indent=2))
    rec.still(6)
    rec.click("left", page.locator(".execute"))
    page.locator(".live-responses-table").wait_for(timeout=15000)
    page.locator(".live-responses-table").scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    rec.still(12)
    page.mouse.wheel(0, 350)
    page.wait_for_timeout(400)
    rec.still(9)
    rec.left = None
    return page


def open_video(yt, url):
    yt.goto(url, wait_until="domcontentloaded")
    end = time.time() + 25
    while time.time() < end and (yt.title().strip() in ("", "YouTube") or not yt.query_selector("ytd-comments#comments")):
        time.sleep(0.5)
    yt.wait_for_timeout(2500)
    yt.evaluate("() => document.querySelector('video')?.pause()")
    return yt.title()


def read_stats(popup):
    return {k: popup.inner_text(f"#{k}") for k in
            ("videoTitle", "total", "score", "moodLabel", "posPct", "neuPct", "negPct", "conf", "latency")}


def save_popup(rec, popup, name):
    rec.shoot()
    rec.imgs["right"].save(SHOTS / name)


def main():
    rec = Recorder()
    results = {"videos": []}
    install(rec)
    launch_browser()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        yt = swagger(rec, ctx)

        subprocess.run(["open", "-a", str(APP)], timeout=10)
        print("Vidéo 1 :", open_video(yt, VIDEOS["rick"]), flush=True)
        helper = ctx.new_page()
        helper.goto(f"chrome-extension://{EXT_ID}/popup.html")
        sw, sh = helper.evaluate("() => [screen.availWidth, screen.availHeight]")
        tab_id = helper.evaluate("async () => (await chrome.tabs.query({url: 'https://www.youtube.com/watch*'}))[0].id")
        with ctx.expect_page() as newp:
            helper.evaluate(f"""() => chrome.windows.create({{url: 'popup.html?tabId={tab_id}', type: 'popup',
                width: 400, height: {min(sh - 40, 860)}, left: {sw - 406}, top: 30}})""")
        popup = newp.value
        helper.close()
        yt.bring_to_front()
        popup.wait_for_load_state()
        popup.evaluate(f"chrome.storage.local.set({{apiUrl: '{API}', maxComments: '100', includeReplies: false, theme: 'light'}})")
        popup.reload()
        popup.wait_for_timeout(600)
        rec.left, rec.right = yt, popup
        rec.still(6)

        L = popup.locator

        def analyze(label, required=True):
            rec.click("right", L("#analyzeBtn"))
            end = time.time() + 120
            while time.time() < end and not (popup.is_visible("#results") or popup.is_visible("#error")):
                rec.live(0.5)
            if popup.is_visible("#error"):
                msg = popup.inner_text("#error")
                print(label, "ERREUR :", msg, flush=True)
                if required:
                    raise SystemExit(f"{label} sans résultat : enregistrement abandonné")
                return msg
            stats = read_stats(popup)
            print(label, stats, flush=True)
            results["videos"].append(stats)
            return stats

        def scroll_list(seconds=12):
            steps = int(seconds * 3)
            for _ in range(steps):
                popup.evaluate("() => document.querySelector('#commentList').scrollBy(0, 45)")
                rec.live(0.3)
            popup.evaluate("() => document.querySelector('#commentList').scrollTo(0, 0)")

        # Réglages et test de l'API
        rec.click("right", L("#settingsBtn"))
        rec.still(5)
        rec.click("right", L("#testApi"))
        popup.wait_for_timeout(500)
        rec.still(6)
        rec.click("right", L("#settingsBtn"))
        rec.still(2)

        # Vidéo 1 : toutes les fonctions
        analyze("Vidéo 1")
        rec.still(12)
        save_popup(rec, popup, "11_resultat_clair.png")
        scroll_list()
        for flt in ("1", "0", "-1"):
            rec.click("right", L(f".filter[data-filter='{flt}']"))
            rec.still(4)
            scroll_list(6)
        rec.click("right", L(".filter[data-filter='all']"))
        rec.still(3)
        rec.click("right", L("#search"))
        L("#search").press_sequentially("the", delay=180)
        rec.still(7)
        L("#search").fill("")
        rec.click("right", L("#themeBtn"))
        rec.still(6)
        save_popup(rec, popup, "12_resultat_sombre.png")
        scroll_list(6)
        rec.click("right", L("#themeBtn"))
        rec.still(3)
        rec.click("right", L("#copyBtn"))
        popup.wait_for_timeout(200)
        print("Copier :", popup.inner_text("#copyBtn"), flush=True)
        rec.still(4)
        rec.click("right", L("#csvBtn"))
        popup.wait_for_timeout(200)
        print("CSV :", popup.inner_text("#csvBtn"), flush=True)
        rec.still(4)

        # Vidéo 2 : 200 commentaires, réponses incluses
        print("Vidéo 2 :", open_video(yt, VIDEOS["gangnam"]), flush=True)
        rec.still(5)
        rec.click("right", L("#settingsBtn"))
        L("#maxComments").select_option("200")
        rec.still(3)
        rec.click("right", L("#includeReplies"))
        rec.still(3)
        rec.click("right", L("#saveSettings"))
        rec.still(3)
        rec.click("right", L("#settingsBtn"))
        analyze("Vidéo 2")
        rec.still(12)
        save_popup(rec, popup, "13_gangnam_style.png")
        scroll_list(10)
        rec.click("right", L(".filter[data-filter='-1']"))
        rec.still(5)
        rec.click("right", L(".filter[data-filter='all']"))
        rec.still(2)

        # Vidéo 3 : réglages par défaut
        rec.click("right", L("#settingsBtn"))
        L("#maxComments").select_option("100")
        rec.click("right", L("#includeReplies"))
        rec.click("right", L("#saveSettings"))
        rec.click("right", L("#settingsBtn"))
        print("Vidéo 3 :", open_video(yt, VIDEOS["shape"]), flush=True)
        rec.still(5)
        analyze("Vidéo 3")
        rec.still(12)
        scroll_list(8)

        # API injoignable
        rec.click("right", L("#settingsBtn"))
        L("#apiUrl").fill("http://127.0.0.1:9")
        rec.still(3)
        rec.click("right", L("#saveSettings"))
        rec.click("right", L("#settingsBtn"))
        msg = analyze("Erreur", required=False)
        if not isinstance(msg, str) or "joindre l'API" not in msg:
            raise SystemExit("L'erreur attendue n'est pas apparue : enregistrement abandonné")
        rec.still(9)
        popup.evaluate(f"chrome.storage.local.set({{apiUrl: '{API}'}})")

    results["duration_s"] = round(rec.frames / FPS, 1)
    rec.close()
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("Durée :", results["duration_s"], "s", flush=True)


if __name__ == "__main__":
    main()
