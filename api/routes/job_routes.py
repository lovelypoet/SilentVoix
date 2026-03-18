from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import AsyncSessionLocal
from api.routes.auth_routes import get_current_user_dep
from db.models import User, JobRecord
from celery.result import AsyncResult
from workers.tasks.celery_app import celery_app

router = APIRouter(prefix="/jobs", tags=["Jobs"])

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    task_type: str
    status: str
    progress: int
    input_payload: Dict[str, Any]
    error_log: Optional[str] = None
    result_location: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    # Celery-specific live info
    celery_status: Optional[str] = None
    celery_result: Any = None

class JobListResponse(BaseModel):
    status: str = "success"
    jobs: List[JobResponse]
    total: int

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    task_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_dep)
):
    """List jobs for the current user."""
    query = select(JobRecord).where(JobRecord.user_id == user.id)
    
    if task_type:
        query = query.where(JobRecord.task_type == task_type)
        
    query = query.order_by(desc(JobRecord.created_at)).offset(offset).limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Count total for pagination
    # (Simplified for now, in production use a count query)
    
    response_jobs = []
    for job in jobs:
        job_data = JobResponse.model_validate(job)
        
        # Try to sync with Celery if job is still active/recent
        try:
            res = AsyncResult(str(job.id))
            job_data.celery_status = res.status
        except Exception:
            pass
            
        response_jobs.append(job_data)
        
    return {
        "status": "success",
        "jobs": response_jobs,
        "total": len(response_jobs) # FIXME: actual total count
    }

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_dep)
):
    """Get detailed job status."""
    query = select(JobRecord).where(JobRecord.id == job_id)
    result = await db.execute(query)
    job = result.scalars().first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Security check: only owner or admin can see job
    if job.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
        
    job_data = JobResponse.model_validate(job)
    
    # Enrich with live Celery data
    try:
        res = AsyncResult(str(job.id))
        job_data.celery_status = res.status
        if res.ready():
            job_data.celery_result = res.result
    except Exception:
        pass
        
    return job_data
