#!/bin/bash
# Lance l'API sur le port 7860, détachée du terminal de démarrage du Codespace.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
pkill -f "uvicorn app_api:app" 2>/dev/null
setsid nohup python -m uvicorn app_api:app --host 0.0.0.0 --port 7860 > logs/uvicorn.log 2>&1 < /dev/null &
disown
sleep 3
