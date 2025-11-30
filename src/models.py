"""
SQLAlchemy database models for ENSAM Cloud Platform.

Models:
- User: User accounts with authentication
- Job: Script execution jobs with full tracking
- JobMetrics: Resource usage metrics per job
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    Float, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from .core.database import Base


class JobStatus(str, enum.Enum):
    """Enumeration of possible job statuses."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionMode(str, enum.Enum):
    """Execution mode for jobs."""
    CPU = "cpu"
    GPU = "gpu"


class ResourceProfile(str, enum.Enum):
    """Resource allocation profiles."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    GPU = "gpu"


class User(Base):
    """
    User model for authentication and job ownership.
    
    Implements EF1: User authentication with secure credential storage.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    jobs = relationship("Job", back_populates="owner", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Job(Base):
    """
    Job model representing a script execution task.
    
    Implements:
    - EF2: Script submission tracking
    - EF3: Resource limits configuration
    - EF4: GPU mode tracking
    - EF6: Full job history with all required fields
    """
    __tablename__ = "jobs"
    
    # Primary key and ownership
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Script information
    script_name = Column(String(255), nullable=False, default="script.py")
    script_content = Column(Text, nullable=True)
    
    # Execution configuration
    status = Column(String(50), default=JobStatus.PENDING.value, index=True)
    execution_mode = Column(String(10), default=ExecutionMode.CPU.value)
    resource_profile = Column(String(20), default=ResourceProfile.MEDIUM.value)
    timeout_seconds = Column(Integer, default=300)
    
    # Docker container tracking
    container_id = Column(String(100), nullable=True)
    
    # Timestamps (EF6 requirement)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    queued_at = Column(DateTime(timezone=True), nullable=True)
    
    # Duration tracking
    duration_seconds = Column(Float, nullable=True)
    queue_time_seconds = Column(Float, nullable=True)
    
    # Results and output
    gpu_used = Column(Boolean, default=False)
    exit_code = Column(Integer, nullable=True)
    logs_location = Column(String(500), nullable=True)
    results_location = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Auto-allocation tracking
    auto_allocated = Column(Boolean, default=False)
    analysis_reasoning = Column(Text, nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="jobs")
    metrics = relationship("JobMetrics", back_populates="job", uselist=False, cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_jobs_user_status', 'user_id', 'status'),
        Index('ix_jobs_created_at_desc', created_at.desc()),
    )
    
    def __repr__(self):
        return f"<Job(id={self.id}, status='{self.status}', user_id={self.user_id})>"
    
    @property
    def is_running(self) -> bool:
        """Check if the job is currently running."""
        return self.status in [JobStatus.RUNNING.value, JobStatus.QUEUED.value]
    
    @property
    def is_finished(self) -> bool:
        """Check if the job has finished."""
        return self.status in [
            JobStatus.SUCCESS.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
            JobStatus.TIMEOUT.value
        ]
    
    @property
    def is_cancellable(self) -> bool:
        """Check if the job can be cancelled."""
        return self.status in [
            JobStatus.PENDING.value,
            JobStatus.QUEUED.value,
            JobStatus.RUNNING.value
        ]
    
    def to_dict(self):
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "job_id": str(self.id),  # For compatibility
            "user_id": self.user_id,
            "script_name": self.script_name,
            "status": self.status,
            "execution_mode": self.execution_mode,
            "resource_profile": self.resource_profile,
            "timeout_seconds": self.timeout_seconds,
            "container_id": self.container_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "queue_time_seconds": self.queue_time_seconds,
            "gpu_used": self.gpu_used,
            "exit_code": self.exit_code,
            "logs_location": self.logs_location,
            "results_location": self.results_location,
            "error_message": self.error_message,
            "auto_allocated": self.auto_allocated,
            "analysis_reasoning": self.analysis_reasoning
        }


class JobMetrics(Base):
    """
    Resource usage metrics for a job execution.
    
    Implements EF7: Measured service with per-job metrics.
    """
    __tablename__ = "job_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    
    # CPU metrics
    cpu_seconds = Column(Float, default=0.0)
    avg_cpu_percent = Column(Float, default=0.0)
    max_cpu_percent = Column(Float, default=0.0)
    
    # Memory metrics
    peak_ram_mb = Column(Float, default=0.0)
    avg_ram_mb = Column(Float, default=0.0)
    
    # GPU metrics
    gpu_seconds = Column(Float, default=0.0)
    avg_gpu_percent = Column(Float, default=0.0)
    max_gpu_percent = Column(Float, default=0.0)
    peak_gpu_memory_mb = Column(Float, default=0.0)
    
    # I/O metrics
    network_rx_bytes = Column(Integer, default=0)
    network_tx_bytes = Column(Integer, default=0)
    disk_read_bytes = Column(Integer, default=0)
    disk_write_bytes = Column(Integer, default=0)
    
    # Timestamps
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="metrics")
    
    def __repr__(self):
        return f"<JobMetrics(job_id={self.job_id}, cpu_seconds={self.cpu_seconds})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "cpu_seconds": self.cpu_seconds,
            "avg_cpu_percent": self.avg_cpu_percent,
            "max_cpu_percent": self.max_cpu_percent,
            "peak_ram_mb": self.peak_ram_mb,
            "avg_ram_mb": self.avg_ram_mb,
            "gpu_seconds": self.gpu_seconds,
            "avg_gpu_percent": self.avg_gpu_percent,
            "max_gpu_percent": self.max_gpu_percent,
            "peak_gpu_memory_mb": self.peak_gpu_memory_mb,
            "network_rx_bytes": self.network_rx_bytes,
            "network_tx_bytes": self.network_tx_bytes,
            "disk_read_bytes": self.disk_read_bytes,
            "disk_write_bytes": self.disk_write_bytes,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None
        }


