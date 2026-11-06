"""Enregistre la vidéo de démonstration : navigateur visible, extension réelle, vraies vidéos YouTube.

Le navigateur doit être lancé avant, avec --remote-debugging-port=9333, et rester visible.
Le popup est ouvert dans sa propre fenêtre (popup.html?tabId=…), car le popup de la barre
d'outils n'est pas filmable par ce moyen. Le script s'arrête si une analyse échoue.

Prérequis : pip install playwright imageio-ffmpeg pillow, API lancée sur le port 8001.
Usage     : python tests/e2e/record_demo.py <dossier_ressources> <video.mp4> <resultats.json>
"""
import io
import json
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ASSETS, OUT, RESULTS = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
ROOT = Path(__file__).resolve().parents[2]
EXT_ID = "cmipaanhhmabdagfjolahadjmdmddlee"
APP = str(Path.home() / "Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app")
VIDEOS = ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=9bZkp7q19f0"]
API = "http://127.0.0.1:8001"
W, H, FPS = 1920, 1080, 12
HOLD = 1.45   # marge de lecture sur les plans fixes
POPUP_W = 380
BG, INK, ACCENT, MUTED = "#12111c", "#f1effa", "#d9a8ff", "#a49fbd"
SANS = "/System/Library/Fonts/Helvetica.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"


def font(size, path=SANS):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            test = f"{cur} {word}".strip()
            if draw.textlength(test, font=fnt) > width and cur:
                lines.append(cur)
                cur = word
            else:
                cur = test
        lines.append(cur)
    return lines


def popup_image(page):
    data = page.screenshot(type="jpeg", quality=90, scale="css", full_page=True)
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return img.crop((0, 0, min(POPUP_W, img.width), img.height))


