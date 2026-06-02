#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
if [[ ! -f .env ]]; then
  echo "Missing .env; copy from .env.example first" >&2
  exit 1
fi
source .venv/bin/activate
python3 scripts/render_config.py
mkdir -p logs state tests/results
if command -v redis-server >/dev/null 2>&1; then
  redis-server --port 6380 --save '' --appendonly no > logs/redis.log 2>&1 &
  echo $! > state/redis.pid
  export REDIS_URL=redis://127.0.0.1:6380/0
fi
litellm --config litellm/config.yaml --host 127.0.0.1 --port 4000 > logs/litellm.log 2>&1 &
echo $! > state/litellm.pid
uvicorn extensions.semantic_cache.app.main:app --host 127.0.0.1 --port 4010 > logs/semantic-cache.log 2>&1 &
echo $! > state/semantic_cache.pid
