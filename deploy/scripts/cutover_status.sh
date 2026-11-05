#!/usr/bin/env bash
# Status JSON do cutover Railway → VPS (sem imprimir segredos).
set -euo pipefail
ROOT=/opt/rosafiscal
cd "$ROOT"

to_json_bool() { [[ "$1" == "true" ]] && echo true || echo false; }

app_up=false
http_ok=false
https_ok=false
db_emissoes=0
db_usuarios=0
json_ok=false
senha_ok=false
ipm_net_ok=false
cert_ok=false
code=000

docker compose ps --status running 2>/dev/null | grep -q rosafiscal-app && app_up=true || true
curl -sf -o /dev/null http://127.0.0.1:8501/_stcore/health && http_ok=true || true
curl -skf -o /dev/null https://vps12436.panel.icontainer.site/_stcore/health && https_ok=true || true

db_emissoes=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from nfse_emissoes" 2>/dev/null || echo 0)
db_usuarios=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from usuarios" 2>/dev/null || echo 0)
docker compose exec -T app test -s /app/data/nfse_emitidas.json && json_ok=true || true

if docker compose exec -T app python - <<"PY" >/dev/null 2>&1
from src.utils.runtime_config import ipm_senha_configurada, get_ipm_senha
raise SystemExit(0 if ipm_senha_configurada() and len(get_ipm_senha()) >= 4 else 1)
PY
then senha_ok=true; fi

code=$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 \
  -u '0:0' -F 'teste=@/etc/hosts;type=text/xml' \
  'https://ws-santarosa.atende.net/?pg=rest&service=WNERestServiceNFSe' || echo 000)
[[ "$code" == "401" || "$code" == "403" || "$code" == "200" ]] && ipm_net_ok=true || true

test -s certificados/cert.pem && test -s certificados/key.pem && cert_ok=true || true

ready=false
if $app_up && $http_ok && $https_ok && [[ "${db_emissoes}" -gt 0 ]] && [[ "${db_usuarios}" -gt 0 ]] && $json_ok && $senha_ok && $ipm_net_ok; then
  ready=true
fi

blocker=null
if [[ "$ready" != "true" ]]; then
  if [[ "$senha_ok" != "true" ]]; then
    blocker='"IPM_SENHA"'
  else
    blocker='"other"'
  fi
fi

cat <<EOF
{
  "cutover_ready": $(to_json_bool "$ready"),
  "app_up": $(to_json_bool "$app_up"),
  "http_8501": $(to_json_bool "$http_ok"),
  "https_panel": $(to_json_bool "$https_ok"),
  "db_emissoes": ${db_emissoes:-0},
  "db_usuarios": ${db_usuarios:-0},
  "json_historico": $(to_json_bool "$json_ok"),
  "ipm_senha": $(to_json_bool "$senha_ok"),
  "ipm_network": $(to_json_bool "$ipm_net_ok"),
  "ipm_network_http": "${code}",
  "cert_a1_optional": $(to_json_bool "$cert_ok"),
  "blocker": ${blocker},
  "url": "https://vps12436.panel.icontainer.site/"
}
EOF
