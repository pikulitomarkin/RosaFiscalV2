#!/usr/bin/env bash
# Pausa o serviço Streamlit no Railway após cutover VPS OK.
# Requer RAILWAY_TOKEN (env) ou arquivo secrets/RAILWAY_TOKEN | secrets/railway_token.
#
# Uso:
#   export RAILWAY_TOKEN=...
#   ./deploy/scripts/agent_pause_railway.sh
#   # ou:
#   printf '%s' "$TOKEN" > secrets/RAILWAY_TOKEN && chmod 600 secrets/RAILWAY_TOKEN
#   ./deploy/scripts/agent_pause_railway.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TOKEN="${RAILWAY_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  for f in "$ROOT/secrets/RAILWAY_TOKEN" "$ROOT/secrets/railway_token" "$ROOT/secrets/railway_token.txt"; do
    if [[ -f "$f" ]]; then
      TOKEN="$(tr -d '\r\n' < "$f")"
      break
    fi
  done
fi
if [[ -z "$TOKEN" ]]; then
  echo "RAILWAY_TOKEN ausente (env ou secrets/RAILWAY_TOKEN)." >&2
  echo "Crie em https://railway.app/account/tokens e rode de novo." >&2
  exit 2
fi

export RAILWAY_TOKEN="$TOKEN"
export PATH="${HOME}/.railway/bin:${PATH}"

if ! command -v railway >/dev/null 2>&1; then
  echo "Instalando Railway CLI..."
  curl -fsSL https://railway.app/install.sh | sh
  export PATH="${HOME}/.railway/bin:${PATH}"
fi

echo "=== cutover gate (VPS) ==="
KEY="${ROSAFISCAL_SSH_KEY:-$HOME/.ssh/rosafiscal_vps}"
HOST="${ROSAFISCAL_SSH_HOST:-root@184.107.179.79}"
if [[ -f "$KEY" ]]; then
  STATUS="$(ssh -i "$KEY" -o IdentitiesOnly=yes -o ConnectTimeout=20 "$HOST" \
    'bash /opt/rosafiscal/deploy/scripts/cutover_status.sh' 2>/dev/null || true)"
  echo "$STATUS" | head -40
  READY="$(STATUS_JSON="$STATUS" python3 - <<'PY'
import json, os, re
raw = os.environ.get("STATUS_JSON", "")
m = re.search(r"\{.*\}", raw, flags=re.S)
data = json.loads(m.group(0)) if m else {}
print("true" if data.get("cutover_ready") and data.get("emission_ready") else "false")
PY
)"
  if [[ "$READY" != "true" ]]; then
    echo "GATE FECHADO na VPS — não pause o Railway ainda." >&2
    exit 3
  fi
else
  echo "WARN: chave SSH VPS ausente — seguindo só com token Railway."
fi

echo "=== railway whoami / status ==="
railway whoami
railway status || true

# Tenta pausar o serviço do ambiente linkado.
# Preferência: RAILWAY_SERVICE_ID; senão o serviço default do link.
if [[ -n "${RAILWAY_SERVICE_ID:-}" ]]; then
  echo "Pausando service id=${RAILWAY_SERVICE_ID}..."
  railway service status --service "$RAILWAY_SERVICE_ID" || true
  railway down --service "$RAILWAY_SERVICE_ID" -y 2>/dev/null \
    || railway pause --service "$RAILWAY_SERVICE_ID" 2>/dev/null \
    || true
else
  echo "Pausando serviço do projeto linkado (railway down)..."
  railway down -y 2>/dev/null || railway pause 2>/dev/null || true
fi

echo
echo "Conferido: abra https://railway.app e confirme pause/stop do Streamlit antigo."
echo "URL oficial permanece: https://vps12436.panel.icontainer.site/"
echo "RAILWAY_PAUSE_ATTEMPTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
