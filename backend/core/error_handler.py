"""
Centralized error handling and logging system.
"""
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import sys

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/app.log")
    ]
)

logger = logging.getLogger("signglove")

class ErrorTracker:
    """Track and log errors with unique trace IDs."""
    
    def __init__(self):
        self.error_log: Dict[str, Dict[str, Any]] = {}
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """Log an error and return trace ID."""
        trace_id = str(uuid.uuid4())
        
        error_info = {
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }
        
        self.error_log[trace_id] = error_info
        
        # Log to structured logger
        logger.error(
            f"Error {trace_id}: {error_info['error_type']} - {error_info['error_message']}",
            extra={
                "trace_id": trace_id,
                "error_type": error_info["error_type"],
                "context": error_info["context"]
            }
        )
        
        return trace_id
    
    def get_error_info(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get error information by trace ID."""
        return self.error_log.get(trace_id)

# Global error tracker instance
error_tracker = ErrorTracker()

class SignGloveException(Exception):
    """Base exception for Sign Glove application."""
    
    def __init__(self, message: str, error_code: str = None, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

class ValidationError(SignGloveException):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(message, "VALIDATION_ERROR", 422)
        self.field = field

class AuthenticationError(SignGloveException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_ERROR", 401)

class AuthorizationError(SignGloveException):
    """Raised when authorization fails."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "AUTHZ_ERROR", 403)

class ModelError(SignGloveException):
    """Raised when model operations fail."""
    
    def __init__(self, message: str):
        super().__init__(message, "MODEL_ERROR", 500)

class DatabaseError(SignGloveException):
    """Raised when database operations fail."""
    
    def __init__(self, message: str):
        super().__init__(message, "DB_ERROR", 500)

def create_error_response(
    error: Exception,
    request: Request,
    include_traceback: bool = False
) -> JSONResponse:
    """Create standardized error response."""
    trace_id = error_tracker.log_error(error, {
        "path": request.url.path,
        "method": request.method,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent")
    })
    
    error_response = {
        "status": "error",
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
        "method": request.method
    }
    
    if isinstance(error, SignGloveException):
        error_response.update({
            "error_code": error.error_code,
            "message": error.message,
            "status_code": error.status_code
        })
        status_code = error.status_code
    elif isinstance(error, HTTPException):
        error_response.update({
            "error_code": "HTTP_ERROR",
            "message": error.detail,
            "status_code": error.status_code
        })
        status_code = error.status_code
    else:
        error_response.update({
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "status_code": 500
        })
        status_code = 500
    
    # Include traceback in development
    if include_traceback:
        error_response["traceback"] = traceback.format_exc()
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )

def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Handle validation errors."""
    return create_error_response(
        ValidationError(str(exc)),
        request
    )

def handle_authentication_error(request: Request, exc: Exception) -> JSONResponse:
    """Handle authentication errors."""
    return create_error_response(
        AuthenticationError(str(exc)),
        request
    )

def handle_database_error(request: Request, exc: Exception) -> JSONResponse:
    """Handle database errors."""
    return create_error_response(
        DatabaseError(f"Database operation failed: {str(exc)}"),
        request
    )

def handle_model_error(request: Request, exc: Exception) -> JSONResponse:
    """Handle model errors."""
    return create_error_response(
        ModelError(f"Model operation failed: {str(exc)}"),
        request
    )

# Performance monitoring
class PerformanceMonitor:
    """Monitor API performance and response times."""
    
    def __init__(self):
        self.request_times: Dict[str, list] = {}
        self.error_counts: Dict[str, int] = {}
    
    def record_request_time(self, path: str, method: str, duration: float):
        """Record request duration."""
        key = f"{method} {path}"
        if key not in self.request_times:
            self.request_times[key] = []
        self.request_times[key].append(duration)
        
        # Keep only last 1000 requests
        if len(self.request_times[key]) > 1000:
            self.request_times[key] = self.request_times[key][-1000:]
    
    def record_error(self, path: str, method: str):
        """Record error occurrence."""
        key = f"{method} {path}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = {}
        
        for key, times in self.request_times.items():
            if times:
                stats[key] = {
                    "avg_response_time": sum(times) / len(times),
                    "min_response_time": min(times),
                    "max_response_time": max(times),
                    "request_count": len(times),
                    "error_count": self.error_counts.get(key, 0)
                }
        
        return stats

# Global performance monitor
performance_monitor = PerformanceMonitor()

def log_request_performance(request: Request, duration: float):
    """Log request performance metrics."""
    performance_monitor.record_request_time(
        request.url.path,
        request.method,
        duration
    )
    
    # Log slow requests
    if duration > 1.0:  # Log requests taking more than 1 second
        logger.warning(
            f"Slow request: {request.method} {request.url.path} took {duration:.2f}s",
            extra={
                "duration": duration,
                "path": request.url.path,
                "method": request.method
            }
        ) 