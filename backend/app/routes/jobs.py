"""
Job management routes.
Implements EF2 (Script Submission), EF6 (Job History), EF8 (Job Cancellation).
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime
import os

from ..core.database import get_db
from ..core.security import get_current_user
from ..core.config import settings
from ..models import User, Job, JobStatus, JobMetrics
from ..schemas import (
    JobSubmitRequest,
    JobResponse,
    JobDetailResponse,
    JobListResponse,
    JobMetricsResponse,
    SuccessResponse,
    ExecutionModeEnum,
    ResourceProfileEnum
)
from ..executor import executor, run_job_async

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def submit_job(
    background_tasks: BackgroundTasks,
    code: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    script_name: str = Form(default="script.py"),
    execution_mode: str = Form(default="cpu"),
    resource_profile: str = Form(default="medium"),
    timeout: int = Form(default=300),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a new Python script for execution.
    
    You can either:
    - Paste code directly in the `code` field, OR
    - Upload a `.py` file
    
    Parameters:
    - **code**: Python code as text (optional if file is provided)
    - **file**: Python file upload (optional if code is provided)
    - **script_name**: Name for the script (default: script.py)
    - **execution_mode**: "cpu" or "gpu"
    - **resource_profile**: "small", "medium", or "large"
    - **timeout**: Maximum execution time in seconds (10-3600)
    """
    # Validate input
    script_content = None
    
    if file and file.filename:
        if not file.filename.endswith(".py"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .py files are allowed"
            )
        content = await file.read()
        script_content = content.decode("utf-8")
        script_name = file.filename
    elif code:
        script_content = code
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either code or file must be provided"
        )
    
    # Validate execution mode
    if execution_mode not in ["cpu", "gpu"]:
        execution_mode = "cpu"
    
    # Validate resource profile
    if resource_profile not in ["small", "medium", "large"]:
        resource_profile = "medium"
    
    # Validate timeout
    timeout = max(10, min(timeout, 3600))
    
    # Ensure script_name ends with .py
    if not script_name.endswith(".py"):
        script_name = script_name + ".py"
    
    # Create job record
    job = Job(
        user_id=current_user.id,
        script_name=script_name,
        script_content=script_content,
        status=JobStatus.PENDING.value,
        execution_mode=execution_mode,
        resource_profile=resource_profile,
        timeout_seconds=timeout,
        gpu_used=False
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Schedule job execution in background
    background_tasks.add_task(run_job_in_background, job.id)
    
    return JobResponse.model_validate(job)


async def run_job_in_background(job_id: int):
    """Run job execution in background task."""
    from ..core.database import SessionLocal
    
    db = SessionLocal()
    try:
        await run_job_async(job_id, db)
    finally:
        db.close()


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List jobs for the current user with pagination and filtering.
    
    Parameters:
    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    - **status_filter**: Filter by status (pending, running, success, failed, cancelled)
    - **search**: Search in script name
    """
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page
    
    # Base query
    query = db.query(Job).filter(Job.user_id == current_user.id)
    
    # Apply filters
    if status_filter:
        query = query.filter(Job.status == status_filter)
    
    if search:
        query = query.filter(Job.script_name.ilike(f"%{search}%"))
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    jobs = query.order_by(desc(Job.created_at)).offset(offset).limit(per_page).all()
    
    # Calculate pages
    pages = (total + per_page - 1) // per_page
    
    return JobListResponse(
        jobs=[JobResponse.model_validate(job) for job in jobs],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/recent", response_model=List[JobResponse])
async def get_recent_jobs(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the most recent jobs for the current user.
    Useful for the dashboard quick view.
    """
    limit = min(limit, 20)
    
    jobs = db.query(Job)\
        .filter(Job.user_id == current_user.id)\
        .order_by(desc(Job.created_at))\
        .limit(limit)\
        .all()
    
    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific job.
    Includes script content and metrics if available.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    response = JobDetailResponse.model_validate(job)
    
    # Include metrics if available
    if job.metrics:
        response.metrics = JobMetricsResponse.model_validate(job.metrics)
    
    return response


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: int,
    tail: int = 1000,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get logs for a specific job.
    
    Parameters:
    - **tail**: Number of lines from the end (default: 1000)
    
    Returns logs from file if job is finished, or from container if running.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    logs = ""
    
    # If job is running, get logs from container
    if job.status == JobStatus.RUNNING.value:
        container_logs = executor.get_container_logs(job_id, tail=tail)
        if container_logs:
            logs = container_logs
    
    # If job is finished, read from log file
    elif job.logs_location and os.path.exists(job.logs_location):
        with open(job.logs_location, "r", encoding="utf-8") as f:
            lines = f.readlines()
            logs = "".join(lines[-tail:])
    
    return {
        "job_id": job_id,
        "status": job.status,
        "logs": logs
    }


@router.post("/{job_id}/cancel", response_model=SuccessResponse)
async def cancel_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a running or pending job.
    
    This will:
    - Stop the Docker container if running
    - Update job status to CANCELLED
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status not in [JobStatus.PENDING.value, JobStatus.RUNNING.value, JobStatus.QUEUED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}"
        )
    
    # Try to stop container if running
    if job.status == JobStatus.RUNNING.value:
        cancelled = await executor.cancel_job(job_id)
        if not cancelled:
            # Container might have already finished
            pass
    
    # Update job status
    job.status = JobStatus.CANCELLED.value
    job.finished_at = datetime.utcnow()
    if job.started_at:
        job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
    
    db.commit()
    
    return SuccessResponse(
        success=True,
        message=f"Job {job_id} has been cancelled"
    )


@router.delete("/{job_id}", response_model=SuccessResponse)
async def delete_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a job and its associated files.
    Only finished jobs can be deleted.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status in [JobStatus.RUNNING.value, JobStatus.QUEUED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running job. Cancel it first."
        )
    
    # Delete job files
    import shutil
    job_dir = os.path.join(settings.SCRIPTS_DIR, str(job_id))
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
    
    # Delete from database
    db.delete(job)
    db.commit()
    
    return SuccessResponse(
        success=True,
        message=f"Job {job_id} has been deleted"
    )








