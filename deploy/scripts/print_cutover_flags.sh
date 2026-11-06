#!/usr/bin/env bash
# Flags one-line (sem segredos) para polling do agent.
# Saída: cutover_ready ipm_senha ipm_auth ipm_auth_http blocker drop
set -euo pipefail
ROOT=/opt/rosafiscal
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/opt/rosafiscal/CUTOVER_STATUS.json")
d = json.loads(p.read_text()) if p.exists() and p.stat().st_size else {}
drop = Path("/opt/rosafiscal/secrets/ipm_senha")
print(
    int(bool(d.get("cutover_ready"))),
    int(bool(d.get("ipm_senha"))),
    int(bool(d.get("ipm_auth"))),
    d.get("ipm_auth_http") or "000",
    d.get("blocker") or "none",
    int(bool(drop.exists() and drop.stat().st_size > 0)),
)
PY
