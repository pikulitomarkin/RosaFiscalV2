"""Perfil multiusuário (CNPJ + certificado A1 por usuário)."""

from .profile import (
    DEFAULT_PRESTADOR_ADDRESS,
    SHARED_PRESTADOR_BASE,
    UserProfile,
    cert_arquivos_ok,
    cert_identity_match,
    cert_pronto,
    clear_user_certificate,
    get_nfse_service_for_username,
    get_user_profile,
    list_usernames,
    read_cert_subject,
    save_user_certificate_pfx,
    save_user_profile,
    ensure_user_columns,
)

__all__ = [
    "DEFAULT_PRESTADOR_ADDRESS",
    "SHARED_PRESTADOR_BASE",
    "UserProfile",
    "cert_arquivos_ok",
    "cert_identity_match",
    "cert_pronto",
    "clear_user_certificate",
    "get_nfse_service_for_username",
    "get_user_profile",
    "list_usernames",
    "read_cert_subject",
    "save_user_certificate_pfx",
    "save_user_profile",
    "ensure_user_columns",
]
