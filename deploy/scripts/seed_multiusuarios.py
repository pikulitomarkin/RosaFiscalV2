#!/usr/bin/env python3
"""
Seed de 2 usuários para API nacional (certificado A1 + CNPJ por usuário).

Cidade / endereço / imposto são compartilhados (SHARED_PRESTADOR_BASE).
Só CNPJ, IM, razão social e certificado mudam por usuário.

Uso (VPS / container app):
  docker compose exec -T app python deploy/scripts/seed_multiusuarios.py

Senha de login padrão dos dois: medico
"""
from __future__ import annotations

import os
import sys

import bcrypt
import psycopg2

USERS = [
    {
        "username": "nathalia",
        "password": "medico",
        "nome_completo": "Nathalia Gabriela",
        "email": "nathalia@localhost",
        "cnpj": "56169351000185",
        "inscricao_municipal": "56937",
        "razao_social": "NATHALIA GABRIELA SERVICOS DE SAUDE LTDA",
        "nome_fantasia": "NATHALIA GABRIELA",
        "is_admin": True,
    },
    {
        "username": "empresa2",
        "password": "medico",
        "nome_completo": "Empresa 2 (configurar CNPJ e certificado)",
        "email": "empresa2@localhost",
        "cnpj": "",  # preencher em Configurações
        "inscricao_municipal": "",
        "razao_social": "",
        "nome_fantasia": "",
        "is_admin": False,
    },
]


def dsn() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://nfse:nfse@db:5432/nfse")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def main() -> int:
    conn = psycopg2.connect(dsn())
    conn.autocommit = True
    cur = conn.cursor()

    for stmt in (
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cnpj VARCHAR(14)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS inscricao_municipal VARCHAR(30)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS razao_social VARCHAR(200)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_fantasia VARCHAR(150)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cert_password VARCHAR(255)",
    ):
        try:
            cur.execute(stmt)
        except Exception as e:
            print(f"skip alter: {e}", file=sys.stderr)

    for u in USERS:
        pw_hash = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
        cur.execute(
            """
            INSERT INTO usuarios (
                username, password_hash, nome_completo, email,
                cnpj, inscricao_municipal, razao_social, nome_fantasia,
                is_active, is_admin
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,true,%s)
            ON CONFLICT (username) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                nome_completo = EXCLUDED.nome_completo,
                email = EXCLUDED.email,
                cnpj = COALESCE(NULLIF(EXCLUDED.cnpj, ''), usuarios.cnpj),
                inscricao_municipal = COALESCE(NULLIF(EXCLUDED.inscricao_municipal, ''), usuarios.inscricao_municipal),
                razao_social = COALESCE(NULLIF(EXCLUDED.razao_social, ''), usuarios.razao_social),
                nome_fantasia = COALESCE(NULLIF(EXCLUDED.nome_fantasia, ''), usuarios.nome_fantasia),
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
                u["is_admin"],
            ),
        )
        print(f"OK usuário={u['username']} cnpj={u['cnpj'] or '(vazio — configurar)'} senha=medico")

    # Mantém admin legado alinhado à senha medico (opcional, se existir)
    pw_admin = bcrypt.hashpw(b"medico", bcrypt.gensalt()).decode()
    cur.execute(
        """
        UPDATE usuarios SET password_hash = %s, is_active = true
        WHERE username = 'admin'
        """,
        (pw_admin,),
    )
    if cur.rowcount:
        print("OK admin senha=medico (legado)")

    cur.close()
    conn.close()
    print("Seed multiusuário concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
