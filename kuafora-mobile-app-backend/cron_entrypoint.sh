#!/usr/bin/env sh

# Minimal, non-verbose cron entrypoint. Do not echo env.

set -eu

CRON_FILE="/etc/cron.d/kuafora"

{
  echo 'SHELL=/bin/sh'
  echo 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
  echo '0 0 * * * django cd /app && python manage.py daily_maintenance >> /proc/1/fd/1 2>&1'
  echo '0 1 * * * django cd /app && python manage.py precompute_day_status --days 7 >> /proc/1/fd/1 2>&1'
  echo ''
} > "$CRON_FILE"

chmod 0644 "$CRON_FILE"

exec cron -f


