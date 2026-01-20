#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."
until python -c "from app.db.session import engine; engine.connect()" 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - running migrations"
alembic upgrade head

echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
