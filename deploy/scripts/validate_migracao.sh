#!/usr/bin/env bash
# Valida cutover Railway → VPS. Exit 0 só se tudo crítico estiver OK.
set -euo pipefail
ROOT=/opt/rosafiscal
cd "$ROOT"
ok=0
fail=0
check() {
  local name="$1"; shift
  if "$@"; then
    echo "OK   $name"
    ok=$((ok+1))
  else
    echo "FAIL $name"
    fail=$((fail+1))
  fi
}

check "docker compose ps (app up)" bash -c 'docker compose ps --status running | grep -q rosafiscal-app'
check "http :8501 health" bash -c 'curl -sf -o /dev/null http://127.0.0.1:8501/_stcore/health'
check "https domain health" bash -c 'curl -skf -o /dev/null https://vps12436.panel.icontainer.site/_stcore/health'
check "cert.pem presente" test -s certificados/cert.pem
check "key.pem presente" test -s certificados/key.pem
check "postgres com emissoes" bash -c 'c=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from nfse_emissoes"); test "$c" -gt 0'
check "postgres com usuarios" bash -c 'c=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from usuarios"); test "$c" -gt 0'
check "json historico" bash -c 'docker compose exec -T app test -s /app/data/nfse_emitidas.json'
check "IPM_SENHA definida" bash -c 'python3 - <<"PY"
from pathlib import Path
v=""
for line in Path(".env").read_text().splitlines():
    if line.startswith("IPM_SENHA="):
        v=line.split("=",1)[1].strip()
raise SystemExit(0 if v else 1)
PY'

echo "---"
echo "OK=$ok FAIL=$fail"
if [[ "$fail" -gt 0 ]]; then
  echo "Cutover incompleto. Se só IPM_SENHA falhou: /opt/rosafiscal/deploy/scripts/set_ipm_senha.sh"
  exit 1
fi
echo "Cutover validado."
exit 0
