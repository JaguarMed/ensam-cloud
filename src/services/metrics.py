"""
Prometheus metrics for monitoring.

Implements EF7: Measured service with metrics exposed at /metrics.

Metrics exposed:
- ensam_cloud_jobs_total: Total jobs by status
- ensam_cloud_jobs_running: Currently running jobs
- ensam_cloud_jobs_queued: Jobs in queue
- ensam_cloud_job_duration_seconds: Job duration histogram
- ensam_cloud_job_queue_time_seconds: Queue wait time histogram
- ensam_cloud_gpu_jobs_total: Total GPU jobs
- ensam_cloud_cpu_jobs_total: Total CPU jobs
"""

from prometheus_client import (
    Counter, Gauge, Histogram, Info,
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, REGISTRY
)
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from ..core.config import settings
from ..models import Job, JobStatus, User

logger = logging.getLogger(__name__)

# Metric prefix
PREFIX = settings.METRICS_PREFIX


class PrometheusMetrics:
    """
    Prometheus metrics collector for the cloud platform.
    """
    
    def __init__(self, registry=REGISTRY):
        self.registry = registry
        
        # Application info
        self.info = Info(
            f'{PREFIX}_app',
            'Application information',
            registry=registry
        )
        self.info.info({
            'version': settings.APP_VERSION,
            'name': settings.APP_NAME
        })
        
        # Job counters
        self.jobs_total = Counter(
            f'{PREFIX}_jobs_total',
            'Total number of jobs by status',
            ['status'],
            registry=registry
        )
        
        self.jobs_submitted = Counter(
            f'{PREFIX}_jobs_submitted_total',
            'Total jobs submitted',
            ['user_id', 'execution_mode'],
            registry=registry
        )
        
        # Current state gauges
        self.jobs_running = Gauge(
            f'{PREFIX}_jobs_running',
            'Number of currently running jobs',
            registry=registry
        )
        
        self.jobs_queued = Gauge(
            f'{PREFIX}_jobs_queued',
            'Number of jobs in queue',
            registry=registry
        )
        
        self.active_users = Gauge(
            f'{PREFIX}_active_users',
            'Number of users with jobs in last 24h',
            registry=registry
        )
        
        # Histograms for timing
        self.job_duration = Histogram(
            f'{PREFIX}_job_duration_seconds',
            'Job execution duration in seconds',
            ['execution_mode', 'resource_profile'],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 900, 1800],
            registry=registry
        )
        
        self.job_queue_time = Histogram(
            f'{PREFIX}_job_queue_time_seconds',
            'Time spent in queue before execution',
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
            registry=registry
        )
        
        # Resource usage
        self.gpu_jobs = Counter(
            f'{PREFIX}_gpu_jobs_total',
            'Total GPU jobs executed',
            registry=registry
        )
        
        self.cpu_jobs = Counter(
            f'{PREFIX}_cpu_jobs_total',
            'Total CPU-only jobs executed',
            registry=registry
        )
    
    def job_started(self, job: Job):
        """Record job start."""
        self.jobs_submitted.labels(
            user_id=str(job.user_id),
            execution_mode=job.execution_mode
        ).inc()
    
    def job_completed(self, job: Job):
        """Record job completion with metrics."""
        # Update status counter
        self.jobs_total.labels(status=job.status).inc()
        
        # Record duration
        if job.duration_seconds:
            self.job_duration.labels(
                execution_mode=job.execution_mode,
                resource_profile=job.resource_profile
            ).observe(job.duration_seconds)
        
        # Record queue time
        if job.queue_time_seconds:
            self.job_queue_time.observe(job.queue_time_seconds)
        
        # GPU vs CPU
        if job.gpu_used:
            self.gpu_jobs.inc()
        else:
            self.cpu_jobs.inc()
    
    def update_gauges(self, db: Session):
        """Update gauge metrics from database."""
        try:
            # Running jobs
            running = db.query(func.count(Job.id)).filter(
                Job.status == JobStatus.RUNNING.value
            ).scalar() or 0
            self.jobs_running.set(running)
            
            # Queued jobs
            queued = db.query(func.count(Job.id)).filter(
                Job.status.in_([JobStatus.PENDING.value, JobStatus.QUEUED.value])
            ).scalar() or 0
            self.jobs_queued.set(queued)
            
            # Active users (jobs in last 24h)
            from datetime import datetime, timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            active = db.query(func.count(func.distinct(Job.user_id))).filter(
                Job.created_at >= yesterday
            ).scalar() or 0
            self.active_users.set(active)
            
        except Exception as e:
            logger.warning(f"Failed to update gauge metrics: {e}")
    
    def get_metrics_text(self) -> str:
        """Generate Prometheus metrics text format."""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_summary(self, db: Session) -> dict:
        """Get metrics summary as dictionary."""
        try:
            total_jobs = db.query(func.count(Job.id)).scalar() or 0
            
            running = db.query(func.count(Job.id)).filter(
                Job.status == JobStatus.RUNNING.value
            ).scalar() or 0
            
            queued = db.query(func.count(Job.id)).filter(
                Job.status.in_([JobStatus.PENDING.value, JobStatus.QUEUED.value])
            ).scalar() or 0
            
            success = db.query(func.count(Job.id)).filter(
                Job.status == JobStatus.SUCCESS.value
            ).scalar() or 0
            
            failed = db.query(func.count(Job.id)).filter(
                Job.status == JobStatus.FAILED.value
            ).scalar() or 0
            
            gpu_jobs = db.query(func.count(Job.id)).filter(
                Job.gpu_used == True
            ).scalar() or 0
            
            avg_duration = db.query(func.avg(Job.duration_seconds)).filter(
                Job.duration_seconds.isnot(None)
            ).scalar() or 0.0
            
            return {
                "total_jobs": total_jobs,
                "running_jobs": running,
                "queued_jobs": queued,
                "successful_jobs": success,
                "failed_jobs": failed,
                "gpu_jobs": gpu_jobs,
                "cpu_jobs": total_jobs - gpu_jobs,
                "avg_duration_seconds": round(avg_duration, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {}


# Global metrics instance
metrics = PrometheusMetrics()








