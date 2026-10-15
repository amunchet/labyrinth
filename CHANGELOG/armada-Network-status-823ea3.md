# Changelog: Network status

- Armada session: `Network status`
- Branch: `armada/Network-status-823ea3`
- Base branch: `master`
- Started: 2026-10-15 01:25 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-14 21:21 CDT
MCP `mcp_read_metrics` now reads `metrics-latest` by default (new `latest` flag; `latest=False` keeps the raw-history read). Querying the unindexed `metrics` table for a host/service with no recent rows scanned the whole table and hung the MCP server, and history rows are never judged stale, so 5-hour-old readings came back as "passing" during a network status sweep.
