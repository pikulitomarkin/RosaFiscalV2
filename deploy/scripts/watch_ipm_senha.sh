#!/usr/bin/env bash
# Aplica /opt/rosafiscal/secrets/ipm_senha assim que o arquivo existir.
# Instalar (cron a cada minuto):
#   * * * * * /opt/rosafiscal/deploy/scripts/watch_ipm_senha.sh >> /var/log/rosafiscal-ipm-watch.log 2>&1
set -euo pipefail
ROOT=/opt/rosafiscal
LOCK=/var/lock/rosafiscal-ipm-watch.lock
LOG_TAG='[watch_ipm_senha]'

# Aceita vários drop-paths (primeiro arquivo não vazio ganha)
CANDIDATES=(
  "$ROOT/secrets/ipm_senha"
  "$ROOT/secrets/IPM_SENHA"
  "$ROOT/secrets/ipm_senha.txt"
)

FILE=""
for c in "${CANDIDATES[@]}"; do
  [[ -f "$c" ]] || continue
  size=$(wc -c < "$c" | tr -d ' ')
  if [[ "$size" -ge 1 ]]; then
    FILE="$c"
    break
  fi
done

[[ -n "$FILE" ]] || exit 0

exec 9>"$LOCK"
if ! flock -n 9; then
  exit 0
fi

size=$(wc -c < "$FILE" | tr -d ' ')
echo "$(date -Is) $LOG_TAG aplicando senha a partir de $FILE (bytes=$size)"
"$ROOT/deploy/scripts/apply_ipm_senha_from_file.sh" "$FILE"
echo "$(date -Is) $LOG_TAG ok"
