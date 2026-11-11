#!/usr/bin/env python3
"""Cancela NFS-e de lote (evento Sefin e101101) para usuários nathalia/guilherme.

Uso no container (VPS):
  # inventário / dry-run (padrão)
  python deploy/scripts/cancelar_lote_ontem.py

  # smoke: cancela 1 nota de nathalia
  python deploy/scripts/cancelar_lote_ontem.py --execute --limit 1 --users nathalia

  # lote completo de ontem (America/Sao_Paulo)
  python deploy/scripts/cancelar_lote_ontem.py --execute --users nathalia,guilherme

Não apaga linhas do banco: só marca status='cancelado' após sucesso Sefin.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, os.environ.get("APP_ROOT", "/app"))

import psycopg2
from psycopg2.extras import RealDictCursor

from src.users.profile import get_nfse_service_for_username, get_user_profile


TZ_SP = timezone(timedelta(hours=-3))
MOTIVO_PADRAO = "Cancelamento de emissao em lote por erro operacional."


def _dsn() -> str:
    raw = os.environ.get("DATABASE_URL") or ""
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def _chave_from_row(row: Dict[str, Any]) -> str:
    for key in ("numero_nfse", "protocolo"):
        val = "".join(ch for ch in str(row.get(key) or "") if ch.isdigit())
        if len(val) == 50:
            return val
    return ""


def listar_emissoes(
    *,
    users: Sequence[str],
    dia_sp: str,
    status_in: Sequence[str] = ("sucesso",),
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Lista emissões do dia civil America/Sao_Paulo (timestamps gravados em UTC)."""
    dsn = _dsn()
    if not dsn.startswith("postgresql://"):
        raise RuntimeError(f"DATABASE_URL inválida: {dsn!r}")

    # data_emissao/created_at são naive UTC no Postgres desta app
    sql = """
        SELECT id, usuario, status, cnpj_prestador, numero_nfse, protocolo,
               valor_servico, data_emissao, created_at
        FROM nfse_emissoes
        WHERE usuario = ANY(%s)
          AND status = ANY(%s)
          AND (
            ((COALESCE(data_emissao, created_at) AT TIME ZONE 'UTC')
              AT TIME ZONE 'America/Sao_Paulo')::date = %s::date
          )
        ORDER BY usuario, id
    """
    params: list[Any] = [list(users), list(status_in), dia_sp]
    if limit is not None and limit > 0:
        sql += " LIMIT %s"
        params.append(int(limit))

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return rows


def marcar_cancelado(emissao_id: int, mensagem: str) -> None:
    dsn = _dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nfse_emissoes
                SET status = 'cancelado',
                    mensagem = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (mensagem[:2000], emissao_id),
            )
        conn.commit()
    finally:
        conn.close()


async def cancelar_uma(
    username: str,
    row: Dict[str, Any],
    *,
    c_motivo: int,
    x_motivo: str,
    dry_run: bool,
) -> Dict[str, Any]:
    chave = _chave_from_row(row)
    out: Dict[str, Any] = {
        "id": row["id"],
        "usuario": username,
        "chave": chave,
        "cnpj": row.get("cnpj_prestador"),
        "ok": False,
    }
    if len(chave) != 50:
        out["erro"] = "chaveAcesso inválida/ausente"
        return out

    profile = get_user_profile(username)
    if not profile:
        out["erro"] = f"perfil {username} não encontrado"
        return out
    cnpj = "".join(ch for ch in (profile.cnpj or row.get("cnpj_prestador") or "") if ch.isdigit())
    if dry_run:
        out["ok"] = True
        out["dry_run"] = True
        out["cnpj_autor"] = cnpj
        return out

    svc = get_nfse_service_for_username(username)
    try:
        resultado = await svc.cancelar_nfse(
            chave,
            c_motivo=c_motivo,
            x_motivo=x_motivo,
            cnpj_autor=cnpj,
        )
        msg = (
            f"Cancelado Sefin idPed={resultado.get('idPedReg')} "
            f"em {resultado.get('dataHoraProcessamento')}"
        )
        marcar_cancelado(int(row["id"]), msg)
        out["ok"] = True
        out["idPedReg"] = resultado.get("idPedReg")
        out["dataHoraProcessamento"] = resultado.get("dataHoraProcessamento")
    except Exception as e:
        detail = str(e)
        # tenta extrair corpo HTTP se httpx
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                detail = json.dumps(resp.json(), ensure_ascii=False)[:800]
            except Exception:
                detail = (resp.text or detail)[:800]
        out["erro"] = detail
    return out


