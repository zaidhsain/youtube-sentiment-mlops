---
title: Commentometre API
emoji: 📊
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Commentomètre

TP3 de Cloud Computing (ENSAM Rabat, filière INDIA, 2026-2027), réalisé par Zaid Hsain.

Une extension Chrome qui lit les commentaires d'une vidéo YouTube et dit s'ils sont plutôt positifs, neutres ou négatifs. Le classement est fait par un modèle scikit-learn (TF-IDF + régression logistique) servi par une petite API FastAPI. Le Dockerfile est prêt pour Hugging Face Spaces ; l'API tourne pour l'instant en local.

*(Le bloc YAML en haut de ce fichier n'est pas une erreur : c'est la configuration du Space Hugging Face.)*

<p align="center"><img src="docs/screenshots/11_rick_astley_clair.png" width="300" alt="Popup de l'extension"> &nbsp; <img src="docs/screenshots/12_rick_astley_sombre.png" width="300" alt="Popup en thème sombre"></p>

## Comment ça marche

1. Sur une vidéo, on clique sur l'extension, puis sur « Analyser cette vidéo ».
2. `content.js` fait défiler la page pour que YouTube charge les commentaires, puis les lit.
3. Le popup les envoie par paquets de 100 à `POST /predict_batch`.
4. L'API nettoie chaque texte, le vectorise et renvoie la classe, la confiance et un bilan.
5. Le popup affiche le score global, la répartition et la liste des commentaires (filtrable, exportable).

Le dossier `src/` contient tout le Python : `data/` pour le téléchargement et la préparation, `models/` pour l'entraînement, `api/` pour l'API, et `utils/` pour le nettoyage de texte (partagé entre l'entraînement et l'API), les logs et le style des figures. L'extension est dans `chrome-extension/`, les tests dans `tests/`, et le rapport dans `docs/`.

## Refaire tourner le projet

Il faut Python 3.10 : c'est la version de l'image Docker, et le modèle doit être rechargé avec les mêmes versions de bibliothèques que celles de l'entraînement.

```bash
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.data.download_data    # récupère data/raw/reddit.csv
python -m src.data.preprocess       # nettoyage, figures, découpage 80/20
python -m src.models.train          # comparaison, GridSearch, sauvegarde du modèle
pytest -q                           # 38 tests
```

Pour lancer l'API en local (Swagger sur `/docs`) :

```bash
uvicorn src.api.main:app --port 8000
```

## Résultats

Sur les 7 290 commentaires du jeu de test, j'obtiens une accuracy de **89,45 %**. Le F1 vaut 0,81 pour les négatifs, 0,94 pour les neutres et 0,90 pour les positifs, et prédire un lot de 50 commentaires prend 0,7 ms. Les trois seuils de l'énoncé (80 % d'accuracy, F1 > 0,75 par classe, moins de 100 ms) sont donc respectés.

Une mise en garde, détaillée dans le rapport : le signe de la polarité TextBlob reproduit 100 % des 37 149 étiquettes du jeu de données. Elles ne viennent donc pas d'humains, et le modèle a surtout appris à imiter TextBlob. C'est pour ça qu'il classe « not bad at all » en négatif, ou « expected much more » en positif.

Le détail est dans `reports/metrics.json` et `reports/model_comparison.csv`, et les figures dans `reports/figures/`.

## L'API

| Route | Rôle |
|---|---|
| `GET /health` | état du service, modèle chargé ou non, version |
| `POST /predict_batch` | de 1 à 500 commentaires, renvoie prédictions et bilan |

```bash
curl -X POST http://localhost:8000/predict_batch \
  -H "Content-Type: application/json" \
  -d '{"comments": ["I love this video!", "worst tutorial ever", "posted at 10am"]}'
```

Chaque prédiction contient `sentiment` (−1, 0 ou 1), `label`, `confidence` et `probabilities`. Le bloc `stats` donne les effectifs, les pourcentages, la confiance moyenne et un score entre −1 et 1. Une requête invalide renvoie 422, et un modèle absent 503.

## Installer l'extension

1. Ouvrir `chrome://extensions` et activer le **mode développeur**.
2. Cliquer sur **Charger l'extension non empaquetée**, puis choisir le dossier `chrome-extension/`.
3. Dans le popup, ouvrir **Réglages**, saisir l'adresse de l'API (locale ou Hugging Face), puis cliquer sur **Tester la connexion**.

## Déploiement sur Hugging Face

Le Space est de type Docker. Je pousse le même dépôt vers deux remotes :

```bash
git remote add hf https://huggingface.co/spaces/<utilisateur>/commentometre-api
git push hf main
python tests/integration_check.py https://<utilisateur>-commentometre-api.hf.space
```

Le dernier script vérifie l'API en ligne et contrôle qu'elle donne les mêmes prédictions que le modèle local.

## Tests

- `pytest -q` : nettoyage du texte, modèle (seuils, cas limites, latence) et API (codes d'erreur, CORS, tailles de lot).
- `tests/integration_check.py <url>` : vérifie une API réelle, locale ou en ligne.
- `tests/e2e/run_e2e.py` : pilote l'extension dans Chromium avec Playwright, sur une page qui reproduit la structure HTML des commentaires YouTube, pour que le test reste reproductible.
- `tests/e2e/record_demo.py` : enregistre la vidéo de démonstration sur de vraies vidéos YouTube.

Le rapport complet est dans [docs/Rapport_Technique.pdf](docs/Rapport_Technique.pdf), et la vidéo de démonstration dans [docs/demo/Demo_Commentometre.mp4](docs/demo/Demo_Commentometre.mp4).
