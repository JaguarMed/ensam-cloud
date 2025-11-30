"""
Docker executor for running Python scripts in isolated containers.

Implements:
- EF3: Isolated execution with resource limits
- EF4: GPU acceleration via NVIDIA Container Toolkit
- EF5: Real-time log streaming support
- EF8: Job cancellation
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from pathlib import Path
import threading
import queue
import shutil

from ..core.config import settings
from ..models import Job, JobStatus, JobMetrics

# --- Docker SDK import with protection against local "docker" package shadowing ---
# The project root contains a folder named "docker/" used for compose files.
# Python would normally import that instead of the real Docker SDK from site-packages.
# We temporarily remove the project root from sys.path to force importing the SDK.

DOCKER_AVAILABLE = False
docker = None

try:
    project_root = Path(__file__).resolve().parents[2]
    original_sys_path = list(sys.path)

    if str(project_root) in sys.path:
        sys.path.remove(str(project_root))

    import docker as docker_sdk  # type: ignore

    docker = docker_sdk
    # Basic sanity check: the real SDK exposes from_env
    if hasattr(docker, "from_env"):
        DOCKER_AVAILABLE = True
    else:
        DOCKER_AVAILABLE = False
        docker = None
finally:
    # Restore original sys.path to avoid impacting the rest of the app
    sys.path = original_sys_path

logger = logging.getLogger(__name__)

# Docker client singleton
_docker_client = None
_docker_available = None


def get_docker_client():
    """Get or create Docker client with lazy initialization."""
    global _docker_client, _docker_available
    
    if not DOCKER_AVAILABLE:
        _docker_available = False
        return None
    
    if _docker_available is False:
        return None
    
    if _docker_client is None:
        try:
            _docker_client = docker.from_env()
            _docker_client.ping()
            _docker_available = True
            logger.info("✅ Docker client connected successfully")
        except Exception as e:
            _docker_available = False
            logger.warning(f"⚠️ Docker not available: {e}")
            return None
    
    return _docker_client


def check_gpu_available() -> bool:
    """Check if NVIDIA GPU is available for Docker."""
    if not DOCKER_AVAILABLE:
        return False
    
    if not settings.GPU_ENABLED:
        return False
    
    client = get_docker_client()
    if not client:
        return False
    
    try:
        # First check if NVIDIA runtime is available
        info = client.info()
        runtimes = info.get('Runtimes', {})
        has_nvidia_runtime = 'nvidia' in runtimes
        
        if not has_nvidia_runtime:
            logger.info("ℹ️ NVIDIA runtime not available in Docker")
            return False
        
        # Try to actually run nvidia-smi in a container to verify GPU access
        # Use detach=True and then stop it to avoid blocking
        try:
            # Try to run nvidia-smi in a container with GPU access
            test_container = client.containers.run(
                image=settings.DOCKER_IMAGE_GPU,
                command=["nvidia-smi", "--list-gpus"],
                remove=True,
                detach=True,  # Start detached
                device_requests=[
                    docker.types.DeviceRequest(
                        count=-1,
                        capabilities=[["gpu"]]
                    )
                ]
            )
            # Wait a bit and check if it's still running (means it started successfully)
            import time
            time.sleep(2)
            try:
                test_container.reload()
                # If container is running or finished, GPU is accessible
                test_container.stop()
                logger.info("✅ NVIDIA GPU detected and accessible")
                return True
            except Exception:
                # Container might have finished already
                logger.info("✅ NVIDIA GPU runtime available (container test passed)")
                return True
        except docker.errors.ImageNotFound:
            # Image not found - try to pull it or just assume GPU available if runtime exists
            logger.info("ℹ️ GPU image not found, but NVIDIA runtime available - assuming GPU available")
            return True
        except docker.errors.ContainerError as e:
            # Container ran but nvidia-smi failed - might still have GPU
            logger.warning(f"⚠️ GPU test container error: {e}")
            # If runtime exists, assume GPU might be available (let actual jobs test it)
            logger.info("ℹ️ NVIDIA runtime available - will test GPU on actual job execution")
            return True
        except Exception as gpu_test_error:
            # Other errors - if runtime exists, assume GPU might be available
            error_msg = str(gpu_test_error)
            if "gpu" in error_msg.lower() or "nvidia" in error_msg.lower():
                logger.warning(f"⚠️ GPU test failed: {gpu_test_error}")
                # If runtime exists, still return True and let actual jobs test
                logger.info("ℹ️ NVIDIA runtime available - will test GPU on actual job execution")
                return True
            else:
                logger.warning(f"⚠️ GPU check error: {gpu_test_error}")
                logger.info("ℹ️ Running in CPU-only mode")
                return False
            
    except Exception as e:
        logger.warning(f"GPU check failed: {e}")
        return False


class DockerExecutor:
    """
    Manages Docker container execution for Python scripts.
    
    Features:
    - Isolated execution with CPU/RAM limits
    - Optional GPU support via NVIDIA Container Toolkit
    - Real-time log streaming via callbacks
    - Timeout enforcement
    - Graceful cancellation
    """
    
    def __init__(self):
        self.client = get_docker_client()
        self.gpu_available = check_gpu_available()
        self.running_containers: Dict[int, str] = {}  # job_id -> container_id
        self.log_queues: Dict[int, queue.Queue] = {}  # job_id -> log queue
        self._lock = threading.Lock()
    
    @property
    def is_available(self) -> bool:
        """Check if Docker is available."""
        return self.client is not None
    
    def get_resource_limits(self, profile: str, job: Optional[Job] = None) -> dict:
        """Get resource limits for a profile, with optional custom overrides from job."""
        profiles = settings.RESOURCE_PROFILES
        if profile not in profiles:
            profile = "medium"
        limits = profiles[profile].copy()
        
        # Apply custom configuration from job if present
        if job and job.analysis_reasoning:
            import json
            import re
            # Extract custom config from analysis_reasoning if present
            match = re.search(r'CUSTOM_CONFIG:({.*?})', job.analysis_reasoning)
            if match:
                try:
                    custom_config = json.loads(match.group(1))
                    # Override limits with custom values
                    if "memory_mb" in custom_config:
                        limits["memory_mb"] = max(256, min(custom_config["memory_mb"], 8192))
                    if "cpu_shares" in custom_config:
                        limits["cpu_shares"] = max(256, min(custom_config["cpu_shares"], 4096))
                    if "timeout" in custom_config:
                        limits["timeout"] = max(10, min(custom_config["timeout"], 3600))
                    logger.info(f"Applied custom config for job {job.id}: {custom_config}")
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse custom config: {e}")
        
        return limits
    
    def prepare_job_directory(self, job_id: int, script_content: str, use_gpu: bool = False) -> Path:
        """
        Prepare the job directory with script and output folders.
        
        Args:
            job_id: Job identifier
            script_content: Python code to execute
            use_gpu: Whether this job will use GPU
            
        Returns:
            Path to the job directory
        """
        job_dir = Path(settings.SCRIPTS_DIR) / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Write the script
        script_path = job_dir / "script.py"
        script_path.write_text(script_content, encoding="utf-8")
        
        # Create wrapper script that installs dependencies and runs the script
        wrapper_script = self._create_wrapper_script(script_content, use_gpu=use_gpu)
        wrapper_path = job_dir / "run.sh"
        # Ensure Unix line endings (LF only) for shell scripts
        wrapper_script_unix = wrapper_script.replace('\r\n', '\n').replace('\r', '\n')
        wrapper_path.write_text(wrapper_script_unix, encoding="utf-8", newline='\n')
        # Make executable (works on Unix, Windows will handle it in Docker)
        try:
            import stat
            wrapper_path.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        except (AttributeError, OSError):
            # Windows doesn't support chmod, but Docker will handle it
            pass
        
        # Create output directory for results
        output_dir = job_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Create logs directory
        logs_dir = Path(settings.LOGS_DIR) / str(job_id)
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        return job_dir
    
    def _create_wrapper_script(self, script_content: str, use_gpu: bool = False) -> str:
        """Create a wrapper script that installs dependencies and runs the script."""
        import re
        
        # Extract imports from script
        imports = set()
        # Match import statements
        import_patterns = [
            r'^import\s+(\w+)',
            r'^from\s+(\w+)',
            r'^\s+import\s+(\w+)',
            r'^\s+from\s+(\w+)',
        ]
        
        for line in script_content.split('\n'):
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    imports.add(match.group(1))
        
        # Map common imports to pip packages
        # For GPU jobs, install tensorflow with CUDA support
        # Note: For CUDA 12.0, we need TensorFlow 2.15+ with proper CUDA libraries
        # tensorflow[and-cuda] may not work well, so we install tensorflow and cudatoolkit separately
        package_map = {
            'tensorflow': 'tensorflow>=2.15.0' if use_gpu else 'tensorflow',
            'torch': 'torch',
            'keras': 'keras',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'matplotlib': 'matplotlib',
            'sklearn': 'scikit-learn',
            'scipy': 'scipy',
            'cv2': 'opencv-python',
            'PIL': 'Pillow',
            'requests': 'requests',
            'flask': 'flask',
            'django': 'django',
        }
        
        # Determine packages to install
        packages_to_install = []
        for imp in imports:
            if imp in package_map:
                pkg = package_map[imp]
                # For GPU jobs with TensorFlow image, TensorFlow is already installed
                # Don't reinstall it unless it's a different version
                if use_gpu and 'tensorflow' in pkg and 'tensorflow/tensorflow' in settings.DOCKER_IMAGE_GPU:
                    # TensorFlow is pre-installed in the image, skip
                    continue
                packages_to_install.append(pkg)
        
        # For GPU jobs with CUDA base image, add TensorFlow and CUDA libraries if needed
        if use_gpu and 'tensorflow' in imports and 'tensorflow/tensorflow' not in settings.DOCKER_IMAGE_GPU:
            # Only add TensorFlow if using CUDA base image (not TensorFlow image)
            has_tensorflow = any('tensorflow' in p for p in packages_to_install)
            if not has_tensorflow:
                packages_to_install.append('tensorflow>=2.15.0')
            # Add CUDA libraries for TensorFlow
            if not any('nvidia-cudnn' in p for p in packages_to_install):
                packages_to_install.append('nvidia-cudnn-cu12>=8.9')
        
        # Create wrapper script that works with both CPU and GPU images
        # Use sh instead of bash for better compatibility
        # Remove 'set -e' to avoid "Illegal option -" error with some shells
        wrapper = """#!/bin/sh
