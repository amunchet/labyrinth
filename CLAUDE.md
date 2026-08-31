# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Labyrinth is a network analyzer, mapper, and monitor built on NMap, Ansible, and Telegraf. It provides autodiscovery, port scanning, and metric collection for on-prem/hybrid networks, plus Proxmox cluster disk-space monitoring.

## Architecture Overview

**Service boundaries:**
- `backend/` - Flask API server (port 7000 in dev) handling all business logic; nearly every route lives in `backend/serve.py` (~3000 lines)
- `metrics-go/` - Go Telegraf ingest service (port 9000, `metrics` compose service). Caddy routes `POST /api/metrics/` here; everything else under `/api/` still goes to Flask. Drop-in replacement for `serve.py`'s `insert_metric`: same `TELEGRAF_KEY` header check, same `METRIC-<json>` Redis keys with the same 120s TTL, but one pipelined Redis round trip per agent batch instead of a connection pool per metric. Also records the per-client ingest counters (see below). Full docs in `metrics-go/README.md`
- `frontend/labyrinth/` - Vue 2 SPA with Bootstrap-Vue for UI, Konva canvas for network topology visualization
- `alertmanager/` - Prometheus Alertmanager for alert routing
- `nginx/` - Reverse proxy with lego for SSL cert management
- `cron/` - Scheduled jobs (crontab in `cron/cron.d/crontab`) running finder, alive checks, watcher, Proxmox refresh/disk-check, EC2 unmatched-instance check, bulk metric writes, AI summaries, level expiry
- `backend/ai/` - hourly AI summary job (`ai.sh` -> `backend/ai/main.py`, built on `ai_pipeline.py`/`ai_settings.py`) that pulls hosts/services/recent metrics from the database, sends them to ChatGPT (`chatgpt_helper.py`) for a plain-English summary, and delivers it by email/Slack (`email_helper.py`, `slack_helper.py`)
- `backend/ai/mcp/` - standalone MCP server (own Dockerfile, runs as the `mcp` compose service on port 8765) exposing host/service/metric tools via `unwrap()`-wrapped Flask handlers, bypassing Auth0; guarded instead by an `MCP_KEY` pre-shared secret and reached externally through Caddy's `/mcp*` route
- `backend/db/` - database adapter ecosystem (see below) - PostgreSQL/TimescaleDB by default, MongoDB as an explicit fallback
- PostgreSQL + TimescaleDB - default data store (`DB_BACKEND=postgres`): JSONB tables for hosts/subnets/services/settings/proxmox_clusters/aws_accounts/themes/dashboards, a TimescaleDB hypertable for `metrics`, a plain table for `metrics-latest`. See `MONGO_MIGRATION.md`.
- MongoDB - fallback data store (`DB_BACKEND=mongo`); prior default, still fully supported
- Redis - write cache for metrics + temporary storage (Telegraf configs, scan output, autosave, job status, Proxmox cluster/guest status caches)

