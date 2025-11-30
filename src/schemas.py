"""
Pydantic schemas for request/response validation.
Defines the API contract for all endpoints.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Any
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class JobStatusEnum(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionModeEnum(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    AUTO = "auto"  # Let the system decide


class ResourceProfileEnum(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    GPU = "gpu"
    AUTO = "auto"  # Let the system decide based on script analysis


# =============================================================================
# Authentication Schemas
# =============================================================================

class LoginRequest(BaseModel):
    """Login request payload."""
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Login response with JWT token."""
    success: bool = True
    token: str
    user: dict
    expires_in: int
    message: str = "Login successful"


class RegisterRequest(BaseModel):
    """User registration request."""
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)


class UserResponse(BaseModel):
    """User response schema."""
    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Job Schemas
# =============================================================================

class JobSubmitRequest(BaseModel):
    """Request to submit a new job."""
    code: str = Field(..., min_length=1, description="Python code to execute")
    script_name: str = Field(default="script.py", max_length=255)
    execution_mode: ExecutionModeEnum = Field(default=ExecutionModeEnum.AUTO)  # Auto by default
    resource_profile: ResourceProfileEnum = Field(default=ResourceProfileEnum.AUTO)  # Auto by default
    timeout: int = Field(default=300, ge=10, le=3600)
    gpu_enabled: bool = Field(default=False)  # Alias for compatibility
    custom_config: Optional[Dict[str, Any]] = Field(default=None, description="Custom resource configuration (memory_mb, cpu_shares, timeout)")


class JobSubmitResponse(BaseModel):
    """Response after submitting a job."""
    success: bool = True
    job_id: int
    status: str
    message: str = "Job submitted successfully"


class ScriptAnalysisResponse(BaseModel):
    """Response from script analysis for auto-allocation."""
    recommended_profile: str
    execution_mode: str
    detected_libraries: List[str]
    gpu_indicators: List[str]
    memory_indicators: List[str]
    compute_indicators: List[str]
    confidence: float
    reasoning: str


class JobResponse(BaseModel):
    """Job details response."""
    id: int
    job_id: str  # String version for compatibility
    user_id: int
    script_name: str
    status: str
    execution_mode: str
    resource_profile: str
    timeout_seconds: int
    container_id: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    queue_time_seconds: Optional[float] = None
    gpu_used: bool = False
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    auto_allocated: bool = False  # Whether resources were auto-allocated
    analysis_reasoning: Optional[str] = None  # Why this profile was chosen
    
    model_config = ConfigDict(from_attributes=True)


class JobDetailResponse(JobResponse):
    """Detailed job response including script content and logs."""
    script_content: Optional[str] = None
    logs_location: Optional[str] = None
    results_location: Optional[str] = None
    output: Optional[str] = None  # For compatibility
    error: Optional[str] = None  # Alias for error_message
    metrics: Optional["JobMetricsResponse"] = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""
    success: bool = True
    jobs: List[JobResponse]
    total: int
    page: int = 1
    per_page: int = 20
    pages: int = 1


class JobCancelResponse(BaseModel):
    """Response for job cancellation."""
    success: bool
    message: str
    job_id: int
    status: str


# =============================================================================
# Metrics Schemas
# =============================================================================

class JobMetricsResponse(BaseModel):
    """Job metrics response."""
    id: int
    job_id: int
    cpu_seconds: float
    avg_cpu_percent: float
    max_cpu_percent: float
    peak_ram_mb: float
    avg_ram_mb: float
    gpu_seconds: float
    avg_gpu_percent: float
    max_gpu_percent: float
    peak_gpu_memory_mb: float
    network_rx_bytes: int
    network_tx_bytes: int
    disk_read_bytes: int
    disk_write_bytes: int
    collected_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class UserMetricsSummary(BaseModel):
    """Summary of resource usage for a user."""
    user_id: int
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    cancelled_jobs: int
    total_cpu_seconds: float
    total_gpu_seconds: float
    total_duration_seconds: float
    avg_job_duration: float


class SystemMetricsResponse(BaseModel):
    """System-wide metrics."""
    total_users: int
    total_jobs: int
    running_jobs: int
    queued_jobs: int
    jobs_today: int
    cpu_jobs: int
    gpu_jobs: int


# =============================================================================
# System Status Schemas
# =============================================================================

class SystemStatusResponse(BaseModel):
    """System resource status."""
    success: bool = True
    status: dict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str
    database: str
    docker: str
    gpu_available: bool


# =============================================================================
# Generic Response Schemas
# =============================================================================

class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None


# Update forward references
JobDetailResponse.model_rebuild()


