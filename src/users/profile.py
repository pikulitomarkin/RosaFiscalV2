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
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

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
    valor_padrao_lote: float = 0.0
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
        """Monta dict do prestador deste usuário.

        Identidade fiscal (CNPJ / razão / fantasia / IM) NÃO herda PRESTADOR_OFICIAL
        (Nathalia): usuário sem cadastro próprio fica com campos vazios — evita emitir
        ou exibir a empresa de outro login.
        Endereço ainda pode usar DEFAULT_PRESTADOR_ADDRESS só como fallback de local.
        """
        def _or(val: str, key: str) -> str:
            v = (val or "").strip()
            return v if v else DEFAULT_PRESTADOR_ADDRESS.get(key, "")

        return {
            "cnpj": re.sub(r"\D", "", self.cnpj or ""),
            "inscricao_municipal": (self.inscricao_municipal or "").strip(),
            "razao_social": (self.razao_social or "").strip(),
            "nome_fantasia": (self.nome_fantasia or "").strip(),
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
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS valor_padrao_lote NUMERIC(10, 2) DEFAULT 0",
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


# Dono canônico do PRESTADOR_OFICIAL no seed multiusuário.
OFICIAL_OWNER_USERNAME = "nathalia"


def _oficial_cnpj_digits() -> str:
    return re.sub(r"\D", "", PRESTADOR_OFICIAL.get("cnpj") or "")


def identity_is_borrowed_oficial(profile: UserProfile) -> bool:
    """True se o perfil carrega CNPJ/razão da Nathalia sem ser o dono e sem A1 próprio.

    Sintoma clássico no sidebar: login guilherme ainda mostra
    CNPJ 56169351000185 / NATHALIA… com certificado pendente e pasta de cert vazia
    (identidade órfã após upload compartilhado ou seed antigo).
    """
    if not profile or not (profile.username or "").strip():
        return False
    if (profile.username or "").strip().lower() == OFICIAL_OWNER_USERNAME:
        return False
    perfil_cnpj = re.sub(r"\D", "", profile.cnpj or "")
    oficial = _oficial_cnpj_digits()
    if not oficial or perfil_cnpj != oficial:
        return False
    # Sem PEM próprio → identidade oficial é emprestada/órfã.
    if not cert_arquivos_ok(profile):
        return True
    # PEM existe mas subject não é o CNPJ oficial → também não exibir como se fosse dele.
    subj = read_cert_subject(profile)
    subj_cnpj = re.sub(r"\D", "", subj.get("cnpj") or "")
    return bool(subj_cnpj) and subj_cnpj != oficial


def display_cnpj_razao(profile: Optional[UserProfile]) -> Dict[str, str]:
    """CNPJ/razão seguros para UI (sidebar/settings/overview).

    Se a identidade for a oficial emprestada, devolve vazio para a UI mostrar
    'CNPJ não configurado' em vez de Nathalia.
    """
    if not profile:
        return {"cnpj": "", "razao_social": "", "nome_fantasia": ""}
    if identity_is_borrowed_oficial(profile):
        return {"cnpj": "", "razao_social": "", "nome_fantasia": ""}
    return {
        "cnpj": (profile.cnpj or "").strip(),
        "razao_social": (profile.razao_social or "").strip(),
        "nome_fantasia": (profile.nome_fantasia or "").strip(),
    }


def clear_borrowed_oficial_identity() -> int:
    """Zera CNPJ/razão/fantasia oficiais em usuários ≠ nathalia sem A1 próprio.

    Idempotente; chamado no boot (ensure_login_users) para limpar poluição
    que o COALESCE do seed preservava.
    """
    ensure_user_columns()
    dsn = _sync_dsn()
    if not dsn.startswith("postgresql://"):
        return 0
    oficial = _oficial_cnpj_digits()
    if not oficial:
        return 0
    cleared = 0
    try:
        usernames = [
            u
            for u in list_usernames()
            if (u or "").strip().lower() != OFICIAL_OWNER_USERNAME
        ]
        for username in usernames:
            profile = get_user_profile(username)
            if not profile or not identity_is_borrowed_oficial(profile):
                continue
            conn = psycopg2.connect(dsn)
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE usuarios
                   SET cnpj = '',
                       razao_social = '',
                       nome_fantasia = '',
                       inscricao_municipal = CASE
                           WHEN COALESCE(inscricao_municipal,'') = %s THEN ''
                           ELSE inscricao_municipal
                       END
                 WHERE username = %s
                   AND regexp_replace(COALESCE(cnpj,''), '[^0-9]', '', 'g') = %s
                """,
                (
                    PRESTADOR_OFICIAL.get("inscricao_municipal") or "",
                    username,
                    oficial,
                ),
            )
            conn.commit()
            cleared += cur.rowcount or 0
            cur.close()
            conn.close()
            app_logger.warning(
                f"clear_borrowed_oficial_identity: limpou CNPJ/razão oficiais "
                f"de usuário={username} (sem A1 próprio)"
            )
        return cleared
    except Exception as e:
        app_logger.warning(f"clear_borrowed_oficial_identity: {e}")
        return cleared


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
                   COALESCE(valor_padrao_lote, 0),
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
        try:
            valor_padrao = float(row[18] or 0)
        except (TypeError, ValueError):
            valor_padrao = 0.0
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
            valor_padrao_lote=valor_padrao,
            is_admin=bool(row[19]),
            is_active=bool(row[20]),
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
            codigo_municipio = %s,
            valor_padrao_lote = %s
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
            max(0.0, float(profile.valor_padrao_lote or 0)),
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


def cert_arquivos_ok(profile: UserProfile) -> bool:
    """True se PEM/key existem no volume (independente de CNPJ)."""
    try:
        return bool(
            profile.cert_pem.exists()
            and profile.key_pem.exists()
            and profile.cert_pem.stat().st_size > 0
            and profile.key_pem.stat().st_size > 0
        )
    except Exception:
        return False


def _cnpj_e_nome_do_certificado(certificate: x509.Certificate) -> tuple[str, str]:
    """Extrai CNPJ (14 dígitos) e razão social do CN do A1 ICP-Brasil."""
    try:
        cn = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    except Exception:
        return "", ""
    cn = str(cn or "").strip()
    m = re.search(r":(\d{14})\s*$", cn)
    cnpj = m.group(1) if m else ""
    razao = cn.rsplit(":", 1)[0].strip() if m else cn
    return cnpj, razao


def read_cert_subject(profile: UserProfile) -> Dict[str, str]:
    """Lê CN/CNPJ do PEM em disco deste usuário (sem alterar o perfil)."""
    empty = {"cn": "", "cnpj": "", "razao_social": ""}
    if not cert_arquivos_ok(profile):
        return empty
    try:
        certificate = x509.load_pem_x509_certificate(
            profile.cert_pem.read_bytes(), default_backend()
        )
        try:
            cn = str(
                certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
                or ""
            ).strip()
        except Exception:
            cn = ""
        cnpj, razao = _cnpj_e_nome_do_certificado(certificate)
        return {"cn": cn, "cnpj": cnpj, "razao_social": razao}
    except Exception as e:
        app_logger.warning(f"read_cert_subject {profile.username}: {e}")
        return empty


def cert_identity_match(profile: UserProfile) -> bool:
    """True se o PEM existe e o CNPJ do subject bate com o CNPJ do perfil."""
    cnpj_perfil = re.sub(r"\D", "", profile.cnpj or "")
    if not cnpj_perfil or not cert_arquivos_ok(profile):
        return False
    subj = read_cert_subject(profile)
    cnpj_cert = re.sub(r"\D", "", subj.get("cnpj") or "")
    # Cert sem CNPJ no CN: não bloqueia só por formato; exige arquivos + CNPJ perfil.
    if not cnpj_cert:
        return True
    return cnpj_cert == cnpj_perfil


def cert_pronto(profile: UserProfile) -> bool:
    """Pronto para emitir: CNPJ no perfil + PEM/key + subject alinhado ao CNPJ."""
    return (
        bool(re.sub(r"\D", "", profile.cnpj or ""))
        and cert_arquivos_ok(profile)
        and cert_identity_match(profile)
    )


def clear_user_certificate(
    username: str, *, clear_identity: bool = False
) -> Optional[UserProfile]:
    """Remove PEM/key do usuário. Opcionalmente zera CNPJ/razão (cert errado)."""
    profile = get_user_profile(username)
    if not profile:
        return None
    for path in (profile.cert_pem, profile.key_pem):
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            app_logger.warning(f"clear_user_certificate unlink {path}: {e}")
    profile.cert_password = ""
    if clear_identity:
        profile.cnpj = ""
        profile.razao_social = ""
        profile.nome_fantasia = ""
    save_user_profile(profile)
    # Força limpar senha mesmo com COALESCE(NULLIF) no UPDATE
    dsn = _sync_dsn()
    if dsn.startswith("postgresql://"):
        try:
            conn = psycopg2.connect(dsn)
            cur = conn.cursor()
            if clear_identity:
                cur.execute(
                    """
                    UPDATE usuarios SET cert_password = '', cnpj = '',
                           razao_social = '', nome_fantasia = ''
                    WHERE username = %s
                    """,
                    (username,),
                )
            else:
                cur.execute(
                    "UPDATE usuarios SET cert_password = '' WHERE username = %s",
                    (username,),
                )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            app_logger.warning(f"clear_user_certificate db: {e}")
    return get_user_profile(username)


def save_user_certificate_pfx(username: str, pfx_bytes: bytes, password: str) -> UserProfile:
    """Converte PFX/P12 em PEM por usuário e persiste senha do certificado.

    Sempre sincroniza CNPJ/razão social a partir do subject do A1
    (padrão ICP-Brasil `RAZAO:CNPJ`) para este username — sobrescreve valores
    anteriores para não manter identidade de outro prestador após reenvio.
    """
    profile = get_user_profile(username)
    if not profile:
        raise RuntimeError(f"Usuário {username} não encontrado")

    password_bytes = password.encode() if password else None
    try:
        private_key, certificate, _additional = pkcs12.load_key_and_certificates(
            pfx_bytes, password_bytes, default_backend()
        )
    except ValueError as e:
        raise RuntimeError(
            "Não foi possível abrir o PFX — confira a senha do certificado A1."
        ) from e
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

    cnpj_cert, razao_cert = _cnpj_e_nome_do_certificado(certificate)
    if cnpj_cert:
        profile.cnpj = cnpj_cert
    if razao_cert:
        profile.razao_social = razao_cert
        if not (profile.nome_fantasia or "").strip():
            profile.nome_fantasia = razao_cert.split()[0] if razao_cert else ""

    profile.cert_password = password or ""
    save_user_profile(profile)
    app_logger.info(
        f"Certificado A1 salvo para usuário={username} cnpj={profile.cnpj or '(vazio)'} "
        f"subject_cnpj={cnpj_cert or '(vazio)'} "
        f"arquivos_ok={cert_arquivos_ok(profile)} pronto={cert_pronto(profile)}"
    )
    return profile


def get_nfse_service_for_username(username: str):
    """Instancia NFSeService com certificado, CNPJ e endereço do usuário logado."""
    from src.api.nfse_service import NFSeService

    profile = get_user_profile(username)
    if not profile:
        raise RuntimeError("Usuário sem perfil — faça login novamente.")
    if not cert_pronto(profile):
        subj = read_cert_subject(profile) if profile else {}
        if (
            cert_arquivos_ok(profile)
            and subj.get("cnpj")
            and re.sub(r"\D", "", profile.cnpj or "")
            and not cert_identity_match(profile)
        ):
            raise RuntimeError(
                "CNPJ do perfil não confere com o certificado A1 em disco. "
                "Vá em Configurações e reenvie o PFX correto deste prestador."
            )
        raise RuntimeError(
            "Certificado A1 ou CNPJ não configurados. Vá em Configurações e envie o PFX."
        )
    prestador = profile.prestador_dict()
    if not prestador.get("cnpj") or not prestador.get("razao_social"):
        raise RuntimeError(
            "Perfil incompleto (CNPJ/razão). Salve o perfil ou reenvie o certificado A1."
        )
    return NFSeService(
        prestador_config=prestador,
        cert_path=str(profile.cert_pem),
        key_path=str(profile.key_pem),
    )
