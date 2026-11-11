# API Nacional (Sefin) + multiusuário

## O que mudou
- Emissão padrão via **API Nacional NFS-e (Sefin)** com **certificado A1 (mTLS)** por usuário.
- Imposto/serviço padrão é **compartilhado**.
- Por usuário mudam: **CNPJ**, **endereço**, inscrição municipal, razão social e **PFX + senha do certificado**.

## Usuários seed
| Usuário     | Senha login | CNPJ              | Certificado                          |
|-------------|-------------|-------------------|--------------------------------------|
| `nathalia`  | `admin`     | `56169351000185`  | enviar PFX em Configurações          |
| `guilherme` | `admin`     | (preencher na UI) | enviar PFX em Configurações (admin)  |

## Seed na VPS
```bash
cd /opt/rosafiscal
git fetch && git checkout cursor/api-nacional-multiusuario-ddd1 && git pull
docker compose up -d --build
docker compose exec -T app python deploy/scripts/seed_multiusuarios.py
```

Depois, em cada login → **Configurações** → salvar CNPJ → enviar PFX + senha do A1.

CLI (VPS):

```bash
CERT_PASS='...' /opt/rosafiscal/deploy/scripts/install_user_pfx.sh nathalia /caminho/nathalia.pfx
docker compose exec -T app python deploy/scripts/check_sefin_certs.py
```

Santa Rosa-RS já usa **Emissor Nacional**: IPM retorna 00378 e não emite.

## Backend
- Padrão: `sefin` (`runtime_config.json` → `emission_backend`).
- IPM permanece no código só como legado (seletor em Configurações).
