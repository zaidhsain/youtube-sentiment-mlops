---
title: YouTube Sentiment API
emoji: 💬
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# YouTube Sentiment Analyzer — projet MLOps complet

Analyse automatique du sentiment (négatif / neutre / positif) des commentaires YouTube :
un modèle scikit-learn servi par une API FastAPI conteneurisée (Hugging Face Spaces),
consommée par une extension Chrome.

> Le bloc YAML en tête de ce fichier sert à configurer le Space Hugging Face (SDK Docker, port 7860).

## Architecture

```
┌──────────────────────┐   1. extrait les     ┌──────────────────────────┐
│  Page YouTube        │◄──── commentaires ───│  content.js              │
│  (DOM)               │    (scroll auto)     │  (content script)        │
└──────────────────────┘                      └────────────┬─────────────┘
                                                           │ chrome.runtime message
                                              ┌────────────▼─────────────┐
                                              │  popup.html / popup.js   │
                                              │  stats, donut, filtres,  │
                                              │  dark mode, copie, CSV   │
                                              └────────────┬─────────────┘
                              2. POST /predict_batch (lots de 100, JSON)
                                                           │ HTTPS
┌──────────────────────────────────────────────────────────▼─────────────┐
│ Hugging Face Space (Docker, python:3.10-slim, port 7860)               │
│  FastAPI ─ Pydantic (validation) ─ CORS ─ logs                         │
│     └─ SentimentPredictor : clean_text → TF-IDF → LogisticRegression   │
│                             (models/vectorizer.joblib, model.joblib)   │
└────────────────────────────────────────────────────────────────────────┘
```

| Composant | Technologie |
|---|---|
| Frontend | Extension Chrome Manifest V3 (HTML, CSS, JS sans dépendance) |
| Backend | FastAPI + Pydantic v2 + Uvicorn |
| ML | scikit-learn 1.5.2 : TF-IDF + Logistic Regression |
| Déploiement | Docker sur Hugging Face Spaces |
| Versioning | Git + GitHub (+ remote Hugging Face) |

## Structure du projet

```
├── data/
│   ├── raw/                 # reddit.csv téléchargé (non versionné)
│   └── processed/           # train.csv / test.csv (non versionnés)
├── models/                  # vectorizer.joblib, model.joblib, metadata.json
├── reports/                 # metrics.json, model_comparison.csv, figures/
├── src/
│   ├── data/                # download_data.py, preprocess.py
│   ├── models/              # train.py
│   ├── api/                 # main.py (FastAPI), predictor.py, schemas.py
│   └── utils/               # text.py (nettoyage partagé), logger.py
├── chrome-extension/        # manifest.json, content.js, popup.*, icons/
├── tests/                   # pytest (prétraitement, modèle, API) + integration_check.py
├── docs/                    # rapport technique
├── app_api.py               # point d'entrée production
├── Dockerfile, .dockerignore
├── requirements.txt         # dev (entraînement, tests)
└── requirements-prod.txt    # prod (servir le modèle uniquement)
```

## Installation et reproduction

```bash
git clone <url-du-repo> && cd <repo>
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.data.download_data   # télécharge data/raw/reddit.csv + statistiques
python -m src.data.preprocess      # nettoyage, EDA (figures), split 80/20 stratifié
python -m src.models.train         # comparaison, GridSearchCV, évaluation, sauvegarde
pytest -q                          # 38 tests
```

## Résultats du modèle

Test set : 7 290 commentaires (20 %, stratifié, `random_state=42`).

| Métrique | Valeur | Critère TP |
|---|---|---|
| Accuracy | **89,45 %** | ≥ 80 % ✅ |
| F1 négatif / neutre / positif | 0,814 / 0,936 / 0,902 | > 0,75 ✅ |
| F1 macro | 0,884 | |
| Latence (batch de 50) | **0,7 ms** | < 100 ms ✅ |

Comparaison des algorithmes (même TF-IDF, paramètres par défaut raisonnables) :

| Modèle | Accuracy | F1 macro | Entraînement |
|---|---|---|---|
| LinearSVC | 0,879 | 0,866 | 1,4 s |
| Logistic Regression | 0,877 | 0,866 | 3,3 s |
| Random Forest | 0,773 | 0,713 | 13,2 s |
| Complement Naive Bayes | 0,685 | 0,658 | 1,2 s |

