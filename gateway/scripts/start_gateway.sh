#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
. ./.env
set +a
MODE="${1:-stable}"
if [[ "${MODE}" == "multi" && -f litellm/config.multi.yaml ]]; then
  export INTERX_LITELLM_CONFIG=litellm/config.multi.yaml
elif [[ -f litellm/config.stable.yaml ]]; then
  export INTERX_LITELLM_CONFIG=litellm/config.stable.yaml
else
  python3 scripts/render_config.py
  export INTERX_LITELLM_CONFIG=litellm/config.yaml
fi
cat > docker-compose.runtime.yml <<YAML
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: interx-gateway-litellm
    extra_hosts:
      - "host.docker.internal:host-gateway"
    env_file:
      - .env
    environment:
      - REDIS_URL=redis://host.docker.internal:6379/0
    command: ["--config", "/app/config.yaml", "--port", "4000", "--host", "0.0.0.0", "--detailed_debug"]
    ports:
      - "4000:4000"
    volumes:
      - ./${INTERX_LITELLM_CONFIG}:/app/config.yaml:ro
      - ./state:/app/state
      - ./logs:/app/logs
YAML
sg docker -c 'docker compose -f docker-compose.runtime.yml up -d --force-recreate litellm'
if [[ -f state/semantic_cache.pid ]]; then
  kill "$(cat state/semantic_cache.pid)" || true
fi
. .venv/bin/activate
nohup uvicorn extensions.semantic_cache.app.main:app --host 127.0.0.1 --port 4010 > logs/semantic-cache.log 2>&1 &
echo $! > state/semantic_cache.pid
