#!/usr/bin/env bash
# Aplica /opt/rosafiscal/secrets/ipm_senha assim que o arquivo existir.
# Instalar (cron a cada minuto):
#   * * * * * /opt/rosafiscal/deploy/scripts/watch_ipm_senha.sh >> /var/log/rosafiscal-ipm-watch.log 2>&1
set -euo pipefail
ROOT=/opt/rosafiscal
FILE="$ROOT/secrets/ipm_senha"
LOCK=/var/lock/rosafiscal-ipm-watch.lock
LOG_TAG='[watch_ipm_senha]'

[[ -f "$FILE" ]] || exit 0

exec 9>"$LOCK"
if ! flock -n 9; then
  exit 0
fi

# Evita aplicar arquivo vazio / ainda em edição
size=$(wc -c < "$FILE" | tr -d ' ')
if [[ "$size" -lt 1 ]]; then
  echo "$(date -Is) $LOG_TAG arquivo vazio — ignorado"
  exit 0
fi

echo "$(date -Is) $LOG_TAG aplicando senha a partir de $FILE (bytes=$size)"
"$ROOT/deploy/scripts/apply_ipm_senha_from_file.sh" "$FILE"
echo "$(date -Is) $LOG_TAG ok"
