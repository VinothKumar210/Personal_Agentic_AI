#!/bin/sh
set -e

echo "[entrypoint] Waiting for Postgres to be ready..."
until python -c "
import socket, sys
try:
    s = socket.create_connection(('postgres', 5432), timeout=2)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
"; do
  echo "[entrypoint] Postgres not ready yet, retrying in 2s..."
  sleep 2
done

echo "[entrypoint] Postgres is ready. Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Migrations complete. Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
