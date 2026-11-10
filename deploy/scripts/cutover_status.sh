#!/usr/bin/env bash
# Status JSON do cutover Railway → VPS (sem imprimir segredos).
# Aceita emission_backend=sefin (padrão) ou ipm (legado).
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
sefin_users_ok=false
sefin_cols_ok=false
code=000
backend=sefin

docker compose ps --status running 2>/dev/null | grep -q rosafiscal-app && app_up=true || true
curl -sf -o /dev/null http://127.0.0.1:8501/_stcore/health && http_ok=true || true
curl -skf -o /dev/null https://vps12436.panel.icontainer.site/_stcore/health && https_ok=true || true

db_emissoes=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from nfse_emissoes" 2>/dev/null || echo 0)
db_usuarios=$(docker compose exec -T db psql -U nfse -d nfse -Atc "select count(*) from usuarios" 2>/dev/null || echo 0)
docker compose exec -T app test -s /app/data/nfse_emitidas.json && json_ok=true || true

backend=$(
  docker compose exec -T app python - <<"PY" 2>/dev/null || echo sefin
from src.utils.runtime_config import get_emission_backend
print(get_emission_backend())
PY
)
backend=$(echo "$backend" | tr -d '\r' | tail -n1)
[[ "$backend" == "ipm" || "$backend" == "sefin" ]] || backend=sefin

if docker compose exec -T app python - <<"PY" >/dev/null 2>&1
from src.utils.runtime_config import ipm_senha_configurada, get_ipm_senha
raise SystemExit(0 if ipm_senha_configurada() and len(get_ipm_senha()) >= 4 else 1)
PY
then senha_ok=true; fi

code=$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 \
  -u '0:0' -F 'teste=@/etc/hosts;type=text/xml' \
  'https://ws-santarosa.atende.net/?pg=rest&service=WNERestServiceNFSe' || echo 000)
[[ "$code" == "401" || "$code" == "403" || "$code" == "200" ]] && ipm_net_ok=true || true

auth_ok=false
auth_http=000
if $senha_ok; then
  auth_http=$(
    docker compose exec -T app python - <<"PY" 2>/dev/null || echo 000
import re
import httpx
from src.utils.runtime_config import get_ipm_senha, get_ipm_usuario
from config.settings import settings
usuario = re.sub(r"\D", "", get_ipm_usuario() or "")
senha = get_ipm_senha() or ""
url = (settings.IPM_WEBSERVICE_URL or "").rstrip("/")
try:
    r = httpx.post(
        url,
        files={"teste": ("probe.xml", b"<nfse/>", "text/xml")},
        auth=(usuario, senha),
        timeout=15.0,
    )
    print(r.status_code)
except Exception:
    print("000")
PY
  )
  auth_http=$(echo "$auth_http" | tr -d '\r' | tail -n1)
  if [[ "$auth_http" != "401" && "$auth_http" != "403" && "$auth_http" != "000" ]]; then
    auth_ok=true
  fi
fi

test -s certificados/cert.pem && test -s certificados/key.pem && cert_ok=true || true

c_users=$(docker compose exec -T db psql -U nfse -d nfse -Atc \
  "select count(*) from usuarios where username in ('nathalia','guilherme') and is_active" 2>/dev/null || echo 0)
[[ "${c_users}" -ge 2 ]] && sefin_users_ok=true || true
c_col=$(docker compose exec -T db psql -U nfse -d nfse -Atc \
  "select count(*) from information_schema.columns where table_name='usuarios' and column_name in ('cnpj','logradouro')" 2>/dev/null || echo 0)
[[ "${c_col}" -ge 2 ]] && sefin_cols_ok=true || true

# Cert A1 por usuário (volume appdata → /app/data/certs/{user}/)
sefin_cert_ok=false
sefin_cert_count=0
sefin_cert_count=$(
  docker compose exec -T app python - <<"PY" 2>/dev/null || echo 0
from pathlib import Path
n = 0
root = Path("/app/data/certs")
if root.is_dir():
    for d in root.iterdir():
        if d.is_dir() and (d / "cert.pem").is_file() and (d / "key.pem").is_file():
            if (d / "cert.pem").stat().st_size > 0 and (d / "key.pem").stat().st_size > 0:
                n += 1
print(n)
PY
)
sefin_cert_count=$(echo "$sefin_cert_count" | tr -d '\r' | tail -n1)
[[ "${sefin_cert_count}" =~ ^[0-9]+$ ]] || sefin_cert_count=0
[[ "${sefin_cert_count}" -ge 1 ]] && sefin_cert_ok=true || true

# IPM legado: Santa Rosa responde 00378 (Emissor Nacional) — não serve para emissão
ipm_emissor_nacional=false
if $senha_ok; then
  if docker compose exec -T app python - <<"PY" >/dev/null 2>&1
import asyncio
from src.api.ipm_soap_client import IPMSoapClient
from src.utils.rps_xml_generator import RPSXMLGenerator
from src.api.nfse_service import NFSeService

