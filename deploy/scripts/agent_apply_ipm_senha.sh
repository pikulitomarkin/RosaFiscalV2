#!/usr/bin/env bash
# Roda no Cloud Agent (não na VPS): se IPM_SENHA estiver no ambiente,
# envia via SSH para set_ipm_senha.sh --stdin sem imprimir o valor.
#
# Uso:
#   export IPM_SENHA=...   # via Cursor Secrets (nunca no chat)
#   ./deploy/scripts/agent_apply_ipm_senha.sh
set -euo pipefail

if [[ -z "${IPM_SENHA:-}" ]]; then
  echo "IPM_SENHA ausente no ambiente do agent — nada a aplicar."
  exit 2
fi

KEY="${ROSAFISCAL_SSH_KEY:-$HOME/.ssh/rosafiscal_vps}"
HOST="${ROSAFISCAL_SSH_HOST:-root@184.107.179.79}"

if [[ ! -f "$KEY" ]]; then
  echo "Chave SSH não encontrada: $KEY" >&2
  exit 1
fi

# Pipe senha sem eco; remoto aplica .env + runtime_config + recreate app
printf '%s' "$IPM_SENHA" | ssh -i "$KEY" -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=20 "$HOST" \
  'bash /opt/rosafiscal/deploy/scripts/set_ipm_senha.sh --stdin'

echo "Aplicado na VPS. Rodando post_cutover_check..."
ssh -i "$KEY" -o ConnectTimeout=20 "$HOST" \
  'bash /opt/rosafiscal/deploy/scripts/post_cutover_check.sh'
