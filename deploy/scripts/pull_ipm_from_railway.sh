#!/usr/bin/env bash
# Busca IPM_SENHA nas variáveis do Railway e aplica na VPS.
# Requer: RAILWAY_TOKEN no ambiente (Account → Tokens).
# Opcional: RAILWAY_PROJECT_ID / RAILWAY_SERVICE_ID
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -z "${RAILWAY_TOKEN:-}" ]]; then
  echo "Defina RAILWAY_TOKEN (https://railway.app/account/tokens)" >&2
  exit 1
fi

if ! command -v railway >/dev/null 2>&1; then
  echo "Instalando Railway CLI..."
  curl -fsSL https://railway.app/install.sh | sh
  export PATH="$HOME/.railway/bin:$PATH"
fi

# Tenta via CLI linked project; se não houver link, usa GraphQL variables
SENHA=""
if railway variables --json >/tmp/railway_vars.json 2>/dev/null; then
  SENHA=$(python3 - <<'PY'
import json
data=json.load(open("/tmp/railway_vars.json"))
# CLI pode retornar dict plano ou lista
if isinstance(data, dict):
    print(data.get("IPM_SENHA") or data.get("ipm_senha") or "")
elif isinstance(data, list):
    for item in data:
        if isinstance(item, dict) and item.get("name") in ("IPM_SENHA","ipm_senha"):
            print(item.get("value") or "")
            break
PY
)
fi

if [[ -z "$SENHA" ]]; then
  echo "IPM_SENHA não encontrada via 'railway variables'. Link o projeto (railway link) ou exporte manualmente." >&2
  exit 2
fi

printf '%s' "$SENHA" | "$ROOT/deploy/scripts/set_ipm_senha.sh" --stdin
unset SENHA
echo "IPM_SENHA puxada do Railway e aplicada."
