# Changelog: Testing callback

- Armada session: `Testing callback`
- Branch: `armada/Testing-callback-8c5a39`
- Base branch: `master`
- Started: 2026-11-13 08:13 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-13 13:44 CST
Added `backend/samples/ansible/armada_callback_test.yml`, a read-only sample playbook for testing the agent conversation -> Labyrinth deploy -> Armada callback loop end to end (prints a marker line, optional deliberate failure via `callback_test_fail`). Documented in the samples README.
