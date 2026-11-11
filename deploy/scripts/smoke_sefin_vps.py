#!/usr/bin/env python3
"""Smoke de emissão Sefin na VPS (usuário nathalia).

Uso no container:
  SMOKE_CPF=96362790049 SMOKE_NOME='...' python deploy/scripts/smoke_sefin_vps.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

sys.path.insert(0, "/app")

from src.users.profile import get_nfse_service_for_username, get_user_profile
from src.utils.runtime_config import get_shared_tax_config, save_shared_tax_config


def main() -> int:
    tax = get_shared_tax_config()
    # Nathalia = SN ME/EPP → opSimpNac=3 (NÃO 2=MEI). Garante defaults corretos.
    if int(tax.get("op_simp_nac") or 0) not in (2, 3, 4) or bool(tax.get("mei")):
        save_shared_tax_config(
            aliquota_iss=float(tax.get("aliquota_iss", 2.01)),
            item_lista=str(tax.get("item_lista", "40303")),
            descricao=str(tax.get("descricao", "CONSULTA MEDICA")),
            nbs=str(tax.get("nbs", "1.2301.21.00")),
            simples_nacional=True,
            mei=False,
            op_simp_nac=3,
            reg_ap_trib_sn=int(tax.get("reg_ap_trib_sn") or 1),
        )
        tax = get_shared_tax_config()

    profile = get_user_profile("nathalia")
    print(
        "prestador",
        profile.cnpj if profile else None,
        profile.codigo_municipio if profile else None,
        "op_simp_nac=",
        tax.get("op_simp_nac"),
        "mei=",
        tax.get("mei"),
        "reg_ap=",
        tax.get("reg_ap_trib_sn"),
    )

    svc = get_nfse_service_for_username("nathalia")
    h = "SMOKE-VPS-" + uuid.uuid4().hex[:16]
    reg = {
        "cpf": os.environ.get("SMOKE_CPF", "96362790049"),
        "nome": os.environ.get("SMOKE_NOME", "Francieli da costa colla"),
        "hash": h,
        "bairro": "CENTRO",
        "cep": "98780000",
        "logradouro": "RUA TESTE CUTOVER",
    }
    cfg = {
        "valor": 1.00,
        "aliquota_iss": float(tax.get("aliquota_iss", 2.01)),
        "item_lista": str(tax.get("item_lista", "40303")),
        "descricao": "SMOKE CUTOVER VPS " + h,
        "simples_nacional": True,
        "mei": False,
        "op_simp_nac": 3,
        "reg_ap_trib_sn": int(tax.get("reg_ap_trib_sn") or 1),
    }
    print("emitindo", reg["cpf"], reg["nome"], h, "cfg_op=", cfg["op_simp_nac"])
    results = asyncio.run(svc.emitir_nfse_lote([reg], cfg))
    for r in results:
        print("status=", r.status)
        print("numero=", r.numero_nfse)
        print("protocolo=", r.protocolo)
        print("link=", r.link_nfse)
        print("msg=", (r.mensagem or "")[:1200])
        print("hash=", r.hash_transacao)
        return 0 if r.status == "sucesso" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
