#!/usr/bin/env bash
# Sobe o dashboard Streamlit em cada boot do Cloud Agent.
# Usa SQLite local por padrao (sem Docker). Credenciais via secrets do ambiente.
set -euo pipefail

if [[ -d /agent/repos/RosaFiscalV2 ]]; then
  cd /agent/repos/RosaFiscalV2
else
  cd "$(cd "$(dirname "$0")/../.." && pwd)"
fi

export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"

mkdir -p certificados data logs

# SQLite para agents; override com DATABASE_URL se necessario.
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///./nfse.db}"
export IPM_AMBIENTE_TESTE="${IPM_AMBIENTE_TESTE:-True}"
export STREAMLIT_SERVER_ADDRESS="${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}"
PORT="${PORT:-${STREAMLIT_SERVER_PORT:-8501}}"

# Se ADMIN_PASSWORD estiver no ambiente (secret), gera ADMIN_PASSWORD_HASH em runtime.
if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
  export ADMIN_PASSWORD_HASH
  ADMIN_PASSWORD_HASH="$(
    python3 - <<'PY'
import bcrypt, os
print(bcrypt.hashpw(os.environ["ADMIN_PASSWORD"].encode(), bcrypt.gensalt()).decode())
PY
  )"
fi

export ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"

exec python3 -m streamlit run app_nfse_enhanced.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true
