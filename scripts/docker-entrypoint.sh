#!/bin/sh
# Wait until MySQL TCP is accepting connections, then exec the container CMD.
set -e

host="${DB_HOST:-mysql}"
port="${DB_PORT:-3306}"
retries="${DB_WAIT_RETRIES:-60}"

echo "Waiting for MySQL at ${host}:${port} ..."
i=0
while [ "$i" -lt "$retries" ]; do
  if python -c "import socket; s=socket.create_connection(('${host}', int('${port}')), 2); s.close()" 2>/dev/null; then
    echo "MySQL is reachable"
    exec "$@"
  fi
  i=$((i + 1))
  sleep 2
done

echo "ERROR: MySQL not reachable at ${host}:${port} after ${retries} attempts" >&2
exit 1
