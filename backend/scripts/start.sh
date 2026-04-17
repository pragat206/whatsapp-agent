#!/bin/sh
set -eu

echo ">>> [start.sh] booting at $(date -u +%FT%TZ)"
echo ">>> [start.sh] BUILD_REV=${BUILD_REV:-unknown}"
echo ">>> [start.sh] PORT=${PORT:-8000}"

echo ">>> [start.sh] running alembic upgrade head"
alembic upgrade head
echo ">>> [start.sh] alembic upgrade completed"

echo ">>> [start.sh] launching uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
