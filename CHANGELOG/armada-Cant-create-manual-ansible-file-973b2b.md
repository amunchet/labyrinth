# Changelog: Cant create manual ansible file

- Armada session: `Cant create manual ansible file`
- Branch: `armada/Cant-create-manual-ansible-file-973b2b`
- Base branch: `master`
- Started: 2026-11-17 07:25 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-17 01:38 CST
Fix "TypeError: \"list\" argument must be an Array of Buffers" when saving a manual Ansible vault on the Deploy page. The lockfile had resolved `ansible-vault` (`^1.0.3`) to 1.3.0, which splits its derived key with `subarray()`; under webpack 4's buffer@4 browser polyfill that returns a plain Uint8Array, and the HMAC's `Buffer.concat` rejects it. Unit tests run on Node's native Buffer, so they never saw it. Pinned `ansible-vault` to 1.1.1, the newest release that uses `slice()`. Checked by bundling it with the project's webpack and decrypting the output, non-ASCII included, with the real `ansible-vault` CLI. Added a test that fails if the version drifts.
