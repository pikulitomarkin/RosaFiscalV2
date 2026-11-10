"""
Perfil por usuário: CNPJ + certificado A1 + endereço + senha do certificado.
Imposto/serviço padrão permanece compartilhado via runtime_config.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import bcrypt
import psycopg2
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from config.settings import settings
from src.utils.logger import app_logger
from src.utils.runtime_config import DATA_DIR, PRESTADOR_OFICIAL

# Defaults só para seed / fallback (Nathalia). Cada usuário pode sobrescrever na UI.
DEFAULT_PRESTADOR_ADDRESS: Dict[str, str] = {
    "logradouro": "RUA TARQUINIO DE OLIVEIRA",
    "numero": "249",
    "complemento": "",
    "bairro": "CRUZEIRO",
    "municipio": "SANTA ROSA",
    "uf": "RS",
    "cep": "98789104",
    "email_contato": "cadastro@dominiocontabil.com.br",
    "telefone": "4836327480",
    "codigo_municipio": "4317202",
}

# Alias legado (imports antigos)
SHARED_PRESTADOR_BASE = DEFAULT_PRESTADOR_ADDRESS


@dataclass
class UserProfile:
    username: str
    nome_completo: str = ""
    email: str = ""
    cnpj: str = ""
    inscricao_municipal: str = ""
    razao_social: str = ""
    nome_fantasia: str = ""
    cert_password: str = ""
    logradouro: str = ""
    numero: str = ""
    complemento: str = ""
    bairro: str = ""
    municipio: str = ""
    uf: str = ""
    cep: str = ""
    email_contato: str = ""
    telefone: str = ""
    codigo_municipio: str = ""
    is_admin: bool = False
    is_active: bool = True

    @property
    def cert_dir(self) -> Path:
        return DATA_DIR / "certs" / self.username

    @property
    def cert_pem(self) -> Path:
        return self.cert_dir / "cert.pem"

    @property
    def key_pem(self) -> Path:
        return self.cert_dir / "key.pem"

    def prestador_dict(self) -> Dict[str, Any]:
        def _or(val: str, key: str) -> str:
            v = (val or "").strip()
            return v if v else DEFAULT_PRESTADOR_ADDRESS.get(key, "")

        return {
            "cnpj": re.sub(r"\D", "", self.cnpj) or PRESTADOR_OFICIAL["cnpj"],
            "inscricao_municipal": (self.inscricao_municipal or PRESTADOR_OFICIAL["inscricao_municipal"]).strip(),
            "razao_social": (self.razao_social or PRESTADOR_OFICIAL["razao_social"]).strip(),
            "nome_fantasia": (self.nome_fantasia or PRESTADOR_OFICIAL["nome_fantasia"]).strip(),
            "logradouro": _or(self.logradouro, "logradouro"),
            "numero": _or(self.numero, "numero"),
            "complemento": (self.complemento or "").strip(),
            "bairro": _or(self.bairro, "bairro"),
            "municipio": _or(self.municipio, "municipio"),
            "uf": _or(self.uf, "uf"),
            "cep": re.sub(r"\D", "", self.cep) or DEFAULT_PRESTADOR_ADDRESS["cep"],
            "email": _or(self.email_contato, "email_contato"),
            "telefone": re.sub(r"\D", "", self.telefone) or DEFAULT_PRESTADOR_ADDRESS["telefone"],
            "codigo_municipio": _or(self.codigo_municipio, "codigo_municipio"),
        }


ADDRESS_COLUMNS = [
    ("logradouro", "VARCHAR(125)"),
    ("numero", "VARCHAR(20)"),
    ("complemento", "VARCHAR(60)"),
    ("bairro", "VARCHAR(60)"),
    ("municipio", "VARCHAR(60)"),
    ("uf", "VARCHAR(2)"),
    ("cep", "VARCHAR(8)"),
    ("email_contato", "VARCHAR(100)"),
    ("telefone", "VARCHAR(20)"),
    ("codigo_municipio", "VARCHAR(7)"),
]


def _sync_dsn() -> str:
    raw = os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", "")
    return str(raw).replace("postgresql+asyncpg://", "postgresql://", 1)


def ensure_user_columns() -> None:
    """Adiciona colunas de perfil nacional + endereço se ainda não existirem."""
    dsn = _sync_dsn()
    if not dsn.startswith("postgresql://"):
        return
    alters = [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cnpj VARCHAR(14)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS inscricao_municipal VARCHAR(30)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS razao_social VARCHAR(200)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_fantasia VARCHAR(150)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cert_password VARCHAR(255)",
    ]
    for col, typ in ADDRESS_COLUMNS:
        alters.append(f"ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS {col} {typ}")
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        for stmt in alters:
            try:
                cur.execute(stmt)
            except Exception as e:
                app_logger.debug(f"ensure_user_columns skip: {e}")
        cur.close()
        conn.close()
    except Exception as e:
        app_logger.warning(f"ensure_user_columns falhou: {e}")


def get_user_profile(username: str) -> Optional[UserProfile]:
    ensure_user_columns()
    dsn = _sync_dsn()
    if not dsn.startswith("postgresql://"):
        return None
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT username, COALESCE(nome_completo,''), COALESCE(email,''),
                   COALESCE(cnpj,''), COALESCE(inscricao_municipal,''),
                   COALESCE(razao_social,''), COALESCE(nome_fantasia,''),
                   COALESCE(cert_password,''),
                   COALESCE(logradouro,''), COALESCE(numero,''), COALESCE(complemento,''),
                   COALESCE(bairro,''), COALESCE(municipio,''), COALESCE(uf,''),
                   COALESCE(cep,''), COALESCE(email_contato,''), COALESCE(telefone,''),
                   COALESCE(codigo_municipio,''),
                   COALESCE(is_admin,false), COALESCE(is_active,true)
            FROM usuarios WHERE username = %s
            """,
            (username,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        return UserProfile(
            username=row[0],
            nome_completo=row[1] or "",
            email=row[2] or "",
            cnpj=row[3] or "",
            inscricao_municipal=row[4] or "",
            razao_social=row[5] or "",
            nome_fantasia=row[6] or "",
            cert_password=row[7] or "",
            logradouro=row[8] or "",
            numero=row[9] or "",
            complemento=row[10] or "",
            bairro=row[11] or "",
            municipio=row[12] or "",
            uf=row[13] or "",
            cep=row[14] or "",
            email_contato=row[15] or "",
            telefone=row[16] or "",
            codigo_municipio=row[17] or "",
            is_admin=bool(row[18]),
            is_active=bool(row[19]),
        )
    except Exception as e:
        app_logger.error(f"get_user_profile: {e}")
        return None


def list_usernames() -> List[str]:
    ensure_user_columns()
    dsn = _sync_dsn()
    if not dsn.startswith("postgresql://"):
        return []
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT username FROM usuarios WHERE is_active = true ORDER BY username")
        rows = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


def save_user_profile(profile: UserProfile, *, update_password: Optional[str] = None) -> None:
    ensure_user_columns()
    dsn = _sync_dsn()
    if not dsn.startswith("postgresql://"):
        raise RuntimeError("Perfil nacional requer PostgreSQL")
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE usuarios SET
            nome_completo = %s,
            email = %s,
            cnpj = %s,
            inscricao_municipal = %s,
            razao_social = %s,
            nome_fantasia = %s,
            cert_password = COALESCE(NULLIF(%s, ''), cert_password),
            logradouro = %s,
            numero = %s,
            complemento = %s,
            bairro = %s,
            municipio = %s,
            uf = %s,
            cep = %s,
            email_contato = %s,
            telefone = %s,
            codigo_municipio = %s
        WHERE username = %s
        """,
        (
            profile.nome_completo,
            profile.email,
            re.sub(r"\D", "", profile.cnpj),
            profile.inscricao_municipal,
            profile.razao_social,
            profile.nome_fantasia,
            profile.cert_password,
            profile.logradouro,
            profile.numero,
            profile.complemento,
            profile.bairro,
            profile.municipio,
            (profile.uf or "").upper()[:2],
            re.sub(r"\D", "", profile.cep),
            profile.email_contato,
            re.sub(r"\D", "", profile.telefone),
            re.sub(r"\D", "", profile.codigo_municipio),
            profile.username,
        ),
    )
    if update_password:
        pw_hash = bcrypt.hashpw(update_password.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "UPDATE usuarios SET password_hash = %s WHERE username = %s",
            (pw_hash, profile.username),
        )
    conn.commit()
    cur.close()
    conn.close()


def cert_pronto(profile: UserProfile) -> bool:
    return bool(
        profile.cnpj
        and profile.cert_pem.exists()
        and profile.key_pem.exists()
        and profile.cert_pem.stat().st_size > 0
        and profile.key_pem.stat().st_size > 0
    )


def save_user_certificate_pfx(username: str, pfx_bytes: bytes, password: str) -> UserProfile:
    """Converte PFX/P12 em PEM por usuário e persiste senha do certificado."""
    profile = get_user_profile(username)
    if not profile:
        raise RuntimeError(f"Usuário {username} não encontrado")

    password_bytes = password.encode() if password else None
    private_key, certificate, _additional = pkcs12.load_key_and_certificates(
        pfx_bytes, password_bytes, default_backend()
    )
    if private_key is None or certificate is None:
        raise RuntimeError("PFX inválido: certificado ou chave ausente")

    profile.cert_dir.mkdir(parents=True, exist_ok=True)
    profile.cert_pem.write_bytes(
        certificate.public_bytes(serialization.Encoding.PEM)
    )
    profile.key_pem.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        profile.cert_pem.chmod(0o600)
        profile.key_pem.chmod(0o600)
    except Exception:
        pass

    profile.cert_password = password or ""
    save_user_profile(profile)
    app_logger.info(f"Certificado A1 salvo para usuário={username}")
    return profile


def get_nfse_service_for_username(username: str):
    """Instancia NFSeService com certificado, CNPJ e endereço do usuário logado."""
    from src.api.nfse_service import NFSeService

    profile = get_user_profile(username)
    if not profile:
        raise RuntimeError("Usuário sem perfil — faça login novamente.")
    if not cert_pronto(profile):
        raise RuntimeError(
            "Certificado A1 ou CNPJ não configurados. Vá em Configurações e envie o PFX."
        )
    return NFSeService(
        prestador_config=profile.prestador_dict(),
        cert_path=str(profile.cert_pem),
        key_path=str(profile.key_pem),
    )
