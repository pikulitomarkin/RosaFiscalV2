# Checklist cutover Railway → VPS

Atualizado com evidência na VPS `184.107.179.79` e migração para **API Nacional (Sefin)**.

| Requisito | Evidência | Status |
|-----------|-----------|--------|
| App Docker no ar | `docker compose ps` app Up | OK |
| Postgres com dados | 3662+ `nfse_emissoes`, usuários Railway | OK |
| Histórico JSON | `/app/data/nfse_emitidas.json` | OK |
| HTTP local | `:8501/_stcore/health` → 200 | OK |
| HTTPS produção | `https://vps12436.panel.icontainer.site/` → 200 | OK |
| Docker no boot | `systemctl is-enabled docker` | OK |
| Backup automático | cron 03:15 | OK |
| Restore dry-run | backup `20261105_203203` | OK |
| Root/admin rotacionados | `/root/rosafiscal_rotated_credentials.txt` | OK (ops: cofre) |
| Branch API nacional no Git | `cursor/api-nacional-multiusuario-ddd1` / PR #3 | OK |
| Deploy branch na VPS | tip com Sefin multiusuário | **OK** |
| Seed `nathalia` + `guilherme` | senha login `admin` | **OK** |
| Cert A1 nathalia | `/app/data/certs/nathalia/` CNPJ `56169351000185` | **OK** |
| Cert A1 guilherme | reenviar PFX na UI (CNPJ auto do subject) | PENDENTE usuário |
| Endereço/CNPJ nathalia | IBGE `4317202` Santa Rosa | **OK** |
| **Emissão Sefin validada** | chave `43172022256169351000185000000000000126114512958866` | **OK** |
| Desligar Railway | pause manual (sem `RAILWAY_TOKEN` neste agent) | **PENDENTE ops** |

## Smoke Sefin (2026-11-10, America/Sao_Paulo)

- Usuário: `nathalia`
- CNPJ: `56169351000185`
- Regime: `opSimpNac=3` (ME/EPP) + `regApTribSN=1`
- Município IBGE: `4317202`
- Hash: `SMOKE-VPS-8d3ca228331f4bc1`
- Chave NFS-e: `43172022256169351000185000000000000126114512958866`
- Status: **sucesso**

## Desligar Railway (manual)

1. Confirmar URL oficial só na VPS: https://vps12436.panel.icontainer.site/
2. No painel Railway: **pause/stop** do serviço Streamlit antigo (não apague volume/DB até backup extra).
3. Remova DNS/custom domain apontando ao Railway, se houver.
4. Backup extra: `/opt/rosafiscal/deploy/scripts/backup_nfse.sh`
5. Gate: `bash /opt/rosafiscal/deploy/scripts/railway_shutdown_gate.sh` (`emission_ready=true`)

## Logins

| Usuário | Senha | CNPJ |
|---------|-------|------|
| `nathalia` | `admin` | `56169351000185` |
| `guilherme` | `admin` | (enviar PFX em Configurações) |

## Notas técnicas

- Santa Rosa usa **Emissor Nacional** (IPM erro 00378) — não emitir via IPM.
- Enum oficial `opSimpNac`: `1` não optante, `2` MEI, `3` ME/EPP (inverter gera **E0160**).
- IBGE Santa Rosa-RS = **4317202** (não `4318002`).
