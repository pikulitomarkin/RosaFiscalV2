# Checklist cutover Railway → VPS

Atualizado com evidência na VPS `184.107.179.79`.

| Requisito | Evidência | Status |
|-----------|-----------|--------|
| App Docker no ar | `docker compose ps` app Up, restart `unless-stopped` | OK |
| Postgres com dados | 3662 `nfse_emissoes`, 3 `usuarios` | OK |
| Histórico JSON | `/app/data/nfse_emitidas.json` no volume | OK |
| HTTP local | `:8501/_stcore/health` → 200 | OK |
| HTTPS produção | `https://vps12436.panel.icontainer.site/` → 200 | OK |
| Docker no boot | `systemctl is-enabled docker` → enabled | OK |
| Backup automático | cron 03:15 + backup manual `20261105_203203` OK | OK |
| Watcher senha IPM | cron `* * * * * watch_ipm_senha.sh` | OK |
| Rede Atende.Net | `ws-santarosa...` HTTP 401 com auth inválida | OK |
| Prestador Nathalia | UI Configurações (sem Gabriel Saleh) | OK |
| Campo senha IPM no dashboard | Configurações + runtime_config volume | OK |
| **IPM_SENHA configurada** | `.env` len=0, runtime sem senha | **FAIL** |
| Emissão / test_ipm_auth | bloqueado sem senha | **PENDENTE** |
| Cert A1 | opcional no fluxo IPM | WARN |
| Trocar senha root | exposta no screenshot do painel | PENDENTE (ops) |
| Desligar Railway | só após emissão validada | PENDENTE |

## Bloqueio atual
Salvar a **senha do portal** https://nfse-santarosa.atende.net/ (login CNPJ) em Configurações → Senha IPM.

Validar depois:
```bash
/opt/rosafiscal/deploy/scripts/post_cutover_check.sh
```
