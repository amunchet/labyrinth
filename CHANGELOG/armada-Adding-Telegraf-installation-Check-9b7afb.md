# Changelog: Adding Telegraf installation Check

- Armada session: `Adding Telegraf installation Check`
- Branch: `armada/Adding-Telegraf-installation-Check-9b7afb`
- Base branch: `master`
- Started: 2026-10-07 17:36 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-07 13:58 CDT
Added a "Telegraf Check" tab under Proxmox (between Disk Space Check and Settings). New `GET /disk-space/proxmox/telegraf-check` walks every VM/LXC on every node of every configured cluster (from the existing Redis-cached Proxmox payload), matches each guest by hostname to a Labyrinth host (same matching rules as the AWS EC2 view, now shared via `_build_host_match`), and classifies it as `ok`, `unmatched` (no Labyrinth host), `not_monitored`, `no_telegraf` (no `metrics-latest` entry for the host's IP/hostname in the last `stale_minutes`, default 15), or `stopped`. The UI shows summary counts, defaults to issues only, and can filter by status.

## 2026-10-07 16:11 CDT
Added a "Graylog Check" tab under Proxmox, next to Telegraf Check. Verification happens on each guest via a new Telegraf exec check, `backend/samples/telegraf/check_graylog.sh` (POSIX sh; installed by the new `samples/ansible/install_check_graylog.yml`), which reports whether rsyslog is installed, running, forwarding to a target (auto-detected from legacy `@@host:port` or RainerScript `omfwd` config, or pinned via argument/`$GRAYLOG_TARGET`), whether a TCP target accepts connections, and whether rsyslog last logged the forward as suspended. New `GET /disk-space/proxmox/graylog-check` reads the newest result per matched Labyrinth host. It is intentionally looser than the Telegraf check: the metric name (default `check_graylog`) and freshness window (default 24h) are configurable via the `proxmox_graylog_check` setting, missing/stale results are warnings, and guests can be deferred for a period or permanently with a reason (`proxmox_graylog_deferrals` setting; expired deferrals stop applying). The guest enumeration/matching and latest-metric lookup are now shared between both checks.
