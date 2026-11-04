"""Phase 3 — Entraînement, comparaison, optimisation et sauvegarde du modèle.

Usage : python -m src.models.train
Produit :
  models/vectorizer.joblib, models/model.joblib, models/metadata.json
  reports/metrics.json, reports/model_comparison.csv, reports/figures/confusion_matrix.png
"""
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

DATA_DIR = Path("data/processed")
MODEL_DIR = Path("models")
REPORT_DIR = Path("reports")
SEED = 42
LABEL_NAMES = ["Négatif", "Neutre", "Positif"]


def load():
    tr = pd.read_csv(DATA_DIR / "train.csv").dropna()
    te = pd.read_csv(DATA_DIR / "test.csv").dropna()
    return tr.text, tr.label, te.text, te.label


def base_tfidf(**kw):
    params = dict(ngram_range=(1, 2), min_df=2, max_df=0.95, sublinear_tf=True, max_features=50000)
    params.update(kw)
    return TfidfVectorizer(**params)


def compare_models(Xtr, ytr, Xte, yte) -> pd.DataFrame:
    """Étape 1 : comparer plusieurs algorithmes avec le même TF-IDF."""
    candidates = {
        "LogisticRegression": LogisticRegression(max_iter=2000, class_weight="balanced", C=5),
        "LinearSVC": LinearSVC(class_weight="balanced", C=0.5),
        "ComplementNB": ComplementNB(alpha=0.3),
        "RandomForest": RandomForestClassifier(n_estimators=200, class_weight="balanced",
                                               n_jobs=-1, random_state=SEED),
    }
    rows = []
    for name, clf in candidates.items():
        pipe = Pipeline([("tfidf", base_tfidf()), ("clf", clf)])
        t0 = time.perf_counter()
        pipe.fit(Xtr, ytr)
        fit_s = time.perf_counter() - t0
        pred = pipe.predict(Xte)
        rows.append({
            "model": name,
            "accuracy": accuracy_score(yte, pred),
            "f1_macro": f1_score(yte, pred, average="macro"),
            "f1_min_class": f1_score(yte, pred, average=None).min(),
            "fit_seconds": fit_s,
        })
        print(f"  {name:20s} acc={rows[-1]['accuracy']:.4f}  f1_macro={rows[-1]['f1_macro']:.4f}  ({fit_s:.1f}s)")
    return pd.DataFrame(rows).sort_values("f1_macro", ascending=False)


def grid_search(Xtr, ytr) -> GridSearchCV:
    """Étape 2 : optimiser TF-IDF + Logistic Regression (modèle imposé par le TP)."""
    pipe = Pipeline([
        ("tfidf", base_tfidf()),
        ("clf", LogisticRegression(max_iter=3000, class_weight="balanced")),
    ])
    grid = {
        "tfidf__ngram_range": [(1, 1), (1, 2), (1, 3)],
        "tfidf__max_features": [30000, 80000],
        "clf__C": [1, 5, 10, 20],
    }
    gs = GridSearchCV(pipe, grid, scoring="f1_macro", n_jobs=-1, verbose=0,
                      cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED))
    gs.fit(Xtr, ytr)
    print(f"  Meilleurs paramètres : {gs.best_params_}")
    print(f"  F1 macro (CV)        : {gs.best_score_:.4f}")
    return gs


def save_confusion(yte, pred) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    cm = confusion_matrix(yte, pred, labels=[-1, 0, 1])
    cm_norm = cm / cm.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    sns.heatmap(cm_norm, annot=cm, fmt="d", cmap="Blues", cbar=False,
                xticklabels=LABEL_NAMES, yticklabels=LABEL_NAMES, ax=ax)
    ax.set_xlabel("Prédit")
    ax.set_ylabel("Réel")
    ax.set_title("Matrice de confusion (test set)")
    fig.tight_layout()
    (REPORT_DIR / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(REPORT_DIR / "figures" / "confusion_matrix.png", dpi=120)
    plt.close(fig)


def inference_latency(vec, model, texts, n_runs=50) -> float:
    batch = list(texts[:50])
    vec.transform(batch)  # warm-up
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        model.predict_proba(vec.transform(batch))
        times.append((time.perf_counter() - t0) * 1000)
    return float(np.median(times))


def main():
    Xtr, ytr, Xte, yte = load()
    print(f"Train={len(Xtr)}  Test={len(Xte)}\n\n[1/3] Comparaison des algorithmes")
    comparison = compare_models(Xtr, ytr, Xte, yte)

    print("\n[2/3] GridSearchCV sur TF-IDF + LogisticRegression")
    gs = grid_search(Xtr, ytr)
    best = gs.best_estimator_
    vec, model = best.named_steps["tfidf"], best.named_steps["clf"]

    print("\n[3/3] Évaluation finale sur le test set")
    pred = best.predict(Xte)
    acc = accuracy_score(yte, pred)
    f1s = f1_score(yte, pred, average=None, labels=[-1, 0, 1])
    print(classification_report(yte, pred, target_names=LABEL_NAMES, digits=4))
    latency = inference_latency(vec, model, Xte.tolist())
    print(f"Latence batch de 50 : {latency:.1f} ms (médiane)")
    save_confusion(yte, pred)

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(vec, MODEL_DIR / "vectorizer.joblib", compress=3)
    joblib.dump(model, MODEL_DIR / "model.joblib", compress=3)

    metrics = {
        "accuracy": round(acc, 4),
        "f1_macro": round(float(f1s.mean()), 4),
        "f1_per_class": {n: round(float(f), 4) for n, f in zip(LABEL_NAMES, f1s)},
        "latency_ms_batch50": round(latency, 2),
        "best_params": {k: str(v) for k, v in gs.best_params_.items()},
        "cv_f1_macro": round(gs.best_score_, 4),
        "criteria": {
            "accuracy>=0.80": acc >= 0.80,
            "f1_each_class>0.75": bool((f1s > 0.75).all()),
            "latency<100ms": latency < 100,
        },
    }
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    comparison.round(4).to_csv(REPORT_DIR / "model_comparison.csv", index=False)
    (MODEL_DIR / "metadata.json").write_text(json.dumps({
        "model_type": "TF-IDF + LogisticRegression",
        "version": "1.0.0",
        "trained_on": "reddit.csv (Himanshu-1703)",
        "classes": [int(c) for c in model.classes_],
        "accuracy": metrics["accuracy"],
        "f1_macro": metrics["f1_macro"],
        "vocab_size": len(vec.vocabulary_),
    }, indent=2))
    print("\nCritères du TP :", metrics["criteria"])


if __name__ == "__main__":
    main()
