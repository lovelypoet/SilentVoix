import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from core.settings import settings
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/video-library", tags=["Video Library"])

VIDEO_LIBRARY_DIR = Path(settings.DATA_DIR) / "video_library"
REGISTRY_PATH = VIDEO_LIBRARY_DIR / "registry.json"
OUTPUT_DIR = Path(settings.DATA_DIR) / "video_process_outputs"

VIDEO_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_ITEMS = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry() -> Dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text())
        except Exception:
            pass
    return {"videos": [], "limit": MAX_ITEMS}


def _save_registry(registry: Dict[str, Any]) -> None:
    registry["limit"] = MAX_ITEMS
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


def _output_path_for(job_id: str) -> Path:
    return OUTPUT_DIR / f"{job_id}_processed.mp4"


def _prune_registry(registry: Dict[str, Any]) -> None:
    videos = registry.get("videos", [])
    videos.sort(key=lambda v: v.get("created_at", ""), reverse=True)
    keep = videos[:MAX_ITEMS]
    removed = videos[MAX_ITEMS:]
    for entry in removed:
        job_id = entry.get("id")
        if job_id:
            path = _output_path_for(job_id)
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
    registry["videos"] = keep


def _worker_url() -> str:
    return os.getenv("VIDEO_PROCESSOR_WORKER_URL", "http://worker-video-processor:8095").rstrip("/")


def _use_worker() -> bool:
    raw = os.getenv("USE_VIDEO_PROCESSOR_WORKER", "true").lower().strip()
    return raw in {"1", "true", "yes", "y"}


async def _refresh_job(entry: Dict[str, Any]) -> Dict[str, Any]:
    if not _use_worker():
        return entry
    job_id = entry.get("id")
    if not job_id:
        return entry
    if entry.get("status") in {"completed", "failed"}:
        return entry
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(f"{_worker_url()}/v1/jobs/{job_id}")
            res.raise_for_status()
            payload = res.json()
    except Exception:
        return entry

    entry["status"] = payload.get("status", entry.get("status"))
    entry["progress"] = payload.get("progress", entry.get("progress", 0))
    entry["error"] = payload.get("error")
    entry["updated_at"] = _utc_now()
    entry["result"] = payload.get("result")
    return entry


@router.get("")
async def list_videos(_user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    videos = registry.get("videos", [])
    refreshed: List[Dict[str, Any]] = []
    for entry in videos:
        refreshed.append(await _refresh_job(entry))
    registry["videos"] = refreshed
    _save_registry(registry)
    return {"status": "success", "videos": registry.get("videos", []), "limit": MAX_ITEMS}


@router.get("/{job_id}")
async def get_video(job_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    entry = next((v for v in registry.get("videos", []) if v.get("id") == job_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Video not found")
    entry = await _refresh_job(entry)
    _save_registry(registry)
    return {"status": "success", "video": entry}


@router.post("/upload")
async def upload_video(
    video_file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    options_json: str = Form("{}"),
    _user=Depends(role_or_internal_dep("editor"))
):
    if not _use_worker():
        raise HTTPException(status_code=503, detail="Video processor worker is disabled.")
    if not video_file.filename:
        raise HTTPException(status_code=400, detail="Missing video file")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                "video_file": (video_file.filename, await video_file.read(), video_file.content_type or "video/mp4")
            }
            data = {"options_json": options_json}
            res = await client.post(f"{_worker_url()}/v1/jobs/process", files=files, data=data)
            res.raise_for_status()
            payload = res.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Worker error: {exc}")

    job_id = payload.get("job_id")
    if not job_id:
        raise HTTPException(status_code=502, detail="Worker did not return job_id")

    entry = {
        "id": job_id,
        "name": name or Path(video_file.filename).stem,
        "status": payload.get("status", "queued"),
        "progress": payload.get("progress", 0.0),
        "created_at": payload.get("created_at") or _utc_now(),
        "updated_at": _utc_now(),
        "result": payload.get("result"),
        "error": payload.get("error"),
        "input_file": video_file.filename,
        "output_file": _output_path_for(job_id).name,
    }

    registry = _load_registry()
    registry.setdefault("videos", [])
    registry["videos"] = [v for v in registry["videos"] if v.get("id") != job_id]
    registry["videos"].insert(0, entry)
    _prune_registry(registry)
    _save_registry(registry)

    return {"status": "success", "video": entry}


@router.delete("/{job_id}")
async def delete_video(job_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    videos = registry.get("videos", [])
    entry = next((v for v in videos if v.get("id") == job_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Video not found")
    registry["videos"] = [v for v in videos if v.get("id") != job_id]
    _save_registry(registry)

    output_path = _output_path_for(job_id)
    if output_path.exists():
        try:
            output_path.unlink()
        except Exception:
            pass

    return {"status": "success", "deleted_id": job_id}


@router.get("/{job_id}/download")
async def download_video(job_id: str, _user=Depends(role_or_internal_dep("editor"))):
    output_path = _output_path_for(job_id)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output video not found")
    return FileResponse(path=str(output_path), filename=output_path.name, media_type="video/mp4")

