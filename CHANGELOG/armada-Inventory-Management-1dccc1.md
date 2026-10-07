# Changelog: Inventory Management

- Armada session: `Inventory Management`
- Branch: `armada/Inventory-Management-1dccc1`
- Base branch: `master`
- Started: 2026-10-07 17:56 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-07 14:12 CDT (19:12 UTC)
Fixed custom dashboards being unusable. Listing dashboards returned a 404 when
none existed yet, so the UI errored on first use; it now returns an empty list
(a named dashboard that does not exist still 404s). Image uploads (dashboard
map graphics and icons) silently failed because `apiPost` set a
`multipart/form-data` header by hand, which drops the multipart boundary since
the switch from axios to fetch; the browser now sets the header itself.