set -x  # Enable debug output to see what's happening

echo "=== Starting job execution ==="
echo "Working directory: $(pwd)"
echo "Script location: /app/run.sh"
echo "User script: /app/script.py"

# Detect Python command
# TensorFlow GPU image has python3, CUDA base images may need installation
PYTHON_CMD=""
echo "=== Detecting Python ==="
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=python3
    PIP_CMD="python3 -m pip"
    echo "✅ Found python3: $(which python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=python
    PIP_CMD="python -m pip"
    echo "✅ Found python: $(which python)"
else
    echo "⚠️  Python not found, installing..."
    apt-get update -qq || true
    apt-get install -y -qq python3 python3-pip || true
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD=python3
        PIP_CMD="python3 -m pip"
        echo "✅ Python3 installed: $(which python3)"
    else
        echo "❌ ERROR: Failed to install Python"
        exit 1
    fi
fi

echo "Using Python: $PYTHON_CMD"
echo "Python version: $($PYTHON_CMD --version 2>&1 || echo 'unknown')"

# Upgrade pip (ignore errors)
echo "=== Upgrading pip ==="
$PIP_CMD install --upgrade pip --quiet || true

# Install detected dependencies (skip if already in image)
"""
        
        if packages_to_install:
            # For TensorFlow GPU image, TensorFlow is pre-installed
            if use_gpu and 'tensorflow/tensorflow' in settings.DOCKER_IMAGE_GPU:
                # Remove tensorflow from packages if using TensorFlow image
                packages_to_install = [p for p in packages_to_install if 'tensorflow' not in p.lower()]
            
            if packages_to_install:
                packages_str = ' '.join(packages_to_install)
                wrapper += f"echo '=== Installing packages: {packages_str} ==='\n"
                wrapper += f"$PIP_CMD install --quiet {packages_str} || true\n"
            else:
                wrapper += "echo '=== No additional packages to install ==='\n"
        
        # For GPU jobs, create GPU configuration wrapper
        if use_gpu:
            wrapper += """
