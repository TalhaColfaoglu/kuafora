3#!/bin/bash

# Simple deployment script for IP-only access (no SSL)
set -e

echo "🚀 Starting deployment..."

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    echo "❌ .env.prod file not found!"
    exit 1
fi

echo "📦 Stopping existing containers..."
docker compose -f docker-compose.prod.yml down

echo "🔄 Building and starting services..."
docker compose -f docker-compose.prod.yml up -d --build

echo "⏳ Waiting for services to be ready..."
sleep 30

echo "🔍 Checking service status..."
docker compose -f docker-compose.prod.yml ps

echo "✅ Deployment completed!"
echo ""
echo "📋 Your API is now available at:"
echo "   http://3.79.28.13/api/docs/  (Swagger UI)"
echo "   http://3.79.28.13/admin/     (Django Admin)"
echo "   http://3.79.28.13/health/    (Health Check)"
echo ""
echo "📊 To check logs: docker compose -f docker-compose.prod.yml logs -f"
