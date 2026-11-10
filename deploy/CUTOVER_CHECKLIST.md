# Checklist cutover Railway → VPS

Atualizado com evidência na VPS `184.107.179.79` e migração para **API Nacional (Sefin)**.

| Requisito | Evidência | Status |
|-----------|-----------|--------|
| App Docker no ar | `docker compose ps` app Up | OK |
| Postgres com dados | 3663 `nfse_emissoes` (smoke +1) | OK |
| Histórico JSON | `/app/data/nfse_emitidas.json` | OK |
| HTTP local | `:8501/_stcore/health` → 200 | OK |
| HTTPS produção | `https://vps12436.panel.icontainer.site/` → 200 | OK |
| Docker no boot | `systemctl is-enabled docker` | OK |
| Backup automático | cron 03:15 | OK |
| Restore dry-run | backup `20261105_203203` | OK |
| Root/admin rotacionados | `/root/rosafiscal_rotated_credentials.txt` | OK (ops: cofre) |
| Branch API nacional no Git | `cursor/api-nacional-multiusuario-ddd1` / PR #3 | OK |
| **Deploy branch na VPS** | tip `5a38639` + rebuild app | **OK** |
| Seed `nathalia` + `guilherme` | senha login `admin`; ambos `is_admin` | **OK** |
| Cert A1 nathalia | `/app/data/certs/nathalia/{cert,key}.pem` CNPJ `56169351000185` | **OK** |
| Cert A1 guilherme (Neuroclin) | PFX perdido após swap — reenviar na UI | **BLOQUEIO** (não impede nathalia) |
| Endereço/CNPJ por usuário | nathalia OK (`4317202`); guilherme preencher | PARCIAL |
| IBGE Santa Rosa | `4317202` (corrigido; era `4318002`) | **OK** |
| Regime SN DPS | `opSimpNac=3` ME/EPP + `regApTribSN=1` | **OK** |
| Emissão Sefin validada | smoke `status=sucesso` chave abaixo | **OK** |
| Gate cutover | `cutover_ready=true` + `emission_ready=true` | **OK** |
| Desligar Railway | sem `RAILWAY_TOKEN` neste ambiente | **MANUAL** |

## Smoke Sefin (2026-11-10) — SUCESSO

```
usuario=nathalia CNPJ=56169351000185 cMun=4317202
opSimpNac=3 mei=False regApTribSN=1
CPF tomador=96362790049
status=sucesso
numero/chave=43172022256169351000185000000000000226112556677509
hash=SMOKE-VPS-dc0b7697a1f540b3
```

## Correção E0160

Sefin oficial: `opSimpNac` **1=Não optante, 2=MEI, 3=ME/EPP**.  
Código antigo enviava `2` para SN ME/EPP (Nathalia) → Sefin lia como MEI → **E0160**.  
BrasilAPI: CNPJ `56169351000185` `opcao_pelo_simples=true`, `opcao_pelo_mei=false`, porte MICRO EMPRESA.

Configurável em `shared_tax` / UI: `mei`, `op_simp_nac`, `reg_ap_trib_sn`.

## Pause Railway (manual)

`railway_shutdown_gate.sh` → **GATE ABERTO**. Sem `RAILWAY_TOKEN` no Cloud Agent: pause/stop no painel Railway.

```bash
bash /opt/rosafiscal/deploy/scripts/railway_shutdown_gate.sh
# 1) Confirmar smoke (já OK)
# 2) Pause/stop serviço Streamlit no Railway
# 3) Remover DNS custom apontando ao Railway
# 4) URL oficial: https://vps12436.panel.icontainer.site/
# 5) Backup extra: /opt/rosafiscal/deploy/scripts/backup_nfse.sh
```

## Ops

- SSH Cloud Agent OK (`/home/ubuntu/.ssh/rosafiscal_vps`).
- Guilherme: reenviar PFX Neuroclin depois.
- Logins: https://vps12436.panel.icontainer.site/

| Usuário | Senha | CNPJ |
|---------|-------|------|
| `nathalia` | `admin` | `56169351000185` |
| `guilherme` | `admin` | (PFX pendente) |
