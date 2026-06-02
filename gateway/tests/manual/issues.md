# Known Issues Log

Record unresolved runtime or integration issues here with date, symptom, impact, and next action.

## 2026-05-28 Environment blockers
- Symptom: `docker` is not installed on this machine.
- Impact: Cannot use the planned docker compose deployment path.
- Workaround: Switched to local `venv` + process-based runtime.

- Symptom: `conda` is not installed on this machine.
- Impact: Cannot use conda bootstrap path.
- Workaround: Switched bootstrap script to Python `venv`.

- Symptom: `redis-server` is not installed and `sudo` requires password.
- Impact: Redis-backed cache path may not start locally until dependency is installed.
- Workaround: Keep LiteLLM/semantic cache runnable path; if Redis missing, document as unresolved blocker.

## 2026-05-28 Docker registry timeout
- Symptom: Pulling `redis:7-alpine` from Docker Hub timed out repeatedly.
- Impact: Full compose stack blocked on Redis image pull.
- Workaround: Reused system `redis-server` on host and switched containers to `host.docker.internal`.

## 2026-05-28 Semantic-cache image timeout
- Symptom: Docker build for `python:3.11-slim` timed out from Docker Hub.
- Impact: semantic-cache container cannot be built in current network conditions.
- Workaround: Run semantic-cache as a local host Python process, keep LiteLLM in container.

## 2026-05-28 LiteLLM Prisma warning
- Symptom: LiteLLM container emitted Prisma postgres validation errors when `database_url` was set for SQLite.
- Impact: Startup was noisy and readiness unclear.
- Fix: Removed DB URL from active config and disabled DB-backed model state for first-phase bring-up.

## 2026-05-28 LiteLLM startup hang under cache path
- Symptom: Proxy port listened but health/models endpoints hung.
- Suspected cause: startup path interacting badly with Redis cache and/or callbacks in current LiteLLM image.
- Mitigation: temporarily removed cache/callbacks and disabled active health checks for first successful bring-up.

## 2026-05-28 Multi-upstream startup hang
- Symptom: single-upstream proxy responds, but multi-upstream config makes `/v1/models` hang under current LiteLLM image.
- Confirmed usable upstreams from `cc-switch`: OpenPort, testvideo, ltcraft, Codex Chat Proxy.
- Next step: inspect LiteLLM multi-deployment config expectations and test a smaller 2-upstream matrix.

## 2026-05-28 Host-local upstream inside Docker
- Symptom: `Codex Chat Proxy` looked healthy in host probing but failed inside LiteLLM container.
- Root cause: upstream base URL used `127.0.0.1`, which pointed to the container itself rather than the host.
- Fix: rewrite host-local upstreams to `host.docker.internal` and add Docker host gateway mapping.
