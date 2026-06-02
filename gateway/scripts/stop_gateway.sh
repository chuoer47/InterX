#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f state/semantic_cache.pid ]]; then
  kill "$(cat state/semantic_cache.pid)" || true
  rm -f state/semantic_cache.pid
fi
if [[ -f docker-compose.runtime.yml ]]; then
  sg docker -c 'docker compose -f docker-compose.runtime.yml down' || true
fi
