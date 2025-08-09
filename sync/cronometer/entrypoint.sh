#!/usr/bin/env sh
set -eu

# Build a runtime crontab with env-configured schedule
SCHEDULE="${CRONOMETER_CRON:-0 3 * * *}"
echo "$SCHEDULE /usr/bin/env python /app/main.py" > /app/.runtime_crontab

exec /usr/local/bin/supercronic -passthrough-logs /app/.runtime_crontab

