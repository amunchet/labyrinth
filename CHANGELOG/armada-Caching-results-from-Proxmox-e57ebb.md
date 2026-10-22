# Changelog: Caching results from Proxmox

- Armada session: `Caching results from Proxmox`
- Branch: `armada/Caching-results-from-Proxmox-e57ebb`
- Base branch: `master`
- Started: 2026-10-22 02:35 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-21 22:13 CDT
Proxmox disk-space data now survives timeouts. The cron refresh (every 30s) no longer overwrites the Redis cache with an error when a cluster is unreachable, or with blank data when a single node's API calls fail. It keeps the previous results flagged `stale`, along with the failure reason and the time of the last good poll. The cache TTL went from 90s to 7 days (`PROXMOX_CACHE_TTL_SECONDS`), so the web page always reads from Redis instead of falling back to a slow live query. The disk-space page shows an "Unreachable - showing results from X ago" badge on stale clusters and nodes. The hourly disk check still checks stale data for issues and logs the failed poll.
