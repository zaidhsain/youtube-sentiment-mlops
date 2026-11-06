# Documentation de l'API

Adresse locale : `http://127.0.0.1:8001`. Adresse publique pendant la démonstration : `https://<nom-du-codespace>-7860.app.github.dev`. La documentation interactive est sur `/docs`.

## GET /health

Indique si le service tourne et si le modèle est chargé.

```bash
curl https://<nom-du-codespace>-7860.app.github.dev/health
```

```json
{"status": "ok", "model_loaded": true, "model_version": "1.0.0", "uptime_seconds": 12.3}
```

`status` vaut `degraded` si le modèle n'a pas pu être chargé.

## POST /predict_batch

Analyse de 1 à 500 commentaires. Chaque commentaire est tronqué à 5 000 caractères.

```bash
curl -X POST https://<nom-du-codespace>-7860.app.github.dev/predict_batch \
  -H "Content-Type: application/json" \
  -d '{"comments": ["I love this video!", "worst tutorial ever", "posted at 10am"]}'
```

| Champ de la réponse | Contenu |
|---|---|
| `predictions[].text` | Commentaire d'origine |
| `predictions[].sentiment` | −1 négatif, 0 neutre, 1 positif |
| `predictions[].label` | `negative`, `neutral` ou `positive` |
| `predictions[].confidence` | Probabilité de la classe retenue |
| `predictions[].probabilities` | Probabilité de chaque classe |
| `stats` | Effectifs, pourcentages, confiance moyenne, score de −1 à 1 |
| `processing_time_ms` | Temps de calcul côté serveur |
| `model_version` | Version du modèle |

## Codes de réponse

| Code | Situation |
|---|---|
| 200 | Prédiction effectuée |
| 422 | Lot vide, plus de 500 éléments, mauvais type, JSON mal formé |
| 503 | Modèle non chargé |
| 500 | Erreur inattendue, détaillée dans les journaux |
