"""Perfil multiusuário (CNPJ + certificado A1 por usuário)."""

from .profile import (
    SHARED_PRESTADOR_BASE,
    UserProfile,
    cert_pronto,
    get_nfse_service_for_username,
    get_user_profile,
    list_usernames,
    save_user_certificate_pfx,
    save_user_profile,
    ensure_user_columns,
)

__all__ = [
    "SHARED_PRESTADOR_BASE",
    "UserProfile",
    "cert_pronto",
    "get_nfse_service_for_username",
    "get_user_profile",
    "list_usernames",
    "save_user_certificate_pfx",
    "save_user_profile",
    "ensure_user_columns",
]
