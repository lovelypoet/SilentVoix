from routes import gestures_predict
from fastapi import WebSocket, WebSocketDisconnect
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from routes import training_routes, sensor_routes, admin_routes, dashboard_routes
from routes import gestures, utils_routes, auth_routes, voice_routes
from AI.gesture_model_inference import preprocess_frame, predict_gesture
from routes import model_status
from routes import audio_files_routes
from ingestion.streaming.live_data import get_latest_data
from core.indexes import create_indexes 
from core.database import client, test_connection
from core.settings import settings
from core.model import model, predict_gesture  # Ensure H5 model is loaded
from routes.auth_routes import (
    role_required_dep as role_required,
    role_or_internal_dep as role_or_internal,
)
from core.middleware import setup_middleware
from core.error_handler import create_error_response, error_tracker, performance_monitor
from contextlib import asynccontextmanager
import logging
import asyncio
from routes.auth_routes import ensure_default_editor

# Improved logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("signglove")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await test_connection() 
    await create_indexes()
    await ensure_default_editor()
    logging.info("Indexes created. App is starting...")

    # Check AI model
    if model is None:
        logging.error("H5 model is NOT loaded! WebSocket predictions will fail.")
    else:
        logging.info(f"H5 model loaded successfully from: {settings.MODEL_PATH}")

    yield
    client.close()
    logging.info("MongoDB connection closed. App is shutting down...")

app = FastAPI(title="Sign Glove API", lifespan=lifespan)

# Setup middleware
setup_middleware(app)

# Global error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return create_error_response(exc, request)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return create_error_response(exc, request)

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return create_error_response(exc, request)

# Use CORS origins from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth_routes.router)
app.include_router(gestures.router)
app.include_router(training_routes.router)
app.include_router(sensor_routes.router)
app.include_router(gestures_predict.router)
app.include_router(admin_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(utils_routes.router)
app.include_router(audio_files_routes.router)
app.include_router(voice_routes.router)
app.include_router(model_status.router)

# Mount models directory for static files if needed
app.mount("/models", StaticFiles(directory=settings.DATA_DIR), name="models")

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker containers"""
    try:
        # Test database connection
        await test_connection()
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.get("/metrics")
async def get_metrics():
    """Get performance metrics."""
    return {
        "performance": performance_monitor.get_performance_stats(),
        "errors": len(error_tracker.error_log)
    }
@app.get("/gesture/latest")
async def latest_sensor():
    data = get_latest_data()
    if data is None:
        return {"values": [], "real_sensor": False}
    return {"values": data, "real_sensor": True}

@app.websocket("/gesture/predict_ws")
async def predict_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            values = data.get("values", [])
            
            if not values:
                await ws.send_json({"status": "error", "message": "No input values"})
                continue
            
            result = predict_gesture(values)
            await ws.send_json(result)

    except WebSocketDisconnect:
        logging.info("WebSocket client disconnected")
    except Exception as e:
        logging.error(f"WebSocket prediction error: {e}")
        await ws.close()