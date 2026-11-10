#!/usr/bin/env bash
# Valida cutover Railway → VPS. Exit 0 só se tudo crítico estiver OK.
# Aceita backend sefin (API nacional / cert por usuário) OU IPM legado.
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
check "http :8501 health" bash -c 'for i in $(seq 1 20); do curl -sf -o /dev/null http://127.0.0.1:8501/_stcore/health && exit 0; sleep 1; done; exit 1'
check "https domain health" bash -c 'curl -skf -o /dev/null https://vps12436.panel.icontainer.site/_stcore/health'
check "postgres com emissoes" bash -c 'c=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from nfse_emissoes"); test "$c" -gt 0'
check "postgres com usuarios" bash -c 'c=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from usuarios"); test "$c" -gt 0'
check "json historico" bash -c 'docker compose exec -T app test -s /app/data/nfse_emitidas.json'

# Backend de emissão
BACKEND=$(docker compose exec -T app python - <<"PY" 2>/dev/null || echo sefin
from src.utils.runtime_config import get_emission_backend
print(get_emission_backend())
PY
)
BACKEND=$(echo "$BACKEND" | tr -d '\r' | tail -1)
echo "INFO emission_backend=$BACKEND"

if [[ "$BACKEND" == "ipm" ]]; then
  if test -s certificados/cert.pem && test -s certificados/key.pem; then
    echo "OK   certificado A1 presente (opcional no IPM)"
    ok=$((ok+1))
  else
    echo "WARN certificado A1 ausente (ok para IPM)"
  fi
  check "IPM_SENHA definida" bash -c 'docker compose exec -T app python - <<"PY"
from src.utils.runtime_config import ipm_senha_configurada, get_ipm_senha
ok = ipm_senha_configurada() and len(get_ipm_senha()) >= 4
raise SystemExit(0 if ok else 1)
PY'
  check "IPM rede Atende.Net" bash -c 'code=$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 -u 0:0 -F "teste=@/etc/hosts;type=text/xml" "https://ws-santarosa.atende.net/?pg=rest&service=WNERestServiceNFSe" || echo 000); [[ "$code" == "401" || "$code" == "403" || "$code" == "200" ]]'
else
  # Sefin / API nacional: usuários seed + colunas fiscais; cert A1 é por usuário (volume)
  check "usuarios nathalia+guilherme" bash -c 'c=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from usuarios where username in ('\''nathalia'\'','\''guilherme'\'') and is_active"); test "$c" -ge 2'
  check "coluna cnpj em usuarios" bash -c 'docker compose exec -T db psql -U nfse -d nfse -Atc "select column_name from information_schema.columns where table_name='\''usuarios'\'' and column_name='\''cnpj'\''" | grep -q cnpj'
  check "coluna logradouro em usuarios" bash -c 'docker compose exec -T db psql -U nfse -d nfse -Atc "select column_name from information_schema.columns where table_name='\''usuarios'\'' and column_name='\''logradouro'\''" | grep -q logradouro'
  if docker compose exec -T app test -d /app/data/certs; then
    echo "OK   data/certs presente (certs por usuário)"
    ok=$((ok+1))
  else
    echo "WARN data/certs ainda vazio — cada usuário deve enviar PFX em Configurações"
  fi
  check "Sefin host alcançável" bash -c 'code=$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 https://sefin.nfse.gov.br/ || echo 000); [[ "$code" != "000" ]]'
fi

echo "---"
echo "OK=$ok FAIL=$fail"
if [[ "$fail" -gt 0 ]]; then
  echo "Cutover incompleto."
  echo "Sefin: rode deploy/scripts/seed_multiusuarios.py e envie PFX por usuário."
  echo "IPM legado: /opt/rosafiscal/deploy/scripts/set_ipm_senha.sh"
  echo "Status JSON: /opt/rosafiscal/deploy/scripts/cutover_status.sh"
  exit 1
fi
echo "Cutover validado."
exit 0
