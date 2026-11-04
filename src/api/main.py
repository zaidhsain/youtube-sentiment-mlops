"""Phase 4 : API REST FastAPI.

Lancement local : uvicorn src.api.main:app --reload --port 8000
Documentation interactive : http://localhost:8000/docs
"""
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.predictor import SentimentPredictor
from src.api.schemas import BatchRequest, BatchResponse, HealthResponse
from src.utils.logger import get_logger

logger = get_logger("api")
STATE = {"predictor": None, "started": time.time()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Le modèle est chargé UNE fois au démarrage, pas à chaque requête.
    try:
        STATE["predictor"] = SentimentPredictor()
        logger.info("Modèle chargé (version %s)", STATE["predictor"].version)
    except Exception:
        logger.exception("Échec du chargement du modèle")
    yield
    STATE["predictor"] = None


app = FastAPI(
    title="Commentomètre API",
    description="Analyse de sentiment (négatif / neutre / positif) de commentaires YouTube "
                "(TF-IDF + régression logistique).",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS : autorise l'extension Chrome (origine chrome-extension://<id>) et le dev local.
# ALLOWED_ORIGINS permet d'ajouter des origines en production sans changer le code.
extra_origins = [o for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=extra_origins + ["https://www.youtube.com"],
    allow_origin_regex=r"^(chrome-extension://[a-z]{32}|http://(localhost|127\.0\.0\.1)(:\d+)?)$",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    logger.info("%s %s -> %d (%.1f ms)", request.method, request.url.path,
                response.status_code, (time.perf_counter() - t0) * 1000)
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("Erreur non gérée sur %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Erreur interne du serveur"})


def get_predictor() -> SentimentPredictor:
    if STATE["predictor"] is None:
        raise HTTPException(status_code=503, detail="Modèle non disponible")
    return STATE["predictor"]


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Commentomètre API", "docs": "/docs", "health": "/health"}


@app.get("/health", response_model=HealthResponse, tags=["monitoring"])
def health():
    p = STATE["predictor"]
    return HealthResponse(
        status="ok" if p else "degraded",
        model_loaded=p is not None,
        model_version=p.version if p else "none",
        uptime_seconds=round(time.time() - STATE["started"], 1),
    )


@app.post("/predict_batch", response_model=BatchResponse, tags=["prediction"])
def predict_batch(req: BatchRequest):
    predictor = get_predictor()
    t0 = time.perf_counter()
    preds = predictor.predict(req.comments)
    elapsed = (time.perf_counter() - t0) * 1000
    logger.info("Batch de %d commentaires traité en %.1f ms", len(preds), elapsed)
    return BatchResponse(
        predictions=preds,
        stats=predictor.compute_stats(preds),
        processing_time_ms=round(elapsed, 2),
        model_version=predictor.version,
    )
