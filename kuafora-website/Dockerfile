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
COPY --from=assets /build/static/dist/styles.css /app/static/dist/styles.css

# Create staticfiles and mediafiles directories
RUN mkdir -p /app/staticfiles /app/mediafiles /app/logs

ENV DJANGO_SETTINGS_MODULE=config.settings
RUN python manage.py collectstatic --noinput || true

ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Create non-root user
RUN groupadd -r django && useradd -r -g django django

# Change ownership of the app directory
RUN chown -R django:django /app

# Switch to non-root user
USER django

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health/ || exit 1

# Start gunicorn on port 8001
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "3", "--worker-class", "gevent", "--worker-connections", "1000", "--max-requests", "1000", "--max-requests-jitter", "100", "--timeout", "30", "--keep-alive", "5", "config.wsgi:application"]