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
| **IPM_SENHA configurada** | `validate_migracao` 7 OK / 1 FAIL | **FAIL** (único) |
| Emissão / test_ipm_auth | bloqueado sem senha | **PENDENTE** |
| Gate desligar Railway | `railway_shutdown_gate.sh` exit 2 enquanto blocker | OK (proteção) |
| Cert A1 | opcional no fluxo IPM | WARN |
| Trocar senha root | rotacionada; ver `/root/rosafiscal_rotated_credentials.txt` | **OK** (ops: copiar p/ cofre) |
| Trocar senha admin dashboard | rotacionada no Postgres + `.env` | **OK** (ops: copiar p/ cofre) |
| Código VPS = tip da branch | sync `cursor/migracao-vps-ddd1` | OK |
| Restore dry-run do backup | `20261105_203203` → 3662/3 = prod | **OK** |
| Desligar Railway | só após emissão validada | PENDENTE |

## Bloqueio atual
Salvar a **senha do portal** https://nfse-santarosa.atende.net/ (login CNPJ `56169351000185`) em:
1. Secrets Cursor `IPM_SENHA`, e/ou
2. Dashboard VPS → Configurações → Senha IPM, e/ou
3. Arquivo `/opt/rosafiscal/secrets/ipm_senha` (watcher cron aplica)

Credenciais root/admin rotacionadas (não versionadas):
```bash
ssh -i KEY root@184.107.179.79 'cat /root/rosafiscal_rotated_credentials.txt'
```

Modelo e-mail contabilidade: `deploy/SOLICITAR_SENHA_IPM.md`

Validar depois:
```bash
/opt/rosafiscal/deploy/scripts/post_cutover_check.sh
```
