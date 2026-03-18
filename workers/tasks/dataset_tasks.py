import os
import csv
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from celery.utils.log import get_task_logger

from workers.tasks.celery_app import celery_app
# We need to import the helper functions or duplicate them for the worker.
# To keep workers clean, we will re-import the core logic from services.datasets.dataset_service
# as long as those are "pure" python and don't depend on heavy ML libs.

from services.datasets.dataset_service import dataset_service
from db.base import get_sync_db
from db.models import JobRecord

logger = get_task_logger(__name__)

def _update_job_status(job_id: str, status: str, progress: int = None, error: str = None, result_location: str = None, finished: bool = False):
    """Helper to update JobRecord in Postgres."""
    with get_sync_db() as db:
        job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if job:
            job.status = status
            if progress is not None:
                job.progress = progress
            if error:
                job.error_log = error
            if result_location:
                job.result_location = result_location
            
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if status == "running" and not job.started_at:
                job.started_at = now
            if finished:
                job.finished_at = now
            
            db.commit()

@celery_app.task(name="scan_dataset_task", bind=True)
def scan_dataset_task(self, csv_name: str, include_archived: bool = True):
    """
    Background task to scan a CSV file and update its metadata.
    """
    job_id = self.request.id
    _update_job_status(job_id, "running", progress=10)
    
    try:
        self.update_state(state="PROGRESS", meta={"status": "resolving_path"})
        _, path, safe_name = dataset_service.resolve_csv_path(csv_name, include_archived)
        
        _update_job_status(job_id, "running", progress=30)
        self.update_state(state="PROGRESS", meta={"status": "scanning", "file": safe_name})
        results = dataset_service.scan_csv_file(path)
        
        _update_job_status(job_id, "running", progress=80)
        # Update sidecar metadata with worker scan results
        sidecar = dataset_service.load_sidecar(path)
        sidecar.update({
            "validation": results,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
            "status": "completed"
        })
        
        # Append to health flags if unknown schema
        if results.get("schema_id") == "unknown":
            flags = set(sidecar.get("health_flags", []))
            flags.add("worker_scan_unknown_schema")
            sidecar["health_flags"] = sorted(list(flags))
            
        dataset_service.save_sidecar(path, sidecar)
        
        _update_job_status(job_id, "completed", progress=100, result_location=str(path), finished=True)
        
        return {
            "status": "success",
            "name": safe_name,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error scanning dataset {csv_name}: {e}")
        _update_job_status(job_id, "failed", error=str(e), finished=True)
        return {
            "status": "error",
            "message": str(e)
        }
