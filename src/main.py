"""
ENSAM Cloud Platform - Main Application

A private cloud platform for remote Python script execution with GPU support.
Built for ENSAM Rabat Cloud Computing course 2025.

Features:
- EF1: JWT Authentication
- EF2: Script upload/edit and job submission
- EF3: Isolated Docker execution with resource limits
- EF4: GPU acceleration via NVIDIA Container Toolkit
- EF5: Real-time log streaming via WebSocket
- EF6: Job history and result visualization
- EF7: Prometheus metrics
- EF8: Job cancellation
"""

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import logging
import os

from .core.config import settings
from .core.database import init_db, get_db
from .core.security import get_current_user_optional, decode_access_token
from .api.routes import auth_router, jobs_router, metrics_router, websocket_router, admin_router
from .services.executor import executor
from .services.metrics import metrics

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize database
    init_db()
    
    # Check Docker availability
    if executor.is_available:
        logger.info("✅ Docker is available")
        if executor.gpu_available:
            logger.info("✅ GPU support detected")
        else:
            logger.info("ℹ️ GPU not available, CPU-only mode")
    else:
        logger.warning("⚠️ Docker not available, using simulation mode")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Private cloud platform for Python script execution with GPU support",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware
# If CORS_ORIGINS contains "*", allow all origins
cors_origins = ["*"] if "*" in settings.CORS_ORIGINS else settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Include API routers
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(metrics_router)
app.include_router(websocket_router)
app.include_router(admin_router)


# =============================================================================
# HTML Page Routes
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to login or app based on auth status."""
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render the registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    """Render the main application page (script editor)."""
    return templates.TemplateResponse("app.html", {
        "request": request,
        "gpu_available": executor.gpu_available
    })


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Render the job history page."""
    return templates.TemplateResponse("history.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Render the admin dashboard page."""
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "docker_available": executor.is_available,
        "gpu_available": executor.gpu_available
    })


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """Render the admin users management page."""
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "docker_available": executor.is_available,
        "gpu_available": executor.gpu_available
    })


@app.get("/admin/jobs", response_class=HTMLResponse)
async def admin_jobs_page(request: Request):
    """Render the admin jobs page."""
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "docker_available": executor.is_available,
        "gpu_available": executor.gpu_available
    })


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    from datetime import datetime
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "docker": "available" if executor.is_available else "unavailable",
        "gpu": "available" if executor.gpu_available else "unavailable"
    }


@app.get("/api/status")
async def system_status():
    """Get system status information."""
    return {
        "success": True,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docker_available": executor.is_available,
        "gpu_available": executor.gpu_available,
        "running_jobs": len(executor.get_running_job_ids()),
        "resource_profiles": list(settings.RESOURCE_PROFILES.keys())
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics_endpoint(db: Session = Depends(get_db)):
    """
    Prometheus metrics endpoint.
    
    Exposes metrics in Prometheus text format for scraping.
    This endpoint is public for Prometheus access.
    
    Alias for /api/metrics/ for compatibility with Prometheus default scraping.
    """
    # Update gauge metrics from database
    metrics.update_gauges(db)
    
    # Generate Prometheus format
    return Response(
        content=metrics.get_metrics_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint(db: Session = Depends(get_db)):
    """
    Prometheus metrics endpoint (alias for /api/metrics/).
    
    This endpoint is used by Prometheus for scraping metrics.
    """
    from fastapi.responses import PlainTextResponse, Response
    from ...services.metrics import metrics as prometheus_metrics
    
    # Update gauge metrics from database
    prometheus_metrics.update_gauges(db)
    
    # Generate Prometheus format
    return Response(
        content=prometheus_metrics.get_metrics_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail or "An error occurred", "status_code": exc.status_code}
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": exc.detail or "An error occurred", "code": exc.status_code},
        status_code=exc.status_code
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    """Handle 500 errors."""
    logger.error(f"Server error: {exc}", exc_info=True)
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc) if settings.DEBUG else None}
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": "Internal server error", "code": 500},
        status_code=500
    )



