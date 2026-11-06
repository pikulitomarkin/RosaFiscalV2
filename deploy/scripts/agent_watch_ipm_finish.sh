#!/usr/bin/env bash
# Poll no Cloud Agent até IPM_SENHA aparecer; aplica e valida cutover.
# Uso: bash deploy/scripts/agent_watch_ipm_finish.sh
# Para em sucesso, após max tentativas, ou se cutover já ready na VPS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
KEY="${ROSAFISCAL_SSH_KEY:-$HOME/.ssh/rosafiscal_vps}"
HOST="${ROSAFISCAL_SSH_HOST:-root@184.107.179.79}"
MAX="${IPM_WATCH_MAX:-120}"   # 120 * 30s ~= 1h
SLEEP_S="${IPM_WATCH_SLEEP:-30}"

for i in $(seq 1 "$MAX"); do
  # Já pronto?
  if ssh -i "$KEY" -o ConnectTimeout=15 "$HOST" \
      'python3 -c "import json; d=json.load(open(\"/opt/rosafiscal/CUTOVER_STATUS.json\")); raise SystemExit(0 if d.get(\"cutover_ready\") else 1)"' \
      2>/dev/null; then
    echo "cutover_ready já true — fim."
    exit 0
  fi

  if [[ -n "${IPM_SENHA:-}" ]] || [[ -f "$ROOT/secrets/ipm_senha" ]] || [[ -f "$ROOT/secrets/IPM_SENHA" ]]; then
    echo "senha detectada (tentativa $i) — aplicando..."
    if bash "$ROOT/deploy/scripts/agent_apply_ipm_senha.sh"; then
      echo "cutover apply+validate OK"
      exit 0
    fi
    echo "apply falhou; nova tentativa depois"
  else
    echo "$(date -Is) waiting IPM_SENHA ($i/$MAX)"
  fi
  sleep "$SLEEP_S"
done
echo "timeout aguardando IPM_SENHA"
exit 2
