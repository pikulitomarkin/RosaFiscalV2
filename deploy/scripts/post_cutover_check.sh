#!/usr/bin/env bash
# Roda após IPM_SENHA existir: validate + auth teste + status.
set -euo pipefail
ROOT=/opt/rosafiscal
cd "$ROOT"

bash deploy/scripts/validate_migracao.sh
docker compose exec -T app python deploy/scripts/test_ipm_auth.py
bash deploy/scripts/cutover_status.sh

echo
echo "Se cutover_ready=true e test_ipm_auth OK, pode desligar o Railway."
echo "Troque a senha root da VPS (passwd) — ela já foi exposta no chat/screenshot."