async def probe():
    prestador = NFSeService()._load_default_prestador()
    gen = RPSXMLGenerator(ambiente_teste=True)
    xml = gen.gerar_enviar_lote_rps_sincrono(
        cnpj_prestador=prestador["cnpj"],
        inscricao_municipal=prestador["inscricao_municipal"],
        numero_lote=1, numero_rps=1, serie_rps="A",
        cpf_tomador="00000000191", nome_tomador="PROBE",
        descricao="PROBE", valor=1.0, aliquota_iss=2.01,
        codigo_servico="40303", nbs="1.2301.21.00",
        bairro_tomador="CENTRO", cep_tomador="98780000",
        logradouro_tomador="RUA",
    )
    r = await IPMSoapClient().enviar_lote_rps_sincrono(xml)
    msgs = " ".join(str(x) for x in (r.get("mensagens") or r.get("erros") or []))
    raise SystemExit(0 if "00378" in msgs or "Emissor Nacional" in msgs else 1)

asyncio.run(probe())
PY
  then ipm_emissor_nacional=true; fi
fi

ready=false
emission_ready=false
blocker=null
if [[ "$backend" == "sefin" ]]; then
  if $app_up && $http_ok && $https_ok && [[ "${db_emissoes}" -gt 0 ]] && [[ "${db_usuarios}" -gt 0 ]] && $json_ok && $sefin_users_ok && $sefin_cols_ok; then
    ready=true
  fi
  if $ready && $sefin_cert_ok; then
    emission_ready=true
  fi
  if [[ "$ready" != "true" ]]; then
    if [[ "$sefin_users_ok" != "true" ]]; then
      blocker='"SEFIN_USERS"'
    elif [[ "$sefin_cols_ok" != "true" ]]; then
      blocker='"SEFIN_SCHEMA"'
    else
      blocker='"other"'
    fi
  elif [[ "$emission_ready" != "true" ]]; then
    blocker='"SEFIN_A1_PFX"'
  fi
else
  if $app_up && $http_ok && $https_ok && [[ "${db_emissoes}" -gt 0 ]] && [[ "${db_usuarios}" -gt 0 ]] && $json_ok && $senha_ok && $auth_ok && $ipm_net_ok; then
    ready=true
  fi
  if $ready && [[ "$ipm_emissor_nacional" != "true" ]]; then
    emission_ready=true
  fi
  if [[ "$ready" != "true" ]]; then
    if [[ "$senha_ok" != "true" ]]; then
      blocker='"IPM_SENHA"'
    elif [[ "$auth_ok" != "true" ]]; then
      blocker='"IPM_AUTH"'
    else
      blocker='"other"'
    fi
  elif [[ "$ipm_emissor_nacional" == "true" ]]; then
    blocker='"IPM_EMISSOR_NACIONAL"'
  fi
fi

json_out=$(cat <<EOF
{
  "cutover_ready": $(to_json_bool "$ready"),
  "emission_ready": $(to_json_bool "$emission_ready"),
  "emission_backend": "${backend}",
  "app_up": $(to_json_bool "$app_up"),
  "http_8501": $(to_json_bool "$http_ok"),
  "https_panel": $(to_json_bool "$https_ok"),
  "db_emissoes": ${db_emissoes:-0},
  "db_usuarios": ${db_usuarios:-0},
  "json_historico": $(to_json_bool "$json_ok"),
  "sefin_users": $(to_json_bool "$sefin_users_ok"),
  "sefin_schema": $(to_json_bool "$sefin_cols_ok"),
  "sefin_cert_users": ${sefin_cert_count:-0},
  "sefin_cert": $(to_json_bool "$sefin_cert_ok"),
  "ipm_senha": $(to_json_bool "$senha_ok"),
  "ipm_auth": $(to_json_bool "$auth_ok"),
  "ipm_auth_http": "${auth_http}",
  "ipm_network": $(to_json_bool "$ipm_net_ok"),
  "ipm_network_http": "${code}",
  "ipm_emissor_nacional": $(to_json_bool "$ipm_emissor_nacional"),
  "cert_a1_optional": $(to_json_bool "$cert_ok"),
  "blocker": ${blocker},
  "url": "https://vps12436.panel.icontainer.site/",
  "icp_admin": "https://vps12436.panel.icontainer.site:2090/admin"
}
EOF
)
printf '%s\n' "$json_out"
tmp="${ROOT}/CUTOVER_STATUS.json.tmp.$$"
printf '%s\n' "$json_out" > "$tmp"
mv -f "$tmp" "$ROOT/CUTOVER_STATUS.json"
if docker compose cp "$ROOT/CUTOVER_STATUS.json" app:/app/data/CUTOVER_STATUS.json >/dev/null 2>&1; then
  :
else
  vol="$(docker volume inspect rosafiscal_appdata -f '{{.Mountpoint}}' 2>/dev/null || true)"
  if [[ -n "$vol" && -d "$vol" ]]; then
    cp -f "$ROOT/CUTOVER_STATUS.json" "$vol/CUTOVER_STATUS.json.tmp"
    mv -f "$vol/CUTOVER_STATUS.json.tmp" "$vol/CUTOVER_STATUS.json" || true
  fi
fi
