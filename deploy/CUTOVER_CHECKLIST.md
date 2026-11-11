# Checklist cutover Railway → VPS

Atualizado com evidência na VPS `184.107.179.79` (API Nacional / Sefin).

| Requisito | Evidência | Status |
|-----------|-----------|--------|
| App Docker no ar | `docker compose ps` app Up | OK |
| Postgres com dados | **3663** `nfse_emissoes` (inclui smoke) | OK |
| Histórico JSON | `/app/data/nfse_emitidas.json` | OK |
| HTTP local | `:8501/_stcore/health` → 200 | OK |
| HTTPS produção | `https://vps12436.panel.icontainer.site/` → 200 | OK |
| Docker no boot | `systemctl is-enabled docker` | OK |
| Backup automático | cron 03:15 | OK |
| Restore dry-run | backup `20261105_203203` | OK |
| Backup pós-smoke | `backups/20261110_205138/` | **OK** |
| Root/admin rotacionados | `/root/rosafiscal_rotated_credentials.txt` | OK (ops: cofre) |
| Branch API nacional | `cursor/api-nacional-multiusuario-ddd1` / PR #3 | OK |
| Deploy na VPS | tip atual + rebuild | **OK** |
| Seed `nathalia` + `guilherme` | senha `admin` | **OK** |
| Cert A1 nathalia | `/app/data/certs/nathalia/` CNPJ `56169351000185` | **OK** |
| Cert A1 guilherme | reenviar PFX na UI | PENDENTE (não bloqueia nathalia) |
| IBGE Santa Rosa | `4317202` | **OK** |
| Regime SN DPS | `opSimpNac=3` + `regApTribSN=1` | **OK** |
| Emissão Sefin | id `3663` / chave abaixo | **OK** |
| Gate cutover | `cutover_ready` + `emission_ready` | **OK** |
| Desligar Railway | **ainda vivo** `rosafiscalv2.up.railway.app` health=200 | **ÚNICO BLOQUEIO OPS** |

## Smoke Sefin (evidência no Postgres)

```
id=3663 usuario=nathalia status=sucesso
hash=SMOKE-VPS-8d3ca228331f4bc1
chave=43172022256169351000185000000000000126114512958866
cMun=4317202 opSimpNac=3 mei=false regApTribSN=1
created_at=2026-11-10 23:50:26 UTC (20:50 America/Sao_Paulo)
```

## Correção E0160

Enum oficial: `opSimpNac` **1=Não optante, 2=MEI, 3=ME/EPP**.  
Código antigo enviava `2` para ME/EPP → Sefin tratava como MEI → E0160.

## Pause Railway (último passo — bloqueado sem token)

Gate VPS aberto. Backup pós-smoke: `20261110_205138`.

**Railway ainda ONLINE (probe 2026-11-10):**
- Health 200: https://rosafiscalv2.up.railway.app/_stcore/health
- Painel: https://railway.com/project/0dff8bdf-7c3c-4cda-8ca5-34c48a9aa7a6?environmentId=d845247a-c997-4fec-bb0d-b0e1cb1ccd76
- Probe: `./deploy/scripts/probe_railway_live.sh` (exit 1 = ainda vivo)

**Opção A — painel:** pause/stop do serviço no link acima (não apague DB/volume).

**Opção B — agent/CLI** (precisa `RAILWAY_TOKEN`):

```bash
# https://railway.app/account/tokens
printf '%s' 'TOKEN' > secrets/RAILWAY_TOKEN && chmod 600 secrets/RAILWAY_TOKEN
./deploy/scripts/agent_pause_railway.sh
./deploy/scripts/probe_railway_live.sh   # deve sair 0 (offline)
```

URL oficial de produção: https://vps12436.panel.icontainer.site/

## Logins

| Usuário | Senha | CNPJ |
|---------|-------|------|
| `nathalia` | `admin` | `56169351000185` |
| `guilherme` | `admin` | (enviar PFX) |
