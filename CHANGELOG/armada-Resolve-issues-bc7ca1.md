# Changelog: Resolve issues

- Armada session: `Resolve issues`
- Branch: `armada/Resolve-issues-bc7ca1`
- Base branch: `master`
- Started: 2026-11-24 19:57 UTC

Entries are appended newest last, each stamped with the Central Time (US/Chicago) date and time.

## 2026-11-24 14:15 CST
Finder ping sweep now also probes TCP 22/80/443 (`-PE -PS22,80,443 -PA80 -T4`, overridable with `FINDER_PING_ARGUMENTS`) instead of ICMP echo at `-T5`. Only hosts the sweep finds get port scanned, and the old sweep missed most of the routed South subnet on any given pass and every EC2 instance. Over the last 10 hours about 25 monitored hosts that alive.py pings fine (jupiter, medusa, equator, graylog.south, data.south, cloudflare-tunnel, the UniFi APs, the EC2 servers) never got an `open_ports` metric, so their open_ports/closed_ports checks always failed. Tests cover the built command.

Live Labyrinth configuration fixed through the MCP in the same pass (not in git):
- `caddy-dhcp` now watches `dhcp-dhcp-1` (Compose v2 renamed it from `dhcp_dhcp_1`).
- security.north: `kremlin-docker-frontend` -> `kremlin-kremlin-web-1`. `kremlin-docker-lego` replaced by the new `kremlin-docker-caddy-auth0` (`caddy-auth0-caddy-1`, since lego is gone). `http-success` replaced by the new `http-auth-required` (401 from the Auth0 gate means the site is up). `cpu` -> `cpu-8` (8 CPUs, still a warning).
- labyrinth: `docker-nginx`/`docker-lego` replaced by the new `labyrinth-frontend`, `labyrinth-metrics` and `labyrinth-postgres` (Caddy replaced nginx and lego).
- graylog.north: removed `graylog-metricbeat` (the container no longer exists).
- judi: removed `judi-internal` (it probed the retired 192.168.0.176 server).
- pve1: IP moved to 192.168.0.175, matching the 2026-11-17 `pve1-change-ip` run.

## 2026-11-24 14:18 CST
Staged six Ansible deployments in Labyrinth conversation d60bc857 for the problems a config change can't fix. Nothing runs until a human enters the vault password:
- `opnsense-telegraf` (192.168.0.3): installs the bare telegraf package on the South OPNsense router, runs Labyrinth's saved config from /usr/local/etc/labyrinth-telegraf.conf as an rc.conf.d service. The router's cpu/mem/disk checks have never had data.
- `opnsense-syslog-graylog` (192.168.0.3): adds a TLS syslog destination for Graylog South through OPNsense's own Syslog model.
- `telegraf-merge-aggregator` (graylog.south): its config lacks `[[aggregators.merge]]`, so the `system` metric arrives split, load5 goes missing and cpu-4 fails. Labyrinth's saved copy of the config now has the block.
- `venus-mars-cron-rename`: the cron container was stuck as `84af8c7da395_mars-cron-1` after a half-finished compose recreate.
- `aptupdate` / `aptupdate-judi` for the nine hosts whose apt checks show pending updates.

## 2026-11-24 17:03 CST
First two staged runs succeeded:
- `opnsense-telegraf`: the South router now sends cpu/mem/disk/system once a minute, and its cpu, mem and disk checks pass for the first time.
- `telegraf-merge-aggregator`: graylog.south's `system` metric now arrives whole (load5 included) and `cpu-4` passes.

The generic `cpu` check fails above a load5 of 1.5 whatever the core count, which is also what put caddy.north in the alert email. Moved three hosts to the per-core checks the fleet already uses (live Labyrinth configuration, not in git): labyrinth (16 cores) to the new `cpu-16`, data.north and caddy.north (4 cores) to `cpu-4`.

