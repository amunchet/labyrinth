# AI Labyrinth

## MCP Server

The MCP (Model Context Protocol) server has been moved to its own directory.

See [mcp/README.md](mcp/README.md) for full documentation.

### Quick Start

The MCP server starts automatically with docker-compose:

```bash
# Development
docker-compose -f docker-compose-development.yml up -d

# Production  
docker-compose -f docker-compose-production.yml up -d
```

The server exposes tools for managing hosts, services, and reading metrics without requiring HTTP authentication.
