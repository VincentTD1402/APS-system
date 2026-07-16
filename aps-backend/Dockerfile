FROM python:3.11-slim

# Python runtime config
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user early — this layer stays cached when application code changes
RUN useradd -m -u 1000 appuser

# Install uv (keep pip for simplicity & stability)
RUN pip install --no-cache-dir uv

# Copy metadata first for better layer cache reuse
COPY pyproject.toml README.md ./

# Install dependencies
RUN uv pip install --system .

# Application code last (avoids invalidating the dependency layer)
COPY app ./app
COPY migrations ./migrations
COPY ontology ./ontology

# Non-root user
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck — nice and forgiving so probes don't pile up while LLM workers are busy.
# /health is async + does no DB/LLM work; 8s timeout + 5 retries gives ~80s grace
# before Docker marks the container unhealthy.
HEALTHCHECK --interval=30s --timeout=8s --start-period=30s --retries=5 \
    CMD curl -fsS --max-time 5 http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
