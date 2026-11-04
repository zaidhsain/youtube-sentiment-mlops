# Image de base légère
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=7860

# Hugging Face exécute le conteneur avec l'UID 1000 : on crée cet utilisateur (non-root).
RUN useradd -m -u 1000 user
WORKDIR /app

# 1) Dépendances d'abord : cette couche reste en cache tant que requirements-prod.txt ne change pas.
COPY --chown=user requirements-prod.txt .
RUN pip install -r requirements-prod.txt

# 2) Puis uniquement le code et les modèles nécessaires (voir .dockerignore).
COPY --chown=user src/__init__.py src/__init__.py
COPY --chown=user src/utils src/utils
COPY --chown=user src/api src/api
COPY --chown=user models models
COPY --chown=user app_api.py .

USER user
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/health')" || exit 1

CMD ["sh", "-c", "uvicorn app_api:app --host 0.0.0.0 --port ${PORT}"]
