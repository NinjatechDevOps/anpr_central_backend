"""
Central Server - FastAPI Application Entry Point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import time

from app.core.config import settings
from app.core.logging import app_logger as logger
# Import routers
from app.api.v1 import organizations
from app.api.v1.endpoints import anpr, admin, analytics, cameras, static_anpr, sync_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("=" * 80)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 80)

    # Store startup time
    app.state.start_time = time.time()

    logger.info(f"Server starting on {settings.HOST}:{settings.PORT}")
    logger.info(f"API documentation: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 80)

    yield

    # Shutdown
    logger.info("=" * 80)
    logger.info("Shutting down application...")
    logger.info("Application shutdown complete")
    logger.info("=" * 80)


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Central Server for ANPR Vehicle Detection System",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(
    organizations.router,
    prefix=f"{settings.API_V1_PREFIX}/organizations",
    tags=["Organizations"]
)

app.include_router(
    anpr.router,
    prefix=f"{settings.API_V1_PREFIX}/anpr",
    tags=["ANPR"]
)

app.include_router(
    admin.router,
    prefix=f"{settings.API_V1_PREFIX}/admin",
    tags=["Admin"]
)

app.include_router(
    analytics.router,
    prefix=f"{settings.API_V1_PREFIX}/analytics",
    tags=["Analytics"]
)

app.include_router(
    cameras.router,
    prefix=f"{settings.API_V1_PREFIX}/cameras",
    tags=["Cameras"]
)

app.include_router(
    static_anpr.router,
    prefix=f"{settings.API_V1_PREFIX}/static",
    tags=["Static"]
)

app.include_router(
    sync_jobs.router,
    prefix=f"{settings.API_V1_PREFIX}/sync-jobs",
    tags=["Sync Jobs"]
)


@app.get("/", tags=["Root"])
def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    import psutil

    uptime = time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0

    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "uptime_seconds": uptime,
        "cpu_usage": psutil.cpu_percent(),
        "ram_usage": psutil.virtual_memory().percent
    }
