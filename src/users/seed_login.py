"""Garante usuários de login nathalia + guilherme (senha admin) no Postgres."""
from __future__ import annotations

import os

import bcrypt
import psycopg2

from config.settings import settings
from src.users.profile import ensure_user_columns
from src.utils.logger import app_logger

LOGIN_USERS = (
    {
        "username": "nathalia",
        "password": "admin",
        "nome_completo": "Nathalia Gabriela",
        "email": "nathalia@localhost",
        "cnpj": "56169351000185",
        "inscricao_municipal": "56937",
        "razao_social": "NATHALIA GABRIELA SERVICOS DE SAUDE LTDA",
        "nome_fantasia": "NATHALIA GABRIELA",
        "logradouro": "RUA TARQUINIO DE OLIVEIRA",
        "numero": "249",
        "bairro": "CRUZEIRO",
        "municipio": "SANTA ROSA",
        "uf": "RS",
        "cep": "98789104",
        "email_contato": "cadastro@dominiocontabil.com.br",
        "telefone": "4836327480",
        "codigo_municipio": "4318002",
        "is_admin": True,
    },
    {
        "username": "guilherme",
        "password": "admin",
        "nome_completo": "Guilherme",
        "email": "guilherme@localhost",
        "cnpj": "",
        "inscricao_municipal": "",
        "razao_social": "",
        "nome_fantasia": "",
        "logradouro": "",
        "numero": "",
        "bairro": "",
        "municipio": "",
        "uf": "",
        "cep": "",
        "email_contato": "",
        "telefone": "",
        "codigo_municipio": "",
        "is_admin": True,
    },
)


def ensure_login_users() -> None:
    """Upsert nathalia/guilherme com senha admin (idempotente)."""
    ensure_user_columns()
    raw = os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", "")
    dsn = str(raw).replace("postgresql+asyncpg://", "postgresql://", 1)
    if not dsn.startswith("postgresql://"):
        return
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        for u in LOGIN_USERS:
            pw_hash = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
            cur.execute(
                """
                INSERT INTO usuarios (
                    username, password_hash, nome_completo, email,
                    cnpj, inscricao_municipal, razao_social, nome_fantasia,
                    logradouro, numero, bairro, municipio, uf, cep,
                    email_contato, telefone, codigo_municipio,
                    is_active, is_admin
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s
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
                    u["logradouro"] or None,
                    u["numero"] or None,
                    u["bairro"] or None,
                    u["municipio"] or None,
                    u["uf"] or None,
                    u["cep"] or None,
                    u["email_contato"] or None,
                    u["telefone"] or None,
                    u["codigo_municipio"] or None,
                    u["is_admin"],
                ),
            )
        cur.close()
        conn.close()
        app_logger.info("Usuários de login garantidos: nathalia, guilherme")
    except Exception as e:
        app_logger.warning(f"ensure_login_users: {e}")
