#!/usr/bin/env sh

# Minimal, non-verbose cron entrypoint. Do not echo env.

set -eu

CRON_FILE="/etc/cron.d/kuafora"

{
  echo 'SHELL=/bin/sh'
  echo 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
  # Daily maintenance at midnight
  echo '0 0 * * * root cd /app && python manage.py daily_maintenance >> /proc/1/fd/1 2>&1'
  # Precompute availability for next 7 days at 1 AM
  echo '0 1 * * * root cd /app && python manage.py precompute_day_status --days 7 >> /proc/1/fd/1 2>&1'
  # Reject stale pending appointments every 15 minutes
  echo '*/15 * * * * root cd /app && python manage.py reject_stale_appointments >> /proc/1/fd/1 2>&1'
  echo ''
} > "$CRON_FILE"

chmod 0644 "$CRON_FILE"

exec cron -f
