#!/bin/sh
set -u
# RQ worker only — do NOT use start.sh here (that runs the HTTP API).
# Railway: set this service’s Custom Start Command to:
#   /app/scripts/start-worker.sh
# or: rq worker -u "$REDIS_URL" "${RQ_QUEUE_NAME:-whatsapp-agent}"

if [ -z "${REDIS_URL:-}" ]; then
  echo ">>> [start-worker.sh] ERROR: REDIS_URL is not set"
  exit 1
fi

QUEUE="${RQ_QUEUE_NAME:-whatsapp-agent}"

# Supervised restart loop.
#
# A bare `rq worker` exits when its Redis connection times out — a transient
# managed-Redis blip is enough ("Redis connection timeout, quitting..."). With
# no supervisor the worker stays dead, inbound webhooks keep enqueueing
# run_ai_reply jobs that nobody drains, and AI replies silently stop while the
# HTTP API still answers 202. (That is exactly what happened: the worker died
# and did not come back until a manual redeploy days later.)
#
# Restart with exponential backoff so a dropped connection self-heals instead
# of requiring human intervention. The backoff resets after any run that lasted
# long enough to be considered healthy, so a genuine crash-loop still backs off
# rather than hammering Redis.
backoff=2
max_backoff=30
while true; do
  echo ">>> [start-worker.sh] starting RQ worker queue=${QUEUE}"
  start=$(date +%s)
  if rq worker -u "$REDIS_URL" "$QUEUE"; then
    exit_code=0
  else
    exit_code=$?
  fi
  end=$(date +%s)

  if [ $((end - start)) -ge 60 ]; then
    backoff=2
  fi

  echo ">>> [start-worker.sh] worker exited (code=${exit_code}); restarting in ${backoff}s"
  sleep "$backoff"
  backoff=$((backoff * 2))
  [ "$backoff" -gt "$max_backoff" ] && backoff=$max_backoff
done
