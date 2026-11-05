#!/usr/bin/env bash
# Define IPM_SENHA no .env da VPS e no volume runtime_config (dashboard).
# Uso (na VPS):
#   /opt/rosafiscal/deploy/scripts/set_ipm_senha.sh
#   echo "$SENHA" | /opt/rosafiscal/deploy/scripts/set_ipm_senha.sh --stdin
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"
umask 077

MODE="${1:-}"
if [[ "$MODE" == "--stdin" ]]; then
  IFS= read -r SENHA || true
else
  read -r -s -p "IPM_SENHA (não será exibida): " SENHA
  echo
fi

if [[ -z "${SENHA}" ]]; then
  echo "Senha vazia — abortado." >&2
  exit 1
fi

export SENHA
python3 - <<'PY'
from pathlib import Path
import os
senha = os.environ["SENHA"]
path = Path(".env")
lines = path.read_text().splitlines() if path.exists() else []
out = []
found = False
for line in lines:
    if line.startswith("IPM_SENHA="):
        out.append("IPM_SENHA=" + senha)
        found = True
    else:
        out.append(line)
if not found:
    out.append("IPM_SENHA=" + senha)
path.write_text("\n".join(out) + "\n")
path.chmod(0o600)
print("IPM_SENHA atualizada em", path.resolve())
PY

# Recria o app com o .env novo e espera health
docker compose up -d --force-recreate app
for _ in $(seq 1 30); do
  if curl -sf -o /dev/null http://127.0.0.1:8501/_stcore/health; then
    break
  fi
  sleep 1
done

# Espelha no volume usado pelo dashboard (runtime_config.json)
docker compose exec -T -e SENHA="$SENHA" app python - <<'PY'
import os
from src.utils.runtime_config import get_ipm_usuario, save_ipm_credentials, ipm_senha_configurada
save_ipm_credentials(get_ipm_usuario(), os.environ["SENHA"])
print("runtime_config OK; senha_configurada=", ipm_senha_configurada())
PY

unset SENHA
echo "Credenciais IPM salvas. Valide com:"
echo "  docker compose exec -T app python deploy/scripts/test_ipm_auth.py"
echo "  /opt/rosafiscal/deploy/scripts/validate_migracao.sh"
