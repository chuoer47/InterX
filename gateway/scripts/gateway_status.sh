#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo '== Process / Container Status =='
if command -v docker >/dev/null 2>&1; then
  sg docker -c 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"' || true
fi
if [[ -f state/semantic_cache.pid ]]; then
  pid="$(cat state/semantic_cache.pid 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && ps -p "${pid}" >/dev/null 2>&1; then
    echo "semantic-cache(pid=${pid}) running"
  else
    echo 'semantic-cache not running'
  fi
fi
if command -v redis-cli >/dev/null 2>&1; then
  echo '== Redis =='
  timeout 3 redis-cli -h 127.0.0.1 -p 6379 ping || true
fi
echo '== HTTP =='
echo '-- semantic-cache health'
timeout 5 curl -sS http://127.0.0.1:4010/health || true
echo

echo '-- litellm models'
timeout 5 curl -sS -H 'Authorization: Bearer interx-local-master-key' http://127.0.0.1:4000/v1/models || true
echo
