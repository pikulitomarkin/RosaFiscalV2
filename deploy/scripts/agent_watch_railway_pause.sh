#!/usr/bin/env bash
# Aguarda RAILWAY_TOKEN (env ou secrets/) e tenta pausar o Railway.
# Uso: bash deploy/scripts/agent_watch_railway_pause.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
MAX="${RAILWAY_WATCH_MAX:-60}"      # 60 * 30s ~= 30min
SLEEP_S="${RAILWAY_WATCH_SLEEP:-30}"

has_token() {
  [[ -n "${RAILWAY_TOKEN:-}" ]] \
    || [[ -f "$ROOT/secrets/RAILWAY_TOKEN" ]] \
    || [[ -f "$ROOT/secrets/railway_token" ]] \
    || [[ -f "$ROOT/secrets/railway_token.txt" ]]
}

for i in $(seq 1 "$MAX"); do
  if has_token; then
    echo "token detectado (tentativa $i) — pausando..."
    if bash "$ROOT/deploy/scripts/agent_pause_railway.sh"; then
      echo "pause attempt finished OK"
      exit 0
    fi
    echo "pause falhou; nova tentativa depois"
  else
    echo "$(date -Is) waiting RAILWAY_TOKEN ($i/$MAX) — coloque em secrets/RAILWAY_TOKEN"
  fi
  sleep "$SLEEP_S"
done
echo "timeout aguardando RAILWAY_TOKEN"
exit 2
