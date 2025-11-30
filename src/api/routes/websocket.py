"""
WebSocket routes for real-time log streaming.

Implements EF5: Real-time streaming of stdout/stderr.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
import os
import logging

from ...core.database import SessionLocal
from ...core.security import decode_access_token
from ...core.config import settings
from ...models import Job, JobStatus
from ...services.executor import executor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """
    Manages WebSocket connections for log streaming.
    
    Supports multiple clients subscribing to the same job.
    """
    
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, job_id: int):
        """Accept and register a new connection."""
        await websocket.accept()
        
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        
        self.active_connections[job_id].append(websocket)
        logger.debug(f"WebSocket connected for job {job_id}")
    
    def disconnect(self, websocket: WebSocket, job_id: int):
        """Remove a connection."""
        if job_id in self.active_connections:
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)
            
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
    
    async def send_log(self, job_id: int, stream: str, message: str):
        """Send log message to all subscribers."""
        if job_id not in self.active_connections:
            return
        
        data = {
            "type": "log",
            "job_id": job_id,
            "stream": stream,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        disconnected = []
        for ws in self.active_connections[job_id]:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.disconnect(ws, job_id)
    
    async def send_status(self, job_id: int, status: str, **kwargs):
        """Send status update to all subscribers."""
        if job_id not in self.active_connections:
            return
        
        data = {
            "type": "status",
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        
        disconnected = []
        for ws in self.active_connections[job_id]:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.disconnect(ws, job_id)


# Global connection manager
manager = ConnectionManager()


def verify_token(token: str) -> Optional[int]:
    """Verify JWT and return user ID."""
    payload = decode_access_token(token)
    if payload and "sub" in payload:
        return int(payload["sub"])
    return None


@router.websocket("/ws/jobs/{job_id}/logs")
async def websocket_job_logs(
    websocket: WebSocket,
    job_id: int,
    token: str = Query(...)
):
    """
    WebSocket endpoint for real-time job log streaming.
    
    Connect with: ws://host/ws/jobs/{job_id}/logs?token={jwt_token}
    
    Message types sent:
    - connected: Initial connection confirmation
    - log: Log line (stdout/stderr)
    - status: Job status change
    - complete: Job finished
    - error: Error message
    
    Example:
    ```json
    {
        "type": "log",
        "job_id": 123,
        "stream": "stdout",
        "message": "Hello, World!",
        "timestamp": "2025-01-01T12:00:00"
    }
    ```
    """
    # Verify token
    user_id = verify_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    
    # Verify job access
    db = SessionLocal()
    try:
        job = db.query(Job).filter(
            Job.id == job_id,
            Job.user_id == user_id
        ).first()
        
        if not job:
            await websocket.close(code=4004, reason="Job not found")
            return
        
        initial_status = job.status
    finally:
        db.close()
    
    # Accept connection
    await manager.connect(websocket, job_id)
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "job_id": job_id,
            "status": initial_status,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # If job already finished, send logs and close
        if initial_status in [JobStatus.SUCCESS.value, JobStatus.FAILED.value,
                               JobStatus.CANCELLED.value, JobStatus.TIMEOUT.value]:
            await send_existing_logs(websocket, job_id)
            await websocket.send_json({
                "type": "complete",
                "job_id": job_id,
                "status": initial_status,
                "timestamp": datetime.utcnow().isoformat()
            })
            return
        
        # Stream logs for running job
        last_position = 0
        
        while True:
            # Check for client messages
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=1.0
                )
                msg = json.loads(data)
                
                if msg.get("action") == "cancel":
                    await websocket.send_json({
                        "type": "info",
                        "message": "Cancel request received"
                    })
                    
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass
            
            # Check job status
            db = SessionLocal()
            try:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job:
                    break
                
                current_status = job.status
                
                # Job finished
                if current_status in [JobStatus.SUCCESS.value, JobStatus.FAILED.value,
                                       JobStatus.CANCELLED.value, JobStatus.TIMEOUT.value]:
                    await send_existing_logs(websocket, job_id, last_position)
                    
                    await websocket.send_json({
                        "type": "complete",
                        "job_id": job_id,
                        "status": current_status,
                        "exit_code": job.exit_code,
                        "duration": job.duration_seconds,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    break
                
                # Get live logs
                logs = executor.get_container_logs(job_id, tail=50)
                if logs:
                    lines = logs.split('\n')
                    for line in lines[last_position:]:
                        if line.strip():
                            await websocket.send_json({
                                "type": "log",
                                "job_id": job_id,
                                "stream": "stdout",
                                "message": line,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                    last_position = len(lines)
                    
            finally:
                db.close()
            
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        manager.disconnect(websocket, job_id)


async def send_existing_logs(websocket: WebSocket, job_id: int, start: int = 0):
    """Send existing logs from file."""
    logs_path = os.path.join(settings.LOGS_DIR, str(job_id), "output.log")
    
    if not os.path.exists(logs_path):
        return
    
    try:
        with open(logs_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[start:], start=start):
                if line.strip():
                    await websocket.send_json({
                        "type": "log",
                        "job_id": job_id,
                        "stream": "stdout",
                        "message": line.rstrip(),
                        "line_number": i + 1,
                        "timestamp": datetime.utcnow().isoformat()
                    })
    except Exception as e:
        logger.warning(f"Failed to send logs for job {job_id}: {e}")


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager








