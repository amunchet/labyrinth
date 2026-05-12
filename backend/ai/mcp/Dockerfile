FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app

# Install dependencies (reuse backend requirements + MCP extras)
COPY backend/requirements.txt /tmp/requirements.txt
COPY backend/ai/mcp/requirements.txt /tmp/requirements-mcp.txt
RUN pip install --no-cache-dir -r /tmp/requirements-mcp.txt

# Copy source
COPY backend /app/backend

EXPOSE 8765

CMD ["uvicorn", "backend.ai.mcp.server:app", "--host", "0.0.0.0", "--port", "8765"]
