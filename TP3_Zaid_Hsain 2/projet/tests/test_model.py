"""Tests du modèle : performance, cas limites, temps d'inférence."""
import time
from pathlib import Path

import pandas as pd
import pytest
from sklearn.metrics import accuracy_score, f1_score

from src.api.predictor import SentimentPredictor

TEST_CSV = Path("data/processed/test.csv")


@pytest.fixture(scope="module")
def predictor():
    return SentimentPredictor()


@pytest.mark.skipif(not TEST_CSV.exists(), reason="Lancer d'abord src.data.preprocess")
def test_performance_on_test_set(predictor):
    df = pd.read_csv(TEST_CSV).dropna()
    X = predictor.vectorizer.transform(df.text)
    pred = predictor.model.predict(X)
    assert accuracy_score(df.label, pred) >= 0.80
    assert (f1_score(df.label, pred, average=None) > 0.75).all()


@pytest.mark.parametrize("text,expected", [
    ("I love this video, amazing work!", 1),
    ("This is the worst and most boring video ever", -1),
    ("Posted on Monday from Paris", 0),
])
def test_obvious_cases(predictor, text, expected):
    assert predictor.predict([text])[0]["sentiment"] == expected


@pytest.mark.parametrize("text", [
    "",                          # vide
    "ok",                        # très court
    "😂😂😂",                     # uniquement des emojis
    "great " * 3000,             # très long
    "c'est génial, super vidéo, love it",  # langues mélangées
    "!!!???...",                 # uniquement ponctuation
])
def test_edge_cases_do_not_crash(predictor, text):
    res = predictor.predict([text])[0]
    assert res["sentiment"] in (-1, 0, 1)
    assert 0.0 <= res["confidence"] <= 1.0
    assert abs(sum(res["probabilities"].values()) - 1) < 1e-3


def test_inference_latency_batch_50(predictor):
    batch = ["this video is really helpful, thanks a lot for sharing"] * 50
    predictor.predict(batch)  # warm-up
    t0 = time.perf_counter()
    predictor.predict(batch)
    assert (time.perf_counter() - t0) * 1000 < 100


def test_stats_are_consistent(predictor):
    preds = predictor.predict(["love it", "hate it", "monday"])
    st = predictor.compute_stats(preds)
    assert st["total"] == 3
    assert st["positive"] + st["neutral"] + st["negative"] == 3
    assert abs(st["positive_pct"] + st["neutral_pct"] + st["negative_pct"] - 100) < 0.1
