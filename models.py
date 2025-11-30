"""
Pydantic models for the Cloud Python Execution Platform.
Defines request/response schemas for the API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class JobStatus(str, Enum):
    """Possible job statuses."""
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


# ============================================================================
# Authentication Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request payload."""
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Login response with JWT token."""
    success: bool
    token: str
    user: dict
    message: str = "Login successful"


class AuthError(BaseModel):
    """Authentication error response."""
    success: bool = False
    message: str


# ============================================================================
# Job Models
# ============================================================================

class JobRunRequest(BaseModel):
    """Request to run a Python script."""
    code: str = Field(..., min_length=1, description="Python code to execute")
    gpu_enabled: bool = Field(default=True, description="Whether to use GPU")


class JobRunResponse(BaseModel):
    """Response after submitting a job."""
    success: bool = True
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    message: str = "Job submitted successfully"


class JobRecord(BaseModel):
    """A job record in the history."""
    job_id: str
    user_id: int
    status: JobStatus
    created_at: datetime
    finished_at: Optional[datetime] = None
    gpu_used: bool = True
    script_name: str = "script.py"
    output: Optional[str] = None
    error: Optional[str] = None


class JobHistoryResponse(BaseModel):
    """Response containing job history."""
    success: bool = True
    jobs: List[JobRecord]
    total: int


# ============================================================================
# System Status Models
# ============================================================================

class SystemStatus(BaseModel):
    """System resource status."""
    cpu_usage: float = Field(..., ge=0, le=100)
    gpu_usage: float = Field(..., ge=0, le=100)
    ram_usage: float = Field(..., ge=0, le=100)
    active_jobs: int = Field(..., ge=0)
    gpu_available: bool = True
    gpu_name: str = "NVIDIA RTX 4090"
    total_ram_gb: float = 32.0


# ============================================================================
# API Response Models
# ============================================================================

class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Generic error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None
