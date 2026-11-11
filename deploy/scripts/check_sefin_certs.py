#!/usr/bin/env python3
"""
Verifica se há certificado A1 (PEM) por usuário no volume /app/data/certs.
Uso: docker compose exec -T app python deploy/scripts/check_sefin_certs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    from src.users.profile import cert_pronto, get_user_profile

    users = ("nathalia", "guilherme")
    ready = []
    pending = []
    for username in users:
        profile = get_user_profile(username)
        if not profile:
            pending.append(f"{username}:usuario_ausente")
            continue
        if cert_pronto(profile):
            ready.append(username)
            print(f"OK {username} cnpj={profile.cnpj} cert={profile.cert_pem}")
        else:
            reason = []
            if not profile.cnpj:
                reason.append("cnpj")
            if not profile.cert_pem.exists() or profile.cert_pem.stat().st_size == 0:
                reason.append("cert.pem")
            if not profile.key_pem.exists() or profile.key_pem.stat().st_size == 0:
                reason.append("key.pem")
            pending.append(f"{username}:faltando={','.join(reason) or 'desconhecido'}")
            print(f"PENDENTE {username} {' '.join(pending[-1:])}")

    print(f"ready={len(ready)} pending={len(pending)}")
    # Santa Rosa exige Sefin; precisa de pelo menos 1 usuário com A1 para smoke.
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
