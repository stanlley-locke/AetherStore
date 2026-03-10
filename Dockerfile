# Optimized Dockerfile for AetherStore Backend Services

FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy python dependencies
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -r pyproject.toml

# Copy project files
COPY . .

# Ensure entrypoint is executable
RUN chmod +x scripts/docker-entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=aetherstore.settings
ENV PORT=8000

# Expose ports for API and Storage Nodes
EXPOSE 8000 8001 8002 8003 8004 8005 8006

# Default entrypoint
ENTRYPOINT ["scripts/docker-entrypoint.sh"]
