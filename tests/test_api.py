"""Tests de l'API FastAPI (sans serveur réel, via TestClient)."""
import time

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.schemas import MAX_BATCH


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # le "with" déclenche le lifespan -> chargement du modèle
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


@pytest.mark.parametrize("size", [1, 10, 50, 200, MAX_BATCH])
def test_predict_batch_sizes(client, size):
    comments = ["great video", "awful sound", "uploaded yesterday"] * (size // 3 + 1)
    r = client.post("/predict_batch", json={"comments": comments[:size]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["predictions"]) == size
    assert body["stats"]["total"] == size
    for p in body["predictions"]:
        assert p["sentiment"] in (-1, 0, 1)
        assert p["label"] in ("negative", "neutral", "positive")


def test_response_keeps_original_text(client):
    original = "Super vidéo !!! 😍 https://t.co/x"
    r = client.post("/predict_batch", json={"comments": [original]})
    assert r.json()["predictions"][0]["text"] == original


@pytest.mark.parametrize("payload", [
    {"comments": []},                         # batch vide
    {"comments": ["x"] * (MAX_BATCH + 1)},    # batch trop grand
    {"comments": "pas une liste"},            # mauvais type
    {"comments": [1, 2, 3]},                  # éléments non textuels
    {"texts": ["mauvaise clé"]},              # champ manquant
    {},
])
def test_invalid_payloads_return_422(client, payload):
    assert client.post("/predict_batch", json=payload).status_code == 422


def test_malformed_json(client):
    r = client.post("/predict_batch", content="{not json",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_wrong_method(client):
    assert client.get("/predict_batch").status_code == 405


def test_cors_allows_chrome_extension(client):
    origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
    r = client.options("/predict_batch", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_unknown_origin(client):
    r = client.options("/predict_batch", headers={
        "Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST",
    })
    assert "access-control-allow-origin" not in r.headers


def test_response_time(client):
    comments = ["this is a really nice and helpful tutorial"] * 100
    t0 = time.perf_counter()
    r = client.post("/predict_batch", json={"comments": comments})
    assert r.status_code == 200
    assert (time.perf_counter() - t0) * 1000 < 500


def test_model_unavailable_returns_503(client, monkeypatch):
    from src.api import main
    monkeypatch.setitem(main.STATE, "predictor", None)
    r = client.post("/predict_batch", json={"comments": ["hello"]})
    assert r.status_code == 503
    assert client.get("/health").json()["status"] == "degraded"
