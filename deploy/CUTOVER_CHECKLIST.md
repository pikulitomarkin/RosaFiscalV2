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
| Branch API nacional no Git | `cursor/api-nacional-multiusuario-ddd1` / PR #3 | OK |
| **Deploy branch na VPS** | tip atual + rebuild app | **OK** |
| Seed `nathalia` + `guilherme` | senha login `admin`; ambos `is_admin` | **OK** |
| Cert A1 por usuário (PFX) | `/app/data/certs/{user}/` no volume | **BLOQUEIO** |
| Endereço/CNPJ por usuário | nathalia OK; guilherme preencher na UI | PARCIAL |
| Emissão Sefin validada | smoke real com A1 | **BLOQUEIO** |
| Desligar Railway | só após `emission_ready=true` + smoke | **BLOQUEIO** |

## Bloqueio atual (produto)

Santa Rosa responde IPM **00378 — Emissor Nacional**. O caminho legado IPM **não emite**.

Sem PFX A1 da nathalia (CNPJ `56169351000185`) não há smoke de emissão nem pause do Railway.

```bash
# Opção UI
# https://vps12436.panel.icontainer.site/ → nathalia/admin → Configurações → enviar PFX

# Opção CLI na VPS
CERT_PASS='senha-do-pfx' /opt/rosafiscal/deploy/scripts/install_user_pfx.sh nathalia /caminho/nathalia.pfx
docker compose exec -T app python deploy/scripts/check_sefin_certs.py
bash /opt/rosafiscal/deploy/scripts/railway_shutdown_gate.sh   # precisa emission_ready=true
```

`cutover_ready=true` = infra VPS OK.  
`emission_ready=true` = pelo menos 1 usuário com A1 em `/app/data/certs/{user}/`.

## Status ops (2026-11-10)

- SSH do Cloud Agent restaurado (chave `cursor-cloud-rosafiscal-20261110`).
- PEM em `certificados/backup_gabriel/` é de **outro CNPJ** (Gabriel) — não usar.
- Sem `RAILWAY_TOKEN` neste ambiente: pause do Railway é manual no painel.

Logins: https://vps12436.panel.icontainer.site/

| Usuário | Senha | CNPJ |
|---------|-------|------|
| `nathalia` | `admin` | `56169351000185` |
| `guilherme` | `admin` | (Configurações) |
