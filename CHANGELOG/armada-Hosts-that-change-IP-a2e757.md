# Changelog: Hosts that change IP

- Armada session: `Hosts that change IP`
- Branch: `armada/Hosts-that-change-IP-a2e757`
- Base branch: `master`
- Started: 2026-10-22 02:34 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-21 21:36 CT
Fast-forwarded the session branch to current `master` (it was 55 commits behind, including the Postgres migration and inventory work) before starting the hostname-as-identity design. Replaced the Armada policy text that another session had committed into `CLAUDE.md` with the Flagship-managed pointer to `CLAUDE.local.md`. No application code changed.

## 2026-10-21 23:04 CT
Hostnames are now the first thing a host is identified by, so DHCP devices (clients, APs, some routers) can be monitored without reserved IPs.
- `finder.py` `reconcile_hosts`: scanned hosts match on hostname first (within the /24, and only when the name answers at one IP in that scan), then real MAC, then IP. A host that moved keeps its record and key, and only its `ip` changes, so Telegraf metrics tagged with the key keep matching. Unnamed records pick up their DNS name. A new device on a moved host's old IP gets a generated `device-` key instead of overwriting the moved host.
- Duplicates are merged on scan. Same-name records in a /24 merge into the best configured one, and unreviewed scanner copies (unmonitored, unnamed or still flagged `new_host`) at the same IP fold into the configured host there. A configured host is never deleted just for sharing an IP, and `new_host` is never carried onto the survivor. A dry run on the production snapshot merges 875 records down to 860, covering the 9 hand-moved monitored hosts and their scanner copies plus the `DESKTOP-D27UII6`/`KasongosiPhone8`/`client-virtual-machine` DHCP duplicates.
- `alive.py`: hosts are checked at the address their hostname resolves to, falling back to the stored IP when DNS fails or answers outside the host's /24 (search-domain and Docker service-name collisions). Alerts are labeled with the hostname.
- MCP `mcp_get_host` also accepts an unambiguous hostname.

## 2026-10-22 01:11 CT
Faster backend tests. `test_08_telegraf.py` parsed the 8,600-line sample Telegraf config six times with the comment-preserving TOML decoder, at about 6s per parse. It now parses each distinct text once and reuses deep copies, taking the file from 42s to 8s. `put_structure` now writes its ~2,500 comment keys to Redis in a single `MSET` instead of one round trip each, which also speeds up the real endpoint. The full suite takes about 1.5 minutes with the dev compose environment.

## 2026-10-22 17:10 CT
Restored the `MONGO_MIGRATION.md` entry under Key Files in CLAUDE.md, which was dropped by accident while resolving the Armada-block conflict. Self-review of the branch is published at https://claude.ai/artifact/QTuUqzEiBKWrdDDnRTPsfF.

## 2026-10-22 17:37 CT
Follow-ups from the branch self-review:
- **Merges keep references intact.** When the finder merges duplicate records, any other host whose `uplink` pointed at a merged-away record now points at the record that was kept. Map placements move the same way; where a map already places the kept record, the duplicate's spot is dropped. A kept record left uplinking to a copy of itself loses that uplink.
- **Metrics stay with the moved host.** Telegraf configs bake in the IP the host had when the config was generated (`global_tags` in `Services.vue`), so a moved host's agent keeps reporting its old IP. The dashboard's `find_metric` used to match on mac *or* IP, which credited those metrics to whatever new device took the old IP. It now never matches by IP when the metric's `mac` tag is a different host's key.
- **Bounded DNS in alive.** Hostnames are resolved once per run in `resolve_names`:
  - Names are deduplicated before lookup.
  - Answers, including "not found", are cached in Redis for 5 minutes.
  - At most 4 lookups run at once (daemon threads).
  - The whole batch gets 10 seconds. A name still pending after that is checked at its stored IP and retried on the next run.
  - Tunable through `ALIVE_DNS_CACHE_SECONDS`, `ALIVE_DNS_WORKERS` and `ALIVE_DNS_TIMEOUT_SECONDS`.
  - Previously, up to 32 uncached and unbounded `gethostbyname` calls ran every minute.
