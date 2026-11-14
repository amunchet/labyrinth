# Changelog: Adding manual ansible vault doesn't work

- Armada session: `Adding manual ansible vault doesn't work`
- Branch: `armada/Adding-manual-ansible-vault-doesn-t-work-2a812c`
- Base branch: `master`
- Started: 2026-11-14 08:40 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-14 02:56 CST
Fixed adding an Ansible vault by hand on the Deploy page (Add Vault File > Manual Entry). The dialog's OK button uploaded `generated_vault_file`, which stayed empty unless the user had first pressed a separate "Generate Ansible File" button, so filling in the form and pressing OK sent an empty file and the backend answered 500 (it `chmod`ed a file it never wrote). Save now checks the entry (vault password, filename, username, password), encrypts it in the browser and uploads it in one step, then selects the new file as the Become Password file. Values are written as quoted YAML strings, so passwords containing `#`, `: ` or quotes no longer break the vault's YAML, and the vault is encrypted from UTF-8 bytes because `ansible-vault` (npm) padded by string length, which made `ansible-vault` reject any secret with a non-ASCII character ("Invalid padding bytes").

`POST /upload/become/<token>` (form-data path) now answers 407/409 for an empty vault or blank filename instead of a 500, validates the vault under a scratch name so a failed check no longer deletes the existing file of the same name, and saves the file with mode 600 like uploaded files.
