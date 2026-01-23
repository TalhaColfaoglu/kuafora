#!/usr/bin/env bash
set -euo pipefail

# Kuafora - Docker disk temizlik script'i
# Amaç: deploy/build sonrası biriken "<none>" (dangling) image'ları ve build cache'i temizlemek.
# Güvenli: ÇALIŞAN container'ların image'larına dokunmaz. Volume silmez.
#
# İsterseniz cron ile haftalık çalıştırın:
#   0 3 * * 0 /usr/local/bin/kuafora-docker-prune >> /var/log/kuafora-docker-prune.log 2>&1

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "Starting docker prune..."

if ! command -v docker >/dev/null 2>&1; then
  log "ERROR: docker not found in PATH"
  exit 127
fi

# Only remove dangling images (repo/tag = <none>)
log "docker image prune (dangling images only)"
docker image prune -f

# Remove build cache (dangling builder cache)
log "docker builder prune (build cache)"
docker builder prune -f

log "Done."


