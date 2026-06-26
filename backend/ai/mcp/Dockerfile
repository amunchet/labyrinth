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

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8765

CMD ["uvicorn", "backend.ai.mcp.server:app", "--host", "0.0.0.0", "--port", "8765"]
