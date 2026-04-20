#!/bin/sh
set -eu
# RQ worker only — do NOT use start.sh here (that runs the HTTP API).
# Railway: set this service’s Custom Start Command to:
#   /app/scripts/start-worker.sh
# or: rq worker -u "$REDIS_URL" "${RQ_QUEUE_NAME:-whatsapp-agent}"

if [ -z "${REDIS_URL:-}" ]; then
  echo ">>> [start-worker.sh] ERROR: REDIS_URL is not set"
  exit 1
fi

QUEUE="${RQ_QUEUE_NAME:-whatsapp-agent}"
echo ">>> [start-worker.sh] starting RQ worker queue=${QUEUE}"
exec rq worker -u "$REDIS_URL" "$QUEUE"