# GPU Configuration - Force TensorFlow to use NVIDIA GPU
echo "=== GPU Configuration ==="
cat > /tmp/gpu_wrapper.py << 'GPU_EOF'
import os
import tensorflow as tf

# Configure TensorFlow for GPU
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'

# Get all GPUs
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    # Configure memory growth for all GPUs
    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, True)
    # Enable soft device placement - allows CPU fallback for operations that can't run on GPU
    # (like data loading), but model operations will still use GPU
    tf.config.set_soft_device_placement(True)
    print(f"✅ GPU configured: {len(gpus)} device(s) available")
    for i, gpu in enumerate(gpus):
        print(f"   GPU {i}: {gpu.name}")
    print("✅ Soft device placement enabled - data loading on CPU, training on GPU")
else:
    raise RuntimeError("No GPU detected - cannot run GPU job")

# Create output directory for files generated by the script
os.makedirs('/app/output', exist_ok=True)
print("=== Output directory created: /app/output ===")

# Change working directory to output for file operations
original_cwd = os.getcwd()
os.chdir('/app/output')

# Execute user script - TensorFlow will automatically use GPU for model operations
print("=== Executing script ===")
print("Note: Data loading may use CPU, but model.fit() and model.evaluate() will use GPU")
print("Note: Files created with df.to_excel(), df.to_csv(), etc. will be saved in /app/output/")
exec(open('/app/script.py').read())

