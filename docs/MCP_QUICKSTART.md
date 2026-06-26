# Labyrinth MCP Server - Quick Start Guide

## Overview

The MCP (Model Context Protocol) server provides AI-friendly tools for managing Labyrinth hosts and services. It runs as a separate container alongside the backend and uses the same MongoDB and Redis instances.

## Automatic Startup

The MCP server starts automatically when you start Labyrinth:

```bash
# Development environment
./start_dev.sh
# OR
docker-compose -f docker-compose-development.yml up -d

# Production environment
docker-compose -f docker-compose-production.yml up -d
```

The MCP service is available at `http://mcp:8765` within the Docker network.

## Verify It's Running

```bash
# Check if the mcp container is running
docker ps | grep mcp

# Check logs
docker logs labyrinth_mcp_1
```

## Available Tools

### Host Management
- **mcp_list_hosts()** - List all hosts
- **mcp_get_host(host_key)** - Get host by MAC or IP
- **mcp_create_or_update_host(host_json)** - Create/update a host
- **mcp_add_service_to_host(host_key, service_name)** - Add service to host
- **mcp_remove_service_from_host(host_key, service_name)** - Remove service from host
- **mcp_replace_host_services(host_key, services_json)** - Replace all services

### Service Management
- **mcp_list_services(include_full)** - List services (names or full records)
- **mcp_create_or_update_service(service_json)** - Create/update service definition

### Metrics
- **mcp_read_metrics(host_key, service, count)** - Read latest metrics

## Example Usage

### Creating a New Host

```python
host_json = '''
{
  "ip": "192.168.1.100",
  "mac": "00:11:22:33:44:55",
  "subnet": "192.168.1",
  "host": "webserver1.local",
  "group": "Web Servers",
  "icon": "server",
  "services": ["open_ports", "closed_ports"],
  "open_ports": [80, 443],
  "class": "health",
  "monitor": true
}
'''

result = mcp_create_or_update_host(host_json)
```

### Adding a Service to a Host

```python
# First, make sure the service exists
service_json = '''
{
  "name": "check_nginx",
  "display_name": "NGINX Check",
  "type": "check",
  "metric": "nginx",
  "field": "active",
  "comparison": "greater",
  "value": 0
}
'''

mcp_create_or_update_service(service_json)

# Then add it to the host
mcp_add_service_to_host("00:11:22:33:44:55", "NGINX Check")
```

### Reading Host Metrics

```python
# Get last 50 metrics for a host
metrics = mcp_read_metrics("192.168.1.100", count=50)

# Get metrics for a specific service
nginx_metrics = mcp_read_metrics("192.168.1.100", service="NGINX Check", count=20)
```

## Important Notes

1. **No Automatic Deployment**: The MCP server only updates the database. You must manually deploy Telegraf configurations after making changes.

2. **Service Names**: When adding services to hosts, use the `display_name` field from the service definition.

3. **Required Fields**:
   - Hosts require: `mac`, `subnet`
   - Services require: `name`

4. **Authentication**: The MCP server bypasses HTTP auth by using `unwrap()` internally. It should only be accessible within the trusted Docker network.

5. **Metrics Ready**: When you add services to hosts, the system is ready to collect metrics once you deploy the Telegraf configuration manually.

## Troubleshooting

### Container won't start
Check environment variables are set correctly:
```bash
docker-compose -f docker-compose-development.yml config | grep -A 10 "mcp:"
```

### Can't connect to MongoDB/Redis
Verify the backend services are running:
```bash
docker ps | grep -E "(mongo|redis)"
```

### Import errors
Make sure the PYTHONPATH is set correctly in the Dockerfile:
```dockerfile
ENV PYTHONPATH=/app/backend
```

## Manual Testing (Local)

To run the MCP server locally for development:

```bash
# Set up environment
export PYTHONPATH=$(pwd)/backend
export MONGO_HOST=localhost
export MONGO_USERNAME=root
export MONGO_PASSWORD=temp
export REDIS_HOST=localhost

# Install dependencies
pip install -r backend/ai/mcp/requirements.txt

# Run the server
python backend/ai/mcp/server.py
```

## See Also

- [MCP Server README](../backend/ai/mcp/README.md) - Detailed documentation
- [Backend API Documentation](../backend/README.md) - Underlying Flask endpoints
