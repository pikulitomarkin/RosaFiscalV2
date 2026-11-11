# Migração Railway → VPS

## Status atual (VPS `184.107.179.79`) — probe 2026-11-11
- **URL oficial de produção:** https://vps12436.panel.icontainer.site/
- Gate: `cutover_ready=true`, `emission_ready=true`, backend **sefin**
- Smoke Sefin id **3663** OK · `db_emissoes=3663` · `sefin_cert_users≥1`
- `migration_complete=false` — **Railway ainda vivo** em https://rosafiscalv2.up.railway.app/ (health 200)
- **Bloqueio residual único:** pausar Railway no painel (`RAILWAY_TOKEN` foi **skipped** pelo usuário)
- App em `/opt/rosafiscal` via Docker Compose (`app` + Postgres)
- Alternativas locais: `http://184.107.179.79:8501` e proxy `http://184.107.179.79:8088`
- Histórico JSON em volume Docker `appdata` → `/app/data/nfse_emitidas.json`
- Prestador oficial: **Nathalia Gabriela** (CNPJ `56169351000185`)
- Docker habilitado no boot (`systemctl enable docker`)
- Scripts cutover: `cutover_status.sh`, `probe_railway_live.sh`, `railway_shutdown_gate.sh`, `agent_pause_railway.sh`

Login admin: usuário `admin`. Senha root/admin rotacionadas na VPS — recuperar com:
`ssh … 'cat /root/rosafiscal_rotated_credentials.txt'` (apagar o arquivo após copiar ao cofre).

### Definir IPM_SENHA (obrigatório para emissão)

Do Cloud Agent (com secret `IPM_SENHA` no ambiente Cursor):
```bash
./deploy/scripts/agent_apply_ipm_senha.sh
```

Na VPS:
**Preferencial — dashboard:** https://vps12436.panel.icontainer.site/ → Configurações → Webservice IPM → salvar → Testar conexão IPM.

**Alternativa — SSH na VPS:**
```bash
/opt/rosafiscal/deploy/scripts/set_ipm_senha.sh
```
O script grava `.env` **e** `runtime_config.json` no volume. Não cole a senha no chat.

**Alternativa — arquivo local (depois é apagado):**
```bash
umask 077
mkdir -p /opt/rosafiscal/secrets
# uma linha com a senha Atende.Net:
nano /opt/rosafiscal/secrets/ipm_senha
chmod 600 /opt/rosafiscal/secrets/ipm_senha
/opt/rosafiscal/deploy/scripts/apply_ipm_senha_from_file.sh
```

Há um watcher (cron) que aplica sozinho se o arquivo aparecer:
```bash
* * * * * /opt/rosafiscal/deploy/scripts/watch_ipm_senha.sh >> /var/log/rosafiscal-ipm-watch.log 2>&1
```

### Onde achar a senha
A senha IPM é a **senha de acesso ao sistema NFS-e** (login do CNPJ), não a senha do dashboard Streamlit.
1. Portal: https://nfse-santarosa.atende.net/ (mesma senha do contribuinte)
2. Variáveis do projeto **Railway** (se ainda existir): `IPM_SENHA`
3. Contabilidade / Domínio Contábil
Não cole a senha neste chat.

Webservice URL (após ago/2025): `https://ws-santarosa.atende.net/?pg=rest&service=WNERestServiceNFSe`

### Puxar do Railway (CLI)
Com `RAILWAY_TOKEN` e projeto linkado na VPS/agent:
```bash
export RAILWAY_TOKEN=...   # não commitar
railway link               # uma vez
/opt/rosafiscal/deploy/scripts/pull_ipm_from_railway.sh
```

### Status rápido
```bash
/opt/rosafiscal/deploy/scripts/cutover_status.sh
```


### Validar cutover
```bash
/opt/rosafiscal/deploy/scripts/validate_migracao.sh
```

### Backup automático
```bash
chmod 700 /opt/rosafiscal/deploy/scripts/backup_nfse.sh
(crontab -l 2>/dev/null; echo "15 3 * * * /opt/rosafiscal/deploy/scripts/backup_nfse.sh >> /var/log/rosafiscal-backup.log 2>&1") | crontab -
```

## Pré-requisitos na VPS
- Ubuntu 22.04/24.04+ (ou similar)
- Docker + Docker Compose plugin
- Portas **8501** (app) e, se usar proxy iContainer, **8088**
- Acesso SSH

### Nota iContainer
Se a VPS já tiver o painel **iContainer** com Nginx em 80/443:
- **não** use o profile `standalone-nginx` do compose
- suba só `app` + `db`
- instale `deploy/icontainer-nfse.conf` em `/etc/icontainer/apps/nginx/nginx/conf/conf.d/nfse.conf`
- acesse `http://IP:8501` (direto) ou `http://IP:8088` (via proxy)

## Secrets (não commitar)
Copie `deploy/env.vps.example` → `.env` na raiz do projeto na VPS e preencha:
- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `IPM_SENHA`
- `ADMIN_PASSWORD_HASH`
- Certificados em `certificados/cert.pem` + `key.pem` **ou** Base64 no `.env`

## Cutover (passo a passo)

### 1. Backup no Railway
```bash
# Postgres
railway connect  # ou pg_dump via DATABASE_URL pública
pg_dump "$RAILWAY_DATABASE_URL" -Fc -f nfse_railway.dump

# Histórico JSON (volume)
# baixe /app/data/nfse_emitidas.json do volume Railway
```

### 2. Subir stack na VPS
```bash
git clone <repo> /opt/rosafiscal
cd /opt/rosafiscal
cp deploy/env.vps.example .env
# edite .env
mkdir -p certificados data logs
# copie cert.pem / key.pem para certificados/
docker compose up -d --build
```

### 3. Restaurar dados
```bash
# Dump Postgres → container db
docker compose exec -T db pg_restore -U nfse -d nfse --clean --if-exists < nfse_railway.dump
# ou:
# docker compose exec -T db psql -U nfse -d nfse < nfse.sql

# JSON histórico
docker compose cp nfse_emitidas.json app:/app/data/nfse_emitidas.json
```

### 4. Validar
- Abrir `http://IP_DA_VPS`
- Login
- Emitir 1 nota de teste (ou lote pequeno)
- Confirmar nota em NFS-e Emitidas após refresh

### 5. DNS / TLS (opcional)
- Aponte o domínio para o IP
- Monte certificados em `deploy/certs/` e habilite o bloco 443 em `deploy/nginx.conf`

### 6. Desligar Railway
Só após validação em produção na VPS (já feita: smoke 3663 + gate aberto).

1. Confirme VPS: `bash /opt/rosafiscal/deploy/scripts/railway_shutdown_gate.sh` → exit 4 = VPS OK, Railway vivo.
2. **Pause no painel** (preferencial; token foi skipped):  
   https://railway.com/project/0dff8bdf-7c3c-4cda-8ca5-34c48a9aa7a6?environmentId=d845247a-c997-4fec-bb0d-b0e1cb1ccd76  
   Não apague DB/volume.
3. Se houver `RAILWAY_TOKEN`: `./deploy/scripts/agent_pause_railway.sh`
4. Confirme offline: `./deploy/scripts/probe_railway_live.sh` → exit 0 (`railway_live=false`)
5. Só então `migration_complete=true`.

**URL oficial:** https://vps12436.panel.icontainer.site/
