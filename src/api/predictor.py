"""Chargement unique du modèle + logique de prédiction (indépendante de FastAPI)."""
import json
import os
from pathlib import Path
from typing import List

import joblib

from src.utils.text import clean_text

MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))
LABELS = {-1: "negative", 0: "neutral", 1: "positive"}


class SentimentPredictor:
    def __init__(self, model_dir: Path = MODEL_DIR):
        self.vectorizer = joblib.load(model_dir / "vectorizer.joblib")
        self.model = joblib.load(model_dir / "model.joblib")
        meta_path = model_dir / "metadata.json"
        self.metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        self.version = self.metadata.get("version", "unknown")
        self.classes = [int(c) for c in self.model.classes_]

    def predict(self, texts: List[str]) -> List[dict]:
        cleaned = [clean_text(t) for t in texts]
        probas = self.model.predict_proba(self.vectorizer.transform(cleaned))
        out = []
        for text, p in zip(texts, probas):
            idx = int(p.argmax())
            sentiment = self.classes[idx]
            out.append({
                "text": text,
                "sentiment": sentiment,
                "label": LABELS[sentiment],
                "confidence": round(float(p[idx]), 4),
                "probabilities": {LABELS[c]: round(float(v), 4) for c, v in zip(self.classes, p)},
            })
        return out

    @staticmethod
    def compute_stats(preds: List[dict]) -> dict:
        n = len(preds)
        pos = sum(p["sentiment"] == 1 for p in preds)
        neu = sum(p["sentiment"] == 0 for p in preds)
        neg = sum(p["sentiment"] == -1 for p in preds)
        return {
            "total": n,
            "positive": pos, "neutral": neu, "negative": neg,
            "positive_pct": round(100 * pos / n, 2),
            "neutral_pct": round(100 * neu / n, 2),
            "negative_pct": round(100 * neg / n, 2),
            "average_confidence": round(sum(p["confidence"] for p in preds) / n, 4),
            "sentiment_score": round((pos - neg) / n, 4),
        }
