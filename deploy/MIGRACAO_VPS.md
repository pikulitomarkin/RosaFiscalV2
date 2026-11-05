# Migração Railway → VPS

## Status atual (VPS `184.107.179.79`)
- App em `/opt/rosafiscal` via Docker Compose (`app` + Postgres)
- **HTTPS (produção):** https://vps12436.panel.icontainer.site/
- Alternativas: `http://184.107.179.79:8501` e proxy `http://184.107.179.79:8088`
- Banco restaurado do Railway: **3662** emissões + **3** usuários
- Histórico JSON em volume Docker `appdata` → `/app/data/nfse_emitidas.json`
- Prestador oficial: **Nathalia Gabriela** (CNPJ `56169351000185`) — identidade Gabriel Saleh removida da UI
- Certificado A1 opcional no fluxo IPM (PEM de terceiro quarentenado em `certificados/backup_gabriel`)
- **Pendente (bloqueia emissão):** `IPM_SENHA` — salve no dashboard (**Configurações → Senha IPM**) ou via script abaixo
- Docker habilitado no boot (`systemctl enable docker`)
- Scripts: `set_ipm_senha.sh`, `validate_migracao.sh`, `test_ipm_auth.py`

Login admin (pós-restauração): `admin` / `Nathalia@2026` (troque após o cutover).

### Definir IPM_SENHA
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
1. Dashboard Atende.Net / prefeitura (webservice NFS-e)
2. Variáveis do projeto **Railway** (se ainda existir): `IPM_SENHA`
3. Contabilidade / Domínio Contábil (e-mail do prestador)
Não cole a senha neste chat.


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
Só após validação em produção na VPS.
