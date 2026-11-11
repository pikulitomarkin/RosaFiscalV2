#!/usr/bin/env bash
# Pausa o serviço Streamlit no Railway após cutover VPS OK.
# Requer RAILWAY_TOKEN (env) ou arquivo secrets/RAILWAY_TOKEN | secrets/railway_token.
#
# Projeto conhecido (GitHub Deployments):
#   project  = 0dff8bdf-7c3c-4cda-8ca5-34c48a9aa7a6
#   environment = d845247a-c997-4fec-bb0d-b0e1cb1ccd76
#   public URL ainda viva (2026-11-11): https://rosafiscalv2.up.railway.app/
#   RAILWAY_TOKEN foi SKIPPED pelo usuário — caminho preferencial = pause no painel.
#
# Uso:
#   export RAILWAY_TOKEN=...
#   ./deploy/scripts/agent_pause_railway.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

RAILWAY_PROJECT_ID="${RAILWAY_PROJECT_ID:-0dff8bdf-7c3c-4cda-8ca5-34c48a9aa7a6}"
RAILWAY_ENVIRONMENT_ID="${RAILWAY_ENVIRONMENT_ID:-d845247a-c997-4fec-bb0d-b0e1cb1ccd76}"
RAILWAY_PUBLIC_URL="${RAILWAY_PUBLIC_URL:-https://rosafiscalv2.up.railway.app}"
OFFICIAL_URL="${OFFICIAL_URL:-https://vps12436.panel.icontainer.site/}"

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
  echo "Token foi skipped — pause o serviço no painel Railway (não apague DB/volume)." >&2
  echo "Projeto: https://railway.com/project/${RAILWAY_PROJECT_ID}?environmentId=${RAILWAY_ENVIRONMENT_ID}" >&2
  echo "URL legada viva: ${RAILWAY_PUBLIC_URL}/_stcore/health" >&2
  echo "URL oficial produção: ${OFFICIAL_URL}" >&2
  exit 2
fi

export RAILWAY_TOKEN="$TOKEN"
export PATH="${HOME}/.railway/bin:${PATH}"

if ! command -v railway >/dev/null 2>&1; then
  echo "Instalando Railway CLI..."
  curl -fsSL https://railway.app/install.sh | sh
  export PATH="${HOME}/.railway/bin:${PATH}"
fi

echo "=== probe Railway público (antes) ==="
BEFORE="$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 \
  "${RAILWAY_PUBLIC_URL}/_stcore/health" || echo 000)"
echo "before_health=${BEFORE} url=${RAILWAY_PUBLIC_URL}"

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

echo "=== railway link/whoami ==="
railway whoami
# Link explícito ao projeto/ambiente conhecidos (idempotente o quanto a CLI permitir)
railway link --project "$RAILWAY_PROJECT_ID" --environment "$RAILWAY_ENVIRONMENT_ID" 2>/dev/null \
  || railway link 2>/dev/null \
  || true
railway status || true

echo "=== pause / down ==="
if [[ -n "${RAILWAY_SERVICE_ID:-}" ]]; then
  echo "Pausando service id=${RAILWAY_SERVICE_ID}..."
  railway service status --service "$RAILWAY_SERVICE_ID" || true
  railway down --service "$RAILWAY_SERVICE_ID" -y 2>/dev/null \
    || railway pause --service "$RAILWAY_SERVICE_ID" 2>/dev/null \
    || true
else
  echo "Pausando serviço do ambiente linkado..."
  railway down -y 2>/dev/null || railway pause 2>/dev/null || true
fi

sleep 5
echo "=== probe Railway público (depois) ==="
AFTER="$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 \
  "${RAILWAY_PUBLIC_URL}/_stcore/health" || echo 000)"
echo "after_health=${AFTER} url=${RAILWAY_PUBLIC_URL}"

if [[ "$AFTER" == "200" ]]; then
  echo "WARN: Railway ainda responde 200 — pause pode ter falhado; confira no painel." >&2
  echo "Painel: https://railway.com/project/${RAILWAY_PROJECT_ID}?environmentId=${RAILWAY_ENVIRONMENT_ID}" >&2
  exit 4
fi

echo "OK: Railway health não está mais 200 (after=${AFTER})."
echo "URL oficial: https://vps12436.panel.icontainer.site/"
echo "RAILWAY_PAUSED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
