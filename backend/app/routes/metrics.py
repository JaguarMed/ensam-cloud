"""
Metrics routes for resource usage monitoring.
Implements EF7 - Measured Service / Metrics.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from ..core.database import get_db
from ..core.security import get_current_user
from ..models import User, Job, JobStatus, JobMetrics
from ..schemas import (
    JobMetricsResponse,
    UserMetricsSummary,
    SystemMetrics
)

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/jobs", response_model=List[JobMetricsResponse])
async def get_all_job_metrics(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get metrics for all jobs belonging to the current user.
    
    Parameters:
    - **limit**: Maximum number of records to return (default: 50)
    """
    metrics = db.query(JobMetrics)\
        .join(Job)\
        .filter(Job.user_id == current_user.id)\
        .order_by(JobMetrics.collected_at.desc())\
        .limit(limit)\
        .all()
    
    return [JobMetricsResponse.model_validate(m) for m in metrics]


@router.get("/jobs/{job_id}", response_model=JobMetricsResponse)
async def get_job_metrics(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed metrics for a specific job.
    """
    metrics = db.query(JobMetrics)\
        .join(Job)\
        .filter(
            JobMetrics.job_id == job_id,
            Job.user_id == current_user.id
        )\
        .first()
    
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metrics not found for this job"
        )
    
    return JobMetricsResponse.model_validate(metrics)


@router.get("/summary", response_model=UserMetricsSummary)
async def get_user_metrics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a summary of resource usage for the current user.
    
    Includes:
    - Total jobs count
    - Success/failure counts
    - Total CPU and GPU time
    - Average job duration
    """
    # Get job counts
    total_jobs = db.query(func.count(Job.id))\
        .filter(Job.user_id == current_user.id)\
        .scalar() or 0
    
    successful_jobs = db.query(func.count(Job.id))\
        .filter(
            Job.user_id == current_user.id,
            Job.status == JobStatus.SUCCESS.value
        )\
        .scalar() or 0
    
    failed_jobs = db.query(func.count(Job.id))\
        .filter(
            Job.user_id == current_user.id,
            Job.status == JobStatus.FAILED.value
        )\
        .scalar() or 0
    
    # Get aggregated metrics
    metrics_agg = db.query(
        func.sum(JobMetrics.cpu_seconds).label("total_cpu"),
        func.sum(JobMetrics.gpu_seconds).label("total_gpu"),
        func.sum(JobMetrics.peak_ram_mb).label("total_ram")
    ).join(Job).filter(Job.user_id == current_user.id).first()
    
    # Get average duration
    avg_duration = db.query(func.avg(Job.duration_seconds))\
        .filter(
            Job.user_id == current_user.id,
            Job.duration_seconds.isnot(None)
        )\
        .scalar() or 0.0
    
    return UserMetricsSummary(
        user_id=current_user.id,
        total_jobs=total_jobs,
        successful_jobs=successful_jobs,
        failed_jobs=failed_jobs,
        total_cpu_seconds=metrics_agg.total_cpu or 0.0,
        total_gpu_seconds=metrics_agg.total_gpu or 0.0,
        total_ram_mb_hours=(metrics_agg.total_ram or 0.0) / 60,  # Convert to MB-hours
        avg_job_duration=avg_duration
    )


@router.get("/system", response_model=SystemMetrics)
async def get_system_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get system-wide metrics.
    
    Note: This endpoint may be restricted to admin users in production.
    Currently shows basic stats for all users.
    """
    # Get counts
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    
    running_jobs = db.query(func.count(Job.id))\
        .filter(Job.status == JobStatus.RUNNING.value)\
        .scalar() or 0
    
    queued_jobs = db.query(func.count(Job.id))\
        .filter(Job.status.in_([JobStatus.PENDING.value, JobStatus.QUEUED.value]))\
        .scalar() or 0
    
    # TODO: Get actual system utilization from Prometheus/cAdvisor
    # For now, return placeholder values
    cpu_utilization = 0.0
    gpu_utilization = 0.0
    memory_utilization = 0.0
    
    # Try to get real metrics from Docker if available
    try:
        from ..executor import executor
        # This would integrate with Prometheus/cAdvisor in production
        pass
    except Exception:
        pass
    
    return SystemMetrics(
        total_users=total_users,
        total_jobs=total_jobs,
        running_jobs=running_jobs,
        queued_jobs=queued_jobs,
        cpu_utilization=cpu_utilization,
        gpu_utilization=gpu_utilization,
        memory_utilization=memory_utilization
    )


@router.get("/prometheus")
async def prometheus_metrics():
    """
    Expose metrics in Prometheus format.
    
    This endpoint can be scraped by Prometheus for monitoring.
    """
    # TODO: Implement Prometheus metrics export using prometheus_client
    # Example metrics:
    # - jaguarmed_jobs_total{status="success|failed|running"}
    # - jaguarmed_job_duration_seconds
    # - jaguarmed_active_users
    
    metrics_output = """
# HELP jaguarmed_jobs_total Total number of jobs
# TYPE jaguarmed_jobs_total counter
jaguarmed_jobs_total{status="pending"} 0
jaguarmed_jobs_total{status="running"} 0
jaguarmed_jobs_total{status="success"} 0
jaguarmed_jobs_total{status="failed"} 0

# HELP jaguarmed_active_containers Number of active Docker containers
# TYPE jaguarmed_active_containers gauge
jaguarmed_active_containers 0
"""
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=metrics_output, media_type="text/plain")








