#!/bin/bash
# Start Celery worker for ANPR processing

echo "Starting Celery worker for ANPR processing..."

# Run Celery worker
celery -A app.core.celery_app:celery_app worker \
    --loglevel=info \
    --queues=anpr_processing \
    --concurrency=2 \
    --max-tasks-per-child=100 \
    --prefetch-multiplier=1
