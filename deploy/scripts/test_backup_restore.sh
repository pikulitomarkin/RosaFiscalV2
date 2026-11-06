#!/usr/bin/env bash
# Dry-run: restaura o backup .sql.gz mais recente num DB temporário e confere contagens.
# Não altera o banco de produção `nfse`.
set -euo pipefail
ROOT=/opt/rosafiscal
cd "$ROOT"

LATEST="$(find "$ROOT/backups" -type f -name 'nfse.sql.gz' | sort | tail -1)"
if [[ -z "$LATEST" ]]; then
  echo "Nenhum backup nfse.sql.gz encontrado em $ROOT/backups" >&2
  exit 1
fi

TMP_DB="nfse_restore_test_$$"
echo "Usando backup: $LATEST"
echo "DB temporário: $TMP_DB"

docker compose exec -T db psql -U nfse -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${TMP_DB};" \
  -c "CREATE DATABASE ${TMP_DB} OWNER nfse;"

gunzip -c "$LATEST" | docker compose exec -T db psql -U nfse -d "$TMP_DB" -v ON_ERROR_STOP=1 >/tmp/restore_test_${TMP_DB}.log

EMISSOES=$(docker compose exec -T db psql -U nfse -d "$TMP_DB" -Atc "SELECT count(*) FROM nfse_emissoes;")
USUARIOS=$(docker compose exec -T db psql -U nfse -d "$TMP_DB" -Atc "SELECT count(*) FROM usuarios;")
PROD_E=$(docker compose exec -T db psql -U nfse -d nfse -Atc "SELECT count(*) FROM nfse_emissoes;")
PROD_U=$(docker compose exec -T db psql -U nfse -d nfse -Atc "SELECT count(*) FROM usuarios;")

echo "restore_emissoes=$EMISSOES prod_emissoes=$PROD_E"
echo "restore_usuarios=$USUARIOS prod_usuarios=$PROD_U"

docker compose exec -T db psql -U nfse -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${TMP_DB};"

if [[ "$EMISSOES" -lt 1 || "$USUARIOS" -lt 1 ]]; then
  echo "FAIL: restore sem dados esperados"
  exit 2
fi
if [[ "$EMISSOES" -ne "$PROD_E" ]]; then
  echo "WARN: contagem de emissões do backup != produção (backup pode ser anterior)"
fi
echo "OK: restore dry-run validado (DB temporário removido)"
