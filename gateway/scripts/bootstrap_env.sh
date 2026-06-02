#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${ROOT}/.venv"
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install 'litellm[proxy]' pyyaml requests httpx redis fastapi uvicorn prometheus-client
python --version
