# Checklist cutover Railway → VPS

Atualizado com evidência na VPS `184.107.179.79` e migração para **API Nacional (Sefin)**.

| Requisito | Evidência | Status |
|-----------|-----------|--------|
| App Docker no ar | `docker compose ps` app Up | OK |
| Postgres com dados | 3662 `nfse_emissoes`, usuários Railway | OK |
| Histórico JSON | `/app/data/nfse_emitidas.json` | OK |
| HTTP local | `:8501/_stcore/health` → 200 | OK |
| HTTPS produção | `https://vps12436.panel.icontainer.site/` → 200 | OK |
| Docker no boot | `systemctl is-enabled docker` | OK |
| Backup automático | cron 03:15 | OK |
| Restore dry-run | backup `20261105_203203` | OK |
| Root/admin rotacionados | `/root/rosafiscal_rotated_credentials.txt` | OK (ops: cofre) |
| Branch API nacional no Git | `cursor/api-nacional-multiusuario-ddd1` / PR #3 | OK (código) |
| **Deploy branch na VPS** | git tip = PR #3 + seed | **BLOQUEADO (SSH)** |
| Seed `nathalia` + `guilherme` | `seed_multiusuarios.py` (senha `admin`) | PENDENTE (após deploy) |
| Cert A1 por usuário (PFX) | `data/certs/{user}/` | PENDENTE (UI) |
| Endereço/CNPJ por usuário | colunas + Configurações | PENDENTE (deploy) |
| Emissão Sefin validada | smoke real | PENDENTE |
| Desligar Railway | só após emissão validada | PENDENTE |

## Bloqueio atual (ops)
Acesso SSH do Cloud Agent: senha root antiga inválida; chave privada da migração perdida no VM efêmero.
Porta 22 pode estar em **fail2ban** para o IP do agent após tentativas falhas.

**Recuperação via ICP (confirmado HTTP 200):**  
https://vps12436.panel.icontainer.site:2090/admin → **Server → Terminal**

```bash
cat /root/rosafiscal_rotated_credentials.txt
mkdir -p /root/.ssh && chmod 700 /root/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAIzVVbceUBZMfbnyC/L08wPIaEsVtJdib/05SryzN7O cursor-cloud-rosafiscal-20261110' >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
# se fail2ban bloqueou o agent:
fail2ban-client set sshd unbanip --all 2>/dev/null || true
```

Guia: `deploy/SSH_RECOVERY.md`  
Depois: `./deploy/scripts/agent_deploy_vps.sh`

## Nota sobre IPM
O fluxo padrão passou a ser **Sefin (API nacional)**. IPM permanece legado (`emission_backend=ipm`). `IPM_SENHA` / auth 401 **não** bloqueiam o cutover sefin.
