"""
Admin routes for managing users and viewing all jobs.

Requires admin privileges for all endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import logging

from ...core.config import settings
from ...core.database import get_db
from ...core.security import get_current_user, get_password_hash
from ...models import User, Job, JobStatus
from ...schemas import RegisterRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


@router.get("/stats")
async def get_admin_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get global statistics for admin dashboard."""
    total_users = db.query(func.count(User.id)).scalar()
    total_jobs = db.query(func.count(Job.id)).scalar()
    
    running_jobs = db.query(func.count(Job.id)).filter(
        Job.status.in_([JobStatus.RUNNING.value, JobStatus.QUEUED.value, JobStatus.PENDING.value])
    ).scalar()
    
    success_jobs = db.query(func.count(Job.id)).filter(
        Job.status == JobStatus.SUCCESS.value
    ).scalar()
    
    failed_jobs = db.query(func.count(Job.id)).filter(
        Job.status.in_([JobStatus.FAILED.value, JobStatus.TIMEOUT.value])
    ).scalar()
    
    completed_jobs = success_jobs + failed_jobs
    success_rate = round((success_jobs / completed_jobs * 100) if completed_jobs > 0 else 0, 1)
    
    # GPU usage stats
    gpu_jobs = db.query(func.count(Job.id)).filter(Job.gpu_used == True).scalar()
    
    return {
        "success": True,
        "total_users": total_users,
        "total_jobs": total_jobs,
        "running_jobs": running_jobs,
        "success_jobs": success_jobs,
        "failed_jobs": failed_jobs,
        "success_rate": success_rate,
        "gpu_jobs": gpu_jobs
    }


@router.get("/users")
async def get_all_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all users with their job counts."""
    users = db.query(User).all()
    
    result = []
    for user in users:
        job_count = db.query(func.count(Job.id)).filter(Job.user_id == user.id).scalar()
        user_dict = user.to_dict()
        user_dict["job_count"] = job_count
        result.append(user_dict)
    
    return {
        "success": True,
        "users": result,
        "total": len(result)
    }


@router.post("/users")
async def create_user(
    request: RegisterRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new user (admin only)."""
    # Check if email already exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        full_name=request.full_name,
        is_active=True,
        is_admin=getattr(request, 'is_admin', False)
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"Admin {admin.email} created user: {user.email}")
    
    return {
        "success": True,
        "message": f"User {user.email} created successfully",
        "user": user.to_dict()
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get a specific user's details."""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    job_count = db.query(func.count(Job.id)).filter(Job.user_id == user.id).scalar()
    user_dict = user.to_dict()
    user_dict["job_count"] = job_count
    
    return {
        "success": True,
        "user": user_dict
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    password: Optional[str] = None,
    is_admin: Optional[bool] = None,
    is_active: Optional[bool] = None
):
    """Update a user's information."""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if trying to modify own admin status
    if user.id == admin.id and is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin privileges"
        )
    
    # Update fields
    if email and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        user.email = email
    
    if full_name is not None:
        user.full_name = full_name
    
    if password:
        user.password_hash = get_password_hash(password)
    
    if is_admin is not None:
        user.is_admin = is_admin
    
    if is_active is not None:
        user.is_active = is_active
    
    db.commit()
    db.refresh(user)
    
    logger.info(f"Admin {admin.email} updated user: {user.email}")
    
    return {
        "success": True,
        "message": f"User {user.email} updated",
        "user": user.to_dict()
    }


