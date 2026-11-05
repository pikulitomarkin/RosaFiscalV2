#!/usr/bin/env bash
# Aplica IPM_SENHA a partir de um arquivo local (não commitado) e apaga o arquivo.
#
# Uso na VPS:
#   umask 077
#   mkdir -p /opt/rosafiscal/secrets
#   # cole a senha UMA linha, sem aspas, sem newline no final se possível:
#   nano /opt/rosafiscal/secrets/ipm_senha
#   chmod 600 /opt/rosafiscal/secrets/ipm_senha
#   /opt/rosafiscal/deploy/scripts/apply_ipm_senha_from_file.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FILE="${1:-$ROOT/secrets/ipm_senha}"
cd "$ROOT"

if [[ ! -f "$FILE" ]]; then
  echo "Arquivo não encontrado: $FILE" >&2
  echo "Crie-o com a senha Atende.Net (uma linha) e rode de novo." >&2
  exit 1
fi

SENHA="$(tr -d '\r\n' < "$FILE")"
if [[ -z "$SENHA" ]]; then
  echo "Arquivo vazio — abortado." >&2
  exit 1
fi

printf '%s' "$SENHA" | "$ROOT/deploy/scripts/set_ipm_senha.sh" --stdin
shred -u "$FILE" 2>/dev/null || rm -f "$FILE"
echo "Arquivo $FILE removido após aplicar."
