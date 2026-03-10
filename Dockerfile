# Multi-Stage Dockerfile for AetherStore Federated Network

# --- Stage 1: Build Frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY aetherstoreweb/package*.json ./
RUN npm install
COPY aetherstoreweb/ ./
RUN npm run build

# --- Stage 2: Python Backend & Final Image ---
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

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/static/frontend

# Ensure entrypoint is executable
RUN chmod +x scripts/docker-entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=aetherstore.settings
ENV PORT=8000

# Expose ports
EXPOSE 8000 8001 8002 8003 8004 8005 8006

# Default entrypoint
ENTRYPOINT ["scripts/docker-entrypoint.sh"]

# --- Stage 3: Nginx Production ---
FROM nginx:stable-alpine AS nginx-prod
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html
COPY config/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
