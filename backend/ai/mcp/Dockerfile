FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app
RUN apt update && apt upgrade -y && apt install -y \
       git

# Install dependencies (reuse backend requirements + MCP extras)
COPY backend/requirements.txt /requirements.txt
COPY backend/ai/mcp/requirements.txt /requirements-mcp.txt
RUN pip install --no-cache-dir -r /requirements-mcp.txt

# Copy source
COPY backend /app/backend

RUN useradd --system --no-create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8765

# --factory because create_http_app() applies the pre-shared secret check and
# materialises the ASGI app; FastMCP itself is not ASGI-callable.
CMD ["sh", "-c", "exec uvicorn ai.mcp.server:create_http_app --factory --host ${MCP_HOST:-0.0.0.0} --port ${MCP_PORT:-8765}"]
