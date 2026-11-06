#!/bin/zsh
# Lance l'API locale puis un navigateur Chromium avec le Commentomètre déjà installé.
# Usage : ./lancer_demo.sh [url_youtube]
cd "$(dirname "$0")"

VIDEO="${1:-https://www.youtube.com/watch?v=jNQXAC9IVRw}"
PORT=8001
BIN="$HOME/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
PROFILE="$HOME/.commentometre-navigateur"

if ! curl -s "http://127.0.0.1:$PORT/health" > /dev/null; then
  echo "Démarrage de l'API sur le port $PORT…"
  nohup .venv/bin/uvicorn src.api.main:app --host 127.0.0.1 --port $PORT > logs/uvicorn.log 2>&1 &
  for i in {1..30}; do curl -s "http://127.0.0.1:$PORT/health" > /dev/null && break; sleep 1; done
fi
curl -s "http://127.0.0.1:$PORT/health"; echo

if [[ ! -x "$BIN" ]]; then
  echo "Chromium introuvable : installez-le avec  pip install playwright && playwright install chromium"
  exit 1
fi
mkdir -p "$PROFILE"
nohup "$BIN" --user-data-dir="$PROFILE" --load-extension="$PWD/chrome-extension" \
  --no-first-run --no-default-browser-check --lang=fr "$VIDEO" > /dev/null 2>&1 &
echo "Navigateur ouvert sur $VIDEO"
