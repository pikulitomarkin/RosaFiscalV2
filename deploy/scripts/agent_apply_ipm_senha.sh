#!/usr/bin/env bash
# Roda no Cloud Agent (não na VPS): aplica IPM_SENHA na VPS sem imprimir o valor.
#
# Fontes (primeira que existir ganha):
#   1) env IPM_SENHA (Cursor Secrets)
#   2) arquivo local secrets/ipm_senha (gitignored)
#
# Uso:
#   ./deploy/scripts/agent_apply_ipm_senha.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
umask 077

SENHA="${IPM_SENHA:-}"
FILE=""
for c in "$ROOT/secrets/ipm_senha" "$ROOT/secrets/IPM_SENHA" "$ROOT/secrets/ipm_senha.txt"; do
  if [[ -z "$SENHA" && -f "$c" ]]; then
    SENHA="$(tr -d '\r\n' < "$c")"
    FILE="$c"
  fi
done

if [[ -z "${SENHA}" ]]; then
  echo "IPM_SENHA ausente (env e secrets/ipm_senha) — nada a aplicar."
  exit 2
fi

KEY="${ROSAFISCAL_SSH_KEY:-$HOME/.ssh/rosafiscal_vps}"
HOST="${ROSAFISCAL_SSH_HOST:-root@184.107.179.79}"

if [[ ! -f "$KEY" ]]; then
  echo "Chave SSH não encontrada: $KEY" >&2
  exit 1
fi

printf '%s' "$SENHA" | ssh -i "$KEY" -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=20 "$HOST" \
  'bash /opt/rosafiscal/deploy/scripts/set_ipm_senha.sh --stdin'

unset SENHA
if [[ -n "$FILE" ]]; then
  shred -u "$FILE" 2>/dev/null || rm -f "$FILE"
  echo "Arquivo local de senha removido após aplicar."
fi

echo "Aplicado na VPS. Rodando post_cutover_check..."
ssh -i "$KEY" -o ConnectTimeout=30 "$HOST" \
  'bash /opt/rosafiscal/deploy/scripts/post_cutover_check.sh'
