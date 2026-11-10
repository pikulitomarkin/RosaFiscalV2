#!/usr/bin/env python3
"""
Seed de 2 usuários para API nacional (certificado A1 + CNPJ + endereço por usuário).

Imposto/serviço padrão permanece compartilhado.
CNPJ, endereço e certificado mudam por usuário.

Uso (VPS / container app):
  docker compose exec -T app python deploy/scripts/seed_multiusuarios.py

Senha de login padrão dos dois: admin
"""
from __future__ import annotations

import os
import sys

import bcrypt
import psycopg2

NATHALIA_ADDR = {
    "logradouro": "RUA TARQUINIO DE OLIVEIRA",
    "numero": "249",
    "complemento": "",
    "bairro": "CRUZEIRO",
    "municipio": "SANTA ROSA",
    "uf": "RS",
    "cep": "98789104",
    "email_contato": "cadastro@dominiocontabil.com.br",
    "telefone": "4836327480",
    "codigo_municipio": "4318002",
}

USERS = [
    {
        "username": "nathalia",
        "password": "admin",
        "nome_completo": "Nathalia Gabriela",
        "email": "nathalia@localhost",
        "cnpj": "56169351000185",
        "inscricao_municipal": "56937",
        "razao_social": "NATHALIA GABRIELA SERVICOS DE SAUDE LTDA",
        "nome_fantasia": "NATHALIA GABRIELA",
        "is_admin": True,
        **NATHALIA_ADDR,
    },
    {
        "username": "guilherme",
        "password": "admin",
        "nome_completo": "Guilherme",
        "email": "guilherme@localhost",
        "cnpj": "",  # preencher em Configurações
        "inscricao_municipal": "",
        "razao_social": "",
        "nome_fantasia": "",
        "is_admin": True,
        "logradouro": "",
        "numero": "",
        "complemento": "",
        "bairro": "",
        "municipio": "",
        "uf": "",
        "cep": "",
        "email_contato": "",
        "telefone": "",
        "codigo_municipio": "",
    },
]

ADDR_COLS = [
    "logradouro", "numero", "complemento", "bairro", "municipio",
    "uf", "cep", "email_contato", "telefone", "codigo_municipio",
]


def dsn() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://nfse:nfse@db:5432/nfse")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def main() -> int:
    conn = psycopg2.connect(dsn())
    conn.autocommit = True
    cur = conn.cursor()

    alters = [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cnpj VARCHAR(14)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS inscricao_municipal VARCHAR(30)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS razao_social VARCHAR(200)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_fantasia VARCHAR(150)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cert_password VARCHAR(255)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS logradouro VARCHAR(125)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS numero VARCHAR(20)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS complemento VARCHAR(60)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS bairro VARCHAR(60)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS municipio VARCHAR(60)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS uf VARCHAR(2)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cep VARCHAR(8)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_contato VARCHAR(100)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS telefone VARCHAR(20)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS codigo_municipio VARCHAR(7)",
    ]
    for stmt in alters:
        try:
            cur.execute(stmt)
        except Exception as e:
            print(f"skip alter: {e}", file=sys.stderr)

    for u in USERS:
        pw_hash = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
        cur.execute(
            f"""
            INSERT INTO usuarios (
                username, password_hash, nome_completo, email,
                cnpj, inscricao_municipal, razao_social, nome_fantasia,
                {", ".join(ADDR_COLS)},
                is_active, is_admin
            ) VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,
                {", ".join(["%s"] * len(ADDR_COLS))},
                true,%s
            )
            ON CONFLICT (username) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                nome_completo = EXCLUDED.nome_completo,
                email = EXCLUDED.email,
                cnpj = COALESCE(NULLIF(EXCLUDED.cnpj, ''), usuarios.cnpj),
                inscricao_municipal = COALESCE(NULLIF(EXCLUDED.inscricao_municipal, ''), usuarios.inscricao_municipal),
                razao_social = COALESCE(NULLIF(EXCLUDED.razao_social, ''), usuarios.razao_social),
                nome_fantasia = COALESCE(NULLIF(EXCLUDED.nome_fantasia, ''), usuarios.nome_fantasia),
                logradouro = COALESCE(NULLIF(EXCLUDED.logradouro, ''), usuarios.logradouro),
                numero = COALESCE(NULLIF(EXCLUDED.numero, ''), usuarios.numero),
                complemento = COALESCE(EXCLUDED.complemento, usuarios.complemento),
                bairro = COALESCE(NULLIF(EXCLUDED.bairro, ''), usuarios.bairro),
                municipio = COALESCE(NULLIF(EXCLUDED.municipio, ''), usuarios.municipio),
                uf = COALESCE(NULLIF(EXCLUDED.uf, ''), usuarios.uf),
                cep = COALESCE(NULLIF(EXCLUDED.cep, ''), usuarios.cep),
                email_contato = COALESCE(NULLIF(EXCLUDED.email_contato, ''), usuarios.email_contato),
                telefone = COALESCE(NULLIF(EXCLUDED.telefone, ''), usuarios.telefone),
                codigo_municipio = COALESCE(NULLIF(EXCLUDED.codigo_municipio, ''), usuarios.codigo_municipio),
                is_active = true,
                is_admin = EXCLUDED.is_admin
            """,
            (
                u["username"],
                pw_hash,
                u["nome_completo"],
                u["email"],
                u["cnpj"] or None,
                u["inscricao_municipal"] or None,
                u["razao_social"] or None,
                u["nome_fantasia"] or None,
                *[u.get(c) or None for c in ADDR_COLS],
                u["is_admin"],
            ),
        )
        print(
            f"OK usuário={u['username']} cnpj={u['cnpj'] or '(vazio)'} "
            f"municipio={u.get('municipio') or '(configurar)'} senha=admin"
        )

    # Desativa placeholders antigos do seed, se existirem
    cur.execute(
        "UPDATE usuarios SET is_active = false WHERE username IN ('empresa2') AND username NOT IN ('nathalia','guilherme')"
    )

    cur.close()
    conn.close()
    print("Seed multiusuário concluído (nathalia + guilherme / admin).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
