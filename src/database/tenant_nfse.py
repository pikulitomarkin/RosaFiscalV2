"""
Isolamento multi-tenant das NFS-e emitidas.

Toda leitura/escrita de histórico deve filtrar por `usuario` (username do login).
Linhas legadas (admin/medico/NULL) são atribuídas a nathalia no backfill.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select, text, update

from src.utils.logger import app_logger

# Usuários legados / placeholders que não são tenants reais pós-migração
LEGACY_USUARIOS = frozenset({"", "admin", "medico", "sistema", "null", "none"})
DEFAULT_LEGACY_OWNER = "nathalia"


def _data_dir() -> Path:
    base = Path(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "./data"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def persistence_path_for_user(username: str) -> Path:
    """Arquivo JSON de cache por usuário (evita vazamento entre tenants)."""
    safe = "".join(ch for ch in (username or "anon").lower() if ch.isalnum() or ch in "_-") or "anon"
    return _data_dir() / f"nfse_emitidas_{safe}.json"


def normalize_username(username: Optional[str]) -> str:
    return (username or "").strip().lower()


def _row_to_dict(r) -> Dict[str, Any]:
    return {
        "chave_acesso": r.hash_transacao,
        "numero": r.numero_nfse or "N/A",
        "data_emissao": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else "N/A",
        "tomador_nome": r.nome_tomador,
        "tomador_cpf": r.cpf_tomador,
        "valor": float(r.valor_servico or 0),
        "iss": float(r.valor_iss or 0),
        "xml_path": None,
        "pdf_path": None,
        "link_nfse": r.url_nfse,
        "usuario": r.usuario,
        "cnpj_prestador": getattr(r, "cnpj_prestador", None),
    }


async def ensure_tenant_schema() -> None:
    """Garante coluna cnpj_prestador + índice por usuário (idempotente)."""
    from config.database import engine
    from config.settings import settings

    if not str(settings.DATABASE_URL).startswith("postgresql"):
        return

    stmts = [
        "ALTER TABLE nfse_emissoes ADD COLUMN IF NOT EXISTS cnpj_prestador VARCHAR(14)",
        "CREATE INDEX IF NOT EXISTS idx_nfse_emissoes_usuario ON nfse_emissoes (usuario)",
        "CREATE INDEX IF NOT EXISTS idx_nfse_emissoes_usuario_status ON nfse_emissoes (usuario, status)",
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                app_logger.debug(f"ensure_tenant_schema skip: {e}")


async def backfill_legacy_ownership(
    owner: str = DEFAULT_LEGACY_OWNER,
    owner_cnpj: str = "56169351000185",
) -> int:
    """
    Atribui emissões sem dono de tenant real ao usuário legado (nathalia).
    Não altera linhas já marcadas com username de tenant (ex.: guilherme, nathalia).
    """
    from config.database import AsyncSessionLocal
    from src.database.models import NFSeEmissao

    owner_norm = normalize_username(owner)
    async with AsyncSessionLocal() as session:
        stmt_count = select(func.count(NFSeEmissao.id)).where(
            (NFSeEmissao.usuario.is_(None))
            | (func.lower(func.btrim(NFSeEmissao.usuario)).in_(list(LEGACY_USUARIOS)))
        )
        pending = await session.scalar(stmt_count) or 0
        if pending == 0:
            await session.commit()
            return 0

        stmt = (
            update(NFSeEmissao)
            .where(
                (NFSeEmissao.usuario.is_(None))
                | (func.lower(func.btrim(NFSeEmissao.usuario)).in_(list(LEGACY_USUARIOS)))
            )
            .values(usuario=owner_norm, cnpj_prestador=owner_cnpj)
        )
        result = await session.execute(stmt)
        await session.commit()
        updated = result.rowcount or 0
        app_logger.info(
            f"Backfill NFS-e tenant: {updated} linhas → usuario={owner_norm} cnpj={owner_cnpj}"
        )
        return updated


async def load_notas_for_user(username: str) -> List[Dict[str, Any]]:
    """Carrega apenas NFS-e de sucesso do usuário autenticado."""
    from config.database import AsyncSessionLocal
    from src.database.models import NFSeEmissao

    user = normalize_username(username)
    if not user:
        return []

    await ensure_tenant_schema()

    async with AsyncSessionLocal() as session:
        stmt = (
            select(NFSeEmissao)
            .where(
                NFSeEmissao.status == "sucesso",
                func.lower(func.btrim(NFSeEmissao.usuario)) == user,
            )
            .order_by(NFSeEmissao.created_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_dict(r) for r in rows]


async def count_notas_for_user(username: str, status: str = "sucesso") -> int:
    from config.database import AsyncSessionLocal
    from src.database.models import NFSeEmissao

    user = normalize_username(username)
    if not user:
        return 0

    async with AsyncSessionLocal() as session:
        stmt = select(func.count(NFSeEmissao.id)).where(
            func.lower(func.btrim(NFSeEmissao.usuario)) == user,
            NFSeEmissao.status == status,
        )
        return int(await session.scalar(stmt) or 0)


async def sync_notas_para_db(
    notas: List[Dict[str, Any]],
    username: str,
    cnpj_prestador: Optional[str] = None,
) -> int:
    """Upsert por chave_acesso, sempre carimbando o usuário atual."""
    from config.database import AsyncSessionLocal
    from src.database.models import NFSeEmissao

    user = normalize_username(username)
    if not user:
        app_logger.warning("sync_notas_para_db: username vazio — abortando persistência")
        return 0

    cnpj = "".join(ch for ch in str(cnpj_prestador or "") if ch.isdigit())[:14] or None

    def _trunc(value, size: int) -> str:
        text_val = str(value or "")
        return text_val[:size] if size > 0 else text_val

    await ensure_tenant_schema()
    salvas = 0

    async with AsyncSessionLocal() as session:
        for nota in notas:
            chave = nota.get("chave_acesso") or nota.get("numero")
            if not chave or chave == "N/A":
                continue
            chave = _trunc(chave, 128)
            cpf = (
                str(nota.get("tomador_cpf", "") or "")
                .replace(".", "")
                .replace("-", "")
                .replace("/", "")
            )
            try:
                stmt = select(NFSeEmissao).where(NFSeEmissao.hash_transacao == chave)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    existing_user = normalize_username(existing.usuario)
                    if existing_user and existing_user != user and existing_user not in LEGACY_USUARIOS:
                        app_logger.warning(
                            f"Ignorando upsert de {chave[:16]}…: dono={existing_user} ≠ {user}"
                        )
                        continue
                    existing.usuario = user
                    if cnpj and not getattr(existing, "cnpj_prestador", None):
                        existing.cnpj_prestador = cnpj
                    continue

                emissao = NFSeEmissao(
                    hash_transacao=chave,
                    numero_nfse=_trunc(nota.get("numero", ""), 80),
                    protocolo=_trunc(chave, 128),
                    cpf_tomador=(cpf[:14] if cpf else "00000000000"),
                    nome_tomador=_trunc(nota.get("tomador_nome", ""), 150),
                    status="sucesso",
                    url_nfse=_trunc(nota.get("link_nfse"), 1000) or None,
                    valor_servico=nota.get("valor"),
                    valor_iss=nota.get("iss"),
                    descricao_servico=nota.get("descricao"),
                    usuario=_trunc(user, 50),
                    cnpj_prestador=cnpj,
                )
                session.add(emissao)
                salvas += 1
            except Exception as e:
                app_logger.error(f"Falha ao persistir nota {chave}: {e}")
        await session.commit()

    app_logger.info(f"Sync DB tenant={user}: {salvas} novas notas persistidas")
    return salvas


async def delete_notas_for_user(username: str) -> int:
    """Remove do banco apenas as NFS-e do usuário (limpeza de histórico)."""
    from config.database import AsyncSessionLocal
    from src.database.models import NFSeEmissao

    user = normalize_username(username)
    if not user:
        return 0

    async with AsyncSessionLocal() as session:
        stmt = delete(NFSeEmissao).where(
            func.lower(func.btrim(NFSeEmissao.usuario)) == user
        )
        result = await session.execute(stmt)
        await session.commit()
        deleted = result.rowcount or 0
        app_logger.info(f"Histórico DB limpo para {user}: {deleted} linhas")
        return deleted


def load_json_for_user(username: str) -> List[Dict[str, Any]]:
    path = persistence_path_for_user(username)
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                user = normalize_username(username)
                return [
                    n
                    for n in data
                    if not n.get("usuario")
                    or normalize_username(str(n.get("usuario"))) == user
                ]
    except Exception as e:
        app_logger.error(f"Erro ao carregar JSON local {path}: {e}")
    return []


def save_json_for_user(username: str, notas: List[Dict[str, Any]]) -> None:
    path = persistence_path_for_user(username)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(notas, f, ensure_ascii=False, indent=2)
        app_logger.info(f"Notas salvas em {path}: {len(notas)} registros")
    except Exception as e:
        app_logger.error(f"Erro ao salvar JSON local: {e}")


def load_emitted_nfse_scoped(username: str) -> List[Dict[str, Any]]:
    """API síncrona: DB prioridade, JSON por usuário como fallback."""
    user = normalize_username(username)
    if not user:
        return []
    try:
        notas_db = asyncio.run(load_notas_for_user(user))
        app_logger.info(f"Notas carregadas do banco (tenant={user}): {len(notas_db)}")
        return notas_db
    except Exception as e:
        app_logger.warning(f"Banco indisponível para tenant={user}, usando JSON: {e}")
    return load_json_for_user(user)


def save_emitted_nfse_scoped(
    username: str,
    notas: List[Dict[str, Any]],
    cnpj_prestador: Optional[str] = None,
) -> None:
    user = normalize_username(username)
    if not user:
        app_logger.warning("save_emitted_nfse_scoped: sem username — não grava")
        return
    stamped = []
    for n in notas:
        item = dict(n)
        item["usuario"] = user
        if cnpj_prestador and not item.get("cnpj_prestador"):
            item["cnpj_prestador"] = cnpj_prestador
        stamped.append(item)
    save_json_for_user(user, stamped)
    try:
        asyncio.run(sync_notas_para_db(stamped, user, cnpj_prestador=cnpj_prestador))
    except Exception as e:
        app_logger.error(f"Erro ao salvar no banco (tenant={user}): {e}")


def clear_emitted_nfse_scoped(username: str) -> int:
    """Limpa JSON + DB somente do tenant atual."""
    user = normalize_username(username)
    if not user:
        return 0
    path = persistence_path_for_user(user)
    try:
        if path.exists():
            path.write_text("[]", encoding="utf-8")
    except Exception as e:
        app_logger.error(f"Erro ao limpar JSON {path}: {e}")
    try:
        return asyncio.run(delete_notas_for_user(user))
    except Exception as e:
        app_logger.error(f"Erro ao limpar DB tenant={user}: {e}")
        return 0
