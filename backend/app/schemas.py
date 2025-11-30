"""
Pydantic schemas for request/response validation.
Defines the API contract for all endpoints.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums for API
# ============================================================================

class JobStatusEnum(str, Enum):
    """Job status values."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionModeEnum(str, Enum):
    """Execution mode options."""
    CPU = "cpu"
    GPU = "gpu"


class ResourceProfileEnum(str, Enum):
    """Resource profile options."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# ============================================================================
# Authentication Schemas
# ============================================================================

class LoginRequest(BaseModel):
    """Login request payload."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Login response with JWT token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)


class TokenPayload(BaseModel):
    """JWT token payload structure."""
    sub: str  # User ID
    exp: datetime
    iat: datetime


# ============================================================================
# User Schemas
# ============================================================================

class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserResponse(UserBase):
    """User response schema (excludes password)."""
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Job Schemas
# ============================================================================

class JobCreate(BaseModel):
    """Schema for creating a new job."""
    script_name: str = Field(..., min_length=1, max_length=255)
    script_content: Optional[str] = None
    execution_mode: ExecutionModeEnum = ExecutionModeEnum.CPU
    resource_profile: ResourceProfileEnum = ResourceProfileEnum.MEDIUM
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    
    @validator('script_name')
    def validate_script_name(cls, v):
        """Ensure script name ends with .py"""
        if not v.endswith('.py'):
            v = v + '.py'
        return v


class JobSubmitRequest(BaseModel):
    """Request for submitting a job via API."""
    code: Optional[str] = Field(None, description="Python code to execute")
    script_name: str = Field(default="script.py", description="Name for the script")
    execution_mode: ExecutionModeEnum = Field(default=ExecutionModeEnum.CPU)
    resource_profile: ResourceProfileEnum = Field(default=ResourceProfileEnum.MEDIUM)
    timeout: int = Field(default=300, ge=10, le=3600, description="Timeout in seconds")


class JobResponse(BaseModel):
    """Job response schema."""
    id: int
    user_id: int
    script_name: str
    status: str
    execution_mode: str
    resource_profile: str
    timeout_seconds: int
    container_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    gpu_used: bool
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class JobDetailResponse(JobResponse):
    """Detailed job response including script content."""
    script_content: Optional[str] = None
    logs_location: Optional[str] = None
    results_location: Optional[str] = None
    metrics: Optional["JobMetricsResponse"] = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int
    pages: int


class JobStatusUpdate(BaseModel):
    """Schema for updating job status."""
    status: JobStatusEnum


# ============================================================================
# Job Metrics Schemas
# ============================================================================

class JobMetricsResponse(BaseModel):
    """Job metrics response schema."""
    id: int
    job_id: int
    cpu_seconds: float
    avg_cpu_percent: float
    peak_ram_mb: float
    gpu_seconds: float
    avg_gpu_percent: float
    gpu_memory_mb: float
    network_rx_bytes: int
    network_tx_bytes: int
    disk_read_bytes: int
    disk_write_bytes: int
    collected_at: datetime
    
    class Config:
        from_attributes = True


class UserMetricsSummary(BaseModel):
    """Summary of resource usage for a user."""
    user_id: int
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    total_cpu_seconds: float
    total_gpu_seconds: float
    total_ram_mb_hours: float
    avg_job_duration: float


class SystemMetrics(BaseModel):
    """System-wide metrics."""
    total_users: int
    total_jobs: int
    running_jobs: int
    queued_jobs: int
    cpu_utilization: float
    gpu_utilization: float
    memory_utilization: float


# ============================================================================
# WebSocket Schemas
# ============================================================================

class LogMessage(BaseModel):
    """Real-time log message."""
    job_id: int
    timestamp: datetime
    stream: str  # "stdout" or "stderr"
    message: str


class JobEvent(BaseModel):
    """Job status change event."""
    job_id: int
    event_type: str  # "status_change", "log", "metrics"
    data: dict


# ============================================================================
# API Response Wrappers
# ============================================================================

class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Error response schema."""
    success: bool = False
    error: str
    detail: Optional[str] = None


# Update forward references
LoginResponse.model_rebuild()
JobDetailResponse.model_rebuild()








