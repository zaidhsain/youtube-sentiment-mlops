"""Construit docs/Rapport_Technique.pdf à partir de docs/RAPPORT_TECHNIQUE.md.

    pip install markdown playwright && playwright install chromium
    python docs/build_pdf.py [url_github] [url_api]

Conventions dans le Markdown :
  - un paragraphe « Tableau : légende » juste avant un tableau devient sa légende numérotée ;
  - le texte alternatif d'une image seule dans son paragraphe devient sa légende numérotée.
"""
import re
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent
SRC = DOCS / "RAPPORT_TECHNIQUE.md"
OUT = DOCS / "Rapport_Technique.pdf"
GITHUB = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/zaidhsain/youtube-sentiment-mlops"
API = sys.argv[2] if len(sys.argv) > 2 else "https://commentometre-api-q746jjrv766gc4j64-7860.app.github.dev"

AUTHOR = "Zaid Hsain"
SUPERVISOR = "Pr. Maria Zemzami"

CSS = """
@page { size: A4; }
:root { --ink: #1f1b16; --muted: #6b645a; --accent: #7b1e2b; --rule: #cfc6b8; }
body { font: 10.5pt/1.48 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
       color: var(--ink); hyphens: auto; -webkit-hyphens: auto; }
p { text-align: justify; margin: 0 0 .55em; orphans: 3; widows: 3; }
h2 { font-size: 15.5pt; font-weight: 600; color: var(--accent); margin: 1.3em 0 .5em;
     padding-bottom: 3px; border-bottom: .6pt solid var(--rule); break-after: avoid; }
h2.chapter { break-before: page; margin-top: 0; }
h3 { font-size: 11.5pt; font-style: italic; font-weight: 600; margin: .9em 0 .3em; break-after: avoid; }
code { font: 9pt "SF Mono", Menlo, Consolas, monospace; color: #4a4036; }
em { font-style: italic; }
strong { font-weight: 600; }
ul, ol { margin: 0 0 .7em 1.2em; padding: 0; }

table { border-collapse: collapse; width: 100%; margin: .2em 0 1.1em; font-size: 9.6pt;
        line-height: 1.35; break-inside: avoid; font-variant-numeric: tabular-nums; }
thead th { border-top: 1.2pt solid var(--ink); border-bottom: .6pt solid var(--ink);
           text-align: left; font-weight: 600; padding: 5px 8px; }
td { padding: 4px 8px; vertical-align: top; }
tbody tr:last-child td { border-bottom: 1.2pt solid var(--ink); }
td code { font-size: 8.4pt; }

.caption { text-align: center; font-size: 9.5pt; margin: 1em 0 .35em; break-after: avoid; }
.caption b, figcaption b { font-variant: small-caps; letter-spacing: .3px; color: var(--accent); }
figure { margin: .6em 0 .8em; text-align: center; break-inside: avoid; }
figure img { max-width: 76%; max-height: 62mm; }
figure img[src$=".svg"] { max-width: 100%; max-height: 84mm; width: 100%; }
figcaption { font-size: 9.5pt; font-style: italic; margin-top: .4em; }
td img { width: 100%; border: .5pt solid var(--rule); }
table.shots { width: 62%; margin-left: auto; margin-right: auto; }
table.shots td { width: 50%; text-align: center; border: 0 !important; }
table.shots thead th { border: 0; text-align: center; font-weight: normal; font-style: italic; font-size: 9pt; }

/* Page de garde */
.cover { height: 247mm; display: flex; flex-direction: column; text-align: center; break-after: page; }
.inst { font-size: 11pt; line-height: 1.5; letter-spacing: .3px; }
.inst .univ { font-variant: small-caps; font-size: 12.5pt; letter-spacing: .8px; }
.cover hr { width: 40%; border: 0; border-top: .6pt solid var(--ink); margin: 14px auto; }
.cover .kind { margin-top: 48mm; font-variant: small-caps; letter-spacing: 1.5px; color: var(--accent); font-size: 12pt; }
.cover h1 { font-size: 25pt; font-weight: 600; line-height: 1.2; margin: 10px 0 6px; }
.cover .subtitle { font-style: italic; font-size: 13pt; color: var(--muted); }
.cover .double { width: 62%; margin: 26px auto; border-top: 1.2pt solid var(--ink); border-bottom: .5pt solid var(--ink); height: 3px; }
.cover .people { display: flex; justify-content: space-between; text-align: left; width: 74%; margin: 18mm auto 0; font-size: 11.5pt; line-height: 1.6; }
.cover .people .lbl { font-style: italic; color: var(--muted); font-size: 10pt; }
.cover .links { margin-top: auto; font-size: 9pt; color: var(--muted); line-height: 1.6; }
.cover .year { margin-top: 6px; font-size: 11pt; }

/* Sommaire */
.toc { break-after: page; }
.toc h2 { margin-top: 0; }
.toc ol { list-style: none; margin: 0; padding: 0; font-size: 11pt; line-height: 1.9; }
.toc li.l2 { font-weight: 600; margin-top: 4px; }
.toc li.l3 { padding-left: 2.2em; font-size: 10.2pt; line-height: 1.6; color: var(--muted); }
"""

