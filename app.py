"""
Cloud Python Execution Platform - Main Application

A futuristic web application for remotely executing Python scripts
on a GPU-powered server. Built with FastAPI, Jinja2, and Tailwind CSS.

ENSAM Rabat - Cloud Computing Project 2025
"""

from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path
import uuid
import random

# Local imports
from auth import (
    authenticate_user, 
    create_access_token, 
    verify_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from models import (
    LoginRequest, 
    LoginResponse, 
    JobRunRequest, 
    JobRunResponse,
    JobRecord,
    JobHistoryResponse,
    JobStatus,
    SystemStatus,
    SuccessResponse,
    ErrorResponse
)

# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="Cloud Python Execution Platform",
    description="GPU-powered Python script execution service",
    version="1.0.0"
)

# Create necessary directories
Path("scripts").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)
Path("static/css").mkdir(exist_ok=True)
Path("templates").mkdir(exist_ok=True)

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================================
# In-Memory Data Store (Replace with database in production)
# ============================================================================

# Store jobs in memory (in production, use PostgreSQL/Redis)
jobs_store: List[dict] = []

# Add some mock historical jobs for demo
def init_mock_jobs():
    """Initialize some mock jobs for demonstration."""
    statuses = ["finished", "finished", "failed", "finished", "running"]
    
    for i, status in enumerate(statuses):
        job = {
            "job_id": str(uuid.uuid4()),
            "user_id": 1,
            "status": status,
            "created_at": (datetime.utcnow() - timedelta(hours=i*2)).isoformat(),
            "finished_at": (datetime.utcnow() - timedelta(hours=i*2-1)).isoformat() if status != "running" else None,
            "gpu_used": random.choice([True, True, True, False]),
            "script_name": f"script_{i+1}.py",
            "output": "Matrix shape: (2000, 2000)\nMean: 0.0012\nStd: 44.7214\n✅ Job finished successfully!" if status == "finished" else None,
            "error": "RuntimeError: CUDA out of memory" if status == "failed" else None
        }
        jobs_store.append(job)

# Initialize mock data
init_mock_jobs()

# ============================================================================
# Page Routes (HTML)
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect root to login page."""
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    """
    Render the main application page (dashboard + editor).
    Note: Authentication is handled client-side via JavaScript.
    """
    return templates.TemplateResponse("app.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """
    Render the job history page.
    Note: Authentication is handled client-side via JavaScript.
    """
    return templates.TemplateResponse("history.html", {"request": request})


# ============================================================================
# Authentication API Routes
# ============================================================================

@app.post("/auth/login")
async def login(credentials: LoginRequest):
    """
    Authenticate user and return JWT token.
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns JWT access token on successful authentication.
    """
    user = authenticate_user(credentials.email, credentials.password)
    
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "message": "Invalid email or password"
            }
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user["id"]),
            "email": user["email"],
            "name": user["name"]
        },
        expires_delta=access_token_expires
    )
    
    return {
        "success": True,
        "token": access_token,
        "user": user,
        "message": "Login successful"
    }


# ============================================================================
# Jobs API Routes
# ============================================================================

@app.post("/api/jobs/run")
async def run_job(
    request: Request,
    job_request: JobRunRequest
):
    """
    Submit a Python script for execution.
    
    - **code**: Python code to execute
    - **gpu_enabled**: Whether to use GPU acceleration
    
    Creates a new job and returns the job ID.
    """
    # Verify authentication
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Save script to file
    job_dir = Path("scripts") / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    script_path = job_dir / "script.py"
    script_path.write_text(job_request.code, encoding="utf-8")
    
    # Create job record
    job = {
        "job_id": job_id,
        "user_id": user["id"],
        "status": JobStatus.QUEUED.value,
        "created_at": datetime.utcnow().isoformat(),
        "finished_at": None,
        "gpu_used": job_request.gpu_enabled,
        "script_name": "script.py",
        "output": None,
        "error": None
    }
    
    # Add to store
    jobs_store.insert(0, job)  # Add to beginning for recent first
    
    # In production, this would trigger actual Docker execution
    # For demo, we'll simulate job completion after a delay
    simulate_job_execution(job_id)
    
    return {
        "success": True,
        "job_id": job_id,
        "status": JobStatus.QUEUED.value,
        "message": "Job submitted successfully"
    }


def simulate_job_execution(job_id: str):
    """
    Simulate job execution (for demo purposes).
    In production, this would be replaced with actual Docker execution.
    """
    import threading
    import time
    
    def run_simulation():
        time.sleep(2)  # Simulate processing time
        
        # Find and update job
        for job in jobs_store:
            if job["job_id"] == job_id:
                # Randomly succeed or fail (90% success rate)
                if random.random() < 0.9:
                    job["status"] = JobStatus.FINISHED.value
                    job["output"] = """🚀 Starting GPU computation...
Creating 2000x2000 matrices...
Performing matrix multiplication...

📊 Results:
  Matrix shape: (2000, 2000)
  Mean: 0.0023
  Std: 44.7156
  Max: 198.4521
  Min: -195.2341

⏱️ Completed in 1.42 seconds
✅ Job finished successfully!"""
                else:
                    job["status"] = JobStatus.FAILED.value
                    job["error"] = "RuntimeError: An error occurred during execution"
                
                job["finished_at"] = datetime.utcnow().isoformat()
                break
    
    # Run simulation in background thread
    thread = threading.Thread(target=run_simulation, daemon=True)
    thread.start()


@app.get("/api/jobs/history")
async def get_jobs_history(request: Request):
    """
    Get job history for the current user.
    Returns a list of all jobs sorted by creation date (newest first).
    """
    # Verify authentication
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Filter jobs for current user (in demo, return all)
    user_jobs = jobs_store  # In production: filter by user_id
    
    return {
        "success": True,
        "jobs": user_jobs,
        "total": len(user_jobs)
    }


@app.get("/api/jobs/{job_id}")
async def get_job(request: Request, job_id: str):
    """
    Get details for a specific job.
    """
    # Verify authentication
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Find job
    for job in jobs_store:
        if job["job_id"] == job_id:
            return {
                "success": True,
                "job": job
            }
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Job not found"
    )


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(request: Request, job_id: str):
    """
    Cancel a running or queued job.
    """
    # Verify authentication
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Find and cancel job
    for job in jobs_store:
        if job["job_id"] == job_id:
            if job["status"] in [JobStatus.QUEUED.value, JobStatus.RUNNING.value]:
                job["status"] = "cancelled"
                job["finished_at"] = datetime.utcnow().isoformat()
                return {
                    "success": True,
                    "message": "Job cancelled successfully"
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot cancel job with status: {job['status']}"
                )
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Job not found"
    )


# ============================================================================
# System Status API Routes
# ============================================================================

@app.get("/api/system/status")
async def get_system_status(request: Request):
    """
    Get current system resource status.
    Returns CPU, GPU, RAM usage and active job count.
    """
    # Verify authentication
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Calculate active jobs
    active_jobs = sum(1 for job in jobs_store if job["status"] in ["queued", "running"])
    
    # Return mock system status (in production, get real metrics)
    return {
        "success": True,
        "status": {
            "cpu_usage": random.uniform(15, 35),
            "gpu_usage": random.uniform(50, 80),
            "ram_usage": random.uniform(30, 50),
            "active_jobs": active_jobs,
            "gpu_available": True,
            "gpu_name": "NVIDIA RTX 4090",
            "total_ram_gb": 32.0
        }
    }


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