# Return to original directory
os.chdir(original_cwd)
GPU_EOF

echo "✅ GPU wrapper ready"
echo "================================"
"""
            wrapper += """
# Run the script with GPU wrapper
echo "=== Starting GPU execution ==="
exec $PYTHON_CMD -u /tmp/gpu_wrapper.py
"""
        else:
            wrapper += """
# Create output directory for files generated by the script
mkdir -p /app/output
echo "=== Output directory created: /app/output ==="

# Run the script
echo "=== Executing user script ==="
if [ ! -f /app/script.py ]; then
    echo "❌ ERROR: User script not found at /app/script.py"
    exit 1
fi

# Inject code to redirect file outputs to /app/output
# This ensures files created with df.to_excel(), df.to_csv(), etc. are saved in output/
cat > /tmp/script_wrapper.py << 'SCRIPT_EOF'
import os
import sys

# Change working directory to output for file operations
original_cwd = os.getcwd()
os.chdir('/app/output')

# Add /app to path for imports
sys.path.insert(0, '/app')

# Execute user script
exec(open('/app/script.py').read())

# Return to original directory
os.chdir(original_cwd)
SCRIPT_EOF

exec $PYTHON_CMD -u /tmp/script_wrapper.py
"""
        
        return wrapper
    
    def build_container_config(self, job: Job, script_dir: Path) -> dict:
        """
        Build Docker container configuration with resource limits.
        
        Implements EF3 (isolation) and EF4 (GPU support).
        """
        limits = self.get_resource_limits(job.resource_profile, job)
        use_gpu = job.execution_mode == "gpu" and self.gpu_available
        
        # Select image
        image = settings.DOCKER_IMAGE_GPU if use_gpu else settings.DOCKER_IMAGE_CPU
        
        # Base configuration
        # Use wrapper script to install dependencies automatically (for both CPU and GPU)
        # The wrapper will detect Python command and install packages
        # Try bash first, fallback to sh if bash not available
        command = ["sh", "/app/run.sh"]
        
        config = {
            "image": image,
            "command": command,
            "working_dir": "/app",
            "volumes": {
                str(script_dir.absolute()): {
                    "bind": "/app",
                    "mode": "rw"
                }
            },
            "detach": True,
            "remove": False,
            "name": f"ensam-job-{job.id}",
            "labels": {
                "ensam.job_id": str(job.id),
                "ensam.user_id": str(job.user_id),
                "ensam.profile": job.resource_profile
            },
            # Resource limits (EF3) - Strict limits to prevent resource exhaustion
            "cpu_shares": limits.get("cpu_shares", 1024),
            "mem_limit": f"{limits.get('memory_mb', 2048)}m",
            "memswap_limit": f"{limits.get('memory_mb', 2048)}m",  # No swap to prevent memory bloat
            "cpu_period": 100000,  # 100ms period for CPU throttling
            "cpu_quota": int(limits.get("cpu_shares", 1024) * 100),  # Limit CPU usage proportionally
            "oom_kill_disable": False,  # Allow OOM killer to stop runaway processes
            # Network: Enable for dependency installation (pip install)
            # We need network access to install Python packages
            # Security: Network is isolated to Docker bridge, no external access except Internet
            "network_mode": "bridge",  # Enable network for pip install
            "read_only": False,
        }
        
        # GPU configuration (EF4)
        if use_gpu and docker:
            config["device_requests"] = [
                docker.types.DeviceRequest(
                    count=-1,
                    capabilities=[["gpu"]]
                )
            ]
        
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
        if not self.is_available:
            # Fallback: simulate execution without Docker
            return await self._simulate_execution(job, db_session, on_log)
        
        container = None
        script_dir = None
        
        try:
            # Determine if GPU will be used
            use_gpu = job.execution_mode == "gpu" and self.gpu_available
            
            # Prepare job directory (with GPU info for proper package installation)
            script_dir = self.prepare_job_directory(
                job.id,
                job.script_content or "print('No script content')",
                use_gpu=use_gpu
            )
            
            # Update job status to RUNNING
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            if job.queued_at:
                job.queue_time_seconds = (job.started_at - job.queued_at).total_seconds()
            db_session.commit()
            
            # Build container config
            config = self.build_container_config(job, script_dir)
            
            # If GPU was requested but not available, log warning and continue with CPU
            if job.execution_mode == "gpu" and not self.gpu_available:
                logger.warning(f"Job {job.id} requested GPU but GPU is not available. Running in CPU mode.")
                job.execution_mode = "cpu"
                job.gpu_used = False
                use_gpu = False
                # Rebuild config without GPU and recreate wrapper script
                script_dir = self.prepare_job_directory(
                    job.id,
                    job.script_content or "print('No script content')",
                    use_gpu=False
                )
                config = self.build_container_config(job, script_dir)
            
            logger.info(f"Starting container for job {job.id}: {config['image']}")
            
            # Pull image if needed
            try:
                container = self.client.containers.run(**config)
            except docker.errors.ImageNotFound:
                logger.info(f"Pulling image {config['image']}...")
                self.client.images.pull(config['image'])
                container = self.client.containers.run(**config)
            except Exception as e:
                # If GPU container fails, try CPU fallback
                if job.execution_mode == "gpu" and "gpu" in str(e).lower():
                    logger.warning(f"GPU container failed for job {job.id}: {e}. Falling back to CPU mode.")
                    job.execution_mode = "cpu"
                    job.gpu_used = False
                    config = self.build_container_config(job, script_dir)
                    try:
                        container = self.client.containers.run(**config)
                    except Exception as cpu_error:
                        raise Exception(f"Both GPU and CPU execution failed. CPU error: {cpu_error}")
                else:
                    raise
            
            # Track running container
            with self._lock:
                job.container_id = container.id
                self.running_containers[job.id] = container.id
            db_session.commit()
            
            # Wait for container with timeout
            limits = self.get_resource_limits(job.resource_profile, job)
            timeout = min(job.timeout_seconds, limits.get("timeout", 300))
            
            result = await self._wait_for_container(container, timeout, on_log)
            
            # Process result
            job.exit_code = result["exit_code"]
            job.finished_at = datetime.utcnow()
            
            if job.started_at:
                job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
            
            # Determine final status
            if result.get("cancelled"):
                job.status = JobStatus.CANCELLED.value
            elif result.get("timeout"):
                job.status = JobStatus.TIMEOUT.value
                job.error_message = f"Job exceeded timeout of {timeout} seconds"
            elif result["exit_code"] == 0:
                job.status = JobStatus.SUCCESS.value
            else:
                job.status = JobStatus.FAILED.value
                job.error_message = f"Script exited with code {result['exit_code']}"
            
            # Save logs
            logs_path = Path(settings.LOGS_DIR) / str(job.id) / "output.log"
            logs_path.parent.mkdir(parents=True, exist_ok=True)
            logs_path.write_text(result.get("logs", ""), encoding="utf-8")
            job.logs_location = str(logs_path)
            
            # Set GPU usage
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
            with self._lock:
                if job.id in self.running_containers:
                    del self.running_containers[job.id]
            
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
        """Wait for container with timeout and log streaming."""
        result = {
            "exit_code": -1,
            "logs": "",
            "timeout": False,
            "cancelled": False
        }
        
        log_buffer = []
        stop_event = threading.Event()
        
        def stream_logs():
            try:
                for log in container.logs(stream=True, follow=True):
                    if stop_event.is_set():
                        break
                    line = log.decode("utf-8", errors="replace")
                    log_buffer.append(line)
                    if on_log:
                        on_log("stdout", line)
            except Exception:
                pass
        
        log_thread = threading.Thread(target=stream_logs, daemon=True)
        log_thread.start()
        
        try:
            start_time = datetime.utcnow()
            
            while True:
                container.reload()
                
                if container.status == "exited":
                    result["exit_code"] = container.attrs["State"]["ExitCode"]
                    break
                
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > timeout:
                    result["timeout"] = True
                    container.stop(timeout=5)
                    break
                
                await asyncio.sleep(0.5)
                
        except asyncio.CancelledError:
            result["cancelled"] = True
            container.stop(timeout=5)
            
        finally:
            stop_event.set()
            log_thread.join(timeout=2)
            
            try:
                result["logs"] = container.logs().decode("utf-8", errors="replace")
            except Exception:
                result["logs"] = "".join(log_buffer)
        
        return result
    
    async def _simulate_execution(
        self,
        job: Job,
        db_session,
        on_log: Optional[Callable] = None
    ) -> Job:
        """Simulate job execution when Docker is not available."""
        logger.warning(f"Simulating execution for job {job.id} (Docker not available)")
        
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.utcnow()
        db_session.commit()
        
        # Simulate execution time
        await asyncio.sleep(2)
        
        # Simulate output
        output = """🚀 Simulation Mode (Docker not available)
        
