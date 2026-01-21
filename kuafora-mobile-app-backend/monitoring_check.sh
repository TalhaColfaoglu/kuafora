#!/bin/bash
# Monitoring health check script (to be run via cron)
# Usage: Add to crontab: */15 * * * * /path/to/monitoring_check.sh

cd "$(dirname "$0")" || exit 1

# Activate virtual environment if exists (adjust path as needed)
# source venv/bin/activate

# Run health check command
python manage.py check_health --send-alerts --alert-email colfaoglutalha@gmail.com

# Exit with appropriate code
exit $?

