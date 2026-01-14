"""
Middleware for performance monitoring, logging, and security.
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from core.error_handler import performance_monitor, log_request_performance
from core.auth import get_required_role_for_path

logger = logging.getLogger("signglove")

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to monitor request performance."""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log performance metrics
        log_request_performance(request, duration)
        
        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response

class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers."""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Log incoming request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Log response
        logger.info(
            f"Response: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "content_length": response.headers.get("content-length", 0)
            }
        )
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old entries (older than 1 minute)
        self.request_counts = {
            ip: times for ip, times in self.request_counts.items()
            if any(current_time - t < 60 for t in times)
        }
        
        # Check rate limit
        if client_ip in self.request_counts:
            recent_requests = [t for t in self.request_counts[client_ip] if current_time - t < 60]
            if len(recent_requests) >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return Response(
                    content='{"error": "Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json"
                )
        
        # Add current request
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        self.request_counts[client_ip].append(current_time)
        
        return await call_next(request)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling."""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            from core.error_handler import create_error_response
            return create_error_response(e, request)

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to check authentication for protected routes."""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip authentication for public routes
        public_routes = ["/auth/login", "/auth/refresh", "/health", "/docs", "/redoc", "/openapi.json"]
        
        if request.url.path in public_routes or request.url.path.startswith("/static"):
            return await call_next(request)
        
        # Check if route requires authentication
        required_role = get_required_role_for_path(request.url.path)
        
        # For now, just log the required role (actual auth is handled by FastAPI dependencies)
        logger.debug(f"Route {request.url.path} requires role: {required_role}")
        
        return await call_next(request)

def setup_middleware(app):
    """Setup all middleware for the FastAPI app."""
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(PerformanceMiddleware)
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthenticationMiddleware) 