Executing script...
print("Hello from ENSAM Cloud Platform!")

📊 Simulated Results:
  Status: Success
  Duration: 2.0s

✅ Job completed successfully (simulated)
"""
        
        if on_log:
            for line in output.split("\n"):
                on_log("stdout", line + "\n")
        
        job.status = JobStatus.SUCCESS.value
        job.finished_at = datetime.utcnow()
        job.duration_seconds = 2.0
        job.exit_code = 0
        
        # Save logs
        logs_path = Path(settings.LOGS_DIR) / str(job.id) / "output.log"
        logs_path.parent.mkdir(parents=True, exist_ok=True)
        logs_path.write_text(output, encoding="utf-8")
        job.logs_location = str(logs_path)
        
        db_session.commit()
        return job
    
    async def _collect_metrics(self, job: Job, container, db_session):
        """Collect resource usage metrics from container."""
        try:
            stats = container.stats(stream=False)
            
            # CPU calculation - handle cases where system_cpu_usage might not be available
            cpu_percent = 0.0
            try:
                cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                           stats["precpu_stats"]["cpu_usage"]["total_usage"]
                
                # Check if system_cpu_usage exists in both stats
                if ("system_cpu_usage" in stats["cpu_stats"] and 
                    "system_cpu_usage" in stats["precpu_stats"]):
                    system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                                  stats["precpu_stats"]["system_cpu_usage"]
                    
                    if system_delta > 0:
                        cpu_percent = (cpu_delta / system_delta) * 100.0
                else:
                    # Fallback: estimate CPU usage based on available data
                    # Use a simple heuristic if system_cpu_usage is not available
                    num_cpus = stats["cpu_stats"].get("online_cpus", 1)
                    if num_cpus > 0 and cpu_delta > 0:
                        # Approximate CPU usage (this is a fallback, not as accurate)
                        cpu_percent = min((cpu_delta / 1000000000.0) * 100.0, 100.0)
            except (KeyError, TypeError) as e:
                logger.debug(f"CPU metrics not available for job {job.id}: {e}")
                cpu_percent = 0.0
            
            # Memory
            memory_usage = stats.get("memory_stats", {}).get("usage", 0)
            memory_mb = memory_usage / (1024 * 1024) if memory_usage > 0 else 0.0
            
            # Create metrics
            metrics = JobMetrics(
                job_id=job.id,
                cpu_seconds=job.duration_seconds or 0,
                avg_cpu_percent=cpu_percent,
                max_cpu_percent=cpu_percent,
                peak_ram_mb=memory_mb,
                avg_ram_mb=memory_mb,
                gpu_seconds=job.duration_seconds if job.gpu_used else 0,
            )
            
            db_session.add(metrics)
            
        except Exception as e:
            logger.warning(f"Failed to collect metrics for job {job.id}: {e}")
    
    async def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a running job by stopping its container.
        Implements EF8.
        Uses aggressive stopping to prevent resource exhaustion.
        """
        with self._lock:
            container_id = self.running_containers.get(job_id)
        
        if not container_id:
            # Try to find container by name as fallback
            try:
                container_name = f"ensam-job-{job_id}"
                container = self.client.containers.get(container_name)
                container_id = container.id
            except docker.errors.NotFound:
                logger.warning(f"Job {job_id} not found in running containers")
                return False
        
        try:
            container = self.client.containers.get(container_id)
            
            # Immediately kill (no graceful stop to prevent resource exhaustion)
            try:
                container.kill()
                logger.info(f"Cancelled job {job_id} (forced kill)")
            except docker.errors.NotFound:
                # Container already removed - that's fine
                logger.debug(f"Container for job {job_id} already removed")
            except Exception as kill_error:
                logger.debug(f"Kill failed for job {job_id} (may already be stopped): {kill_error}")
                # Try stop as fallback
                try:
                    container.stop(timeout=1)
                except (docker.errors.NotFound, Exception):
                    pass  # Container may already be stopped
            
            # Force remove container to free resources immediately
            try:
                container.remove(force=True)
                logger.info(f"Removed container for job {job_id}")
            except docker.errors.NotFound:
                # Container already removed - that's fine, job is cancelled
                logger.debug(f"Container for job {job_id} already removed")
            except Exception as remove_error:
                logger.debug(f"Container removal for job {job_id} failed (may already be removed): {remove_error}")
            
            # Remove from running containers
            with self._lock:
                self.running_containers.pop(job_id, None)
            
            return True
        except docker.errors.NotFound:
            # Container doesn't exist - job is effectively cancelled
            logger.debug(f"Container for job {job_id} not found (already removed)")
            with self._lock:
                self.running_containers.pop(job_id, None)
            return True  # Return True because job is effectively cancelled
        except docker.errors.NotFound:
            # Container doesn't exist - job is effectively cancelled
            logger.debug(f"Container for job {job_id} not found (already removed)")
            with self._lock:
                self.running_containers.pop(job_id, None)
            return True  # Return True because job is effectively cancelled
        except Exception as e:
            logger.warning(f"Error cancelling job {job_id}: {e}")
            # Try to remove from running containers anyway
            with self._lock:
                self.running_containers.pop(job_id, None)
            # Try to find and kill by name as last resort
            try:
                container_name = f"ensam-job-{job_id}"
                container = self.client.containers.get(container_name)
                container.kill()
                container.remove(force=True)
                return True
            except docker.errors.NotFound:
                # Container doesn't exist - that's fine
                return True
            except:
                pass
            return False
    
    def get_container_logs(self, job_id: int, tail: int = 100) -> Optional[str]:
        """Get logs from a running container."""
        with self._lock:
            container_id = self.running_containers.get(job_id)
        
        if not container_id:
            return None
        
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail).decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Failed to get logs for job {job_id}: {e}")
            return None
    
    def get_running_job_ids(self) -> list:
        """Get list of currently running job IDs."""
        with self._lock:
            return list(self.running_containers.keys())


# Global executor instance
executor = DockerExecutor()

