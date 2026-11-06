"""Point d'entrée de production (Docker / GitHub Codespaces).

Réutilise l'application modulaire de src/api et la lance sur le port attendu
pour la démonstration (7860), configurable via la variable d'environnement PORT.
"""
import os

from src.api.main import app  # noqa: F401  (exposé pour `uvicorn app_api:app`)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_api:app", host="0.0.0.0", port=int(os.getenv("PORT", 7860)),
                workers=1, log_level="info")
