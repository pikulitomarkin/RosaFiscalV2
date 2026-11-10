#!/usr/bin/env bash
# Só libera desligar o Railway quando infra + emissão estiverem prontas.
# Uso: /opt/rosafiscal/deploy/scripts/railway_shutdown_gate.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

STATUS_JSON="$(bash deploy/scripts/cutover_status.sh)"
echo "$STATUS_JSON"

eval "$(
  STATUS_JSON="$STATUS_JSON" python3 - <<'PY'
import json, os, re
raw = os.environ.get("STATUS_JSON", "")
m = re.search(r"\{.*\}", raw, flags=re.S)
data = json.loads(m.group(0)) if m else {}
print(f"READY={'true' if data.get('cutover_ready') else 'false'}")
print(f"EMISSION={'true' if data.get('emission_ready') else 'false'}")
print(f"BLOCKER={data.get('blocker')!r}")
print(f"IPM_NACIONAL={'true' if data.get('ipm_emissor_nacional') else 'false'}")
print(f"SEFIN_CERT={int(data.get('sefin_cert_users') or 0)}")
PY
)"

if [[ "$READY" != "true" ]]; then
  echo
  echo "GATE FECHADO: cutover_ready=false (blocker=${BLOCKER})."
  echo "Sefin: precisa seed nathalia/guilherme + schema (deploy branch API nacional)."
  echo "Não desligue o Railway ainda."
  exit 2
fi

if [[ "$EMISSION" != "true" ]]; then
  echo
  echo "INFRA OK (cutover_ready=true) — EMISSÃO BLOQUEADA (emission_ready=false)."
  echo "blocker=${BLOCKER}"
  if [[ "$IPM_NACIONAL" == "true" ]]; then
    echo "Santa Rosa usa Emissor Nacional (IPM erro 00378). IPM legado NÃO emite mais."
  fi
  echo "Instale o PFX A1 da nathalia (CNPJ 56169351000185):"
  echo "  UI: https://vps12436.panel.icontainer.site/ → Configurações → enviar PFX"
  echo "  ou: CERT_PASS='...' ./deploy/scripts/install_user_pfx.sh nathalia /caminho/arquivo.pfx"
  echo "Depois: docker compose exec -T app python deploy/scripts/check_sefin_certs.py"
  echo "Só então emita 1 NFS-e de smoke e pause o Railway."
  exit 3
fi

cat <<'EOF'

GATE ABERTO — cutover_ready=true e emission_ready=true
Checklist para desligar o Railway (manual):
1. Confirme emissão real de 1 NFS-e pela VPS (Sefin/A1).
2. No Railway: pause/stop o serviço Streamlit antigo (não delete o volume/DB até backup extra).
3. Remova DNS/custom domain apontando ao Railway, se houver.
4. Mantenha só https://vps12436.panel.icontainer.site/ como URL oficial.
5. Guarde RAILWAY_TOKEN só se ainda precisar exportar variáveis; depois revogue.
6. Rode um backup extra: /opt/rosafiscal/deploy/scripts/backup_nfse.sh

EOF
exit 0
