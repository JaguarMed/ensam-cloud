"""
Job management routes.

Implements:
- EF2: Script upload/edition and job submission
- EF6: Job history and result visualization
- EF8: Manual job cancellation
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import logging
import asyncio
import os
import io
import pandas as pd

from ...core.config import settings
from ...core.database import get_db, SessionLocal
from ...core.security import get_current_user
from ...models import Job, JobStatus, JobMetrics, User
from ...schemas import (
    JobSubmitRequest, JobSubmitResponse,
    JobResponse, JobDetailResponse, JobListResponse,
    JobCancelResponse
)
from ...services.executor import executor
from ...services.metrics import metrics
from ...services.script_analyzer import analyze_script, ScriptAnalysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/analyze")
async def analyze_script_endpoint(
    request: JobSubmitRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Analyze a script to preview resource allocation without submitting.
    
    Returns the recommended profile, execution mode, and reasoning.
    Useful for users to understand what resources will be allocated.
    """
    gpu_available = executor.gpu_available if executor.is_available else False
    analysis: ScriptAnalysis = analyze_script(request.code, gpu_available)
    
    return {
        "success": True,
        "analysis": {
            "recommended_profile": analysis.recommended_profile,
            "execution_mode": analysis.execution_mode,
            "detected_libraries": analysis.detected_libraries,
            "gpu_indicators": analysis.gpu_indicators,
            "memory_indicators": analysis.memory_indicators,
            "compute_indicators": analysis.compute_indicators,
            "confidence": analysis.confidence,
            "reasoning": analysis.reasoning
        },
        "gpu_available": gpu_available
    }


async def run_job_background(job_id: int):
    """Background task to execute a job."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found for execution")
            return
        
        # Mark as queued
        job.status = JobStatus.QUEUED.value
        job.queued_at = datetime.utcnow()
        db.commit()
        
        # Record job start
        metrics.job_started(job)
        
        # Execute
        job = await executor.execute_job(job, db)
        
        # Record completion
        metrics.job_completed(job)
        
    except Exception as e:
        logger.error(f"Error executing job {job_id}: {e}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@router.post("/run", response_model=JobSubmitResponse)
async def submit_job(
    request: JobSubmitRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a Python script for execution.
    
    Implements EF2: Script submission with AUTO-ALLOCATION.
    
    - **code**: Python code to execute
    - **script_name**: Optional name for the script
    - **execution_mode**: 'cpu', 'gpu', or 'auto' (recommended)
    - **resource_profile**: 'small', 'medium', 'large', 'gpu', or 'auto' (recommended)
    - **timeout**: Maximum execution time in seconds
    
    When 'auto' is selected, the system analyzes the script to detect:
    - GPU libraries (torch, tensorflow, etc.)
    - Memory-intensive operations (pandas, numpy, etc.)
    - Compute patterns (training loops, large iterations)
    """
    # Détection automatique comme Google Colab - toujours en mode auto
    # Analyse le script pour déterminer automatiquement GPU/CPU et ressources
    gpu_available = executor.gpu_available if executor.is_available else False
    analysis: ScriptAnalysis = analyze_script(request.code, gpu_available)
    
    auto_allocated = True
    analysis_reasoning = analysis.reasoning
    
    # Utilise la détection automatique pour le mode d'exécution
    exec_mode = analysis.execution_mode
    
    # Utilise le profil demandé ou la détection automatique
    if request.resource_profile.value == "auto":
        resource_profile = analysis.recommended_profile
    else:
        resource_profile = request.resource_profile.value
        # Si l'utilisateur choisit GPU manuellement, force le mode GPU
        if resource_profile == "gpu":
            exec_mode = "gpu"
    
    # Apply custom configuration if provided
    timeout_seconds = request.timeout
    custom_config_json = None
    if request.custom_config:
        # Override timeout if custom timeout is provided
        if "timeout" in request.custom_config:
            timeout_seconds = max(10, min(request.custom_config["timeout"], 3600))
        # Store custom config as JSON string for executor to use
        import json
        custom_config_json = json.dumps(request.custom_config)
        # Store custom config in analysis_reasoning for reference
        custom_info = f"Custom config: {request.custom_config}"
        analysis_reasoning = f"{analysis_reasoning} | {custom_info}"
    
    logger.info(f"Auto-allocation (Colab-style): profile={resource_profile}, mode={exec_mode}, reason={analysis.reasoning}")
    
    # Create job record
    job = Job(
        user_id=current_user.id,
        script_name=request.script_name,
        script_content=request.code,
        status=JobStatus.PENDING.value,
        execution_mode=exec_mode,
        resource_profile=resource_profile,
        timeout_seconds=timeout_seconds,
        auto_allocated=auto_allocated,
        analysis_reasoning=analysis_reasoning
    )
    
    # Store custom config in a way executor can access it
    # We'll use a custom attribute or store in analysis_reasoning
    if custom_config_json:
        # Store in analysis_reasoning with a special marker
        job.analysis_reasoning = f"{analysis_reasoning} | CUSTOM_CONFIG:{custom_config_json}"
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    message = "Job submitted successfully"
    if auto_allocated:
        message = f"Job submitted with auto-allocation: {resource_profile} profile, {exec_mode} mode"
    
    logger.info(f"Job {job.id} submitted by user {current_user.id} (auto={auto_allocated})")
    
    # Start execution in background
    background_tasks.add_task(run_job_background, job.id)
    
    return JobSubmitResponse(
        success=True,
        job_id=job.id,
        status=job.status,
        message=message
    )


