# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Labyrinth is a network analyzer, mapper, and monitor built on NMap, Ansible, and Telegraf. It provides autodiscovery, port scanning, and metric collection for on-prem/hybrid networks, plus Proxmox cluster disk-space monitoring.

## Architecture Overview

**Service boundaries:**
- `backend/` - Flask API server (port 7000 in dev) handling all business logic; nearly every route lives in `backend/serve.py` (~3000 lines)
- `frontend/labyrinth/` - Vue 2 SPA with Bootstrap-Vue for UI, Konva canvas for network topology visualization
- `alertmanager/` - Prometheus Alertmanager for alert routing
- `nginx/` - Reverse proxy with lego for SSL cert management
- `cron/` - Scheduled jobs (crontab in `cron/cron.d/crontab`) running finder, alive checks, watcher, Proxmox refresh/disk-check, bulk metric writes, AI summaries, level expiry
- `backend/ai/` - hourly AI summary job (`ai.sh` -> `backend/ai/main.py`) that pulls hosts/services/recent metrics from Mongo, sends them to ChatGPT (`chatgpt_helper.py`) for a plain-English summary, and delivers it by email/Slack (`email_helper.py`, `slack_helper.py`)
- `backend/ai/mcp/` - standalone MCP server (own Dockerfile, runs as the `mcp` compose service on port 8765) exposing host/service/metric tools via `unwrap()`-wrapped Flask handlers, bypassing HTTP auth for trusted-network agent access
- MongoDB - primary data store (hosts, subnets, services, metrics, settings, proxmox_clusters)
- Redis - write cache for metrics + temporary storage (Telegraf configs, scan output, autosave, job status, Proxmox cluster/guest status caches)

**Data flow:**
1. Network scans via `backend/finder.py` (nmap) create/update hosts in MongoDB
2. Telegraf agents collect metrics and POST to `/metrics` with a `TELEGRAF_KEY` header (checked via the `requires_header` decorator, not Auth0)
3. Metrics are written to Redis first, then bulk-moved to MongoDB by `cron/bulk_write.sh`
4. Frontend polls the backend API to display topology and metrics
5. `backend/watcher.py` judges service health and sends alerts to Alertmanager (`http://alertmanager:9093/api/v2/alerts`, password read from `/alertmanager/pass`); frontend can list/resolve them via `/alertmanager/alerts`
6. Proxmox: `cron/proxmox_refresh.sh` refreshes the per-cluster Redis cache; `cron/disk_check.sh` runs `backend/proxmox_disk_check.py` hourly to email disk-space alerts

### Proxmox disk-space monitoring (`backend/proxmox_helper.py`, `backend/proxmox_disk_check.py`)

