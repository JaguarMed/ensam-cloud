"""
Docker executor for running Python scripts in isolated containers.
Implements EF3 (Isolated Execution) and EF4 (GPU Acceleration).
"""

import docker
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, AsyncGenerator, Callable
from pathlib import Path
import threading
import queue

from .core.config import settings
from .models import Job, JobStatus, JobMetrics

# Configure logging
logger = logging.getLogger(__name__)

# Docker client (lazy initialization)
_docker_client = None


def get_docker_client():
    """Get or create Docker client."""
    global _docker_client
    if _docker_client is None:
        try:
            _docker_client = docker.from_env()
            # Test connection
            _docker_client.ping()
            logger.info("✅ Docker client connected successfully")
        except docker.errors.DockerException as e:
            logger.error(f"❌ Failed to connect to Docker: {e}")
            raise RuntimeError(f"Docker is not available: {e}")
    return _docker_client


def check_gpu_available() -> bool:
    """Check if NVIDIA GPU is available for Docker."""
    try:
        client = get_docker_client()
        # Try to get GPU info
        info = client.info()
        runtimes = info.get('Runtimes', {})
        return 'nvidia' in runtimes
    except Exception as e:
        logger.warning(f"GPU check failed: {e}")
        return False


class DockerExecutor:
    """
    Manages Docker container execution for Python scripts.
    
    Features:
    - Isolated execution with resource limits
    - Optional GPU support via NVIDIA Container Toolkit
    - Real-time log streaming
    - Timeout enforcement
    - Graceful cancellation
    """
    
    def __init__(self):
        self.client = get_docker_client()
        self.gpu_available = check_gpu_available()
        self.running_containers: dict[int, str] = {}  # job_id -> container_id
        self.log_callbacks: dict[int, list[Callable]] = {}  # job_id -> callbacks
        
    def get_resource_limits(self, profile: str) -> dict:
        """Get resource limits for a profile."""
        profiles = settings.RESOURCE_PROFILES
        if profile not in profiles:
            profile = "medium"
        return profiles[profile]
    
    def prepare_script_directory(self, job_id: int, script_content: str) -> Path:
        """
        Prepare the script directory with the Python code.
        
        Args:
            job_id: Job identifier
            script_content: Python code to execute
            
        Returns:
            Path to the script directory
        """
        job_dir = Path(settings.SCRIPTS_DIR) / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Write the script
        script_path = job_dir / "script.py"
        script_path.write_text(script_content, encoding="utf-8")
        
        # Create output directory
        output_dir = job_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        return job_dir
    
    def build_container_config(
        self,
        job: Job,
        script_dir: Path
    ) -> dict:
        """
        Build Docker container configuration.
        
        Args:
            job: Job model instance
            script_dir: Path to script directory
            
        Returns:
            Docker container configuration dict
        """
        limits = self.get_resource_limits(job.resource_profile)
        
        # Base configuration
        config = {
            "image": settings.DOCKER_IMAGE_CPU,
            "command": ["python", "/app/script.py"],
            "working_dir": "/app",
            "volumes": {
                str(script_dir.absolute()): {
                    "bind": "/app",
                    "mode": "rw"
                }
            },
            "detach": True,
            "remove": False,  # Keep container for log retrieval
            "name": f"jaguarmed-job-{job.id}",
            "labels": {
                "jaguarmed.job_id": str(job.id),
                "jaguarmed.user_id": str(job.user_id)
            },
            # Resource limits
            "cpu_shares": limits["cpu_shares"],
            "mem_limit": f"{limits['memory_mb']}m",
            "memswap_limit": f"{limits['memory_mb']}m",  # Disable swap
            # Security
            "network_mode": "none",  # No network access by default
            "read_only": False,  # Allow writing to /app/output
            "user": "nobody",  # Run as non-root (may need adjustment)
        }
        
        # GPU configuration
        if job.execution_mode == "gpu" and self.gpu_available:
            config["image"] = settings.DOCKER_IMAGE_GPU
            config["device_requests"] = [
                docker.types.DeviceRequest(
                    count=-1,  # All GPUs
                    capabilities=[["gpu"]]
                )
            ]
            # GPU containers may need network for CUDA
            config["network_mode"] = "bridge"
        
        return config
    
    async def execute_job(
        self,
        job: Job,
        db_session,
        on_log: Optional[Callable[[str, str], None]] = None
    ) -> Job:
        """
        Execute a job in a Docker container.
        
        Args:
            job: Job model instance
            db_session: Database session for updates
            on_log: Callback for log streaming (stream, message)
            
        Returns:
            Updated Job instance
        """
        container = None
        
        try:
            # Prepare script directory
            script_dir = self.prepare_script_directory(
                job.id, 
                job.script_content or "print('No script content')"
            )
            
            # Update job status to RUNNING
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            db_session.commit()
            
            # Build container config
            config = self.build_container_config(job, script_dir)
            
            # Log configuration
            logger.info(f"Starting container for job {job.id} with config: {config['image']}")
            
            # Create and start container
            try:
                container = self.client.containers.run(**config)
            except docker.errors.ImageNotFound:
                # Pull image if not found
                logger.info(f"Pulling image {config['image']}...")
                self.client.images.pull(config['image'])
                container = self.client.containers.run(**config)
            
            # Store container reference
            job.container_id = container.id
            self.running_containers[job.id] = container.id
            db_session.commit()
            
            # Get resource limits for timeout
            limits = self.get_resource_limits(job.resource_profile)
            timeout = min(job.timeout_seconds, limits["timeout"])
            
            # Wait for container with timeout
            result = await self._wait_for_container(
                container, 
                timeout, 
                on_log
            )
            
            # Process result
            job.exit_code = result["exit_code"]
            job.finished_at = datetime.utcnow()
            
            if job.started_at:
                job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
            
            # Determine final status
            if result.get("timeout"):
                job.status = JobStatus.TIMEOUT.value
                job.error_message = f"Job exceeded timeout of {timeout} seconds"
            elif result.get("cancelled"):
                job.status = JobStatus.CANCELLED.value
            elif result["exit_code"] == 0:
                job.status = JobStatus.SUCCESS.value
            else:
                job.status = JobStatus.FAILED.value
                job.error_message = f"Script exited with code {result['exit_code']}"
            
            # Save logs
            logs_path = script_dir / "logs.txt"
            logs_path.write_text(result.get("logs", ""), encoding="utf-8")
            job.logs_location = str(logs_path)
            
            # Check if GPU was actually used
            job.gpu_used = job.execution_mode == "gpu" and self.gpu_available
            
            # Collect metrics
            await self._collect_metrics(job, container, db_session)
            
            db_session.commit()
            
        except docker.errors.ContainerError as e:
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            if job.started_at:
                job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
            db_session.commit()
            logger.error(f"Container error for job {job.id}: {e}")
            
        except Exception as e:
            job.status = JobStatus.FAILED.value
            job.error_message = f"Execution error: {str(e)}"
            job.finished_at = datetime.utcnow()
            if job.started_at:
                job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
            db_session.commit()
            logger.error(f"Error executing job {job.id}: {e}")
            
        finally:
            # Cleanup
            if job.id in self.running_containers:
                del self.running_containers[job.id]
            
            # Remove container
            if container:
                try:
                    container.remove(force=True)
                except Exception as e:
                    logger.warning(f"Failed to remove container: {e}")
        
        return job
    
    async def _wait_for_container(
        self,
        container,
        timeout: int,
        on_log: Optional[Callable] = None
    ) -> dict:
        """
        Wait for container to finish with timeout and log streaming.
        
        Returns:
            Dict with exit_code, logs, timeout, cancelled flags
        """
        result = {
            "exit_code": -1,
            "logs": "",
            "timeout": False,
            "cancelled": False
        }
        
        log_queue = queue.Queue()
        stop_event = threading.Event()
        
        def stream_logs():
            """Stream logs in a separate thread."""
            try:
                for log in container.logs(stream=True, follow=True):
                    if stop_event.is_set():
                        break
                    log_line = log.decode("utf-8", errors="replace")
                    log_queue.put(log_line)
                    if on_log:
                        on_log("stdout", log_line)
            except Exception as e:
                logger.debug(f"Log streaming ended: {e}")
        
        # Start log streaming thread
        log_thread = threading.Thread(target=stream_logs, daemon=True)
        log_thread.start()
        
        try:
            # Wait for container with timeout
            start_time = datetime.utcnow()
            
            while True:
                # Check container status
                container.reload()
                status = container.status
                
                if status == "exited":
                    result["exit_code"] = container.attrs["State"]["ExitCode"]
                    break
                
                # Check timeout
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > timeout:
                    result["timeout"] = True
                    container.stop(timeout=5)
                    break
                
                # Collect logs from queue
                while not log_queue.empty():
                    result["logs"] += log_queue.get_nowait()
                
                await asyncio.sleep(0.5)
                
        except asyncio.CancelledError:
            result["cancelled"] = True
            container.stop(timeout=5)
            
        finally:
            stop_event.set()
            log_thread.join(timeout=2)
            
            # Get remaining logs
            try:
                remaining_logs = container.logs().decode("utf-8", errors="replace")
                result["logs"] = remaining_logs
            except Exception:
                pass
        
        return result
    
    async def _collect_metrics(self, job: Job, container, db_session):
        """Collect resource usage metrics from container."""
        try:
            stats = container.stats(stream=False)
            
            # Calculate CPU usage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0
            
            # Memory usage
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_mb = memory_usage / (1024 * 1024)
            
            # Create metrics record
            metrics = JobMetrics(
                job_id=job.id,
                cpu_seconds=job.duration_seconds or 0,
                avg_cpu_percent=cpu_percent,
                peak_ram_mb=memory_mb,
                gpu_seconds=job.duration_seconds if job.gpu_used else 0,
                avg_gpu_percent=0.0,  # TODO: Get from nvidia-smi
                gpu_memory_mb=0.0,
            )
            
            db_session.add(metrics)
            
        except Exception as e:
            logger.warning(f"Failed to collect metrics for job {job.id}: {e}")
    
    async def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a running job by stopping its container.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if cancelled successfully
        """
        container_id = self.running_containers.get(job_id)
        if not container_id:
            return False
        
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=5)
            logger.info(f"Cancelled job {job_id}")
            return True
        except docker.errors.NotFound:
            return False
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False
    
    def get_container_logs(self, job_id: int, tail: int = 100) -> Optional[str]:
        """Get logs from a running container."""
        container_id = self.running_containers.get(job_id)
        if not container_id:
            return None
        
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail).decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Failed to get logs for job {job_id}: {e}")
            return None


# Global executor instance
executor = DockerExecutor()


async def run_job_async(job_id: int, db_session):
    """
    Async wrapper to run a job.
    Called from the jobs router after creating the job record.
    """
    from .models import Job
    
    job = db_session.query(Job).filter(Job.id == job_id).first()
    if not job:
        logger.error(f"Job {job_id} not found")
        return
    
    await executor.execute_job(job, db_session)








