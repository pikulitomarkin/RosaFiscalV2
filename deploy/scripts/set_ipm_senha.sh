#!/usr/bin/env bash
# Define IPM_SENHA no .env da VPS sem exibir a senha.
# Uso (na VPS):
#   /opt/rosafiscal/deploy/scripts/set_ipm_senha.sh
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"
umask 077

read -r -s -p "IPM_SENHA (não será exibida): " SENHA
echo
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
unset SENHA

docker compose up -d app
echo "App recriado. Valide login e uma emissão de teste."
