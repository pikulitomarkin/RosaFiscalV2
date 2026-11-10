#!/usr/bin/env bash
# Cole este script no Terminal do ICP (Server → Terminal):
#   https://vps12436.panel.icontainer.site:2090/admin
#
# Autoriza a chave do Cloud Agent atual e tenta desbanir IPs no fail2ban.
set -euo pipefail
PUB='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAIzVVbceUBZMfbnyC/L08wPIaEsVtJdib/05SryzN7O cursor-cloud-rosafiscal-20261110'

mkdir -p /root/.ssh
chmod 700 /root/.ssh
touch /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
grep -qxF "$PUB" /root/.ssh/authorized_keys || echo "$PUB" >> /root/.ssh/authorized_keys

# Desbanir SSH (fail2ban pode ter bloqueado o Cloud Agent)
if command -v fail2ban-client >/dev/null 2>&1; then
  fail2ban-client status sshd 2>/dev/null || true
  fail2ban-client set sshd unbanip --all 2>/dev/null || true
  # reinicia jail se unbanip --all não existir nesta versão
  fail2ban-client reload sshd 2>/dev/null || systemctl reload fail2ban 2>/dev/null || true
fi

# Garantir sshd escutando
systemctl is-active ssh || systemctl is-active sshd || true
ss -tlnp | grep -E ':22\b' || true

echo "AUTHORIZED_KEYS_OK"
echo "Pub fingerprint expected: SHA256:aWNOsBKsjS5cXvKCg4xgt1lD3OanN3r78bjaogecwqE"
if test -f /root/rosafiscal_rotated_credentials.txt; then
  echo "CRED_FILE=/root/rosafiscal_rotated_credentials.txt (existe; não imprimido)"
fi
echo "Avise o Cloud Agent para rodar: ./deploy/scripts/agent_deploy_vps.sh"
