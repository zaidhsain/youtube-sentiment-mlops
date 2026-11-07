#!/bin/zsh
# À lancer avant la démonstration : démarre le Codespace et rend le port 7860 public.
# Le port repasse en privé à chaque redémarrage du Codespace.
CS="commentometre-api-q746jjrv766gc4j64"
URL="https://commentometre-api-q746jjrv766gc4j64-7860.app.github.dev"
# Le Codespace appartient au compte zaidhsain, quel que soit le compte gh actif.
export GH_TOKEN="$(gh auth token -h github.com -u zaidhsain)"
echo "Démarrage du Codespace…"
gh codespace ssh -c "$CS" -- 'sleep 10; curl -s -m 5 127.0.0.1:7860/health > /dev/null || bash /workspaces/youtube-sentiment-mlops/.devcontainer/start_api.sh'
gh codespace ports visibility 7860:public -c "$CS"
sleep 3
curl -s -m 20 "$URL/health"; echo
echo "API publique : $URL"
