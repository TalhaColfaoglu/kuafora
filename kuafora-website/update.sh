#!/bin/bash

# Kuafora.com Update Script
# Usage: ./update.sh

set -e

echo "🔄 Updating Kuafora.com..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Navigate to project directory
cd /opt/kuafora

# Create backup before update
log_info "Creating backup before update..."
./backup.sh

# Pull latest changes
log_info "Pulling latest code..."
git pull origin main

# Build new images
log_info "Building updated Docker images..."
docker-compose -f docker-compose.prod.yml build --no-cache

# Update services with zero downtime
log_info "Updating services..."
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
log_info "Running database migrations..."
docker-compose -f docker-compose.prod.yml exec -T web python manage.py migrate

# Collect static files
log_info "Collecting static files..."
docker-compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput

# Health check
log_info "Running health check..."
sleep 10

if docker-compose -f docker-compose.prod.yml exec -T web curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
    log_success "Update completed successfully!"
else
    log_warning "Health check failed, rolling back..."
    # Simple rollback - restart with previous images
    docker-compose -f docker-compose.prod.yml restart
    exit 1
fi

log_success "🎉 Update completed!"
echo "Check logs: docker-compose -f docker-compose.prod.yml logs -f"
