"""
WebSocket routes for real-time log streaming.
Implements EF5 - Real-time Log Streaming.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
import asyncio
import json
from datetime import datetime
from typing import Optional
import os

from ..core.database import get_db, SessionLocal
from ..core.security import decode_access_token
from ..core.config import settings
from ..models import Job, JobStatus

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """
    Manages WebSocket connections for log streaming.
    
    Features:
    - Multiple clients can subscribe to the same job
    - Automatic cleanup on disconnect
    - Broadcast to all subscribers
    """
    
    def __init__(self):
        # job_id -> list of WebSocket connections
        self.active_connections: dict[int, list[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, job_id: int):
        """Accept a new WebSocket connection for a job."""
        await websocket.accept()
        
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        
        self.active_connections[job_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, job_id: int):
        """Remove a WebSocket connection."""
        if job_id in self.active_connections:
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)
            
            # Clean up empty lists
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
    
    async def send_log(self, job_id: int, stream: str, message: str):
        """Send a log message to all subscribers of a job."""
        if job_id not in self.active_connections:
            return
        
        log_data = {
            "type": "log",
            "job_id": job_id,
            "stream": stream,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        disconnected = []
        for connection in self.active_connections[job_id]:
            try:
                await connection.send_json(log_data)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn, job_id)
    
    async def send_status(self, job_id: int, status: str, message: str = ""):
        """Send a status update to all subscribers of a job."""
        if job_id not in self.active_connections:
            return
        
        status_data = {
            "type": "status",
            "job_id": job_id,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        disconnected = []
        for connection in self.active_connections[job_id]:
            try:
                await connection.send_json(status_data)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn, job_id)
    
    async def broadcast_to_job(self, job_id: int, data: dict):
        """Broadcast any data to all subscribers of a job."""
        if job_id not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[job_id]:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn, job_id)


# Global connection manager
manager = ConnectionManager()


def verify_ws_token(token: str) -> Optional[int]:
    """Verify WebSocket token and return user ID."""
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
    
    Messages sent:
    - type: "log" - Log line from stdout/stderr
    - type: "status" - Job status change
    - type: "error" - Error message
    - type: "complete" - Job finished
    
    Example log message:
    {
        "type": "log",
        "job_id": 123,
        "stream": "stdout",
        "message": "Hello, World!",
        "timestamp": "2025-01-01T12:00:00"
    }
    """
    # Verify token
    user_id = verify_ws_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    
    # Verify job exists and belongs to user
    db = SessionLocal()
    try:
        job = db.query(Job).filter(
            Job.id == job_id,
            Job.user_id == user_id
        ).first()
        
        if not job:
            await websocket.close(code=4004, reason="Job not found")
            return
    finally:
        db.close()
    
    # Accept connection
    await manager.connect(websocket, job_id)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "job_id": job_id,
            "status": job.status,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # If job is already finished, send existing logs and close
        if job.status in [JobStatus.SUCCESS.value, JobStatus.FAILED.value, 
                          JobStatus.CANCELLED.value, JobStatus.TIMEOUT.value]:
            await send_existing_logs(websocket, job)
            await websocket.send_json({
                "type": "complete",
                "job_id": job_id,
                "status": job.status,
                "exit_code": job.exit_code,
                "timestamp": datetime.utcnow().isoformat()
            })
            return
        
        # For running jobs, stream logs
        last_log_position = 0
        
        while True:
            # Check for client messages (e.g., cancel request)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=1.0
                )
                message = json.loads(data)
                
                if message.get("action") == "cancel":
                    # Handle cancel request
                    await websocket.send_json({
                        "type": "info",
                        "message": "Cancel request received",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass
            
            # Refresh job status
            db = SessionLocal()
            try:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job:
                    break
                
                # Check if job finished
                if job.status in [JobStatus.SUCCESS.value, JobStatus.FAILED.value,
                                  JobStatus.CANCELLED.value, JobStatus.TIMEOUT.value]:
                    # Send final logs
                    await send_existing_logs(websocket, job, last_log_position)
                    
                    await websocket.send_json({
                        "type": "complete",
                        "job_id": job_id,
                        "status": job.status,
                        "exit_code": job.exit_code,
                        "duration": job.duration_seconds,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    break
                
                # Stream new logs from running container
                from ..executor import executor
                logs = executor.get_container_logs(job_id, tail=50)
                if logs:
                    # Send new log lines
                    lines = logs.split('\n')
                    for line in lines[last_log_position:]:
                        if line.strip():
                            await websocket.send_json({
                                "type": "log",
                                "job_id": job_id,
                                "stream": "stdout",
                                "message": line,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                    last_log_position = len(lines)
                    
            finally:
                db.close()
            
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass
    finally:
        manager.disconnect(websocket, job_id)


async def send_existing_logs(websocket: WebSocket, job: Job, start_position: int = 0):
    """Send existing logs from file to WebSocket client."""
    if not job.logs_location or not os.path.exists(job.logs_location):
        return
    
    try:
        with open(job.logs_location, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines[start_position:], start=start_position):
                if line.strip():
                    await websocket.send_json({
                        "type": "log",
                        "job_id": job.id,
                        "stream": "stdout",
                        "message": line.rstrip(),
                        "line_number": i + 1,
                        "timestamp": datetime.utcnow().isoformat()
                    })
    except Exception:
        pass


# Export manager for use in executor
def get_ws_manager() -> ConnectionManager:
    """Get the global WebSocket connection manager."""
    return manager








