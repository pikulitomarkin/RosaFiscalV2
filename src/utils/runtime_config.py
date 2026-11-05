"""
Configurações runtime persistidas no volume de dados (ex.: senha IPM).
Não vão para o git — ficam em DATA_DIR/runtime_config.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

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
