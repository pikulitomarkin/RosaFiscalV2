#!/usr/bin/env bash
# Rotaciona POSTGRES_PASSWORD no .env e no Postgres em execução.
# Uso: /opt/rosafiscal/deploy/scripts/rotate_postgres_password.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
umask 077

NEW="$(openssl rand -base64 24 | tr -d '/+=' | head -c 28)"
export NEW

python3 - <<'PY'
from pathlib import Path
import os
new = os.environ["NEW"]
path = Path(".env")
lines = path.read_text().splitlines() if path.exists() else []
out, found = [], False
for line in lines:
    if line.startswith("POSTGRES_PASSWORD="):
        out.append("POSTGRES_PASSWORD=" + new)
        found = True
    else:
        out.append(line)
if not found:
    out.append("POSTGRES_PASSWORD=" + new)
path.write_text("\n".join(out) + "\n")
path.chmod(0o600)
print("POSTGRES_PASSWORD atualizada no .env (len=%s)" % len(new))
PY

# Altera no servidor Postgres (usuário nfse)
docker compose exec -T db psql -U nfse -d postgres -v ON_ERROR_STOP=1 \
  -c "ALTER USER nfse WITH PASSWORD '$NEW';"

docker compose up -d --force-recreate app
for _ in $(seq 1 30); do
  curl -sf -o /dev/null http://127.0.0.1:8501/_stcore/health && break
  sleep 1
done
echo "Rotação OK. Guarde a nova senha do .env em local seguro (não no Git)."
unset NEW
