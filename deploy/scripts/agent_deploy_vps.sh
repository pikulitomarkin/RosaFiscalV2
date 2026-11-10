#!/usr/bin/env bash
# Deploy do branch atual (ou BRANCH=) na VPS RosaFiscal.
# Auth: ROSAFISCAL_SSH_KEY (preferido) ou SSHPASS + sshpass.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BRANCH="${BRANCH:-cursor/api-nacional-multiusuario-ddd1}"
HOST="${ROSAFISCAL_SSH_HOST:-root@184.107.179.79}"
KEY="${ROSAFISCAL_SSH_KEY:-$HOME/.ssh/rosafiscal_vps}"

run_remote() {
  # Prefer SSHPASS quando definido (chave local pode existir mas ainda não estar na VPS)
  if [[ -n "${SSHPASS:-}" ]]; then
    command -v sshpass >/dev/null || { echo "sshpass ausente" >&2; exit 1; }
    sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no \
      -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 -p 22 "$HOST" "$@"
  elif [[ -f "$KEY" ]]; then
    ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "$HOST" "$@"
  else
    echo "Sem ROSAFISCAL_SSH_KEY nem SSHPASS — configure o secret e rode de novo." >&2
    exit 2
  fi
}

echo "Deploy $BRANCH → $HOST:/opt/rosafiscal"
run_remote "bash -s" <<REMOTE
set -euo pipefail
APP_DIR=/opt/rosafiscal
cd "\$APP_DIR"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
docker compose up -d --build
sleep 8
docker compose exec -T app python deploy/scripts/seed_multiusuarios.py || true
docker compose ps
curl -sf -o /dev/null -w "local_8501=%{http_code}\\n" http://127.0.0.1:8501/ || true
REMOTE

echo "Deploy remoto concluído."
