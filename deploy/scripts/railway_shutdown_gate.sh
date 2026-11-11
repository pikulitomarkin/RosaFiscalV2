#!/usr/bin/env bash
# Libera cutover completo só quando VPS está pronta E o Railway antigo está offline.
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
print(f"MIGRATION={'true' if data.get('migration_complete') else 'false'}")
print(f"RAILWAY_LIVE={'true' if data.get('railway_live') else 'false'}")
print(f"BLOCKER={data.get('blocker')!r}")
print(f"RAILWAY_URL={data.get('railway_url')!r}")
print(f"RAILWAY_PROJECT={data.get('railway_project')!r}")
PY
)"

if [[ "$READY" != "true" ]]; then
  echo
  echo "GATE FECHADO: cutover_ready=false (blocker=${BLOCKER})."
  echo "Não desligue o Railway ainda."
  exit 2
fi

if [[ "$EMISSION" != "true" ]]; then
  echo
  echo "INFRA OK — EMISSÃO BLOQUEADA (emission_ready=false, blocker=${BLOCKER})."
  exit 3
fi

if [[ "$RAILWAY_LIVE" == "true" ]]; then
  echo
  echo "VPS PRONTA — Railway AINDA VIVO (migration_complete=false)."
  echo "blocker=${BLOCKER}"
  echo "Health: ${RAILWAY_URL}/_stcore/health"
  echo "Painel: ${RAILWAY_PROJECT}"
  echo "Preferencial: pause no painel (RAILWAY_TOKEN foi skipped)."
  echo "Opcional se token existir: ./deploy/scripts/agent_pause_railway.sh"
  echo "URL oficial: https://vps12436.panel.icontainer.site/"
  exit 4
fi

cat <<'EOF'

CUTOVER COMPLETO — migration_complete=true
VPS em produção e Railway antigo offline.
URL oficial: https://vps12436.panel.icontainer.site/

EOF
exit 0
