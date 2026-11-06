"""Test d'intégration contre une API réelle (locale OU publique sur GitHub Codespaces).

Usage :
  python tests/integration_check.py http://localhost:8000
  python tests/integration_check.py https://<nom-du-codespace>-7860.app.github.dev

Vérifie /health, /predict_batch, la gestion d'erreurs, mesure les temps de réponse
et contrôle la cohérence avec le modèle local (mêmes prédictions).
"""
import statistics
import sys
import time

import requests

SAMPLES = [
    "I love this video, amazing work!",
    "This is the worst tutorial ever, total waste of time",
    "Posted on Monday from Paris",
    "Thanks a lot, very helpful 😍",
    "the audio is terrible and annoying",
]


def main(base: str) -> int:
    base = base.rstrip("/")
    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'OK' if cond else 'ÉCHEC'}] {name} {extra}")

    print(f"API : {base}")
    t0 = time.perf_counter()
    h = requests.get(f"{base}/health", timeout=60)  # 1er appel : délai large pour une API distante
    check("/health", h.ok and h.json().get("model_loaded"), f"({(time.perf_counter() - t0) * 1000:.0f} ms)")

    r = requests.post(f"{base}/predict_batch", json={"comments": SAMPLES}, timeout=30)
    check("/predict_batch 5 commentaires", r.ok and len(r.json()["predictions"]) == 5)
    remote = [p["sentiment"] for p in r.json()["predictions"]] if r.ok else []

    try:
        sys.path.insert(0, ".")
        from src.api.predictor import SentimentPredictor
        local = [p["sentiment"] for p in SentimentPredictor().predict(SAMPLES)]
        check("cohérence local vs distant", local == remote, f"local={local} distant={remote}")
    except Exception as e:  # modèle local absent : on saute ce contrôle
        print(f"  [--] cohérence non vérifiée ({e})")

    check("batch vide -> 422",
          requests.post(f"{base}/predict_batch", json={"comments": []}, timeout=30).status_code == 422)

    for size in (10, 50, 100, 500):
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            requests.post(f"{base}/predict_batch", json={"comments": SAMPLES * (size // 5)}, timeout=30)
            times.append((time.perf_counter() - t0) * 1000)
        print(f"  batch {size:>3} : médiane {statistics.median(times):6.1f} ms (aller-retour réseau)")

    print("\nRÉSULTAT :", "SUCCÈS" if ok else "ÉCHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
