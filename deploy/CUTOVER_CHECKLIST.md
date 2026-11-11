# Checklist cutover Railway → VPS

Atualizado com evidência na VPS `184.107.179.79` (API Nacional / Sefin).  
Probe refeito em **2026-11-11T00:35Z** (agent cutover).

| Requisito | Evidência | Status |
|-----------|-----------|--------|
| App Docker no ar | `docker compose ps` app Up | OK |
| Postgres pós-wipe | **0** `nfse_emissoes` (wipe intencional; users/certs OK) | OK |
| Histórico JSON | `/app/data/nfse_emitidas.json` | OK |
| HTTP local | `:8501/_stcore/health` → 200 | OK |
| HTTPS produção | `https://vps12436.panel.icontainer.site/` → 200 | OK |
| Docker no boot | `systemctl is-enabled docker` | OK |
| Backup automático | cron 03:15 | OK |
| Restore dry-run | backup `20261105_203203` | OK |
| Backup pós-smoke | `backups/20261110_205138/` | **OK** |
| Backup pré-wipe | `backups/pre_wipe_20261111_003233/` (3663→0) | **OK** |
| Root/admin rotacionados | `/root/rosafiscal_rotated_credentials.txt` | OK (ops: cofre) |
| Branch API nacional | `cursor/api-nacional-multiusuario-ddd1` / PR #3 | OK |
| Deploy multi-tenant VPS | HEAD **`cf0ba22`** (`cursor/deploy-vps-all-fixes-ddd1` / PR #5) | **OK** |
| Seed `nathalia` + `guilherme` | senha `admin`; `db_usuarios=5` | **OK** |
| Cert A1 nathalia | `/app/data/certs/nathalia/` CNPJ `56169351000185` | **OK** |
| Cert A1 (gate) | `sefin_cert_users=2` no `cutover_status` | OK |
| IBGE Santa Rosa | `4317202` | **OK** |
| Regime SN DPS | `opSimpNac=3` + `regApTribSN=1` | **OK** |
| Emissão Sefin (pré-wipe) | id `3663` / chave abaixo (histórico) | **OK** (wipe) |
| Gate cutover | pós-wipe: `cutover_ready=false` / `emission_ready=false` (`db_emissoes=0`, blocker=other) | **pendente re-smoke** |
| Desligar Railway | **ainda vivo** health=200 (probe 2026-11-11T00:35Z) | **ÚNICO BLOQUEIO OPS** |

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

## Progresso não-token (2026-11-11T00:35Z)

- VPS em **`cf0ba22`**: tenant isolation + spinner + cert/sidebar + valor padrão lote (PR #5).
- Emissões limpas (`nfse_emissoes` 3663→**0**); usuários/certs preservados (`db_usuarios=5`, `sefin_cert_users=2`).
- App/HTTPS OK; `railway_live=true` → `migration_complete=false`.
- Gate pós-wipe fecha `cutover_ready`/`emission_ready` até novo smoke de emissão.

## Pause Railway (último passo — token dispensado)

Backup pós-smoke: `20261110_205138`. Backup pré-wipe: `pre_wipe_20261111_003233`.  
`migration_complete` **permanece false** enquanto `railway_live=true`.

**Railway ainda ONLINE (probe 2026-11-11T00:35Z):**
- Health 200: https://rosafiscalv2.up.railway.app/_stcore/health
- Painel: https://railway.com/project/0dff8bdf-7c3c-4cda-8ca5-34c48a9aa7a6?environmentId=d845247a-c997-4fec-bb0d-b0e1cb1ccd76
- Probe: `./deploy/scripts/probe_railway_live.sh` (exit 1 = ainda vivo)
- Gate: `./deploy/scripts/railway_shutdown_gate.sh` → `railway_live=true`, exit **4**
- `RAILWAY_TOKEN` ausente neste agent (`agent_pause_railway.sh` exit 2)

**`RAILWAY_TOKEN` — SKIPPED pelo usuário.** Não aguardar token nem re-solicitar de forma agressiva.  
Caminho operacional restante: **pause/stop no painel** (Opção A). Não apague DB/volume.

**Opção A — painel (preferencial agora):** pause/stop do serviço no link do projeto acima.

**Opção B — agent/CLI** (só se o token voltar a ser fornecido):

```bash
# https://railway.app/account/tokens
printf '%s' 'TOKEN' > secrets/RAILWAY_TOKEN && chmod 600 secrets/RAILWAY_TOKEN
./deploy/scripts/agent_pause_railway.sh
./deploy/scripts/probe_railway_live.sh   # deve sair 0 (offline)
```

**URL oficial de produção (use esta):** https://vps12436.panel.icontainer.site/  
URL legada Railway (não usar após cutover): https://rosafiscalv2.up.railway.app/

## Logins

| Usuário | Senha | CNPJ |
|---------|-------|------|
| `nathalia` | `admin` | `56169351000185` |
| `guilherme` | `admin` | (cert sob outro agent) |
