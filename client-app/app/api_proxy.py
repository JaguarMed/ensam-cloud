"""
API Proxy - Handles communication with the remote compute server.

This module acts as a gateway between the client frontend and the
remote compute server that handles actual job execution.
"""

import httpx
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Remote compute server URL - Configure via environment variable
COMPUTE_SERVER_URL = os.getenv("COMPUTE_SERVER_URL", "http://localhost:8000")

# Request timeout in seconds
REQUEST_TIMEOUT = 30.0


# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login credentials."""
    email: str
    password: str


class LoginResponse(BaseModel):
    """Login response from server."""
    success: bool
    token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    message: str = ""


class JobSubmitRequest(BaseModel):
    """Job submission request."""
    code: str
    gpu_enabled: bool = True


class JobSubmitResponse(BaseModel):
    """Job submission response."""
    success: bool
    job_id: Optional[str] = None
    status: Optional[str] = None
    message: str = ""


class JobRecord(BaseModel):
    """Job record from history."""
    job_id: str
    status: str
    created_at: str
    finished_at: Optional[str] = None
    gpu_used: bool = True
    script_name: str = "script.py"
    output: Optional[str] = None
    error: Optional[str] = None


class JobHistoryResponse(BaseModel):
    """Job history response."""
    success: bool
    jobs: List[Dict[str, Any]] = []
    total: int = 0
    message: str = ""


# ============================================================================
# API Proxy Class
# ============================================================================

class ComputeServerProxy:
    """
    Proxy class for communicating with the remote compute server.
    
    All methods are async and return structured responses.
    Handles connection errors gracefully.
    """
    
    def __init__(self, base_url: str = COMPUTE_SERVER_URL):
        """
        Initialize the proxy with the server URL.
        
        Args:
            base_url: Base URL of the compute server
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = REQUEST_TIMEOUT
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        token: Optional[str] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the compute server.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/auth/login")
            token: Optional JWT token for authentication
            json_data: Optional JSON body data
            params: Optional query parameters
            
        Returns:
            Response data as dict
        """
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    params=params
                )
                
                # Try to parse JSON response
                try:
                    data = response.json()
                except Exception:
                    data = {"success": False, "message": response.text}
                
                # Add status code info
                data["_status_code"] = response.status_code
                
                return data
                
        except httpx.ConnectError:
            logger.error(f"Connection error to {url}")
            return {
                "success": False,
                "message": f"Cannot connect to compute server at {self.base_url}",
                "_status_code": 503
            }
        except httpx.TimeoutException:
            logger.error(f"Timeout connecting to {url}")
            return {
                "success": False,
                "message": "Request to compute server timed out",
                "_status_code": 504
            }
        except Exception as e:
            logger.error(f"Error making request to {url}: {e}")
            return {
                "success": False,
                "message": f"Error communicating with server: {str(e)}",
                "_status_code": 500
            }
    
    # ========================================================================
    # Authentication
    # ========================================================================
    
    async def login(self, email: str, password: str) -> LoginResponse:
        """
        Authenticate with the compute server.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            LoginResponse with token if successful
        """
        data = await self._make_request(
            method="POST",
            endpoint="/auth/login",
            json_data={"email": email, "password": password}
        )
        
        return LoginResponse(
            success=data.get("success", False),
            token=data.get("token"),
            user=data.get("user"),
            message=data.get("message", "")
        )
    
    # ========================================================================
    # Jobs
    # ========================================================================
    
    async def submit_job(
        self,
        token: str,
        code: str,
        gpu_enabled: bool = True
    ) -> JobSubmitResponse:
        """
        Submit a Python script for execution.
        
        Args:
            token: JWT authentication token
            code: Python code to execute
            gpu_enabled: Whether to use GPU
            
        Returns:
            JobSubmitResponse with job_id if successful
        """
        data = await self._make_request(
            method="POST",
            endpoint="/api/jobs/run",
            token=token,
            json_data={"code": code, "gpu_enabled": gpu_enabled}
        )
        
        return JobSubmitResponse(
            success=data.get("success", False),
            job_id=data.get("job_id"),
            status=data.get("status"),
            message=data.get("message", "")
        )
    
    async def get_job_history(self, token: str) -> JobHistoryResponse:
        """
        Get job history from the compute server.
        
        Args:
            token: JWT authentication token
            
        Returns:
            JobHistoryResponse with list of jobs
        """
        data = await self._make_request(
            method="GET",
            endpoint="/api/jobs/history",
            token=token
        )
        
        return JobHistoryResponse(
            success=data.get("success", False),
            jobs=data.get("jobs", []),
            total=data.get("total", 0),
            message=data.get("message", "")
        )
    
    async def get_job_details(self, token: str, job_id: str) -> Dict[str, Any]:
        """
        Get details for a specific job.
        
        Args:
            token: JWT authentication token
            job_id: Job identifier
            
        Returns:
            Job details dict
        """
        data = await self._make_request(
            method="GET",
            endpoint=f"/api/jobs/{job_id}",
            token=token
        )
        
        return data
    
    async def cancel_job(self, token: str, job_id: str) -> Dict[str, Any]:
        """
        Cancel a running job.
        
        Args:
            token: JWT authentication token
            job_id: Job identifier
            
        Returns:
            Cancellation result
        """
        data = await self._make_request(
            method="POST",
            endpoint=f"/api/jobs/{job_id}/cancel",
            token=token
        )
        
        return data
    
    # ========================================================================
    # System Status
    # ========================================================================
    
    async def get_system_status(self, token: str) -> Dict[str, Any]:
        """
        Get system status from compute server.
        
        Args:
            token: JWT authentication token
            
        Returns:
            System status dict
        """
        data = await self._make_request(
            method="GET",
            endpoint="/api/system/status",
            token=token
        )
        
        return data
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check if the compute server is healthy.
        
        Returns:
            Health check response
        """
        data = await self._make_request(
            method="GET",
            endpoint="/health"
        )
        
        return data


# ============================================================================
# Global Proxy Instance
# ============================================================================

# Create a global proxy instance
proxy = ComputeServerProxy()


# ============================================================================
# Convenience Functions
# ============================================================================

async def login(email: str, password: str) -> LoginResponse:
    """Convenience function for login."""
    return await proxy.login(email, password)


async def submit_job(token: str, code: str, gpu_enabled: bool = True) -> JobSubmitResponse:
    """Convenience function for job submission."""
    return await proxy.submit_job(token, code, gpu_enabled)


async def get_job_history(token: str) -> JobHistoryResponse:
    """Convenience function for getting job history."""
    return await proxy.get_job_history(token)


async def get_system_status(token: str) -> Dict[str, Any]:
    """Convenience function for getting system status."""
    return await proxy.get_system_status(token)








