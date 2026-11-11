#!/usr/bin/env bash
# Verifica se o Streamlit antigo no Railway ainda responde.
# Exit 0 = offline (bom para cutover); exit 1 = ainda online.
set -euo pipefail
URL="${RAILWAY_PUBLIC_URL:-https://rosafiscalv2.up.railway.app}"
OFFICIAL="${OFFICIAL_URL:-https://vps12436.panel.icontainer.site/}"
CODE="$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 8 --max-time 15 \
  "${URL}/_stcore/health" || echo 000)"
echo "railway_url=${URL}"
echo "railway_health=${CODE}"
echo "railway_project=https://railway.com/project/0dff8bdf-7c3c-4cda-8ca5-34c48a9aa7a6?environmentId=d845247a-c997-4fec-bb0d-b0e1cb1ccd76"
echo "official_url=${OFFICIAL}"
if [[ "$CODE" == "200" ]]; then
  echo "railway_live=true"
  echo "blocker=RAILWAY_STILL_LIVE (pause no painel; RAILWAY_TOKEN skipped)"
  exit 1
fi
echo "railway_live=false"
exit 0
