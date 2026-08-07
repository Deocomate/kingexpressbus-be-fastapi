#!/bin/sh
# Wait for MySQL, optionally run migrations, then exec the container CMD.
set -e

host="${DB_HOST:-mysql}"
port="${DB_PORT:-3306}"
retries="${DB_WAIT_RETRIES:-60}"

echo "Waiting for MySQL at ${host}:${port} ..."
i=0
while [ "$i" -lt "$retries" ]; do
  if python -c "import socket; s=socket.create_connection(('${host}', int('${port}')), 2); s.close()" 2>/dev/null; then
    echo "MySQL is reachable"
    break
  fi
  i=$((i + 1))
  sleep 2
done

if [ "$i" -ge "$retries" ]; then
  echo "ERROR: MySQL not reachable at ${host}:${port} after ${retries} attempts" >&2
  exit 1
fi

# Coolify-safe: run migrations inside api (no one-shot migrate service).
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Running alembic upgrade head ..."
  alembic upgrade head
fi

exec "$@"
