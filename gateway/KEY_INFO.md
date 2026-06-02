# Key Info

## Project
- Name: InterX Gateway
- Scope: Independent LiteLLM-based gateway layer for InterX multi-repo architecture
- Primary interface: OpenAI-compatible API

## Approved Decisions
- Use LiteLLM as gateway core
- Use Redis for cache/state
- Use Prometheus + Grafana for observability
- Keep LiteLLM UI/Admin if practical
- No stream replay cache in first implementation
- Semantic cache uses external adjudicator layer

## Local Environment Notes
- `cc-switch` is installed locally under `/home/amax01/.local/bin/`
- `cc-switch` related state exists under `/home/amax01/.cc-switch/`
- Detected local proxy config file: `/home/amax01/.cc-switch/codex-chat-proxy.json`
- Do not commit discovered secrets; only store templates and env var references

## Security Rules
- Never commit raw upstream API keys
- Never commit local provider secrets copied from `cc-switch`
- Prefer `.env` + `.env.example`

## Discovered Upstream Summary
- Local `cc-switch` proxy service listens on `127.0.0.1:15721` for Codex-compatible chat/responses
- Local chat proxy config file indicates one upstream OpenAI-compatible endpoint and one model alias
- Actual secrets remain local-only and uncommitted

## Runtime Constraints
- `docker` unavailable locally
- `conda` unavailable locally
- `redis-server` unavailable locally without system install
- `sudo` requires password, so system package installation is blocked in-agent

## Environment Updates
- Docker and Docker Compose are now installed locally
- `redis-server` is installed locally and running on `127.0.0.1:6379`
- User `amax01` is in docker group

## Working Runtime
- LiteLLM proxy runs in Docker on `127.0.0.1:4000`
- Semantic cache runs as local `uvicorn` process on `127.0.0.1:4010`
- Host `redis-server` is used on `127.0.0.1:6379`
- Stream and non-stream proxy calls are validated against local cc-switch upstream

## Upstream Findings
- Probed `cc-switch` codex providers directly
- Usable in direct probe: `OpenPort`, `testvideo`, `ltcraft`, `Codex Chat Proxy`
- Unusable in direct probe: `gmail-freemodel`, `qq1-freemodel`
- Multi-upstream continuous stability is weaker than single-shot availability; routing should degrade gracefully

## Ops Surface
- Unified command entrypoint: `ops/interx-gateway`
- Local monitor UI: `http://127.0.0.1:4020`
- Routing diagnostics output: `tests/results/routing_probe.json`
- Semantic cache metrics: `http://127.0.0.1:4010/metrics`

## Scoreboard
- Upstream ranking output: `tests/results/upstream_scoreboard.json`
- Human-readable ranking: `tests/results/upstream_scoreboard.md`
- Local dashboard consumes probe + scoreboard data
