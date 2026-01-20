#!/bin/bash
# Start Flower - Celery monitoring web UI

echo "Starting Flower monitoring UI..."

# Run Flower on port 5555
celery -A app.core.celery_app:celery_app flower \
    --port=5555 \
    --broker=redis://redis:6379/0
