#!/usr/bin/env bash
# Backup diário Postgres + JSON de histórico (VPS).
# Cron sugerido:
#   15 3 * * * /opt/rosafiscal/deploy/scripts/backup_nfse.sh >> /var/log/rosafiscal-backup.log 2>&1
set -euo pipefail
ROOT=/opt/rosafiscal
BACKUP_ROOT=/opt/rosafiscal/backups
STAMP=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"
cd "$ROOT"

docker compose exec -T db pg_dump -U nfse -d nfse --no-owner --no-acl \
  | gzip > "$DEST/nfse.sql.gz"

if docker compose exec -T app test -f /app/data/nfse_emitidas.json; then
  docker compose cp app:/app/data/nfse_emitidas.json "$DEST/nfse_emitidas.json"
fi

# retenção 14 dias
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +

echo "Backup OK: $DEST"
ls -lh "$DEST"
