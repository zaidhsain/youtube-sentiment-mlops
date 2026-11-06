"""Construit docs/Guide_Utilisateur.pdf à partir de docs/GUIDE_UTILISATEUR.md."""
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent
CSS = """body{font:11pt/1.5 "Iowan Old Style",Palatino,Georgia,serif;color:#1f1b16}
h1{color:#7b1e2b;font-size:21pt;border-bottom:1pt solid #cfc6b8;padding-bottom:6px}
h2{color:#7b1e2b;font-size:14pt;margin-top:1.1em;break-after:avoid}
img{display:block;width:62mm;margin:8px auto;border:.5pt solid #cfc6b8;break-inside:avoid}
table{border-collapse:collapse;width:100%;font-size:10pt;break-inside:avoid}
th{border-top:1.2pt solid #1f1b16;border-bottom:.6pt solid #1f1b16;text-align:left;padding:5px 8px}
td{padding:4px 8px;vertical-align:top}tbody tr:last-child td{border-bottom:1.2pt solid #1f1b16}
code{font:9pt Menlo,monospace}"""
html = markdown.markdown((DOCS / "GUIDE_UTILISATEUR.md").read_text(encoding="utf-8"), extensions=["tables"])
tmp = DOCS / "_guide.html"
tmp.write_text(f"<!doctype html><html lang='fr'><meta charset='utf-8'><style>{CSS}</style><body>{html}</body></html>", encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(tmp.as_uri(), wait_until="networkidle")
    pg.pdf(path=str(DOCS / "Guide_Utilisateur.pdf"), format="A4", print_background=True,
           margin={"top": "18mm", "bottom": "18mm", "left": "20mm", "right": "20mm"})
    b.close()
tmp.unlink()
