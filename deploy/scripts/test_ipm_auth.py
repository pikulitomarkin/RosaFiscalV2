#!/usr/bin/env python3
"""
Testa autenticação IPM em modo teste (nfse_teste=1) — não emite nota real.
Uso na VPS:
  docker compose exec -T app python deploy/scripts/test_ipm_auth.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Garante imports quando rodado como `python deploy/scripts/test_ipm_auth.py`
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


async def main() -> int:
    from src.utils.runtime_config import get_ipm_senha, get_ipm_usuario, ipm_senha_configurada
    from src.api.ipm_soap_client import IPMSoapClient
    from src.utils.rps_xml_generator import RPSXMLGenerator
    from src.api.nfse_service import NFSeService

    if not ipm_senha_configurada():
        print("FAIL: IPM_SENHA não configurada (dashboard → Configurações)")
        return 1

    prestador = NFSeService()._load_default_prestador()
    gen = RPSXMLGenerator(ambiente_teste=True)
    xml = gen.gerar_enviar_lote_rps_sincrono(
        cnpj_prestador=prestador["cnpj"],
        inscricao_municipal=prestador["inscricao_municipal"],
        numero_lote=1,
        numero_rps=1,
        serie_rps="A",
        cpf_tomador="00000000191",
        nome_tomador="TESTE MIGRACAO VPS",
        descricao="TESTE VALIDACAO CREDENCIAIS IPM",
        valor=1.0,
        aliquota_iss=2.01,
        codigo_servico="40303",
        nbs="1.2301.21.00",
        bairro_tomador="CENTRO",
        cep_tomador="98780000",
        logradouro_tomador="RUA TESTE",
    )

    client = IPMSoapClient()
    print(f"Usuario IPM: {get_ipm_usuario()} (senha len={len(get_ipm_senha())})")
    print(f"POST {client.base_url} (modo teste)")
    try:
        result = await client.enviar_lote_rps_sincrono(xml)
    except Exception as e:
        print(f"FAIL: exceção na chamada IPM: {e}")
        return 2

    ok = bool(result.get("sucesso"))
    print("sucesso=", ok)
    print("mensagens=", result.get("mensagens") or result.get("erros"))
    if ok:
        print("OK: credenciais IPM aceitas (modo teste).")
        return 0
    print("FAIL: IPM rejeitou a requisição — verifique usuário/senha.")
    return 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