## 2026-11-24 17:12 CST
More of the staged runs came back:
- `venus-mars-cron-rename` succeeded; venus `mars-docker-cron-new` passes.
- `opnsense-syslog-graylog` stopped at OPNsense's validation ("A certificate is required for tls types") before saving anything. Restaged: it now uses the router's web GUI certificate as the client certificate, which Graylog South accepts because its input has client authentication off. It always removes its temporary helper, and it prints the generated syslog-ng block and syslog-ng's messages so a TLS handshake failure shows in the run.
- `aptupdate` failed on every host: alexandria.north (Python 3.8) and appdistribution (Python older than 3.7) are too old for ansible-core 2.21's modules, the EC2 website's SSH timed out, and on the other five the apt module only reported "Failed to update apt cache" (python-apt's message when one repository fails to refresh). Staged the new `apt-upgrade-raw` for the seven reachable hosts. It does the same dist-upgrade and telegraf-unit shutdown using only raw commands, names the repositories that fail to refresh, and reports what is still pending and whether a reboot is required.

## 2026-11-24 21:52 CST
Results of the third round, and what they turned up:
- `apt-upgrade-raw` upgraded venus, zeus, appdistribution, website-staging and data.north. Their `apt` checks pass again, except zeus's (see below). alexandria.north upgraded too but timed out on the sudo prompt at the last step, and balexandria at the first. The one repository that failed on every host is InfluxData's: it now signs with a new key (`NO_PUBKEY DA61C26A0585BD3B`), and the 2023 `influxdata-archive_compat` key these hosts trust expired on 2026-01-17. `aptupdate-judi` failed the same way.
- The upgrade moved zeus to telegraf 1.37.0 from its stale index, and zeus has sent no metrics since. Telegraf 1.37 refuses any config with options it no longer knows, and zeus's `inputs.docker` still sets the long-deprecated `perdevice`/`total`. Reproduced with the telegraf 1.37.0 and 1.40 images. Labyrinth's saved copy of zeus's config now uses `perdevice_include` instead.
- Restaged `apt-upgrade-raw` for those hosts plus data.south, and separately for judi. Tested in Ubuntu 18.04, 22.04 and 24.04 containers:
  - It first installs InfluxData's current key, but only if the download has the fingerprint from InfluxData's install docs and includes the new signing key. It then rewrites the repository entry, and moves the expired and revoked keys aside after backing them up.
  - It checks telegraf's config with the version about to be installed. If that version rejects it, telegraf's own `config migrate` is used when the result passes. Otherwise telegraf is held at its current version and the host fails with the reason.
  - The sudo timeout is now 30 seconds.
- venus's container uptime checks fail for an hour because the docker-ce 29.10.1 upgrade restarted its containers. All of them came back.
- `opnsense-syslog-graylog` added the destination, but syslog-ng drops the connection because Graylog South's input certificate is self-signed (`CN=0.0.0.0:null`). OPNsense's GUI destinations always verify the server, so restaged as a syslog-ng drop-in in `/usr/local/etc/syslog-ng.conf.d/`. It makes the same unverified TLS connection the fleet's rsyslog makes, and switches the GUI destination off.
- Router moved from `cpu` to `cpu-4` (4 cores): a brief load5 above 1.5 had failed the generic check.

## 2026-11-25 02:25 CST
Fourth round:
- Router: the syslog-ng drop-in works. syslog-ng connects to Graylog South without verifying its self-signed certificate, and the router's logs (including the test message) arrive there now. The GUI destination is switched off.
- Router logs show the WAN_DHCP gateway (192.168.76.10, monitoring 1.1.1.1) failing every second with `sendto error: 65` (no route to host), so the default route is on OPT1. OPT1's monitor (8.8.8.8, RTT about 50 ms) keeps flipping between "delay" and "none", and each flip makes OPNsense reconfigure routing. Reported to the user, not changed.
- `apt-upgrade-raw` installed InfluxData's new key on all eight hosts and judi. Every one of them has nothing pending now, so their `apt` checks pass. Telegraf went to 1.40.4 on four hosts. It was held on zeus (1.37.0), 10.237 and 10.242 (1.25.0), balexandria (1.32.2) and judi (1.34.2), because 1.40.4 rejects `inputs.docker`'s `container_names`/`perdevice`/`total` and telegraf's `config migrate` failed. Migrate cannot read Labyrinth's single-table `[outputs.http]` ("is not a list of tables"). zeus is still without metrics, because its installed 1.37.0 already rejects the config.
- Restaged `apt-upgrade-raw` for those five hosts. The guard now migrates a copy written with `[[outputs.http]]`, and when migration still fails it prints why. Tested with judi's own config (key replaced) on a held host, and with a config migration cannot fix.
- Labyrinth's saved configs for judi, 10.237, 10.242 and balexandria no longer set the three removed options. Their new-style equivalents were already there and set the same way, so what they collect is unchanged.
- Those options came from the default Telegraf sample: `services.prepare()` uncomments every option in `master.conf`, which starts as a copy of `backend/uploads/defaults/telegraf.conf`. Removed `container_names`, `perdevice` and `total` from its docker section, so new installs stop offering them. An existing `/src/uploads/master.conf` keeps them until it is edited the same way.

## 2026-11-25 02:39 CST
The `apt-upgrade-raw` reruns succeeded on all five held hosts (zeus, 10.237, 10.242, balexandria, judi). On each, the guard lifted its own hold, migrated `/etc/telegraf/telegraf.conf` (backed up in `/root/labyrinth-apt-backup/`), and telegraf went to 1.40.4 with nothing left pending. The upgrade had re-enabled the telegraf unit, and the run turned it off again. zeus has been sending again since 08:36 UTC (185 metrics a minute) after about 90 minutes without metrics. The other four kept the same per-minute batch sizes as before. zeus and judi still need a reboot, as do 0.202 and 10.121 from the earlier run.

## 2026-11-25 22:34 CST
- Staged `labyrinth-master-conf-docker` for the Labyrinth server (192.168.10.244). Inside the backend container it removes `container_names`, `perdevice` and `total` from the live `/src/uploads/master.conf`, making the docker section match `backend/uploads/defaults/telegraf.conf`. If the section was edited by hand, it removes only those three option lines. The edited copy must parse to the same input plugins minus those keys before it replaces the file, and the original is kept as `master.conf.bak-<time>`. It then rebuilds the copy the Services page reads (Redis `master.data`) with the page's own `put_structure`. Tested end to end against a stand-in backend container with Redis, in the re-serialised form Labyrinth saves. Labyrinth's playbook check rejects YAML's `!unsafe` tag, so the scripts sit in `{% raw %}` blocks.
- Reboots are still needed on zeus, judi, website-staging (0.202) and datanorth (10.121). Their uptime metrics show none has booted since the 2026-11-25 upgrades (last boots 11-04, 11-12, 11-23 and 07-31), and `/var/run/reboot-required` is only cleared by a reboot.
