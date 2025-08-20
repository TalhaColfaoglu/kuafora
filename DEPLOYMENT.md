# Centralized Deployment (Docker + Nginx)

This repository contains two Django projects managed by a single, centralized Nginx:
- `kuafora-mobile-app-backend` → exposed on port 8000 internally, served at `https://api.kuafora.com`.
- `kuafora-website` → exposed on port 8001 internally, served at `https://kuafora.com` and `https://www.kuafora.com`.

Nginx configuration is centralized at `nginx/conf.d/`.

## Directory Layout
- `docker-compose.yml` (root): Orchestrates `backend`, `website`, and `nginx`.
- `nginx/conf.d/api.conf`: Server block for `api.kuafora.com`.
- `nginx/conf.d/website.conf`: Server block for `kuafora.com` and `www.kuafora.com`.
- `nginx/certbot/`: LetsEncrypt files (optional; create as needed).

## Requirements
- Docker, Docker Compose
- DNS A/AAAA records pointing to the host for:
  - `api.kuafora.com`
  - `kuafora.com`, `www.kuafora.com`

## Environment Files
Create the following files before starting services:

`kuafora-mobile-app-backend/.env.prod`:
```
DEBUG=0
SECRET_KEY=replace-with-a-strong-secret
ALLOWED_HOSTS=api.kuafora.com
CSRF_TRUSTED_ORIGINS=https://api.kuafora.com

POSTGRES_HOST=<your-db-host-or-service>
POSTGRES_PORT=5432
POSTGRES_DB=<your-db-name>
POSTGRES_USER=<your-db-user>
POSTGRES_PASSWORD=<your-db-password>
```

`kuafora-website/.env.prod`:
```
DEBUG=0
SECRET_KEY=replace-with-a-strong-secret
ALLOWED_HOSTS=kuafora.com,www.kuafora.com
CSRF_TRUSTED_ORIGINS=https://kuafora.com,https://www.kuafora.com

# Example managed DB
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
```

## Start
```
cd ~/kuafora
# ensure your user can access docker daemon or use sudo
# sudo usermod -aG docker $USER && newgrp docker

docker compose up -d --build
```

## Certificates
The Nginx configs expect Let’s Encrypt files under `nginx/certbot/conf`. You can:
- Temporarily use self-signed certs to bring containers up (for smoke testing), or
- Add a certbot container/process to obtain real certificates.

Self-signed example (temporary):
```
mkdir -p nginx/certbot/conf/live/api.kuafora.com nginx/certbot/conf/live/kuafora.com

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -keyout nginx/certbot/conf/live/api.kuafora.com/privkey.pem \
  -out    nginx/certbot/conf/live/api.kuafora.com/fullchain.pem \
  -subj "/CN=api.kuafora.com"
cp nginx/certbot/conf/live/api.kuafora.com/fullchain.pem nginx/certbot/conf/live/api.kuafora.com/chain.pem

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -keyout nginx/certbot/conf/live/kuafora.com/privkey.pem \
  -out    nginx/certbot/conf/live/kuafora.com/fullchain.pem \
  -subj "/CN=kuafora.com"
cp nginx/certbot/conf/live/kuafora.com/fullchain.pem nginx/certbot/conf/live/kuafora.com/chain.pem
```

## Notes
- Project-level Nginx and deploy scripts were removed. All Nginx config lives in `nginx/conf.d/`.
- The backend exposes port 8000 internally; the website exposes port 8001 internally.
- Static and media volumes are mounted into Nginx for direct serving.
