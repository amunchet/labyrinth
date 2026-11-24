# Changelog: Resolve issues

- Armada session: `Resolve issues`
- Branch: `armada/Resolve-issues-bc7ca1`
- Base branch: `master`
- Started: 2026-11-24 19:57 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-24 14:15 CST
Finder ping sweep now also probes TCP 22/80/443 (`-PE -PS22,80,443 -PA80 -T4`, overridable with `FINDER_PING_ARGUMENTS`) instead of ICMP echo at `-T5`. Only hosts the sweep finds get port scanned, and the old sweep missed most of the routed South subnet on any given pass and every EC2 instance. Over the last 10 hours about 25 monitored hosts that alive.py pings fine (jupiter, medusa, equator, graylog.south, data.south, cloudflare-tunnel, the UniFi APs, the EC2 servers) never got an `open_ports` metric, so their open_ports/closed_ports checks always failed. Tests cover the built command.

Live Labyrinth configuration fixed through the MCP in the same pass (not in git):
- `caddy-dhcp` now watches `dhcp-dhcp-1` (Compose v2 renamed it from `dhcp_dhcp_1`).
- security.north: `kremlin-docker-frontend` -> `kremlin-kremlin-web-1`. `kremlin-docker-lego` replaced by the new `kremlin-docker-caddy-auth0` (`caddy-auth0-caddy-1`, since lego is gone). `http-success` replaced by the new `http-auth-required` (401 from the Auth0 gate means the site is up). `cpu` -> `cpu-8` (8 CPUs, still a warning).
- labyrinth: `docker-nginx`/`docker-lego` replaced by the new `labyrinth-frontend`, `labyrinth-metrics` and `labyrinth-postgres` (Caddy replaced nginx and lego).
- graylog.north: removed `graylog-metricbeat` (the container no longer exists).
- judi: removed `judi-internal` (it probed the retired 192.168.0.176 server).
- pve1: IP moved to 192.168.0.175, matching the 2026-11-17 `pve1-change-ip` run.
