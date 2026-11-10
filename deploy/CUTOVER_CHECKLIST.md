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
| Cert A1 nathalia | `/app/data/certs/nathalia/{cert,key}.pem` CNPJ `56169351000185` | **OK** |
| Cert A1 guilherme (Neuroclin) | PFX perdido após swap — reenviar na UI | **BLOQUEIO** |
| Endereço/CNPJ por usuário | nathalia OK (`4317202`); guilherme preencher | PARCIAL |
| IBGE Santa Rosa | `4317202` (corrigido; era `4318002`) | **OK** |
| Regime SN DPS | `opSimpNac=3` ME/EPP + `regApTribSN=1` (enum oficial; 2=MEI) | **OK (código)** |
| Emissão Sefin validada | smoke real com A1 nathalia | **PENDENTE / ver smoke** |
| Desligar Railway | só após smoke sucesso + `RAILWAY_TOKEN` | **BLOQUEIO MANUAL** |

## Correção E0160 (2026-11-10)

Sefin oficial: `opSimpNac` **1=Não optante, 2=MEI, 3=ME/EPP**.  
Código antigo enviava `2` para SN ME/EPP (Nathalia) → Sefin lia como MEI → **E0160**.  
BrasilAPI confirma CNPJ `56169351000185`: `opcao_pelo_simples=true`, `opcao_pelo_mei=false`, porte MICRO EMPRESA.

Configurável em `shared_tax` / UI Configurações: `mei`, `op_simp_nac`, `reg_ap_trib_sn`.

## Bloqueio produto / ops

Santa Rosa responde IPM **00378 — Emissor Nacional**. IPM legado **não emite**.

```bash
# Smoke (após deploy)
scp deploy/scripts/smoke_sefin_vps.py root@VPS:/tmp/
ssh root@VPS 'docker cp /tmp/smoke_sefin_vps.py rosafiscal-app-1:/tmp/ && \
  docker compose -f /opt/rosafiscal/docker-compose.yml exec -T \
  -e SMOKE_CPF=96362790049 -e SMOKE_NOME="Francieli da costa colla" \
  app python /tmp/smoke_sefin_vps.py'

# Gate Railway (precisa emission_ready + smoke)
bash /opt/rosafiscal/deploy/scripts/railway_shutdown_gate.sh
```

Sem `RAILWAY_TOKEN` neste ambiente: **pause do Railway é manual no painel**.

`cutover_ready=true` = infra VPS OK.  
`emission_ready=true` = pelo menos 1 usuário com A1 em `/app/data/certs/{user}/`.

## Status ops (2026-11-10)

- SSH Cloud Agent OK (chave `/home/ubuntu/.ssh/rosafiscal_vps`).
- Guilherme: reenviar PFX Neuroclin depois (não bloqueia smoke nathalia).
- Logins: https://vps12436.panel.icontainer.site/

| Usuário | Senha | CNPJ |
|---------|-------|------|
| `nathalia` | `admin` | `56169351000185` |
| `guilherme` | `admin` | (Configurações / PFX pendente) |
