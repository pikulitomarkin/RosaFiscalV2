#!/usr/bin/env bash
# Só imprime o checklist para desligar o Railway quando o cutover VPS estiver pronto.
# Uso: /opt/rosafiscal/deploy/scripts/railway_shutdown_gate.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

STATUS_JSON="$(bash deploy/scripts/cutover_status.sh)"
echo "$STATUS_JSON"

READY="$(
  STATUS_JSON="$STATUS_JSON" python3 - <<'PY'
import json, os, re
raw = os.environ.get("STATUS_JSON", "")
# Aceita JSON pretty-printed ou inline
m = re.search(r"\{.*\}", raw, flags=re.S)
if not m:
    print("false")
    raise SystemExit(0)
data = json.loads(m.group(0))
print("true" if data.get("cutover_ready") else "false")
PY
)"

if [[ "$READY" != "true" ]]; then
  echo
  echo "GATE FECHADO: cutover_ready=false."
  echo "Sefin: precisa seed nathalia/guilherme + schema (deploy branch API nacional)."
  echo "IPM legado: IPM_SENHA + auth OK."
  echo "Não desligue o Railway ainda."
  echo "Recuperação SSH: https://vps12436.panel.icontainer.site:2090/admin → Terminal"
  echo "  bash /opt/rosafiscal/deploy/scripts/icp_recover_ssh.sh   # após git pull do branch"
  exit 2
fi

cat <<'EOF'

GATE ABERTO — cutover_ready=true
Checklist para desligar o Railway (manual):
1. Confirme emissão real de 1 NFS-e pela VPS (Sefin com cert A1, ou IPM legado).
2. No Railway: pause/stop o serviço Streamlit antigo (não delete o volume/DB até backup extra).
3. Remova DNS/custom domain apontando ao Railway, se houver.
4. Mantenha só https://vps12436.panel.icontainer.site/ como URL oficial.
5. Guarde RAILWAY_TOKEN só se ainda precisar exportar variáveis; depois revogue.
6. Rode um backup extra: /opt/rosafiscal/deploy/scripts/backup_nfse.sh

EOF
exit 0