COVER = """<section class="cover">
  <div class="inst"><div class="univ">Université Mohammed V de Rabat</div>
    École Nationale Supérieure d'Arts et Métiers de Rabat<br>Filière INDIA</div>
  <hr>
  <div class="kind">Rapport de travaux pratiques · Cloud Computing · TP3</div>
  <h1>Analyse de sentiment<br>des commentaires YouTube</h1>
  <div class="subtitle">Du modèle d'apprentissage automatique au déploiement dans le cloud</div>
  <div class="double"></div>
  <div class="people">
    <div><span class="lbl">Réalisé par</span><br>{author}</div>
    <div style="text-align:right"><span class="lbl">Encadré par</span><br>{supervisor}</div>
  </div>
  <div class="links">Code source : {github}<br>API : {api}</div>
  <div class="year">Année universitaire 2026–2027</div>
</section>"""


def number_captions(html: str) -> str:
    n_tab = 0

    def tab(m):
        nonlocal n_tab
        n_tab += 1
        return f'<p class="caption"><b>Tableau {n_tab}</b> : {m.group(1)}</p>'

    html = re.sub(r"<p>Tableau : (.*?)</p>", tab, html)

    n_fig = 0

    def fig(m):
        nonlocal n_fig
        alt, src = m.group(1), m.group(2)
        n_fig += 1
        return (f'<figure><img src="{src}" alt="{alt}">'
                f"<figcaption><b>Figure {n_fig}</b> : {alt}</figcaption></figure>")

    # python-markdown produit <img alt="…" src="…" /> ; seules les images légendées sont numérotées
    html = re.sub(r'<p><img alt="([^"]+)" src="([^"]+)" ?/?></p>', fig, html)
    # Tableau de captures d'écran : mise en forme dédiée
    html = re.sub(r"<table>(\s*<thead>\s*<tr>\s*<th>[^<]*thème clair[^<]*</th>)",
                  r'<table class="shots">\1', html)
    return html


def build_toc(html: str) -> str:
    items = []
    for level, title in re.findall(r"<h([23])[^>]*>(.*?)</h\1>", html):
        items.append(f'<li class="l{level}">{title}</li>')
    return "<section class='toc'><h2>Sommaire</h2><ol>" + "".join(items) + "</ol></section>"


def main():
    md = SRC.read_text(encoding="utf-8")
    md = md.split("\n---\n", 1)[1] if "\n---\n" in md else md   # l'en-tête va sur la page de garde
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
    body = number_captions(body)
    toc = build_toc(body)

    html = (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f"{COVER.format(author=AUTHOR, supervisor=SUPERVISOR, github=GITHUB, api=API)}{toc}{body}</body></html>")
    tmp = DOCS / "_rapport.html"
    tmp.write_text(html, encoding="utf-8")

    footer = ("<div style='font: 9px Georgia, serif; color:#6b645a; width:100%; text-align:center'>"
              "Z. Hsain · TP3 Cloud Computing · <span class='pageNumber'></span></div>")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(tmp.as_uri(), wait_until="networkidle")
        page.pdf(path=str(OUT), format="A4", print_background=True, display_header_footer=True,
                 header_template="<span></span>", footer_template=footer,
                 margin={"top": "18mm", "bottom": "18mm", "left": "20mm", "right": "20mm"})
        browser.close()
    tmp.unlink()
    print(f"PDF généré : {OUT}")


if __name__ == "__main__":
    main()
