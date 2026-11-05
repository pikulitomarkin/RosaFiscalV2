#!/usr/bin/env bash
# Roda após IPM_SENHA existir: validate + auth teste + status + evidência.
set -euo pipefail
ROOT=/opt/rosafiscal
cd "$ROOT"
EVID="$ROOT/CUTOVER_EVIDENCE.txt"
umask 077

{
  echo "=== post_cutover_check $(date -Is) ==="
  bash deploy/scripts/validate_migracao.sh
  echo
  echo "=== test_ipm_auth ==="
  docker compose exec -T -w /app app python deploy/scripts/test_ipm_auth.py
  echo
  echo "=== cutover_status ==="
  bash deploy/scripts/cutover_status.sh
  echo
  bash deploy/scripts/railway_shutdown_gate.sh || true
} | tee "$EVID"

# Espelha status no volume do app (UI / ops)
if [[ -f CUTOVER_STATUS.json ]] || bash deploy/scripts/cutover_status.sh > /tmp/cutover_status.json; then
  cp -f /tmp/cutover_status.json "$ROOT/CUTOVER_STATUS.json" 2>/dev/null || true
  docker compose exec -T app mkdir -p /app/data >/dev/null 2>&1 || true
  docker compose cp /tmp/cutover_status.json app:/app/data/CUTOVER_STATUS.json >/dev/null 2>&1 || true
fi

# Gate final
python3 - <<'PY'
import json, pathlib, sys
p = pathlib.Path("/tmp/cutover_status.json")
if not p.exists():
    p = pathlib.Path("/opt/rosafiscal/CUTOVER_STATUS.json")
data = json.loads(p.read_text()) if p.exists() else {}
ok = bool(data.get("cutover_ready"))
print("cutover_ready=", ok)
sys.exit(0 if ok else 1)
PY
