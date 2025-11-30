"""
Cloud Platform Client App - Main Application

This is the frontend application that serves the UI and acts as an API gateway
to communicate with the remote compute server.

Run with: uvicorn app.app:app --reload --port 3000
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import os

from .api_proxy import proxy, LoginResponse, JobSubmitResponse, JobHistoryResponse
from .auth import get_token_from_request

# ============================================================================
# Configuration
# ============================================================================

# Remote compute server URL - set via environment variable
COMPUTE_SERVER_URL = os.getenv("COMPUTE_SERVER_URL", "http://localhost:8000")

# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="Cloud Platform Client",
    description="Frontend application for GPU-powered Python execution",
    version="1.0.0"
)

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Templates and static files
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


# ============================================================================
# Request Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login credentials."""
    email: str
    password: str


class JobRunRequest(BaseModel):
    """Job submission request."""
    code: str
    gpu_enabled: bool = True


# ============================================================================
# Page Routes (HTML)
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root to login page."""
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "server_url": COMPUTE_SERVER_URL
    })


@app.get("/editor", response_class=HTMLResponse)
async def editor_page(request: Request):
    """Render the script editor page."""
    return templates.TemplateResponse("editor.html", {
        "request": request,
        "server_url": COMPUTE_SERVER_URL
    })


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Render the job history page."""
    return templates.TemplateResponse("history.html", {
        "request": request,
        "server_url": COMPUTE_SERVER_URL
    })


# ============================================================================
# API Gateway Routes
# ============================================================================

@app.post("/api/auth/login")
async def api_login(credentials: LoginRequest):
    """
    Proxy login request to the compute server.
    
    Args:
        credentials: Email and password
        
    Returns:
        Login response with JWT token
    """
    result = await proxy.login(credentials.email, credentials.password)
    
    if not result.success:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "message": result.message or "Login failed"
            }
        )
    
    return {
        "success": True,
        "token": result.token,
        "user": result.user,
        "message": "Login successful"
    }


@app.post("/api/jobs/run")
async def api_run_job(request: Request, job_request: JobRunRequest):
    """
    Proxy job submission to the compute server.
    
    Args:
        request: FastAPI request (for auth token)
        job_request: Code and GPU settings
        
    Returns:
        Job submission response with job_id
    """
    # Get token from request
    token = await get_token_from_request(request)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    result = await proxy.submit_job(
        token=token,
        code=job_request.code,
        gpu_enabled=job_request.gpu_enabled
    )
    
    if not result.success:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": result.message or "Failed to submit job"
            }
        )
    
    return {
        "success": True,
        "job_id": result.job_id,
        "status": result.status,
        "message": "Job submitted successfully"
    }


@app.get("/api/jobs/history")
async def api_job_history(request: Request):
    """
    Proxy job history request to the compute server.
    
    Args:
        request: FastAPI request (for auth token)
        
    Returns:
        List of jobs
    """
    # Get token from request
    token = await get_token_from_request(request)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    result = await proxy.get_job_history(token)
    
    if not result.success:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": result.message or "Failed to fetch history",
                "jobs": [],
                "total": 0
            }
        )
    
    return {
        "success": True,
        "jobs": result.jobs,
        "total": result.total
    }


@app.get("/api/jobs/{job_id}")
async def api_job_details(request: Request, job_id: str):
    """
    Proxy job details request to the compute server.
    """
    token = await get_token_from_request(request)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    result = await proxy.get_job_details(token, job_id)
    return result


@app.post("/api/jobs/{job_id}/cancel")
async def api_cancel_job(request: Request, job_id: str):
    """
    Proxy job cancellation request to the compute server.
    """
    token = await get_token_from_request(request)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    result = await proxy.cancel_job(token, job_id)
    return result


@app.get("/api/system/status")
async def api_system_status(request: Request):
    """
    Proxy system status request to the compute server.
    """
    token = await get_token_from_request(request)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    result = await proxy.get_system_status(token)
    return result


# ============================================================================
# Health Check
# ============================================================================

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    Also checks connectivity to the compute server.
    """
    # Check compute server
    server_health = await proxy.health_check()
    server_online = server_health.get("status") == "healthy"
    
    return {
        "client_status": "healthy",
        "server_status": "online" if server_online else "offline",
        "server_url": COMPUTE_SERVER_URL
    }


@app.get("/health")
async def simple_health():
    """Simple health check for the client app."""
    return {"status": "healthy"}


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000, reload=True)








