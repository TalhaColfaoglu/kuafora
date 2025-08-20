#!/bin/bash

# Fix PostgreSQL authentication issue

echo "🔧 Fixing PostgreSQL authentication..."

# Stop containers
docker compose -f docker-compose.prod.yml down

# Remove old database volume
docker volume rm makas-backend-deneme_postgres_data || true

# Add POSTGRES_HOST_AUTH_METHOD to docker-compose.prod.yml
sed -i '/POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}/a\      POSTGRES_HOST_AUTH_METHOD: trust' docker-compose.prod.yml

# Restart with new configuration
docker compose -f docker-compose.prod.yml up -d --build

echo "✅ Database fix applied. Waiting for services..."
sleep 30

echo "🔍 Testing connection..."
docker compose -f docker-compose.prod.yml exec web curl -I http://localhost:8000/health/ || echo "Still waiting..."

echo "📊 Service status:"
docker compose -f docker-compose.prod.yml ps
