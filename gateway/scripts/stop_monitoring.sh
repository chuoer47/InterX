#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f docker-compose.monitoring.yml ]]; then
  sg docker -c 'docker compose -f docker-compose.monitoring.yml down' || true
fi
