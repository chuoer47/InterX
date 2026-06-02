#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cat > docker-compose.monitoring.yml <<'YAML'
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: interx-gateway-prometheus
    extra_hosts:
      - "host.docker.internal:host-gateway"
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/local/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./state/prometheus:/prometheus

  grafana:
    image: grafana/grafana:latest
    container_name: interx-gateway-grafana
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
    ports:
      - "3000:3000"
    volumes:
      - ./grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
YAML
sg docker -c 'docker compose -f docker-compose.monitoring.yml up -d'
