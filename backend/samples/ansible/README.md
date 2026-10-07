# Sample Ansible Playbooks

These are example Ansible playbooks for use with Labyrinth's **Deploy to Tag** feature.

## proxmox_list_vms.yml

Lists all VMs (QEMU) and LXC containers on a set of Proxmox hosts, given a Labyrinth tag.

**Steps:**
1. Tag your Proxmox hosts in Labyrinth with a tag (e.g. `proxmox`).
2. In the Deploy page, select **Deploy to Tag** and choose `proxmox`.
3. Upload/select this playbook and run.

**Requirements:**
- SSH access to each Proxmox host.
- `pvesh` CLI available (default on Proxmox).

---

## proxmox_check_monitoring.yml

For all running VMs and LXCs on Proxmox hosts, checks whether rsyslog and Telegraf are properly configured.

**Steps:**
1. Tag your Proxmox hosts in Labyrinth with `proxmox`.
2. In the Deploy page, select **Deploy to Tag** → `proxmox`.
3. Upload/select this playbook and run.

**Requirements:**
- SSH access to Proxmox hosts and to guest VMs/LXCs.
- Guest VMs/LXCs must be reachable via SSH from the Ansible controller.
- `pvesh`, `qm`, and `pct` CLIs on Proxmox hosts.

**What it checks per guest:**
- Is `rsyslog` service active?
- Does `/etc/rsyslog.conf` exist?
- Is the `telegraf` process running?
- Does `/etc/telegraf/telegraf.conf` exist and contain configuration sections?

---

## install_check_graylog.yml

Installs `samples/telegraf/check_graylog.sh`, the Telegraf exec check behind the Proxmox **Graylog Check** tab.

**Steps:**
1. Run this playbook against the guests (Deploy to Tag, or a host group).
2. Add the `[[inputs.exec]]` block from the top of the playbook to each host's Telegraf config in Labyrinth.

**What the check reports (`check_graylog` metric):**
- `ok` - 1 when everything below passes
- `installed` / `active` - rsyslog installed and running
- `forwarding` - rsyslog forwards to a target (the one given as an argument / `$GRAYLOG_TARGET`, else any)
- `target_reachable` - TCP connect succeeds (UDP targets only need to resolve)
- `suspended` - rsyslog's last forwarding action log line is "suspended"
- `status` - human-readable first failure, or `ok`
