# Proxmox API Refactor - Cluster-Based Architecture

## Overview
Refactored the Proxmox integration from per-host API keys to a centralized cluster-based architecture. This allows managing Proxmox cluster credentials independently from individual hosts while still supporting manual hosts and monitoring.

## Architecture Changes

### Before
- Proxmox API keys stored at three levels: host field (`proxmox_api_key`), legacy per-mac settings, or global settings
- API credentials tightly coupled to host definitions
- Limited flexibility for managing multiple clusters

### After
- New `proxmox_clusters` MongoDB collection stores cluster definitions with credentials
- Hosts reference clusters via `proxmox_cluster` field (cluster ID or name)
- Clean separation of infrastructure (clusters) from host definitions
- Backward compatible with manual hosts

## Database Schema

### New Collection: `proxmox_clusters`
```javascript
{
  "_id": ObjectId,
  "name": String,              // Unique cluster identifier
  "host": String,              // Cluster node IP/hostname
  "user": String,              // Proxmox user (e.g., root@pam)
  "token_id": String,          // API token ID
  "token_secret": String,      // API token secret
  "verify_ssl": Boolean,       // SSL certificate verification
  "created": ISOString,
  "updated": ISOString
}
```

Index created on `name` field for efficient lookups.

### Modified Collection: `hosts`
- **Removed**: `proxmox_api_key` field
- **Added**: `proxmox_cluster` field (references cluster by ID or name)
- **Deprecated endpoints**: Legacy per-host and global API key settings still exist but marked as deprecated

## Backend Changes

### New Endpoints

#### Cluster Management
- `GET /proxmox-clusters` - List all clusters (requires READ auth)
- `POST /proxmox-clusters` - Create new cluster (requires ADMIN auth)
- `GET /proxmox-clusters/<cluster_id>` - Get cluster details (requires READ auth, strips token_secret)
- `PUT /proxmox-clusters/<cluster_id>` - Update cluster (requires ADMIN auth)
- `DELETE /proxmox-clusters/<cluster_id>` - Delete cluster (requires ADMIN auth)

#### Updated Endpoints
- `GET /disk-space/settings` - Now returns cluster list and unconfigured hosts instead of API keys
- `GET /disk-space` - Now resolves hosts to clusters for Proxmox data collection
  - Maps hosts tagged with `proxmox_tag` to cluster configurations
  - Returns error if cluster not found or not configured
  - Includes `cluster_name` in response data

### Modified Functions

#### `proxmox_helper.get_proxmox_disk_data()`
**Before**: Accepted API key string in format `user@pam!token_id=token_secret`
**After**: Accepts cluster configuration dictionary
```python
cluster_config = {
    "user": "root@pam",
    "token_id": "token-123",
    "token_secret": "secret-123",
    "verify_ssl": False
}
result = proxmox_helper.get_proxmox_disk_data(host_ip, cluster_config)
```

#### `get_proxmox_disk_space()` Route
- Loads all clusters into lookup dictionary (by ID and name)
- For each Proxmox-tagged host:
  1. Reads `proxmox_cluster` field
  2. Looks up cluster in dictionary
  3. Passes cluster config to helper
  4. Returns detailed error if cluster not found

#### `get_disk_space_settings()` Route
Now returns:
- `proxmox_tag` - Tag used to identify Proxmox hosts
- `clusters` - Array of configured clusters (token_secret stripped)
- `unconfigured_proxmox_hosts` - Hosts with Proxmox tag but no cluster assigned

### Deprecated (Backward Compatible)
The following endpoints still work but are marked as deprecated. They support legacy migrations:
- `POST /disk-space/settings/proxmox-api-key` - Set global API key
- `POST /disk-space/settings/proxmox-api-key/<mac>` - Set host-specific key
- `DELETE /disk-space/settings/proxmox-api-key` - Delete global key
- `DELETE /disk-space/settings/proxmox-api-key/<mac>` - Delete host key

## Frontend Changes

### CreateEditHost.vue Component
- **Removed**: Proxmox API Key input field and password form group
- **Added**: Proxmox Cluster field (dropdown or text input for cluster reference)
- **Updated**: Host model initialization to include `proxmox_cluster` field

### DiskSpaceSettings.vue Component
**Complete redesign of Proxmox Configuration tab:**

#### Old Tabs
- Proxmox Configuration (global/host keys)
- Manual Hosts
- Documentation

#### New Tabs
- **Proxmox Clusters** - Cluster management interface
  - Proxmox Tag configuration
  - Add Cluster form (name, host, user, token ID, secret, SSL verification)
  - Configured Clusters list with edit/delete actions
  - Unconfigured Proxmox Hosts warning section
- **Manual Hosts** - Unchanged
- **Documentation** - Unchanged

#### Cluster Management Features
- List all configured clusters
- Create new clusters with form validation
- Delete clusters
- Edit functionality placeholder (coming soon)
- Visual indicator for unconfigured hosts
- Token secrets never displayed in UI

## Test Updates

### test_13_disk_space.py Refactored
Complete rewrite of test suite to use cluster-based architecture:

**New Tests:**
- `test_get_proxmox_disk_space_uses_tag_and_cluster_lookup()` - Cluster resolution
- `test_get_proxmox_disk_space_cluster_not_found_returns_error()` - Error handling
- `test_get_proxmox_disk_space_no_cluster_returns_host_error()` - Missing cluster
- `test_get_proxmox_disk_space_backfills_qemu_warning_fields()` - QEMU agent flags
- `test_proxmox_cluster_crud()` - Cluster CRUD operations
- `test_proxmox_cluster_create_requires_fields()` - Field validation
- `test_proxmox_cluster_duplicate_name_rejected()` - Uniqueness enforcement
- `test_disk_space_settings_includes_clusters()` - Settings endpoint
- `test_get_proxmox_disk_data_marks_missing_qemu_guest_agent()` - Updated for new API
- `test_get_proxmox_disk_data_infers_missing_qemu_from_zero_disk()` - Updated for new API

**Removed Tests:**
- Tests for per-host API key precedence (no longer applicable)
- Tests for global API key fallback (no longer applicable)
- Tests for legacy API key settings (deprecated)

## Migration Path

### For Existing Deployments

1. **Create Cluster Definitions**
   ```bash
   POST /api/proxmox-clusters
   {
     "name": "pve-prod-1",
     "host": "10.1.1.1",
     "user": "root@pam",
     "token_id": "token-123",
     "token_secret": "secret-123",
     "verify_ssl": false
   }
   ```

2. **Update Host Definitions**
   - Add `proxmox_cluster` field to each Proxmox host
   - Value can be cluster ID (ObjectId as string) or cluster name
   - Remove `proxmox_api_key` field from hosts

3. **Delete Legacy Settings** (Optional)
   - `proxmox_api_key` global setting
   - `proxmox_api_key_<mac>` per-host settings
   - Old UI endpoints will continue to work but are deprecated

## Benefits

1. **Centralized Management** - Cluster credentials in one place
2. **Multi-Cluster Support** - Easily manage multiple Proxmox clusters
3. **Cleaner Architecture** - Clear separation of infrastructure and hosts
4. **Flexibility** - Support for both cluster-based and manual monitoring
5. **Security** - Token secrets not stored on host documents
6. **Error Clarity** - Clear error messages for misconfigured hosts
7. **Backward Compatibility** - Old endpoints still functional for migrations

## Future Enhancements

1. Edit cluster functionality in UI
2. Cluster health/connection status indicator
3. Bulk cluster operations
4. Cluster role-based access control
5. Encrypted credential storage for token_secret
6. Cluster auto-discovery from Proxmox API
