#!/usr/bin/env python3
"""
Backfill de ownership das NFS-e + schema multi-tenant.

Atribui linhas legadas (admin/medico/NULL/vazio) a nathalia (CNPJ 56169351000185).
Não altera linhas já marcadas com tenants reais (ex.: guilherme, nathalia).

Uso:
  docker compose exec -T app python deploy/scripts/backfill_nfse_tenant.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import psycopg2


def _dsn() -> str:
    raw = os.getenv("DATABASE_URL") or ""
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def print_counts(label: str) -> None:
    dsn = _dsn()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COALESCE(NULLIF(btrim(usuario), ''), '(null)') AS usuario,
               COUNT(*) FILTER (WHERE status = 'sucesso') AS sucessos,
               COUNT(*) AS total
        FROM nfse_emissoes
        GROUP BY 1
        ORDER BY total DESC
        """
    )
    rows = cur.fetchall()
    print(f"=== {label} ===")
    for u, ok, total in rows:
        print(f"  {u}: sucesso={ok} total={total}")
    cur.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE lower(btrim(coalesce(usuario,''))) = 'guilherme') AS guilherme,
          COUNT(*) FILTER (WHERE lower(btrim(coalesce(usuario,''))) = 'nathalia') AS nathalia,
          COUNT(*) AS total
        FROM nfse_emissoes
        WHERE status = 'sucesso'
        """
    )
    g, n, t = cur.fetchone()
    print(f"  RESUMO sucesso → guilherme={g} nathalia={n} total={t}")
    cur.close()
    conn.close()


async def main() -> int:
    from src.database.tenant_nfse import backfill_legacy_ownership, ensure_tenant_schema

    print_counts("ANTES")
    await ensure_tenant_schema()
    updated = await backfill_legacy_ownership(
        owner="nathalia",
        owner_cnpj="56169351000185",
    )
    print(f"Backfill atualizou {updated} linhas")
    print_counts("DEPOIS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
