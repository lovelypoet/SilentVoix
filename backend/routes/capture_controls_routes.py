from typing import Any, Dict, Optional
import os
import subprocess
import sys
import time

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/capture-controls", tags=["Capture Controls"])

# Sensor capture process (single instance)
SENSOR_CAPTURE_PROCESS: Optional[subprocess.Popen] = None
SENSOR_CAPTURE_MODE: Optional[str] = None
SENSOR_CAPTURE_STARTED_AT: Optional[float] = None
SENSOR_CAPTURE_LOG_PATH: Optional[str] = None


def _tail_file(path: str, lines: int = 40) -> list[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.readlines()[-lines:]
    except Exception:
        return []


@router.post("/sensor-capture/start")
async def start_sensor_capture(mode: str = "single") -> Dict[str, Any]:
    """
    Start the local sensor capture script (single or dual).
    """
    global SENSOR_CAPTURE_PROCESS, SENSOR_CAPTURE_MODE, SENSOR_CAPTURE_STARTED_AT, SENSOR_CAPTURE_LOG_PATH
    if mode not in ["single", "dual"]:
        raise HTTPException(status_code=400, detail="mode must be 'single' or 'dual'")

    if SENSOR_CAPTURE_PROCESS and SENSOR_CAPTURE_PROCESS.poll() is None:
        uptime = int(time.time() - SENSOR_CAPTURE_STARTED_AT) if SENSOR_CAPTURE_STARTED_AT else None
        return {
            "status": "running",
            "mode": SENSOR_CAPTURE_MODE,
            "pid": SENSOR_CAPTURE_PROCESS.pid,
            "uptime_seconds": uptime,
            "log_path": SENSOR_CAPTURE_LOG_PATH,
        }

    # Reset stale process state if previous process exited.
    SENSOR_CAPTURE_PROCESS = None

    script = "collect_data.py" if mode == "single" else "collect_dual_hand_data.py"
    script_path = os.path.join(os.path.dirname(__file__), "..", "ingestion", script)
    script_path = os.path.abspath(script_path)

    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Capture script not found: {script}")

    try:
        runtime_log = os.path.abspath(
            os.path.join(os.path.dirname(script_path), f"runtime_capture_{mode}.log")
        )
        log_handle = open(runtime_log, "a", encoding="utf-8")
        try:
            SENSOR_CAPTURE_PROCESS = subprocess.Popen(
                [sys.executable, script_path],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(script_path),
                start_new_session=True,
            )
        finally:
            log_handle.close()
        SENSOR_CAPTURE_MODE = mode
        SENSOR_CAPTURE_STARTED_AT = time.time()
        SENSOR_CAPTURE_LOG_PATH = runtime_log

        # Validate startup quickly; if it exits immediately, surface useful logs.
        time.sleep(1.0)
        exit_code = SENSOR_CAPTURE_PROCESS.poll()
        if exit_code is not None:
            tail = _tail_file(runtime_log, lines=40)
            SENSOR_CAPTURE_PROCESS = None
            SENSOR_CAPTURE_MODE = None
            SENSOR_CAPTURE_STARTED_AT = None
            SENSOR_CAPTURE_LOG_PATH = None
            raise HTTPException(
                status_code=500,
                detail={
                    "message": f"Capture process exited immediately with code {exit_code}",
                    "log_tail": tail,
                },
            )

        return {
            "status": "started",
            "mode": mode,
            "pid": SENSOR_CAPTURE_PROCESS.pid,
            "log_path": runtime_log,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start capture: {str(e)}")


@router.post("/sensor-capture/stop")
async def stop_sensor_capture() -> Dict[str, Any]:
    """
    Stop the local sensor capture script if running.
    """
    global SENSOR_CAPTURE_PROCESS, SENSOR_CAPTURE_MODE, SENSOR_CAPTURE_STARTED_AT, SENSOR_CAPTURE_LOG_PATH
    if not SENSOR_CAPTURE_PROCESS or SENSOR_CAPTURE_PROCESS.poll() is not None:
        SENSOR_CAPTURE_PROCESS = None
        SENSOR_CAPTURE_MODE = None
        SENSOR_CAPTURE_STARTED_AT = None
        return {"status": "stopped", "log_path": SENSOR_CAPTURE_LOG_PATH}
    try:
        SENSOR_CAPTURE_PROCESS.terminate()
        try:
            SENSOR_CAPTURE_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            SENSOR_CAPTURE_PROCESS.kill()
            SENSOR_CAPTURE_PROCESS.wait(timeout=2)
        SENSOR_CAPTURE_PROCESS = None
        SENSOR_CAPTURE_MODE = None
        SENSOR_CAPTURE_STARTED_AT = None
        return {"status": "stopped", "log_path": SENSOR_CAPTURE_LOG_PATH}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop capture: {str(e)}")


@router.get("/sensor-capture/status")
async def sensor_capture_status() -> Dict[str, Any]:
    """
    Check current capture process status.
    """
    global SENSOR_CAPTURE_PROCESS, SENSOR_CAPTURE_MODE, SENSOR_CAPTURE_STARTED_AT, SENSOR_CAPTURE_LOG_PATH
    if not SENSOR_CAPTURE_PROCESS:
        return {
            "status": "stopped",
            "mode": None,
            "pid": None,
            "exit_code": None,
            "uptime_seconds": None,
            "log_path": SENSOR_CAPTURE_LOG_PATH,
        }

    exit_code = SENSOR_CAPTURE_PROCESS.poll()
    if exit_code is None:
        uptime = int(time.time() - SENSOR_CAPTURE_STARTED_AT) if SENSOR_CAPTURE_STARTED_AT else None
        return {
            "status": "running",
            "mode": SENSOR_CAPTURE_MODE,
            "pid": SENSOR_CAPTURE_PROCESS.pid,
            "exit_code": None,
            "uptime_seconds": uptime,
            "log_path": SENSOR_CAPTURE_LOG_PATH,
        }

    # Process has exited; keep last known details and clear active references.
    pid = SENSOR_CAPTURE_PROCESS.pid
    mode = SENSOR_CAPTURE_MODE
    SENSOR_CAPTURE_PROCESS = None
    SENSOR_CAPTURE_MODE = None
    SENSOR_CAPTURE_STARTED_AT = None
    return {
        "status": "stopped",
        "mode": mode,
        "pid": pid,
        "exit_code": exit_code,
        "uptime_seconds": None,
        "log_path": SENSOR_CAPTURE_LOG_PATH,
    }
