"""
Metrics routes for monitoring and Prometheus integration.

Implements EF7: Measured service with per-user and per-job metrics.
"""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

from ...core.config import settings
from ...core.database import get_db
from ...core.security import get_current_user, get_current_user_optional
from ...models import User, Job, JobStatus, JobMetrics
from ...schemas import UserMetricsSummary, SystemMetricsResponse
from ...services.metrics import metrics as prometheus_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


@router.get("/", response_class=PlainTextResponse)
async def prometheus_metrics_endpoint(db: Session = Depends(get_db)):
    """
    Prometheus metrics endpoint.
    
    Exposes metrics in Prometheus text format for scraping.
    This endpoint is public for Prometheus access.
    
    Metrics exposed:
    - ensam_cloud_jobs_total{status}
    - ensam_cloud_jobs_running
    - ensam_cloud_jobs_queued
    - ensam_cloud_job_duration_seconds
    - ensam_cloud_active_users
    """
    # Update gauge metrics from database
    prometheus_metrics.update_gauges(db)
    
    # Generate Prometheus format
    return Response(
        content=prometheus_metrics.get_metrics_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@router.get("/summary")
async def get_metrics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get metrics summary for dashboard.
    """
    summary = prometheus_metrics.get_summary(db)
    return {
        "success": True,
        "metrics": summary
    }


@router.get("/user", response_model=UserMetricsSummary)
async def get_user_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get resource usage summary for the current user.
    
    Includes:
    - Total jobs count
    - Success/failure/cancelled counts
    - Total CPU and GPU time
    - Average job duration
    """
    # Job counts by status
    total_jobs = db.query(func.count(Job.id)).filter(
        Job.user_id == current_user.id
    ).scalar() or 0
    
    successful = db.query(func.count(Job.id)).filter(
        Job.user_id == current_user.id,
        Job.status == JobStatus.SUCCESS.value
    ).scalar() or 0
    
    failed = db.query(func.count(Job.id)).filter(
        Job.user_id == current_user.id,
        Job.status == JobStatus.FAILED.value
    ).scalar() or 0
    
    cancelled = db.query(func.count(Job.id)).filter(
        Job.user_id == current_user.id,
        Job.status == JobStatus.CANCELLED.value
    ).scalar() or 0
    
    # Aggregated metrics
    metrics_agg = db.query(
        func.sum(JobMetrics.cpu_seconds).label("cpu"),
        func.sum(JobMetrics.gpu_seconds).label("gpu")
    ).join(Job).filter(Job.user_id == current_user.id).first()
    
    # Duration stats
    duration_stats = db.query(
        func.sum(Job.duration_seconds).label("total"),
        func.avg(Job.duration_seconds).label("avg")
    ).filter(
        Job.user_id == current_user.id,
        Job.duration_seconds.isnot(None)
    ).first()
    
    return UserMetricsSummary(
        user_id=current_user.id,
        total_jobs=total_jobs,
        successful_jobs=successful,
        failed_jobs=failed,
        cancelled_jobs=cancelled,
        total_cpu_seconds=metrics_agg.cpu or 0.0,
        total_gpu_seconds=metrics_agg.gpu or 0.0,
        total_duration_seconds=duration_stats.total or 0.0,
        avg_job_duration=duration_stats.avg or 0.0
    )


@router.get("/system", response_model=SystemMetricsResponse)
async def get_system_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get system-wide metrics.
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    
    running = db.query(func.count(Job.id)).filter(
        Job.status == JobStatus.RUNNING.value
    ).scalar() or 0
    
    queued = db.query(func.count(Job.id)).filter(
        Job.status.in_([JobStatus.PENDING.value, JobStatus.QUEUED.value])
    ).scalar() or 0
    
    jobs_today = db.query(func.count(Job.id)).filter(
        Job.created_at >= today
    ).scalar() or 0
    
    cpu_jobs = db.query(func.count(Job.id)).filter(
        Job.execution_mode == "cpu"
    ).scalar() or 0
    
    gpu_jobs = db.query(func.count(Job.id)).filter(
        Job.execution_mode == "gpu"
    ).scalar() or 0
    
    return SystemMetricsResponse(
        total_users=total_users,
        total_jobs=total_jobs,
        running_jobs=running,
        queued_jobs=queued,
        jobs_today=jobs_today,
        cpu_jobs=cpu_jobs,
        gpu_jobs=gpu_jobs
    )


@router.get("/jobs/{job_id}")
async def get_job_metrics(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed metrics for a specific job.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    metrics = job.metrics
    
    return {
        "success": True,
        "job_id": job_id,
        "job_status": job.status,
        "duration_seconds": job.duration_seconds,
        "queue_time_seconds": job.queue_time_seconds,
        "metrics": metrics.to_dict() if metrics else None
    }








