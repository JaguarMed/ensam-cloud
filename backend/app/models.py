"""
SQLAlchemy database models for JaguarMed Private Cloud.

Models:
- User: User accounts with authentication
- Job: Script execution jobs with status tracking
- JobMetrics: Resource usage metrics for each job
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Enum
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


class User(Base):
    """
    User model for authentication and job ownership.
    
    Attributes:
        id: Primary key
        email: Unique email address for login
        password_hash: Bcrypt hashed password
        full_name: User's display name
        is_active: Whether the account is enabled
        is_admin: Whether the user has admin privileges
        created_at: Account creation timestamp
        updated_at: Last update timestamp
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
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class Job(Base):
    """
    Job model representing a script execution task.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to the user who submitted the job
        script_name: Name of the script file
        script_content: The actual Python code (stored for reference)
        status: Current job status (pending, running, success, failed, cancelled)
        execution_mode: CPU or GPU execution
        resource_profile: Resource allocation (small, medium, large)
        timeout_seconds: Maximum execution time allowed
        container_id: Docker container ID (when running)
        created_at: Job submission timestamp
        started_at: Execution start timestamp
        finished_at: Execution end timestamp
        duration_seconds: Total execution time
        gpu_used: Whether GPU was actually used
        logs_location: Path to log file
        results_location: Path to results directory
        exit_code: Container exit code
        error_message: Error message if failed
    """
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Script information
    script_name = Column(String(255), nullable=False)
    script_content = Column(Text, nullable=True)
    
    # Execution configuration
    status = Column(String(50), default=JobStatus.PENDING.value, index=True)
    execution_mode = Column(String(10), default=ExecutionMode.CPU.value)
    resource_profile = Column(String(20), default=ResourceProfile.MEDIUM.value)
    timeout_seconds = Column(Integer, default=300)
    
    # Docker information
    container_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Results
    gpu_used = Column(Boolean, default=False)
    logs_location = Column(String(500), nullable=True)
    results_location = Column(String(500), nullable=True)
    exit_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    metrics = relationship("JobMetrics", back_populates="job", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Job(id={self.id}, status='{self.status}', user_id={self.user_id})>"
    
    @property
    def is_running(self) -> bool:
        """Check if the job is currently running."""
        return self.status in [JobStatus.RUNNING.value, JobStatus.QUEUED.value]
    
    @property
    def is_finished(self) -> bool:
        """Check if the job has finished (success, failed, cancelled, or timeout)."""
        return self.status in [
            JobStatus.SUCCESS.value, 
            JobStatus.FAILED.value, 
            JobStatus.CANCELLED.value,
            JobStatus.TIMEOUT.value
        ]


class JobMetrics(Base):
    """
    Resource usage metrics for a job execution.
    
    Attributes:
        id: Primary key
        job_id: Foreign key to the job
        cpu_seconds: Total CPU time used
        gpu_seconds: Total GPU time used (if applicable)
        peak_ram_mb: Peak RAM usage in megabytes
        avg_cpu_percent: Average CPU utilization percentage
        avg_gpu_percent: Average GPU utilization percentage (if applicable)
        gpu_memory_mb: Peak GPU memory usage in megabytes
        network_rx_bytes: Network bytes received
        network_tx_bytes: Network bytes transmitted
        disk_read_bytes: Disk bytes read
        disk_write_bytes: Disk bytes written
    """
    __tablename__ = "job_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    
    # CPU metrics
    cpu_seconds = Column(Float, default=0.0)
    avg_cpu_percent = Column(Float, default=0.0)
    
    # Memory metrics
    peak_ram_mb = Column(Float, default=0.0)
    
    # GPU metrics (if applicable)
    gpu_seconds = Column(Float, default=0.0)
    avg_gpu_percent = Column(Float, default=0.0)
    gpu_memory_mb = Column(Float, default=0.0)
    
    # Network I/O
    network_rx_bytes = Column(Integer, default=0)
    network_tx_bytes = Column(Integer, default=0)
    
    # Disk I/O
    disk_read_bytes = Column(Integer, default=0)
    disk_write_bytes = Column(Integer, default=0)
    
    # Timestamps
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="metrics")
    
    def __repr__(self):
        return f"<JobMetrics(job_id={self.job_id}, cpu_seconds={self.cpu_seconds})>"








