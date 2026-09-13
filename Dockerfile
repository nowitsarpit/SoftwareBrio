# =============================================================================
# Autonomous Lead Enrichment Pipeline — Production Dockerfile
# Base: Python 3.11 Slim with Playwright Chromium
# =============================================================================

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies needed for Playwright headless browser
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium headless binary
RUN playwright install chromium

# Copy application source code and defaults
COPY app/ /app/app/
COPY data/ /app/data/
COPY .env.example /app/.env.example

# Create directories for persistent volume mounts and non-root execution
RUN mkdir -p /app/cache /app/logs && \
    useradd -u 1000 -U -d /app -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Healthcheck to verify Python runtime and module loading
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from app.config import settings; print('ok')" || exit 1

ENTRYPOINT ["python", "-m", "app.main"]
CMD ["--input", "data/input.json", "--output", "data/output.json", "--output-format", "all"]
