# Changelog: Scaling issue

- Armada session: `Scaling issue`
- Branch: `armada/Scaling-issue-57e998`
- Base branch: `master`
- Started: 2026-08-21 19:06 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-08-24 15:41 UTC
Evaluated the `no-mistakes` static-analysis CLI (v0.47.0) as a session tool. No
application code changed; this entry records the findings so they are not
rediscovered later.

- Installed globally in the session container along with its Claude Code skill,
  but deliberately **not** added to `frontend/labyrinth/package.json`. The
  package ships glibc-2.35+ Linux binaries only, so its postinstall exits 1 on
  musl/Alpine and would break `npm install` for anyone building on one. Running
  it here needed `--ignore-scripts`, a checksum-verified manual binary fetch
  from the GitHub release, and the `gcompat` shim.
- Its TS/JS module graph cannot parse `.vue` SFCs (it parses them as TypeScript
  and errors), so it reports nothing useful for the Vue 2 frontend.
- Its Python graph does work on `backend/` given a three-line
  `backend/.no-mistakes.yml` containing `tests.python.packages: ["."]`. With
  that, `no-mistakes tests plan python --changed-file proxmox_helper.py` selects
  23 of 32 test files at high confidence with no fallback, tracing real import
  paths (`proxmox_helper.py -> serve.py -> test/test_03_serve.py`). Potentially
  useful for trimming runs against the 95% coverage gate. The config file was
  tested and then removed; it is not part of this branch.