- Proxmox integration is cluster-based (see `proxmox_clusters` MongoDB collection): each cluster stores its own host/user/token credentials, and individual `hosts` reference a cluster via `proxmox_cluster` (by id or name). Legacy per-host/global API key settings still exist but are deprecated.
- `ProxmoxClient` wraps the Proxmox REST API to pull nodes, storage, VM/LXC status, and (via the QEMU guest agent, falling back to a `df -h` "escape valve" exec'd in-guest) real filesystem usage.
- Two layers of Redis caching exist, both namespaced separately:
  - Whole-cluster payload cache (`proxmox-disk:{cluster}`, `PROXMOX_CACHE_TTL_SECONDS`, default 90s) - read by `get_proxmox_disk_data_cached`, refreshed by `cron/proxmox_refresh.sh`.
  - Per-VM/LXC guest status fallback cache (`proxmox-guest-status:{cluster}:{node}:{vm|lxc}:{vmid}`, `PROXMOX_GUEST_STATUS_CACHE_TTL_SECONDS`, default 2 hours) - when a live `get_vm_status`/`get_container_status` call fails, the last known-good status is reused instead of treating the guest as having zero disk usage. This exists specifically to avoid false-positive "missing QEMU guest agent" alerts caused by a single transient API failure.
- `collect_disk_issues` in `proxmox_disk_check.py` turns cluster payloads into threshold-based issues (datastore/vm/container) and always surfaces VMs whose QEMU guest agent is inferred missing, regardless of threshold - a running VM with `maxdisk > 0` and `disk == 0` is a real "we can't measure this" case, not a clean bill of health.
- Email alerts render via Jinja2 (`backend/templates/disk_space_alert.html`, autoescaped) through `email_helper`.

### AI summaries and MCP (`backend/ai/`)

- `cron/ai.sh` runs `backend/ai/main.py` hourly: `process_dashboard()` pulls hosts/services and recent metrics from MongoDB, slims them down, and `main()` sends the result to ChatGPT (`chatgpt_helper.py`) using a prompt template (`initial_prompt.txt`, gitignored - see `initial_prompt.txt.example`) to produce a plain-English network summary, delivered via `email_helper.py`/`slack_helper.py`.
- `backend/ai/mcp/server.py` is a separate MCP (Model Context Protocol) server, run as its own Docker service (`mcp` in compose files) with its own `Dockerfile`/`requirements.txt`. It shares the backend's MongoDB/Redis and calls `serve.py` route handlers directly via `unwrap()`, so it exposes host/service/metric management tools (`mcp_list_hosts`, `mcp_create_or_update_host`, `mcp_add_service_to_host`, `mcp_list_services`, `mcp_read_metrics`, etc.) without HTTP auth - intended for trusted-network agent access only. Full tool/schema docs in `backend/ai/mcp/README.md`.

## Development Workflows

**Start development environment:**
```bash
./start_dev.sh  # sets up Auth0, alertmanager, SSL certs, then starts docker-compose-development.yml
```
- Frontend dev server: port 8001 (hot reload) / port 8002 (live frontend) - see `devel` service in `docker-compose-development.yml`
- Backend API: port 7000
- NGINX/SSL: port 7210 (Caddy uses an internal dev CA - accept its cert in-browser)
- MongoDB: localhost:27017, Mongo Express: port 8071
- MCP server: port 8765 (internal to the `labyrinth` docker network)

**Backend tests:**
```bash
cd backend && ./run_tests.sh
# or, inside the backend container/venv directly:
PYTHONPATH=. pytest --cov=. --cov-config=.coveragerc --cov-report term-missing --cov-fail-under=95 test/
# single file / single test:
PYTHONPATH=. pytest test/test_13_proxmox_helper.py -q
PYTHONPATH=. pytest test/test_13_proxmox_helper.py::test_get_proxmox_disk_data_no_nodes -q
```
- Requires `GITHUB=1` or `TESTBED=1` env var so `serve.py`/`proxmox_disk_check.py` use plain `mongodb://` instead of `mongodb+srv://` (SRV DNS lookup fails without a real Atlas host).
- 95% coverage is enforced (`--cov-fail-under=95`); `.coveragerc` excludes `templates/`, `uploads/`, `samples/`, `snippets/`.
- Fixtures are defined per test file, not centralized in `conftest.py`.
- Routes are wrapped in Auth0 decorators; tests call them via `common.test.unwrap(serve.some_route)()` to bypass auth and invoke the underlying function directly.
- Mock MongoDB/Redis via fixtures/monkeypatch (e.g. `Mock(spec=redis.Redis)`, hand-rolled `FakeRedis` classes) rather than hitting real services.

**Frontend (`frontend/labyrinth/`):**
```bash
npm install
npm run serve       # dev server with hot reload
npm run build        # production build -> dist/, served by nginx
npm run test:unit
npm run test:e2e
npm run lint
```

**Production build:**
```bash
docker-compose -f docker-compose-production.yml up --build -d
```

**CI** (`.github/workflows/push.yml`): backend tests run inside docker-compose-development via `start_dev.sh` + `backend/run_tests.sh`; frontend tests/lint run separately with npm.

## Code Conventions

**Authentication:**
- Three permission levels: `PERM_READ`, `PERM_WRITE`, `PERM_ADMIN`, applied via `@requires_auth_read`/`@requires_auth_write`/`@requires_auth_admin` decorators (Auth0 JWT validation in `backend/common/auth.py`).
- Telegraf metrics ingestion instead uses header auth (`requires_header`, checks `TELEGRAF_KEY`).

**Service/health-check model:**
- `services` MongoDB collection stores check/port monitoring configs; two service types: `"check"` (command execution) and `"port"` (TCP/UDP checks).
- Judging logic lives in `backend/metrics.py` (`judge()`, `judge_check()`, `judge_port()`).

**Telegraf config management:**
- Master config at `/src/uploads/master.conf` (TOML), parsed by `backend/services.py` (handles duplicates, multiline arrays, preserves comments).
- Per-host configs are generated from the master template plus service definitions; the TOML structure is stored in Redis for UI editing.

**Ansible integration:**
- Playbooks under `/src/uploads/ansible/`, vault files under `/src/uploads/become/`.
- `backend/ansible_helper.py` validates YAML before saving.
- Background execution via `run_ansible_background()`; job status and streamed results (`{job_id}_log`) live in Redis.

**Network scanning:**
- `backend/finder.py` runs an nmap ping + service-detection scan (`-sT -PU0 -Pn`), stores results in Redis (`output-{subnet}`), and updates the `hosts` collection with discovered IPs/MACs. Triggered via `/scan/` or the cron job.

## Key Files
- `backend/serve.py` - all API endpoints
- `backend/finder.py` - network discovery
- `backend/metrics.py` - service health judging
- `backend/services.py` - Telegraf config parsing
- `backend/ansible_helper.py` - Ansible validation/execution
- `backend/proxmox_helper.py` / `backend/proxmox_disk_check.py` - Proxmox cluster querying, caching, and disk-space alert emails
- `backend/watcher.py` - Alertmanager alert dispatch
- `backend/ai/main.py` - hourly AI dashboard summary job
- `backend/ai/mcp/server.py` - MCP server exposing host/service/metric tools
- `cron/run.sh`, `cron/cron.d/crontab` - scheduled job definitions
- `start_dev.sh` - development environment bootstrap
