# Local Monitoring Notes

Current stable runtime in this environment:
- LiteLLM in Docker
- Semantic cache as local uvicorn process
- Redis as host service

Because Docker Hub pulls were unstable, Grafana/Prometheus containers are scaffolded but not treated as the only monitoring path.
Use `scripts/gateway_status.sh` for immediate operational visibility.
