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
| **Deploy branch na VPS** | tip `379fee2` + rebuild app | **OK** |
| Seed `nathalia` + `guilherme` | senha login `admin`; ambos `is_admin` | **OK** |
| Cert A1 por usuário (PFX) | `data/certs/{user}/` | PENDENTE (UI — enviar PFX) |
| Endereço/CNPJ por usuário | nathalia OK; guilherme preencher na UI | PARCIAL |
| Emissão Sefin validada | smoke real com A1 | PENDENTE |
| Desligar Railway | só após emissão validada | PENDENTE |

## Status ops (2026-11-10)

- SSH do Cloud Agent restaurado (chave `cursor-cloud-rosafiscal-20261110` em `authorized_keys`).
- `cutover_ready=true`, `emission_backend=sefin`, `validate_migracao.sh` → OK=10 FAIL=0.
- Gate Railway aberto (`railway_shutdown_gate.sh`); **não desligar** até smoke de emissão Sefin com certificado A1.

Logins produção: https://vps12436.panel.icontainer.site/

| Usuário | Senha | CNPJ |
|---------|-------|------|
| `nathalia` | `admin` | `56169351000185` |
| `guilherme` | `admin` | (Configurações) |

## Nota sobre IPM
O fluxo padrão passou a ser **Sefin (API nacional)**. IPM permanece legado (`emission_backend=ipm`). `IPM_SENHA` / auth 401 **não** bloqueiam o cutover sefin.
