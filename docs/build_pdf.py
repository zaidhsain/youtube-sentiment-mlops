"""Génère docs/Rapport_Technique.pdf depuis docs/RAPPORT_TECHNIQUE.md.

Prérequis : pip install markdown playwright && playwright install chromium
Usage     : python docs/build_pdf.py [url_github] [url_api]
"""
import re
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent
SRC = DOCS / "RAPPORT_TECHNIQUE.md"
OUT = DOCS / "Rapport_Technique.pdf"
GITHUB = sys.argv[1] if len(sys.argv) > 1 else "(à compléter)"
API = sys.argv[2] if len(sys.argv) > 2 else "(à compléter)"

CSS = """
@page { size: A4; margin: 18mm 17mm 18mm 17mm; }
body { font: 10.4pt/1.5 "Helvetica Neue", Arial, sans-serif; color: #1c2024; }
h1 { display: none; }
h2 { font-size: 15pt; color: #1a2b6d; border-bottom: 2px solid #c5cff0; padding-bottom: 3px;
     margin: 22px 0 10px; break-after: avoid; }
h2:not(:first-of-type) { break-before: auto; }
h3 { font-size: 12pt; color: #1a2b6d; break-after: avoid; }
p, li { text-align: justify; }
strong { color: #111; }
code { font: 9pt Menlo, monospace; background: #f1f3f7; padding: 1px 4px; border-radius: 3px; }
pre { background: #f1f3f7; padding: 8px; border-radius: 6px; font-size: 8.6pt; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9.2pt; break-inside: avoid; }
th { background: #1a2b6d; color: #fff; text-align: left; padding: 5px 7px; }
td { border-bottom: 1px solid #dfe3ea; padding: 4px 7px; vertical-align: top; }
tr:nth-child(even) td { background: #f7f8fb; }
img { max-width: 100%; border-radius: 6px; }
td img { border: 1px solid #dfe3ea; }
p:has(> img) { text-align: center; break-inside: avoid; }
blockquote { border-left: 3px solid #c5cff0; margin: 0; padding-left: 10px; color: #555; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: space-between;
         text-align: center; break-after: page; }
.cover .head { display: flex; justify-content: space-between; font-size: 10pt; font-weight: 600; text-align: left; }
.cover .title { color: #1a2b6d; }
.cover .title .tp { font-size: 26pt; font-weight: 800; border-bottom: 2px solid #1a2b6d; padding-bottom: 10px; }
.cover .title .sub { font-size: 20pt; font-weight: 700; color: #111; margin-top: 22px; }
.cover .title .sub2 { font-size: 13pt; margin-top: 8px; }
.cover .kpis { display: flex; gap: 10px; justify-content: center; margin-top: 30px; }
.cover .kpi { border: 1px solid #c5cff0; border-radius: 8px; padding: 10px 14px; min-width: 110px; }
.cover .kpi b { display: block; font-size: 17pt; color: #1a2b6d; }
.cover .kpi span { font-size: 8.5pt; color: #555; }
.cover .meta { font-size: 10.5pt; line-height: 1.8; }
.toc { break-after: page; }
.toc ol { line-height: 2; font-size: 11pt; }
"""

COVER = """<section class="cover">
 <div class="head"><div>Université Mohammed V<br>ENSAM Rabat</div>
   <div style="text-align:right">Année universitaire 2026/27<br>Filière INDIA</div></div>
 <div class="title">
   <div class="tp">TP3 : Projet ML complet</div>
   <div class="sub">Analyse de sentiment des commentaires YouTube</div>
   <div class="sub2">Du développement au déploiement cloud — Rapport technique</div>
   <div class="kpis">
     <div class="kpi"><b>89,5 %</b><span>accuracy (test)</span></div>
     <div class="kpi"><b>0,81</b><span>F1 minimal par classe</span></div>
     <div class="kpi"><b>0,7 ms</b><span>inférence, lot de 50</span></div>
     <div class="kpi"><b>38 + E2E</b><span>tests automatisés</span></div>
   </div>
 </div>
 <div class="meta">Réalisé par : <b>Nom Prénom</b><br>Encadrante : Prof. Maria Zemzami<br>
   Dépôt : {github}<br>API : {api}<br>Novembre 2026</div>
</section>"""


def main():
    md = SRC.read_text(encoding="utf-8")
    md = md.replace("{{GITHUB_URL}}", GITHUB).replace("{{API_URL}}", API)
    # Retire l'en-tête (titre + ligne de méta), déjà présents sur la page de garde
    md = md.split("\n---\n", 1)[1] if "\n---\n" in md else md
    # {width=48%} -> attribut style (attr_list)
    md = re.sub(r"\{width=(\d+%)\}", r'{: style="width:\1" }', md)
    body = markdown.markdown(md, extensions=["tables", "attr_list", "fenced_code", "sane_lists"])
    titles = re.findall(r"<h2>(.*?)</h2>", body)
    num_re = re.compile(r"^\d+\.\s*")
    toc = "<section class='toc'><h2>Sommaire</h2><ol>" + "".join(
        "<li>" + num_re.sub("", t) + "</li>" for t in titles) + "</ol></section>"
    html = (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body>{COVER.format(github=GITHUB, api=API)}{toc}{body}</body></html>")
    tmp = DOCS / "_rapport.html"
    tmp.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(tmp.as_uri(), wait_until="networkidle")
        pg.pdf(path=str(OUT), format="A4", print_background=True, display_header_footer=True,
               header_template="<span></span>",
               footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#888'>"
                               "TP3 Cloud Computing — Analyse de sentiment YouTube — "
                               "<span class='pageNumber'></span>/<span class='totalPages'></span></div>",
               margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
        b.close()
    tmp.unlink()
    print(f"PDF généré : {OUT}")


if __name__ == "__main__":
    main()