@router.post("/upload", response_model=JobSubmitResponse)
async def upload_and_run(
    file: UploadFile = File(...),
    execution_mode: str = Form(default="cpu"),
    resource_profile: str = Form(default="medium"),
    timeout: int = Form(default=300),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a .py file and execute it.
    
    Implements EF2: File upload for script submission.
    """
    # Validate file
    if not file.filename.endswith('.py'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .py files are allowed"
        )
    
    # Read file content
    content = await file.read()
    try:
        code = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded"
        )
    
    # Create job
    job = Job(
        user_id=current_user.id,
        script_name=file.filename,
        script_content=code,
        status=JobStatus.PENDING.value,
        execution_mode=execution_mode,
        resource_profile=resource_profile,
        timeout_seconds=timeout
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    logger.info(f"Job {job.id} created from upload: {file.filename}")
    
    # Start execution
    background_tasks.add_task(run_job_background, job.id)
    
    return JobSubmitResponse(
        success=True,
        job_id=job.id,
        status=job.status,
        message=f"Script '{file.filename}' submitted successfully"
    )


@router.get("/history", response_model=JobListResponse)
async def get_job_history(
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get job history for the current user.
    
    Implements EF6: Job history visualization.
    
    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20)
    - **status_filter**: Filter by status (optional)
    """
    query = db.query(Job).filter(Job.user_id == current_user.id)
    
    if status_filter:
        query = query.filter(Job.status == status_filter)
    
    # Get total count
    total = query.count()
    
    # Paginate
    jobs = query.order_by(desc(Job.created_at))\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    pages = (total + per_page - 1) // per_page
    
    return JobListResponse(
        success=True,
        jobs=[JobResponse(
            id=j.id,
            job_id=str(j.id),
            user_id=j.user_id,
            script_name=j.script_name,
            status=j.status,
            execution_mode=j.execution_mode,
            resource_profile=j.resource_profile,
            timeout_seconds=j.timeout_seconds,
            container_id=j.container_id,
            created_at=j.created_at,
            started_at=j.started_at,
            finished_at=j.finished_at,
            duration_seconds=j.duration_seconds,
            queue_time_seconds=j.queue_time_seconds,
            gpu_used=j.gpu_used,
            exit_code=j.exit_code,
            error_message=j.error_message,
            auto_allocated=j.auto_allocated or False,
            analysis_reasoning=j.analysis_reasoning
        ) for j in jobs],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_detail(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information for a specific job.
    
    Implements EF6: Job details visualization.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get logs if available
    output = None
    if job.logs_location and os.path.exists(job.logs_location):
        try:
            with open(job.logs_location, 'r', encoding='utf-8') as f:
                output = f.read()
        except Exception:
            pass
    
    # Get metrics
    job_metrics = None
    if job.metrics:
        job_metrics = job.metrics.to_dict()
    
    return JobDetailResponse(
        id=job.id,
        job_id=str(job.id),
        user_id=job.user_id,
        script_name=job.script_name,
        script_content=job.script_content,
        status=job.status,
        execution_mode=job.execution_mode,
        resource_profile=job.resource_profile,
        timeout_seconds=job.timeout_seconds,
        container_id=job.container_id,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        duration_seconds=job.duration_seconds,
        queue_time_seconds=job.queue_time_seconds,
        gpu_used=job.gpu_used,
        exit_code=job.exit_code,
        error_message=job.error_message,
        logs_location=job.logs_location,
        results_location=job.results_location,
        output=output,
        error=job.error_message
    )


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: int,
    tail: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get logs for a job.
    
    For running jobs, returns live container logs.
    For finished jobs, returns stored log file.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    logs = ""
    
    # Check if job is running
    if job.status in [JobStatus.RUNNING.value, JobStatus.QUEUED.value]:
        # Get live logs from container
        container_logs = executor.get_container_logs(job.id, tail=tail)
        if container_logs:
            logs = container_logs
    else:
        # Get logs from file
        if job.logs_location and os.path.exists(job.logs_location):
            try:
                with open(job.logs_location, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    logs = "".join(lines[-tail:])
            except Exception:
                pass
    
    return {
        "success": True,
        "job_id": job_id,
        "status": job.status,
        "logs": logs
    }


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
async def cancel_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a running or queued job.
    
    Implements EF8: Manual job cancellation.
    """
    # First check if job exists (without user filter)
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Check if user owns the job or is admin
    if job.user_id != current_user.id and not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to cancel this job"
        )
    
    # Check if job is cancellable, but allow cancellation even if status suggests otherwise
    # (user might want to stop a job that's in a weird state)
    if job.status in [JobStatus.SUCCESS.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value, JobStatus.TIMEOUT.value]:
        # Job is already finished, but we can still mark it as cancelled if user wants
        logger.info(f"Job {job_id} is already finished (status: {job.status}), but allowing cancellation for cleanup")
    elif not job.is_cancellable:
        # For other statuses, check if it's really not cancellable
        logger.warning(f"Job {job_id} has status {job.status} which is not normally cancellable, but attempting anyway")
    
    # Try to stop container (even if not running, try to clean up)
    try:
        await executor.cancel_job(job.id)
    except Exception as e:
        logger.warning(f"Error stopping container for job {job_id}: {e}")
        # Continue anyway to update status
    
    # Update status
    job.status = JobStatus.CANCELLED.value
    job.finished_at = datetime.utcnow()
    if job.started_at:
        job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
    
    db.commit()
    
    logger.info(f"Job {job_id} cancelled by user {current_user.id}")
    
    return JobCancelResponse(
        success=True,
        message="Job cancelled successfully",
        job_id=job_id,
        status=job.status
    )


@router.get("/{job_id}/results")
async def get_job_results(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get result files for a completed job.
    
    Implements EF6: Result visualization.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get output directory
    output_dir = Path(settings.SCRIPTS_DIR) / str(job_id) / "output"
    
    files = []
    if output_dir.exists():
        for f in output_dir.iterdir():
            if f.is_file():
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "path": str(f)
                })
    
    return {
        "success": True,
        "job_id": job_id,
        "status": job.status,
        "files": files
    }


@router.get("/{job_id}/files")
async def get_job_files(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all files available for download from a job's output directory.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check ownership
    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    files = []
    if job.results_location and os.path.exists(job.results_location):
        output_dir = Path(job.results_location)
        if output_dir.exists() and output_dir.is_dir():
            for file_path in output_dir.iterdir():
                if file_path.is_file():
                    files.append({
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime
                    })
    
    return {"success": True, "files": files}


@router.get("/{job_id}/download/{filename:path}")
async def download_job_file(
    job_id: int,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download a file from a completed job's output directory.
    
    Supports downloading Excel, CSV, and other files generated by the job.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get output directory
    output_dir = Path(settings.SCRIPTS_DIR) / str(job_id) / "output"
    file_path = output_dir / filename
    
    # Security: prevent directory traversal
    if not file_path.resolve().is_relative_to(output_dir.resolve()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Determine media type
    file_ext = file_path.suffix.lower()
    media_types = {
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.csv': 'text/csv',
        '.json': 'application/json',
        '.txt': 'text/plain',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.pdf': 'application/pdf'
    }
    media_type = media_types.get(file_ext, 'application/octet-stream')
    
    def iterfile():
        with open(file_path, 'rb') as f:
            yield from f
    
    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.post("/upload-data")
async def upload_data_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV or Excel file and return its preview.
    
    Supports:
    - CSV files (.csv)
    - Excel files (.xlsx, .xls)
    
    Returns a preview of the data (first 10 rows) and basic statistics.
    """
    # Validate file extension
    allowed_extensions = ['.csv', '.xlsx', '.xls']
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Parse based on file type
        if file_ext == '.csv':
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding, nrows=1000)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not decode CSV file. Try saving as UTF-8."
                )
        else:  # Excel
            df = pd.read_excel(io.BytesIO(content), nrows=1000)
        
        # Get preview (first 10 rows)
        preview = df.head(10).to_dict(orient='records')
        
        # Get basic statistics
        stats = {
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "memory_usage": df.memory_usage(deep=True).sum()
        }
        
        # Get summary statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            stats["numeric_summary"] = df[numeric_cols].describe().to_dict()
        
        return {
            "success": True,
            "filename": file.filename,
            "preview": preview,
            "statistics": stats,
            "message": f"File '{file.filename}' uploaded successfully. {len(df)} rows, {len(df.columns)} columns."
        }
        
    except Exception as e:
        logger.error(f"Error processing data file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        )


@router.post("/export-excel")
async def export_dataframe_to_excel(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Export a DataFrame to Excel format.
    
    Accepts JSON body in the format:
    {
        "data": [{"col1": val1, "col2": val2}, ...] OR
        "columns": ["col1", "col2", ...],
        "rows": [[val1, val2, ...], ...],
        "filename": "export.xlsx" (optional)
    }
    
    Returns an Excel file for download.
    """
    try:
        body = await request.json()
        filename = body.get("filename", "export.xlsx")
        
        # Create DataFrame from provided data
        if "data" in body and isinstance(body["data"], list):
            # If data is a list of dictionaries
            df = pd.DataFrame(body["data"])
        elif "columns" in body and "rows" in body:
            # If data is in columns/rows format
            df = pd.DataFrame(body["rows"], columns=body["columns"])
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data format. Expected {'data': [...]} or {'columns': [...], 'rows': [[...]]}"
            )
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        output.seek(0)
        
        # Ensure filename has .xlsx extension
        if not filename.endswith('.xlsx'):
            filename = f"{filename}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting to Excel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating Excel file: {str(e)}"
        )