**Data flow:**
1. Network scans via `backend/finder.py` (nmap) create/update hosts in the database
2. Telegraf agents collect metrics and POST to `/metrics` with a `TELEGRAF_KEY` header (checked via the `requires_header` decorator, not Auth0). In deployed stacks this is served by `metrics-go`; the Flask route remains as a fallback
3. Metrics are written to Redis first (short-lived, 120s TTL, overwritten in place), then bulk-moved to the database once a minute by `cron/bulk_write.sh` (`serve.py`'s `bulk_insert()`). Only one transfer runs at a time - a run that overruns the minute makes the next tick wait, via the Redis lock in `backend/common/single_run.py` (fencing token + heartbeat-extended TTL). See "Redis -> Postgres metrics transfer" in `MONGO_MIGRATION.md`
4. Frontend polls the backend API to display topology and metrics
5. `backend/watcher.py` judges service health and sends alerts to Alertmanager (`http://alertmanager:9093/api/v2/alerts`, password read from `/alertmanager/pass`); frontend can list/resolve them via `/alertmanager/alerts`
6. Proxmox: `cron/proxmox_refresh.sh` refreshes the per-cluster Redis cache; `cron/disk_check.sh` runs `backend/proxmox_disk_check.py` hourly to email disk-space alerts
7. AWS: `cron/ec2_check.sh` runs `backend/ec2_unmatched_check.py` hourly to email a list of EC2 instances that don't match any known Labyrinth host (matching logic shared with `serve.py` via `aws_helper.py`)
8. Postgres backend only: `cron/compact_metrics.sh` daily rolls raw `metrics` rows older than `METRICS_RAW_RETENTION_DAYS` into `metrics_daily` aggregates; `cron/backup_db.sh` daily dumps the database to `/backups` for an external offsite system to pick up

### Database adapter ecosystem (`backend/db/`)

- `backend/db/__init__.py` is the single entry point, selecting a backend via the `DB_BACKEND` env var (`postgres` default, `mongo` fallback). Every module that touches the database goes through it - there is no direct `pymongo`/`psycopg2` usage outside `backend/db/`.
- **Which entry point matters for connection count.** On Postgres a `Client` owns a connection pool and nothing reaps pools, so: `shared_db()` (lazy proxy onto the process-wide client) for module-level application code, `get_shared_client()` for helpers that need a `Client` immediately, and `get_db()` - which builds a **new** client every call - only for tests and one-shot tooling that will `close()` it. Calling `get_db()` per request/per job is how the backend ran Postgres out of connections; `serve.py`'s `db = shared_db()` is lazy specifically because `finder.py`/`alive.py`/`serve.py updater` import it just to reuse route handlers. Budget and history: "Connection budget" in `MONGO_MIGRATION.md`.
- `POSTGRES_POOL_MIN`/`POSTGRES_POOL_MAX` (1/2) bound each process's pool; the compose files pin `max_connections` explicitly because the `timescale/timescaledb` image's autotuner sets it to 50, not 100.
- `backend/db/base.py` defines the interface (`Client`/`Database`/`Collection`/`Cursor`, plus `InsertOne`/`ReplaceOne`/`UpdateOne`/`DeleteOne` bulk-op classes) - a deliberately narrow, pymongo-shaped surface covering only what this codebase actually uses (no aggregation pipelines, transactions, GridFS, or change streams anywhere in the app).
- `backend/db/mongo_adapter.py` is a thin passthrough onto real `pymongo` - full Mongo query language support, byte-identical behavior to the pre-migration code.
- `backend/db/postgres_adapter.py` translates that narrow operator set ($set/$or/$pull/$push/$in/$regex-as-prefix/$exists/$unset/upsert, plus $lt for TTL emulation) onto JSONB/typed-column Postgres tables, with schema bootstrap running eagerly at client construction (not lazily like Mongo, since Postgres tables must exist before first use - see `MONGO_MIGRATION.md`).
- Full design rationale, schema, and operational runbook: `MONGO_MIGRATION.md`. Adapter contract details: `backend/db/README.md`.

### Proxmox disk-space monitoring (`backend/proxmox_helper.py`, `backend/proxmox_disk_check.py`)

- Proxmox integration is cluster-based (see the `proxmox_clusters` collection/table): each cluster stores its own host/user/token credentials, and individual `hosts` reference a cluster via `proxmox_cluster` (by id or name). Legacy per-host/global API key settings still exist but are deprecated.
- `ProxmoxClient` wraps the Proxmox REST API to pull nodes, storage, VM/LXC status, and (via the QEMU guest agent, falling back to a `df -h` "escape valve" exec'd in-guest) real filesystem usage.
- Two layers of Redis caching exist, both namespaced separately:
  - Whole-cluster payload cache (`proxmox-disk:{cluster}`, `PROXMOX_CACHE_TTL_SECONDS`, default 90s) - read by `get_proxmox_disk_data_cached`, refreshed by `cron/proxmox_refresh.sh`.
  - Per-VM/LXC guest status fallback cache (`proxmox-guest-status:{cluster}:{node}:{vm|lxc}:{vmid}`, `PROXMOX_GUEST_STATUS_CACHE_TTL_SECONDS`, default 2 hours) - when a live `get_vm_status`/`get_container_status` call fails, the last known-good status is reused instead of treating the guest as having zero disk usage. This exists specifically to avoid false-positive "missing QEMU guest agent" alerts caused by a single transient API failure.
- `collect_disk_issues` in `proxmox_disk_check.py` turns cluster payloads into threshold-based issues (datastore/vm/container) and always surfaces VMs whose QEMU guest agent is inferred missing, regardless of threshold - a running VM with `maxdisk > 0` and `disk == 0` is a real "we can't measure this" case, not a clean bill of health.
- Email alerts render via Jinja2 (`backend/templates/disk_space_alert.html`, autoescaped) through `email_helper`.

### Telegraf ingest and per-client counters (`metrics-go/`, `backend/ingest_counters.py`)

- `metrics-go` reproduces the Flask ingest contract exactly, including the Redis key format. `metrics-go/pyjson.go` reimplements the subset of CPython's `json.dumps` that `serve.py` uses to build keys (`", "`/`": "` separators, insertion order, `ensure_ascii=True`), so both implementations write the *same* key for the same metric and can run side by side or be rolled back cleanly.
- While storing a batch it also counts it, in the same pipeline: `ingest:count:<client>` (hash of `requests`/`metrics`/`skipped`/`first_seen`/`last_seen`/`last_batch`/`mac`/`ip`/`host`, 30 day TTL) and `ingest:min:<client>:<minute>:r` / `:m` (per-minute buckets, 65 minute TTL so the last hour needs no pruning). `<client>` is the upper-cased `mac` tag, else the `ip` tag, else `remote:<address>`.
- The counter prefix must never be `METRIC-`: `bulk_insert` does `KEYS METRIC-*` and `GET`s every match, so a hash under that prefix would fail the bulk writer with `WRONGTYPE`.
- `backend/ingest_counters.py` is the read side (`GET`/`DELETE /metrics_counts/<host>` in `serve.py`, resolving a host by mac or ip), and the counters are displayed in the host settings modal (`CreateEditHost.vue`).

### AI summaries and MCP (`backend/ai/`)

- `cron/ai.sh` runs `backend/ai/main.py` hourly: `ai_pipeline.py`'s `process_dashboard()` pulls hosts/services and recent metrics from the database, slims them down, and `main()` sends the result to ChatGPT (`chatgpt_helper.py`) to produce a plain-English network summary, delivered via `email_helper.py`/`slack_helper.py`.
- The prompt, model, recipients, subject template, and from-name are configurable under Settings -> AI Alerts (`/ai/settings` routes, stored in the generic `settings` collection/table); `backend/ai/ai_settings.py` reads them with built-in defaults, so `initial_prompt.txt` (gitignored - see `initial_prompt.txt.example`) is now only a fallback. `/ai/test-email` sends either a simple deliverability check or a full dashboard -> ChatGPT -> email run on demand.
- `backend/ai/mcp/server.py` is a separate MCP (Model Context Protocol) server, run as its own Docker service (`mcp` in compose files) with its own `Dockerfile`/`requirements.txt`. It shares the backend's database/Redis (same `DB_BACKEND` selection, own `backend/ai/mcp/requirements.txt` needs the same driver pins kept in sync with `backend/requirements.txt`) and calls `serve.py` route handlers directly via `unwrap()`, so it exposes host/service/metric management tools (`mcp_list_hosts`, `mcp_create_or_update_host`, `mcp_add_service_to_host`, `mcp_list_services`, `mcp_read_metrics`, etc.) without Auth0. Because `unwrap()` removes the only authorization the handlers have, every HTTP request must instead carry the `MCP_KEY` pre-shared secret (`X-MCP-Key`, `Authorization: Bearer <key>`, or the bare `Authorization: <key>` form); the check lives in `backend/ai/mcp/auth.py` as ASGI middleware wrapping the whole app, and the server refuses to start if the key is unset. The transport is MCP streamable HTTP mounted at `/mcp`, served by `create_http_app()` (FastMCP itself is not ASGI-callable) and proxied externally by Caddy's `/mcp*` route. Full tool/schema docs in `backend/ai/mcp/README.md`.

## Development Workflows

**Start development environment:**
```bash
./start_dev.sh  # sets up Auth0, alertmanager, SSL certs, then starts docker-compose-development.yml
```
- Frontend dev server: port 8001 (hot reload) / port 8002 (live frontend) - see `devel` service in `docker-compose-development.yml`
- Backend API: port 7000
- NGINX/SSL: port 7210 (Caddy uses an internal dev CA - accept its cert in-browser)
- PostgreSQL/TimescaleDB (default backend): localhost:5432; MongoDB (fallback backend, still started in dev so `DB_BACKEND=mongo` stays testable): localhost:27017, Mongo Express: port 8071
- MCP server: port 8765 (internal to the `labyrinth` docker network)

**Backend tests:**
```bash
cd backend && ./run_tests.sh
# or, inside the backend container/venv directly:
PYTHONPATH=. pytest --cov=. --cov-config=.coveragerc --cov-report term-missing --cov-fail-under=95 test/
# single file / single test:
PYTHONPATH=. pytest test/test_13_proxmox_helper.py -q
PYTHONPATH=. pytest test/test_13_proxmox_helper.py::test_get_proxmox_disk_data_no_nodes -q
# run against the Mongo fallback instead of the Postgres default:
DB_BACKEND=mongo PYTHONPATH=. pytest test/
```
- Requires `GITHUB=1` or `TESTBED=1` env var so `serve.py`/`proxmox_disk_check.py` use plain `mongodb://` instead of `mongodb+srv://` when `DB_BACKEND=mongo` (SRV DNS lookup fails without a real Atlas host).
- 95% coverage is enforced (`--cov-fail-under=95`); `.coveragerc` excludes `templates/`, `uploads/`, `samples/`, `snippets/`.
- Fixtures are defined per test file, not centralized in `conftest.py`.
- Routes are wrapped in Auth0 decorators; tests call them via `common.test.unwrap(serve.some_route)()` to bypass auth and invoke the underlying function directly.
- The database is tested against real ephemeral containers (both `mongo` and `postgres` run in dev/CI), not mocks - matches the existing convention for Mongo, now extended to Postgres. Redis is a mix: some tests hit the real `redis` container, others mock via fixtures/monkeypatch (e.g. `Mock(spec=redis.Redis)`, hand-rolled `FakeRedis` classes).
- `backend/test/test_18_db_adapters.py` runs the same black-box scenarios against both `MongoClientAdapter` and `PostgresClientAdapter`; `test_19_compact_metrics.py`, `test_20_backup_db.py`, `test_21_migrate_to_postgres.py` cover the cron/migration tooling. Note the numeric test-file prefixes are not unique - `test_18_ec2_unmatched_check.py`, `test_19_ai_settings.py`, and `test_20_ai_pipeline.py` were added independently and collide by number only, not by name.

**Go ingest service tests (`metrics-go/`):**
```bash
cd metrics-go
# no Go toolchain in the stack's images - use the official one
docker run --rm -v "$PWD":/src -w /src golang:1.23-alpine \
  sh -c 'gofmt -l . && go vet ./... && go test ./... -cover'
```
- `pyjson_test.go` holds golden keys generated by CPython; a failure there means the Go and Flask ingest paths have drifted.
- Redis is faked with `miniredis`, so no services are needed.

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
- `services` collection/table stores check/port monitoring configs; two service types: `"check"` (command execution) and `"port"` (TCP/UDP checks).
- Judging logic lives in `backend/metrics.py` (`judge()`, `judge_check()`, `judge_port()`).

**Database access:**
- Always go through `db.get_db()` / the `Client`/`Database`/`Collection` interface in `backend/db/base.py` - never import `pymongo`/`psycopg2` directly outside `backend/db/`. Call sites look like pymongo (`db["labyrinth"]["hosts"].find_one({...})`) regardless of backend.
- Only the operators actually used anywhere in the app are supported by the Postgres translator: `$set`, `$or`, `$pull` (scalar = exact match, document = Mongo-style subset match on each array element), `$push`, `$in`, `$regex` (anchored prefix only), `$exists`, `$unset`, `upsert=True`, `$lt` (TTL emulation only). Don't reach for other Mongo query operators - they won't work on the Postgres backend. See `backend/db/README.md`.
- IDs are opaque strings shaped like `bson.ObjectId` hex (`str(bson.ObjectId())`), generated by the Postgres adapter without a real Mongo connection - `_validate_object_id()` and the frontend's `_id` handling work unchanged on both backends.

**Telegraf config management:**
- Master config at `/src/uploads/master.conf` (TOML), parsed by `backend/services.py` (handles duplicates, multiline arrays, preserves comments).
- Per-host configs are generated from the master template plus service definitions; the TOML structure is stored in Redis for UI editing.

**Ansible integration:**
- Playbooks under `/src/uploads/ansible/`, vault files under `/src/uploads/become/`.
- `backend/ansible_helper.py` validates YAML before saving.
- Background execution via `run_ansible_background()`; job status and streamed results (`{job_id}_log`) live in Redis.

**Network scanning:**
- `backend/finder.py` runs an nmap ping + service-detection scan (`-sT -PU0 -Pn`), stores results in Redis (`output-{subnet}`), and updates the `hosts` collection/table with discovered IPs/MACs. Triggered via `/scan/` or the cron job.

## Key Files
- `backend/serve.py` - all API endpoints
- `backend/db/` - database adapter ecosystem (`base.py` interface, `mongo_adapter.py`, `postgres_adapter.py`, `__init__.py`'s `get_db()` factory)
- `metrics-go/` - Go Telegraf ingest service (`server.go` handler, `parse.go` batch parsing, `pyjson.go` Python-compatible key rendering, `counters.go` ingest counters)
- `backend/ingest_counters.py` - read/reset side of the per-client ingest counters
- `backend/finder.py` - network discovery
- `backend/metrics.py` - service health judging
- `backend/services.py` - Telegraf config parsing
- `backend/ansible_helper.py` - Ansible validation/execution
- `backend/proxmox_helper.py` / `backend/proxmox_disk_check.py` - Proxmox cluster querying, caching, and disk-space alert emails
- `backend/aws_helper.py` / `backend/ec2_unmatched_check.py` - EC2 inventory, EC2<->host matching, and unmatched-instance alert emails (see `cron/ec2_check.sh`)
- `backend/watcher.py` - Alertmanager alert dispatch
- `backend/ai/main.py` / `backend/ai/ai_pipeline.py` / `backend/ai/ai_settings.py` - hourly AI dashboard summary job, its dashboard->ChatGPT->email pipeline, and the configurable prompt/model/recipient settings
- `backend/ai/mcp/server.py` - MCP server exposing host/service/metric tools
- `backend/migrate_to_postgres.py` - one-time Mongo-to-Postgres data migration tool (operator-run, not automatic)
- `backend/compact_metrics.py` / `backend/backup_db.py` - Postgres-only metrics compaction and database backup (see `cron/compact_metrics.sh`, `cron/backup_db.sh`)
- `cron/run.sh`, `cron/cron.d/crontab` - scheduled job definitions
- `start_dev.sh` - development environment bootstrap
- `MONGO_MIGRATION.md` - full design rationale, schema, and operational runbook for the Postgres migration

<!-- BEGIN ARMADA GLOBAL INSTRUCTIONS (managed by Flagship) -->
## Armada session policy

You are running inside an Armada session. These rules come from the Flagship
and apply to every session in the fleet. They sit on top of this project's own
instructions, and they win wherever the two disagree.

- Armada session: `MCP Server`
- Working branch: `armada/MCP-Server-200b93`
- Base branch: `master`
- Session changelog: `CHANGELOG/armada-MCP-Server-200b93.md`

### Commit and push your work

- Commit as soon as a change is coherent on its own. Never end a turn with a
  dirty working tree, and never wait to be asked to commit.
- Push to `origin` right after committing, so the branch on the remote always
  matches what you have locally.
- This holds even when the working branch is the base branch. Armada sessions
  are disposable and their history is the only durable record of the work, so
  committing directly to `master` is expected here, not a mistake.
- If a push is rejected because the remote moved ahead, pull with rebase and
  push again. Report the failure only if that still does not resolve it.

### Keep the branch mergeable

- Whenever the working branch is not the base branch, verify the work still
  merges cleanly into `master` before you consider a task finished.
- Check without mutating the working tree, for example:
  `git fetch origin && git merge-tree $(git merge-base HEAD origin/master) HEAD origin/master`
- If that reports conflicts, resolve them now rather than leaving them for
  whoever opens the pull request. Rebase or merge the base branch in, fix each
  conflict on its merits, re-run the tests, then commit and push.
- If a conflict genuinely needs a human decision, stop and say exactly which
  files conflict and what the competing changes are.

### Keep the changelog current

- Record what you did in `CHANGELOG/armada-MCP-Server-200b93.md` as part of the same commit that
  makes the change.
- The file is scoped to this branch, so it never conflicts with changelogs
  written by other sessions.
- Append one entry per meaningful change, newest last, in this shape:

  ```markdown
  ## 2025-01-31 14:22 UTC
  Short description of what changed and why.
  ```

- Use Central Time (US/Chicago), and include both the date and the time. Get them from `date -u`
  rather than guessing.
- Describe the change in terms a reviewer would care about. Skip routine
  mechanics like formatting passes or lint fixes unless they are the point of
  the work.
- This per-branch file is yours to maintain. A top-level auto-generated
  `CHANGELOG.md`, if the project has one, is still off limits.
<!-- END ARMADA GLOBAL INSTRUCTIONS -->
