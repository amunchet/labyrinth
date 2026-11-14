FROM python:3.11-slim

# Same timezone as the backend and cron: stored metric timestamps are naive
# local time, so freshness checks run here must use the same clock.
ARG TZ
ENV TZ=${TZ}

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app
RUN apt update && apt upgrade -y && apt install -y \
       git \
       iputils-ping

# Install dependencies (reuse backend requirements + MCP extras)
COPY backend/requirements.txt /requirements.txt
COPY backend/ai/mcp/requirements.txt /requirements-mcp.txt
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: \
    -r /requirements-mcp.txt

# Copy source
COPY backend /app/backend

# Runs as root, like the backend and cron containers: its tools write
# playbooks, Telegraf configs, map images and icons into the same root-owned
# bind mounts they do

EXPOSE 8765

# --factory because create_http_app() applies the pre-shared secret check and
# materialises the ASGI app; FastMCP itself is not ASGI-callable.
CMD ["sh", "-c", "exec uvicorn ai.mcp.server:create_http_app --factory --host ${MCP_HOST:-0.0.0.0} --port ${MCP_PORT:-8765}"]
