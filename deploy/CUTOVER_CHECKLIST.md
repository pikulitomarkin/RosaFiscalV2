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
Acesso SSH do Cloud Agent à VPS: senha root antiga **não funciona** (foi rotacionada) e a chave `rosafiscal_vps` do agente anterior **não está neste VM**.

Instale a chave pública abaixo em `/root/.ssh/authorized_keys` (console iContainer / KVM) e avise:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAIzVVbceUBZMfbnyC/L08wPIaEsVtJdib/05SryzN7O cursor-cloud-rosafiscal-20261110
```

Ou adicione secret Cursor `SSHPASS` (senha root atual) / `ROSAFISCAL_SSH_KEY` (chave privada).

Depois:
```bash
./deploy/scripts/agent_deploy_vps.sh
# na VPS: seed + PFX por usuário em Configurações
```

## Nota sobre IPM
O fluxo padrão passou a ser **Sefin (API nacional)**. IPM permanece legado (`emission_backend=ipm`). `IPM_SENHA` / auth 401 **não** bloqueiam o cutover sefin.
