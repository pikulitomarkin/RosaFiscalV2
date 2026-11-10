"""Smoke: conversão PFX → PEM por usuário (sem Postgres)."""
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID
import datetime


def _make_pfx(password: bytes) -> bytes:
    key = rsa.generate_private_key(65537, 2048, default_backend())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "TESTE NFSE")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256(), default_backend())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"teste",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=BestAvailableEncryption(password),
    )


def test_pfx_roundtrip_pem(tmp_path, monkeypatch):
    from src.users import profile as profile_mod

    monkeypatch.setattr(profile_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(profile_mod, "ensure_user_columns", lambda: None)

    saved = {}

    def fake_get(username):
        return profile_mod.UserProfile(username=username, cnpj="56169351000185")

    def fake_save(p, update_password=None):
        saved["profile"] = p

    monkeypatch.setattr(profile_mod, "get_user_profile", fake_get)
    monkeypatch.setattr(profile_mod, "save_user_profile", fake_save)

    pfx = _make_pfx(b"senha123")
    out = profile_mod.save_user_certificate_pfx("nathalia", pfx, "senha123")
    assert out.cert_pem.exists()
    assert out.key_pem.exists()
    assert out.cert_pem.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
    assert b"PRIVATE KEY" in out.key_pem.read_bytes()
    assert saved["profile"].cert_password == "senha123"
    assert profile_mod.cert_pronto(out)


def test_prestador_dict_address_per_user():
    from src.users.profile import DEFAULT_PRESTADOR_ADDRESS, UserProfile

    p = UserProfile(
        username="empresa2",
        cnpj="12.345.678/0001-99",
        inscricao_municipal="111",
        razao_social="EMPRESA DOIS LTDA",
        nome_fantasia="EMPRESA 2",
        logradouro="AV OUTRA",
        numero="10",
        bairro="CENTRO",
        municipio="PORTO ALEGRE",
        uf="RS",
        cep="90010-000",
        codigo_municipio="4314902",
    )
    d = p.prestador_dict()
    assert d["cnpj"] == "12345678000199"
    assert d["municipio"] == "PORTO ALEGRE"
    assert d["logradouro"] == "AV OUTRA"
    assert d["cep"] == "90010000"
    assert d["codigo_municipio"] == "4314902"
    assert d["razao_social"] == "EMPRESA DOIS LTDA"

    # sem endereço preenchido → fallback default
    p2 = UserProfile(username="x", cnpj="56169351000185")
    d2 = p2.prestador_dict()
    assert d2["municipio"] == DEFAULT_PRESTADOR_ADDRESS["municipio"]
