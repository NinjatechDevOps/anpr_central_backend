"""
Celery application configuration for ANPR processing tasks.
"""
from celery import Celery
from app.core.config import settings
from app.core.logging import app_logger as logger

# Create Celery app
celery_app = Celery(
    "anpr_worker",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    include=["app.tasks.anpr_tasks"]  # Import tasks module
)

# Celery Configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge task after completion (ensures retry on failure)
    task_reject_on_worker_lost=True,  # Reject task if worker crashes

    # Retry settings
    task_default_retry_delay=60,  # Retry after 60 seconds
    task_max_retries=3,  # Maximum 3 retries

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },

    # Worker settings
    worker_prefetch_multiplier=1,  # Worker fetches 1 task at a time (prevents overload)
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Task routes (optional - for multiple queues)
celery_app.conf.task_routes = {
    "app.tasks.anpr_tasks.process_anpr_detection": {"queue": "anpr_processing"},
}

logger.info("Celery app configured successfully")