async def run(args: argparse.Namespace) -> int:
    users = [u.strip() for u in args.users.split(",") if u.strip()]
    dia = args.dia
    rows = listar_emissoes(
        users=users,
        dia_sp=dia,
        status_in=[s.strip() for s in args.status.split(",") if s.strip()],
        limit=args.limit,
    )

    por_user: Dict[str, int] = {}
    for r in rows:
        por_user[r["usuario"]] = por_user.get(r["usuario"], 0) + 1

    print(
        json.dumps(
            {
                "dia_sp": dia,
                "users": users,
                "execute": bool(args.execute),
                "total": len(rows),
                "por_usuario": por_user,
                "amostra_chaves": [
                    {
                        "id": r["id"],
                        "usuario": r["usuario"],
                        "chave": _chave_from_row(r),
                        "cnpj": r.get("cnpj_prestador"),
                        "status": r.get("status"),
                    }
                    for r in rows[:5]
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    if not rows:
        print("Nenhuma emissão elegível.")
        return 0

    dry_run = not args.execute
    if dry_run:
        print("DRY-RUN: nenhuma chamada Sefin. Use --execute para cancelar.")
        return 0

    ok = 0
    fail = 0
    results: List[Dict[str, Any]] = []
    for i, row in enumerate(rows, 1):
        username = row["usuario"]
        print(f"[{i}/{len(rows)}] cancelando id={row['id']} user={username} ...", flush=True)
        out = await cancelar_uma(
            username,
            row,
            c_motivo=args.c_motivo,
            x_motivo=args.x_motivo,
            dry_run=False,
        )
        results.append(out)
        if out.get("ok"):
            ok += 1
            print(f"  OK idPed={out.get('idPedReg')}", flush=True)
        else:
            fail += 1
            print(f"  FALHA {out.get('erro')}", flush=True)
        if args.delay > 0 and i < len(rows):
            await asyncio.sleep(args.delay)

    summary = {"ok": ok, "fail": fail, "total": len(rows)}
    print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2))

    # grava log local no volume
    try:
        out_path = f"/app/data/cancel_lote_{dia.replace('-', '')}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {"summary": summary, "results": results, "ts": datetime.now(TZ_SP).isoformat()},
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        print(f"log={out_path}")
    except Exception as e:
        print(f"aviso: não gravou log: {e}")

    return 0 if fail == 0 else 2


def main() -> int:
    ontem_sp = (datetime.now(TZ_SP) - timedelta(days=1)).date().isoformat()
    p = argparse.ArgumentParser(description="Cancelar NFS-e de lote (Sefin e101101)")
    p.add_argument("--users", default="nathalia,guilherme")
    p.add_argument("--dia", default=ontem_sp, help="Dia America/Sao_Paulo YYYY-MM-DD")
    p.add_argument("--status", default="sucesso")
    p.add_argument("--limit", type=int, default=0, help="0 = todas")
    p.add_argument("--execute", action="store_true", help="Envia cancelamento à Sefin")
    p.add_argument("--c-motivo", dest="c_motivo", type=int, default=1)
    p.add_argument("--x-motivo", dest="x_motivo", default=MOTIVO_PADRAO)
    p.add_argument("--delay", type=float, default=1.5, help="Segundos entre cancelamentos")
    args = p.parse_args()
    if args.limit is not None and args.limit <= 0:
        args.limit = None
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