@router.post("/users/{user_id}/toggle")
async def toggle_user_status(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Toggle user active status."""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account"
        )
    
    user.is_active = not user.is_active
    db.commit()
    
    status_text = "activated" if user.is_active else "deactivated"
    logger.info(f"Admin {admin.email} {status_text} user: {user.email}")
    
    return {
        "success": True,
        "message": f"User {user.email} {status_text}",
        "is_active": user.is_active
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a user and all their jobs."""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    email = user.email
    db.delete(user)
    db.commit()
    
    logger.info(f"Admin {admin.email} deleted user: {email}")
    
    return {
        "success": True,
        "message": f"User {email} deleted"
    }


@router.get("/jobs")
async def get_all_jobs(
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[str] = None,
    user_id: Optional[int] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all jobs from all users."""
    query = db.query(Job)
    
    if status_filter:
        query = query.filter(Job.status == status_filter)
    
    if user_id:
        query = query.filter(Job.user_id == user_id)
    
    total = query.count()
    jobs = query.order_by(Job.created_at.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()
    
    # Get user emails for display
    user_ids = list(set(job.user_id for job in jobs))
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    user_map = {u.id: u.email for u in users}
    
    result = []
    for job in jobs:
        job_dict = job.to_dict()
        job_dict["user_email"] = user_map.get(job.user_id, "Unknown")
        result.append(job_dict)
    
    return {
        "success": True,
        "jobs": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_admin(
    job_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Cancel any job (admin only)."""
    from ...services.executor import executor
    
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if not job.is_cancellable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job cannot be cancelled (status: {job.status})"
        )
    
    # Try to cancel via executor (even if not running, try to clean up)
    try:
        cancelled = await executor.cancel_job(job_id)
        if not cancelled:
            logger.warning(f"Container for job {job_id} not found or already stopped")
    except Exception as e:
        logger.warning(f"Error stopping container for job {job_id}: {e}")
        # Continue anyway to update status
    
    # Update job status
    job.status = JobStatus.CANCELLED.value
    job.finished_at = datetime.utcnow()
    if job.started_at:
        job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
    job.error_message = f"Cancelled by admin: {admin.email}"
    db.commit()
    
    logger.info(f"Admin {admin.email} cancelled job #{job_id}")
    
    return {
        "success": True,
        "message": f"Job #{job_id} cancelled"
    }


@router.get("/monitoring/charts")
async def get_monitoring_charts(
    days: int = 7,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get data for monitoring charts."""
    from datetime import datetime, timedelta
    from sqlalchemy import cast, Date
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Jobs per day
    jobs_per_day = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        count = db.query(func.count(Job.id)).filter(
            Job.created_at >= day_start,
            Job.created_at < day_end
        ).scalar()
        
        success_count = db.query(func.count(Job.id)).filter(
            Job.created_at >= day_start,
            Job.created_at < day_end,
            Job.status == JobStatus.SUCCESS.value
        ).scalar()
        
        failed_count = db.query(func.count(Job.id)).filter(
            Job.created_at >= day_start,
            Job.created_at < day_end,
            Job.status.in_([JobStatus.FAILED.value, JobStatus.TIMEOUT.value])
        ).scalar()
        
        jobs_per_day.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "label": day_start.strftime("%d/%m"),
            "total": count,
            "success": success_count,
            "failed": failed_count
        })
    
    # Jobs by status (pie chart)
    status_counts = {}
    for status in JobStatus:
        count = db.query(func.count(Job.id)).filter(Job.status == status.value).scalar()
        if count > 0:
            status_counts[status.value] = count
    
    # Jobs by execution mode
    cpu_jobs = db.query(func.count(Job.id)).filter(Job.execution_mode == 'cpu').scalar()
    gpu_jobs = db.query(func.count(Job.id)).filter(Job.execution_mode == 'gpu').scalar()
    auto_jobs = db.query(func.count(Job.id)).filter(Job.execution_mode == 'auto').scalar()
    
    # Average execution time per day
    avg_time_per_day = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        avg_time = db.query(func.avg(Job.duration_seconds)).filter(
            Job.created_at >= day_start,
            Job.created_at < day_end,
            Job.duration_seconds.isnot(None)
        ).scalar()
        
        avg_time_per_day.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "label": day_start.strftime("%d/%m"),
            "avg_time": round(avg_time, 2) if avg_time else 0
        })
    
    # Top users by job count
    top_users = db.query(
        User.email,
        func.count(Job.id).label('job_count')
    ).join(Job, User.id == Job.user_id)\
     .group_by(User.id)\
     .order_by(func.count(Job.id).desc())\
     .limit(5)\
     .all()
    
    top_users_data = [{"email": u[0], "jobs": u[1]} for u in top_users]
    
    # Resource usage (simulated for now - in real app, get from Prometheus)
    import random
    resource_history = []
    for i in range(24):  # Last 24 hours
        hour = end_date - timedelta(hours=23-i)
        resource_history.append({
            "time": hour.strftime("%H:00"),
            "cpu": random.randint(10, 60),
            "ram": random.randint(20, 70),
            "gpu": random.randint(0, 40) if gpu_jobs > 0 else 0
        })
    
    return {
        "success": True,
        "jobs_per_day": jobs_per_day,
        "status_distribution": status_counts,
        "mode_distribution": {
            "cpu": cpu_jobs,
            "gpu": gpu_jobs,
            "auto": auto_jobs
        },
        "avg_time_per_day": avg_time_per_day,
        "top_users": top_users_data,
        "resource_history": resource_history
    }


@router.get("/monitoring/realtime")
async def get_realtime_metrics(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get real-time system metrics."""
    import random
    from ...services.executor import executor
    
    # Get running jobs count
    running_jobs = db.query(func.count(Job.id)).filter(
        Job.status.in_([JobStatus.RUNNING.value, JobStatus.QUEUED.value])
    ).scalar()
    
    # Simulated metrics (in production, get from system/Docker)
    cpu_usage = random.randint(15, 55) + (running_jobs * 5)
    ram_usage = random.randint(25, 45) + (running_jobs * 8)
    gpu_usage = random.randint(10, 40) if executor.gpu_available and running_jobs > 0 else 0
    
    # Limit to 100%
    cpu_usage = min(cpu_usage, 100)
    ram_usage = min(ram_usage, 100)
    gpu_usage = min(gpu_usage, 100)
    
    return {
        "success": True,
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage,
        "gpu_usage": gpu_usage,
        "running_containers": running_jobs,
        "docker_available": executor.is_available,
        "gpu_available": executor.gpu_available,
        "timestamp": datetime.utcnow().isoformat()
    }


from datetime import datetime


