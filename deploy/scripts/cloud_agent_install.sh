#!/usr/bin/env bash
# Bootstrap idempotente para Cloud Agents (Cursor).
# Instala deps Python no --user e expoe CLIs em /usr/local/bin (PATH de login).
set -euo pipefail
cd "$(cd "$(dirname "$0")/../.." && pwd)"

python3 -m pip install --user --upgrade pip
python3 -m pip install --user -r requirements.txt

mkdir -p "$HOME/.local/bin" certificados data logs
for bin in streamlit pytest; do
  if [[ -x "$HOME/.local/bin/$bin" ]]; then
    sudo ln -sf "$HOME/.local/bin/$bin" "/usr/local/bin/$bin"
  fi
done

python3 -c "import streamlit, sqlalchemy, psycopg2, pdfplumber; print('cloud_agent_install_ok', streamlit.__version__)"
