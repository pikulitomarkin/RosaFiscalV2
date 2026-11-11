"""
Configurações runtime persistidas no volume de dados (ex.: senha IPM).
Não vão para o git — ficam em DATA_DIR/runtime_config.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings

DATA_DIR = Path(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "./data"))
CONFIG_FILE = DATA_DIR / "runtime_config.json"

# Prestador oficial deste sistema (Nathalia Gabriela — Santa Rosa-RS)
PRESTADOR_OFICIAL = {
    "cnpj": "56169351000185",
    "inscricao_municipal": "56937",
    "razao_social": "NATHALIA GABRIELA SERVICOS DE SAUDE LTDA",
    "nome_fantasia": "NATHALIA GABRIELA",
}


def _read() -> Dict[str, Any]:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        CONFIG_FILE.chmod(0o600)
    except Exception:
        pass


def get_ipm_usuario() -> str:
    data = _read()
    return (
        str(data.get("ipm_usuario") or "").strip()
        or (settings.IPM_USUARIO or "").strip()
        or PRESTADOR_OFICIAL["cnpj"]
    )


def get_ipm_senha() -> str:
    data = _read()
    if data.get("ipm_senha"):
        return str(data["ipm_senha"])
    return (settings.IPM_SENHA or os.getenv("IPM_SENHA") or "").strip()


def ipm_senha_configurada() -> bool:
    return bool(get_ipm_senha())


def save_ipm_credentials(usuario: str, senha: str) -> None:
    data = _read()
    data["ipm_usuario"] = "".join(ch for ch in usuario if ch.isdigit()) or PRESTADOR_OFICIAL["cnpj"]
    if senha:
        data["ipm_senha"] = senha
    _write(data)
    # Espelha no processo atual para leituras via settings/env no mesmo run
    os.environ["IPM_USUARIO"] = data["ipm_usuario"]
    if senha:
        os.environ["IPM_SENHA"] = senha


def get_emission_backend() -> str:
    """Backend de emissão: 'sefin' (API nacional, padrão) ou 'ipm' (legado)."""
    data = _read()
    raw = str(data.get("emission_backend") or os.getenv("EMISSION_BACKEND") or "sefin").strip().lower()
    return raw if raw in ("sefin", "ipm") else "sefin"


def set_emission_backend(backend: str) -> None:
    data = _read()
    data["emission_backend"] = "ipm" if str(backend).lower() == "ipm" else "sefin"
    _write(data)


def _normalize_op_simp_nac(raw: Any, *, simples_nacional: bool, mei: bool) -> int:
    """1=Não optante, 2=MEI, 3=ME/EPP, 4=Optante Pendente (Sefin oficial)."""
    if raw is not None and str(raw).strip() != "":
        try:
            code = int(raw)
            if code in (1, 2, 3, 4):
                return code
        except (TypeError, ValueError):
            pass
    if mei:
        return 2
    if simples_nacional:
        return 3
    return 1


def _normalize_reg_ap_trib_sn(raw: Any, *, op_simp_nac: int) -> Optional[int]:
    """Só aplica a ME/EPP (opSimpNac=3). Default 1 = federais+municipal pelo SN."""
    if op_simp_nac != 3:
        return None
    try:
        code = int(raw) if raw is not None and str(raw).strip() != "" else 1
    except (TypeError, ValueError):
        code = 1
    return code if code in (1, 2, 3) else 1


def get_shared_tax_config() -> Dict[str, Any]:
    """Imposto / serviço padrão compartilhado entre usuários."""
    data = _read()
    shared = data.get("shared_tax") or {}
    simples_nacional = bool(shared.get("simples_nacional", True))
    mei = bool(shared.get("mei", False))
    op_simp_nac = _normalize_op_simp_nac(
        shared.get("op_simp_nac"),
        simples_nacional=simples_nacional,
        mei=mei,
    )
    # Se op_simp_nac explícito for MEI/ME, alinhar flags derivadas
    if op_simp_nac == 2:
        mei = True
        simples_nacional = True
    elif op_simp_nac == 3:
        mei = False
        simples_nacional = True
    elif op_simp_nac == 1:
        mei = False
        simples_nacional = False
    reg_ap_trib_sn = _normalize_reg_ap_trib_sn(
        shared.get("reg_ap_trib_sn"),
        op_simp_nac=op_simp_nac,
    )
    return {
        "aliquota_iss": float(shared.get("aliquota_iss", 2.01)),
        "item_lista": str(shared.get("item_lista", "40303")),
        "descricao": str(shared.get("descricao", "CONSULTA MEDICA")),
        "nbs": str(shared.get("nbs", "1.2301.21.00")),
        "simples_nacional": simples_nacional,
        "mei": mei,
        "op_simp_nac": op_simp_nac,
        "reg_ap_trib_sn": reg_ap_trib_sn if reg_ap_trib_sn is not None else 1,
    }


def save_shared_tax_config(
    *,
    aliquota_iss: float,
    item_lista: str,
    descricao: str,
    nbs: str = "1.2301.21.00",
    simples_nacional: bool = True,
    mei: bool = False,
    op_simp_nac: Optional[int] = None,
    reg_ap_trib_sn: Optional[int] = None,
) -> None:
    # Preferência: op_simp_nac explícito > mei > simples_nacional
    if op_simp_nac is not None and str(op_simp_nac).strip() != "":
        code = _normalize_op_simp_nac(op_simp_nac, simples_nacional=True, mei=False)
    elif mei:
        code = 2
    elif simples_nacional:
        code = 3
    else:
        code = 1

    mei_flag = code == 2
    sn_flag = code in (2, 3, 4)
    reg_ap = _normalize_reg_ap_trib_sn(reg_ap_trib_sn, op_simp_nac=code)

    data = _read()
    payload: Dict[str, Any] = {
        "aliquota_iss": float(aliquota_iss),
        "item_lista": "".join(ch for ch in str(item_lista) if ch.isdigit()) or "40303",
        "descricao": (descricao or "CONSULTA MEDICA").strip(),
        "nbs": (nbs or "1.2301.21.00").strip(),
        "simples_nacional": sn_flag,
        "mei": mei_flag,
        "op_simp_nac": code,
    }
    if reg_ap is not None:
        payload["reg_ap_trib_sn"] = reg_ap
    data["shared_tax"] = payload
    _write(data)
