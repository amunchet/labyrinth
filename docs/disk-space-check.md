# Disk Space Check

This feature monitors disk usage across Proxmox hosts and manually configured systems.

## Overview

- Proxmox hosts are discovered by tag.
- Each Proxmox host can use a global API key or a host-specific override.
- Manual hosts can be added for systems that do not expose Proxmox APIs directly.
- The UI keeps most processing in the backend so future scheduled emails can reuse the same data shape.

## Proxmox setup

### 1. Create an API token

1. Log in to the Proxmox web UI.
2. Select the user that will own the token, commonly `root@pam` or a dedicated service account.
3. Open **Permissions** and create or select the user.
4. Go to **API Tokens**.
5. Create a new token.
6. Copy the token ID and secret immediately. The secret is shown only once.

### 2. Grant permissions

The token needs permission to read nodes, VMs, LXCs, and storage.

Typical roles include:

- `PVEAuditor` for read-only inventory access.
- A custom role with read permissions on `/nodes`, `/storage`, `/vms`, and `/access` if you want to be explicit.

If you use a restrictive role, confirm the token can access:

- Node status
- VM status
- Container status
- Storage lists

### 3. API key format used by Labyrinth

Store keys in this format:

`user@pam!token_id=token_secret`

Example:

`root@pam!diskcheck=3d9e...`

### 4. Tag Proxmox hosts

Tag every Proxmox node with the configured tag name. The default tag is:

`Proxmox`

You can change it in the Disk Space settings tab if you want a different label.

## QEMU on VM hosts

If you want disk monitoring data from virtual machines that run on Proxmox or on other VM hosts, install the QEMU guest agent inside the guest OS.

### Linux guests

Debian or Ubuntu:

```bash
sudo apt update
sudo apt install qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent
```

RHEL, Rocky, Alma, Fedora:

```bash
sudo dnf install qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent
```

### Windows guests

1. Install the Proxmox QEMU guest tools inside the VM.
2. Reboot the guest.
3. Confirm the guest agent is enabled in the Proxmox VM options.

### Why it matters

The guest agent improves:

- Disk usage reporting
- Memory reporting
- Shutdown/reboot control
- Accurate VM metadata

## Manual host monitoring

Use manual hosts for systems that are not Proxmox nodes but still need disk tracking, such as:

- AWS EC2
- OPNsense
- Generic Linux servers
- FreeBSD hosts

For manual hosts, the current backend stores the host metadata and provides a place to extend with agent-based or automation-based collectors later.

## API endpoints

- `GET /disk-space/proxmox` — Proxmox disk inventory by host
- `GET /disk-space/manual` — manually configured hosts
- `POST /disk-space/manual` — add a manual host
- `DELETE /disk-space/manual/<id>` — remove a manual host
- `GET /disk-space/settings` — current Proxmox tag and API key status
- `POST /disk-space/settings/proxmox-api-key` — save global Proxmox API key
- `POST /disk-space/settings/proxmox-api-key/<mac>` — save host-specific API key

## Automation notes

The backend returns structured data so scheduled jobs can reuse the same output for:

- Threshold checks
- Hourly summaries
- Daily email reports
- Alert routing

That keeps the frontend thin and makes later automation easier.
