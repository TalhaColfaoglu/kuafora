##########
# Stage 1: Build static assets with Node (Tailwind)
##########
FROM node:18-alpine AS assets

WORKDIR /build

# Install node deps
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install

# Copy project for asset build
COPY . .

# Build Tailwind to static/dist/styles.css
RUN npm run build

##########
# Stage 2: Python runtime
##########
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        gcc \
        python3-dev \
        libpq-dev \
        curl \
        gettext \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Copy built assets from assets stage (match template path)
RUN mkdir -p /app/static/dist
# Copy full dist to avoid missing manifest entries
COPY --from=assets /build/static/dist /app/static/dist

# Create staticfiles and mediafiles directories
RUN mkdir -p /app/staticfiles /app/mediafiles /app/logs

ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Ensure entrypoint exists and is executable before switching user
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create non-root user
RUN groupadd -r django && useradd -r -g django django

# Change ownership of the app directory
RUN chown -R django:django /app

# Switch to non-root user
USER django

# Expose port
EXPOSE 8001

# Health check
# Host header'ını kuafora.com olarak gönderiyoruz ki ALLOWED_HOSTS ile uyumlu olsun.
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f -H "Host: kuafora.com" http://localhost:8001/health/ || exit 1

# Entrypoint: collectstatic at container startup then run gunicorn
ENTRYPOINT ["/app/entrypoint.sh"]