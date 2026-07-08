# Email Templates

This directory contains Jinja2 templates used for email notifications in Labyrinth.

## disk_space_alert.html

HTML email template for Proxmox disk space alerts.

### Available Variables

- `{{ threshold_percent }}` - Alert threshold percentage (e.g., 80)
- `{{ timestamp }}` - Generation timestamp in UTC
- `{{ issues }}` - List of all disk issues found
- `{{ datastores }}` - Filtered list of datastore issues
- `{{ vms }}` - Filtered list of VM issues
- `{{ containers }}` - Filtered list of container issues

### Issue Object Properties

Each issue object has the following properties:

#### Datastores
- `cluster` - Cluster name
- `host` - Cluster host IP
- `node` - Node name in cluster
- `name` - Storage name
- `storage_type` - Storage type (e.g., "dir", "lvm", "ceph")
- `used` - Bytes used
- `total` - Total bytes available
- `percentage` - Usage percentage (0-100)

#### VMs
- `cluster` - Cluster name
- `host` - Cluster host IP
- `node` - Node name in cluster
- `name` - VM name
- `vm_id` - VM ID number
- `status` - VM status (running, stopped, etc.)
- `used` - Bytes used
- `total` - Maximum disk bytes
- `percentage` - Usage percentage (0-100)
- `qemu_agent_installed` - Boolean indicating if QEMU guest agent is installed

#### Containers
- `cluster` - Cluster name
- `host` - Cluster host IP
- `node` - Node name in cluster
- `name` - Container name
- `container_id` - Container ID number
- `status` - Container status
- `used` - Bytes used
- `total` - Maximum disk bytes
- `percentage` - Usage percentage (0-100)

### Available Filters

- `{{ value|format_size }}` - Converts bytes to human-readable format (B, KB, MB, GB, TB, PB)
  - Example: `{{ 1073741824|format_size }}` outputs `1.00 GB`

### Customization Examples

#### Change Header Color

Replace the `background-color` in the `.header` style:
```css
.header { background-color: #007bff; /* Blue instead of red */ }
```

#### Add Custom Columns

Add columns to the VM table:
```html
<th>Memory</th>
{# In the loop: #}
<td>{{ vm.maxmem|format_size }}</td>
```

#### Change Alert Threshold Display

Modify the summary section:
```html
<p><strong>Alert Threshold:</strong> {{ threshold_percent }}% (Critical above this value)</p>
```

#### Add Cluster Information

Include cluster details:
```html
<p><strong>Cluster:</strong> {{ datastores.0.cluster if datastores else 'N/A' }}</p>
```

#### Change Language

Replace emoji and text as needed:
```html
<h3>📦 Datastores</h3>  {# Replace emoji #}
```

### CSS Styling

All styles are embedded in the `<head>` for email compatibility. Common email clients have limited CSS support, so the template uses:
- Inline styles for critical elements
- Standard CSS properties
- No external stylesheets or fonts
- HTML tables for layout (better email support)

To modify styling:
1. Edit the `<style>` section in the template
2. Test in email clients (Gmail, Outlook, etc.)
3. Avoid CSS that's not widely supported

### Testing Template Locally

```bash
# Dry run to generate HTML without sending email
cd /home/amunchet/labyrinth/backend
python3 -c "
from proxmox_disk_check import render_email_template
issues = [
    {
        'type': 'datastore',
        'cluster': 'test-cluster',
        'host': '192.168.1.100',
        'node': 'node1',
        'name': 'local',
        'storage_type': 'dir',
        'used': 107374182400,  # 100 GB
        'total': 1099511627776,  # 1 TB
        'percentage': 97.65
    }
]
html = render_email_template(issues, 80)
print(html)
" > /tmp/test_email.html
```

Then open `/tmp/test_email.html` in a web browser to preview.

### Adding New Templates

To add additional email templates:

1. Create a new `.html` file in this directory
2. Use Jinja2 syntax with available variables
3. Update `proxmox_disk_check.py` to load and use the template:
   ```python
   template = jinja_env.get_template('new_template.html')
   ```

### Email Client Compatibility

This template is designed for compatibility with:
- Gmail
- Outlook
- Apple Mail
- Mobile email clients (iOS, Android)

Features tested:
- HTML5 structure
- Embedded CSS styles
- Unicode emoji support
- Responsive design
- Table-based layout

### Troubleshooting

**Template not found error:**
- Ensure file is in the same directory as this README
- Check filename matches exactly (case-sensitive)
- Verify the `TEMPLATE_DIR` path in `proxmox_disk_check.py`

**Filters not working:**
- Ensure filter is registered: `jinja_env.filters['filter_name'] = function`
- Check filter function exists and is imported
- Review Jinja2 filter syntax

**Styling not displayed:**
- Some email clients strip `<style>` tags; use inline styles
- Test in Gmail first, then other clients
- Use table borders instead of CSS borders

**Missing data in email:**
- Verify variable names match exactly (case-sensitive)
- Check data exists in the issue objects
- Add conditional: `{% if variable %}...{% endif %}`