class Recorder:
    def __init__(self):
        self.w = imageio_ffmpeg.write_frames(OUT, (W, H), fps=FPS, codec="libx264", quality=7,
                                             pix_fmt_out="yuv420p", macro_block_size=8)
        self.w.send(None)
        self.frames = 0
        self.left = self.right = None        # pages filmées
        self.imgs = {"left": None, "right": None}
        self.chapter, self.text, self.ring = "", "", None
        self.chapters = []

    def cap(self, chapter, text):
        if chapter != self.chapter:
            self.chapters.append((self.frames / FPS, chapter))
        self.chapter, self.text = chapter, text

    def shoot(self):
        for key, page in (("left", self.left), ("right", self.right)):
            if page is not None:
                if key == "right":      # la fenêtre est plus large que le popup : on recadre
                    self.imgs[key] = popup_image(page)
                else:
                    data = page.screenshot(type="jpeg", quality=75, scale="css")
                    self.imgs[key] = Image.open(io.BytesIO(data)).convert("RGB")

    def compose(self):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        area_h = 930
        if self.right is not None and self.imgs["right"] is not None:
            rw = 440
            r = self.imgs["right"]
            k = min(rw / r.width, area_h / r.height)
            rs = r.resize((int(r.width * k), int(r.height * k)), Image.LANCZOS)
            rx = W - 20 - rs.width
            img.paste(rs, (rx, 16))
            if self.ring:
                x, y, bw, bh = self.ring
                d.rounded_rectangle([rx + x * k - 5, 16 + y * k - 5, rx + (x + bw) * k + 5, 16 + (y + bh) * k + 5],
                                    radius=12, outline="#ffd54a", width=4)
            lw = W - rw - 60
        else:
            lw = W - 40
        if self.left is not None and self.imgs["left"] is not None:
            l = self.imgs["left"]
            k = min(lw / l.width, area_h / l.height)
            img.paste(l.resize((int(l.width * k), int(l.height * k)), Image.LANCZOS), (20, 16))
        self._caption(img, d)
        return img

    def _caption(self, img, d):
        d.rectangle([0, 950, W, H], fill="#1d1b2d")
        d.text((36, 964), self.chapter.upper(), font=font(22), fill=ACCENT)
        y = 996
        for line in wrap(d, self.text, font(31), W - 72)[:2]:
            d.text((36, y), line, font=font(31), fill=INK)
            y += 38

    def emit(self, img, seconds=None, count=None):
        n = count if count is not None else max(1, int(seconds * FPS))
        raw = img.tobytes()
        for _ in range(n):
            self.w.send(raw)
        self.frames += n

    def live(self, seconds):
        """Filme en temps réel."""
        start, target = time.time(), self.frames
        while time.time() - start < seconds:
            self.shoot()
            due = int((time.time() - start) * FPS)
            have = self.frames - target
            self.emit(self.compose(), count=max(1, due - have))

    def still(self, seconds):
        """Tient l'image à l'écran pour laisser le temps de lire."""
        self.shoot()
        self.emit(self.compose(), seconds * HOLD)

    def card(self, title, body, seconds, picture=None, mono=None):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((90, 70), title, font=font(62), fill=INK)
        d.rectangle([90, 152, 300, 157], fill=ACCENT)
        y = 190
        for line in wrap(d, body, font(38), W - 180):
            d.text((90, y), line, font=font(38), fill=INK)
            y += 54
        if mono:
            y += 12
            box_h = min(H - y - 60, 34 * len(mono) + 40)
            d.rounded_rectangle([90, y, W - 90, y + box_h], radius=14, fill="#000000")
            for i, line in enumerate(mono):
                d.text((120, y + 20 + 34 * i), line[:96], font=font(25, MONO), fill="#9be8b4")
        if picture:
            p = Image.open(picture).convert("RGB")
            top = y + 16
            k = min((W - 180) / p.width, (H - top - 50) / p.height)
            p = p.resize((int(p.width * k), int(p.height * k)), Image.LANCZOS)
            img.paste(p, ((W - p.width) // 2, top))
        self.emit(img, seconds * HOLD)

    def close(self):
        self.w.close()


def open_video(yt, url):
    """Ouvre une vidéo, attend son titre réel et met la lecture en pause."""
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


def main():
    popup_w, top = 400, 30
    results = {"videos": []}
    rec = Recorder()
    rec.card("Commentomètre", "Analyse de sentiment des commentaires YouTube\nTP3 Cloud Computing, ENSAM Rabat, filière INDIA\nZaid Hsain, 2026-2027", 7)
    rec.card("Le problème", "Une vidéo reçoit des centaines de commentaires. Les lire tous prend du temps, et l'impression qu'on en garde est subjective. "
             "L'objectif : une extension Chrome qui les lit, les envoie à une API de machine learning et affiche un bilan chiffré.", 13)
    rec.card("Architecture", "L'extension lit la page, l'API FastAPI applique le modèle TF-IDF + régression logistique.", 16, picture=ASSETS / "architecture.png")
    rec.card("Déroulement d'une analyse", "Du clic sur le bouton jusqu'à l'affichage du bilan.", 14, picture=ASSETS / "sequence.png")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        yt = next(pg for pg in ctx.pages if "youtube.com" in pg.url)

        # --- API
        tech = ctx.new_page()
        rec.left = tech
        tech.goto(f"{API}/health")
        rec.cap("L'API", "GET /health : l'API répond, le modèle est chargé, sa version est indiquée.")
        rec.still(9)
        tech.goto(f"{API}/docs", wait_until="networkidle")
        tech.wait_for_timeout(800)
        rec.cap("L'API", "FastAPI génère cette documentation Swagger à partir des schémas Pydantic.")
        rec.still(10)

        # --- Extension installée
        tech.goto(f"chrome://extensions/?id={EXT_ID}")
        tech.wait_for_timeout(1200)
        rec.cap("Installation", "chrome://extensions, mode développeur, puis « Charger l'extension non empaquetée » et le dossier chrome-extension. Elle est ici déjà installée.")
        rec.still(14)
        rec.left = None
        tech.close()

        # --- Analyse sur une vraie vidéo
        yt.bring_to_front()
        subprocess.run(["open", "-a", APP], timeout=10)
        print("Vidéo 1 :", open_video(yt, VIDEOS[0]), flush=True)

        helper = ctx.new_page()
        helper.goto(f"chrome-extension://{EXT_ID}/popup.html")
        sw, sh = helper.evaluate("() => [screen.availWidth, screen.availHeight]")
        print("Écran :", sw, sh, flush=True)
        tab_id = helper.evaluate("async () => (await chrome.tabs.query({url: 'https://www.youtube.com/watch*'}))[0].id")
        with ctx.expect_page() as newp:
            helper.evaluate(f"""() => chrome.windows.create({{url: 'popup.html?tabId={tab_id}', type: 'popup',
                width: {popup_w}, height: {min(sh - 40, 860)}, left: {sw - popup_w - 6}, top: {top}}})""")
        popup = newp.value
        helper.close()
        yt.bring_to_front()
        popup.wait_for_load_state()
        popup.evaluate(f"chrome.storage.local.set({{apiUrl: '{API}', maxComments: '100', includeReplies: false, theme: 'light'}})")
        popup.reload()
        popup.wait_for_timeout(600)
        rec.left, rec.right = yt, popup

        def click(selector, hold=0.7):
            box = popup.locator(selector).bounding_box()
            rec.ring = (box["x"], box["y"], box["width"], box["height"])
            rec.still(hold)
            popup.click(selector)
            rec.ring = None

        def analyze(label):
            click("#analyzeBtn")
            end = time.time() + 100
            while time.time() < end and not (popup.is_visible("#results") or popup.is_visible("#error")):
                rec.live(0.5)
            if popup.is_visible("#error"):
                msg = popup.inner_text("#error")
                print(label, "ERREUR :", msg, flush=True)
                return None
            stats = read_stats(popup)
            print(label, stats, flush=True)
            return stats

        rec.cap("Démonstration", "Une vraie vidéo YouTube à gauche, le popup de l'extension à droite.")
        rec.still(7)
        click("#settingsBtn")
        rec.cap("Réglages", "Adresse de l'API, nombre de commentaires à lire, option pour inclure les réponses.")
        rec.still(7)
        click("#testApi")
        popup.wait_for_timeout(500)
        rec.cap("Réglages", f"Test de connexion : {popup.inner_text('#apiStatus')}")
        rec.still(6)
        click("#settingsBtn")

        rec.cap("Analyse", "L'extension fait défiler la page pour que YouTube charge les commentaires, puis les envoie à l'API.")
        stats = analyze("Vidéo 1")
        if stats is None:
            raise SystemExit("Vidéo 1 sans résultat : enregistrement abandonné")
        else:
            results["videos"].append(stats)
            popup_image(popup).save(ASSETS / "real_1.png")
            rec.cap("Résultat", f"{stats['total']} commentaires analysés. {stats['moodLabel']}, score {stats['score']}.")
            rec.still(11)
            rec.cap("Résultat", f"Temps de réponse de l'API : {stats['latency']} ms. Confiance moyenne : {stats['conf']}.")
            rec.still(8)
            for sel, txt in ((".filter[data-filter='1']", "Filtre : uniquement les commentaires positifs."),
                             (".filter[data-filter='0']", "Filtre : les commentaires neutres, sans mot d'opinion reconnu par le modèle."),
                             (".filter[data-filter='-1']", "Filtre : les négatifs, avec la confiance du modèle pour chacun."),
                             (".filter[data-filter='all']", "Retour à la liste complète.")):
                click(sel)
                rec.cap("Filtres", txt)
                rec.still(7)
            popup.fill("#search", "rick")
            rec.cap("Recherche", "La recherche filtre par mot ou par pseudo.")
            rec.still(7)
            popup.fill("#search", "")
            click("#themeBtn")
            rec.cap("Mode sombre", "Le thème sombre, mémorisé d'une session à l'autre.")
            rec.still(8)
            popup_image(popup).save(ASSETS / "real_dark.png")
            click("#themeBtn")
            click("#copyBtn")
            popup.wait_for_timeout(250)
            copied = popup.inner_text("#copyBtn")
            print("Bouton copier :", copied, flush=True)
            rec.cap("Export", "Le bouton Copier place le résumé et la liste dans le presse-papiers." if "Copié" in copied else "Bouton Copier.")
            rec.still(6)

        # --- Deuxième vidéo
        print("Vidéo 2 :", open_video(yt, VIDEOS[1]), flush=True)
        rec.cap("Deuxième vidéo", "Même analyse sur une autre vidéo très commentée.")
        rec.still(5)
        stats = analyze("Vidéo 2")
        if stats is None:
            raise SystemExit("Vidéo 2 sans résultat : enregistrement abandonné")
        else:
            results["videos"].append(stats)
            popup_image(popup).save(ASSETS / "real_2.png")
            rec.cap("Deuxième vidéo", f"{stats['total']} commentaires. {stats['moodLabel']}, score {stats['score']}.")
            rec.still(11)

        # --- Erreur réseau
        click("#settingsBtn")
        popup.fill("#apiUrl", "http://127.0.0.1:9")
        click("#saveSettings")
        click("#settingsBtn")
        rec.cap("Gestion d'erreur", "API volontairement injoignable : l'extension l'explique au lieu de rester bloquée.")
        analyze("Erreur")
        if "joindre l'API" not in popup.inner_text("#error"):
            raise SystemExit("L'erreur affichée n'est pas celle du sous-titre : enregistrement abandonné")
        rec.still(8)
        popup.evaluate(f"chrome.storage.local.set({{apiUrl: '{API}'}})")
        rec.left = rec.right = None

    tests = (ASSETS / "pytest_out.txt").read_text().strip()
    integ = (ASSETS / "integration_out.txt").read_text().splitlines()
    rec.chapter = ""
    rec.card("Tests", f"pytest : {tests}\nTest d'intégration contre l'API en local :", 15, mono=integ)
    rec.card("Performances du modèle", "Accuracy 89,45 % sur 7 290 commentaires de test. F1 : négatif 0,81, neutre 0,94, positif 0,90. 0,7 ms pour un lot de 50.", 14,
             picture=ROOT / "reports/figures/confusion_matrix.png")
    rec.card("Une limite importante", "Le signe de la polarité TextBlob reproduit 100 % des 37 149 étiquettes du jeu de données. Le modèle apprend donc à imiter TextBlob, pas un jugement humain. "
             "Il est aussi entraîné sur de l'anglais : sur une vidéo commentée en arabe et en darija, 93 % des commentaires sont sortis en neutre.", 16)
    rec.card("État du projet", "Modèle, API, extension et tests fonctionnent en local. Le Dockerfile est prêt, mais l'image n'a pas encore été construite et l'API n'est pas encore en ligne sur Hugging Face.", 12)
    results["duration_s"] = round(rec.frames / FPS, 1)
    results["chapters"] = [[round(t, 1), c] for t, c in rec.chapters]
    rec.close()
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("Durée :", results["duration_s"], "s", flush=True)


if __name__ == "__main__":
    main()
