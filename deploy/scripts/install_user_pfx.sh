#!/usr/bin/env bash
# Instala PFX/P12 A1 para um usuário no volume da app (data/certs/{user}/).
# Uso na VPS:
#   CERT_PASS='...' ./deploy/scripts/install_user_pfx.sh nathalia /caminho/arquivo.pfx
#   cat arquivo.pfx | CERT_PASS='...' ./deploy/scripts/install_user_pfx.sh nathalia --stdin
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

USER_NAME="${1:-}"
SRC="${2:-}"
if [[ -z "$USER_NAME" || -z "$SRC" ]]; then
  echo "Uso: $0 <username> </path/file.pfx|--stdin>" >&2
  exit 2
fi
if [[ -z "${CERT_PASS:-}" ]]; then
  echo "Defina CERT_PASS (senha do PFX) no ambiente." >&2
  exit 2
fi

TMP="$(mktemp /tmp/rosafiscal-pfx.XXXXXX)"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

if [[ "$SRC" == "--stdin" ]]; then
  cat > "$TMP"
else
  cp -f "$SRC" "$TMP"
fi
[[ -s "$TMP" ]] || { echo "PFX vazio"; exit 3; }

docker compose cp "$TMP" "app:/tmp/user.pfx"
docker compose exec -T -e CERT_PASS -e PFX_USER="$USER_NAME" app python - <<'PY'
import os, pathlib
from src.users.profile import save_user_certificate_pfx, cert_pronto, get_user_profile
pfx = pathlib.Path("/tmp/user.pfx").read_bytes()
u = os.environ["PFX_USER"]
save_user_certificate_pfx(u, pfx, os.environ["CERT_PASS"])
p = get_user_profile(u)
print("OK", u, "cert_pronto=", cert_pronto(p), "cnpj=", p.cnpj if p else None)
PY
docker compose exec -T app rm -f /tmp/user.pfx
echo "Certificado instalado. Valide: docker compose exec -T app python deploy/scripts/check_sefin_certs.py"