Meilleurs hyperparamètres (GridSearchCV, 3-fold, F1 macro) : `C=20`, unigrammes, 30 000 features.
Figures : `reports/figures/` (distribution des classes, longueurs, matrice de confusion).

## API

Lancement local :

```bash
uvicorn src.api.main:app --reload --port 8000
# Documentation interactive Swagger : http://localhost:8000/docs
```

### `GET /health`

```json
{"status": "ok", "model_loaded": true, "model_version": "1.0.0", "uptime_seconds": 12.3}
```

### `POST /predict_batch`

Requête (1 à 500 commentaires, chaque commentaire tronqué à 5 000 caractères) :

```bash
curl -X POST http://localhost:8000/predict_batch \
  -H "Content-Type: application/json" \
  -d '{"comments": ["I love this video!", "Worst tutorial ever", "Posted at 10am"]}'
```

Réponse :

```json
{
  "predictions": [
    {"text": "I love this video!", "sentiment": 1, "label": "positive", "confidence": 0.99,
     "probabilities": {"negative": 0.0, "neutral": 0.01, "positive": 0.99}},
    ...
  ],
  "stats": {"total": 3, "positive": 1, "neutral": 1, "negative": 1,
            "positive_pct": 33.33, "neutral_pct": 33.33, "negative_pct": 33.33,
            "average_confidence": 0.97, "sentiment_score": 0.0},
  "processing_time_ms": 2.1,
  "model_version": "1.0.0"
}
```

| Code | Cas |
|---|---|
| 200 | Succès |
| 422 | Batch vide, > 500 éléments, mauvais type, JSON invalide |
| 503 | Modèle non chargé |
| 500 | Erreur interne (journalisée, message générique renvoyé) |

## Déploiement sur Hugging Face Spaces

1. Sur <https://huggingface.co/new-space> : nom `youtube-sentiment-api`, SDK **Docker**, template *Blank*.
2. Créer un token d'accès en écriture (*Settings → Access Tokens*).
3. Pousser le dépôt :

```bash
git remote add hf https://huggingface.co/spaces/<utilisateur>/youtube-sentiment-api
git push hf main          # identifiant = utilisateur HF, mot de passe = token
```

4. Suivre le build dans l'onglet *Logs* du Space, puis vérifier :

```bash
python tests/integration_check.py https://<utilisateur>-youtube-sentiment-api.hf.space
```

5. Mettre l'URL dans l'extension (⚙ → URL de l'API) ou dans `DEFAULT_API_URL` de `chrome-extension/popup.js`.

Test local de l'image (si Docker est installé) :

```bash
docker build -t yt-sentiment .
docker run -p 7860:7860 yt-sentiment
```

## Extension Chrome

**Installation** : `chrome://extensions` → activer *Mode développeur* → *Charger l'extension non empaquetée* → choisir le dossier `chrome-extension/`.

**Utilisation** :
1. Ouvrir une vidéo YouTube.
2. Cliquer sur l'icône de l'extension → ⚙ → saisir l'URL de l'API → *Tester l'API*.
3. *Analyser les commentaires* : l'extension fait défiler la page pour charger les commentaires
   (50 à 500), les envoie par lots de 100 et affiche :
   - le donut de répartition et le score global (−1 à +1),
   - les pourcentages et effectifs par sentiment, la confiance moyenne, le temps de réponse,
   - la liste des commentaires avec badge sentiment + confiance,
   - filtres Positifs / Neutres / Négatifs et recherche texte,
   - mode sombre/clair (mémorisé), copie des résultats, export CSV.

Captures d'écran : à ajouter dans `docs/screenshots/`.

## Limites connues

- Les labels du dataset proviennent d'un lexique automatique (TextBlob) : le modèle apprend ce lexique
  plutôt que le jugement humain. Les négations (« not bad ») et l'ironie sont mal gérées.
- Entraîné sur Reddit en anglais : moins fiable sur d'autres langues.
- Voir `docs/RAPPORT_TECHNIQUE.md` pour l'analyse complète et les pistes d'amélioration.
