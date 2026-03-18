"""
Middleware for performance monitoring, logging, and security.
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from api.core.error_handler import performance_monitor, log_request_performance
from api.core.auth import get_required_role_for_path

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
        log_request_performance(request, duration, status_code=response.status_code)
        
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

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from api.core.error_handler import performance_monitor, log_request_performance
from api.core.auth import get_required_role_for_path
from api.core.settings import settings
import redis

logger = logging.getLogger("signglove")

# --- Redis Rate Limiting ---

def get_redis_client():
    """Create a Redis client for rate limiting (DB 1)."""
    try:
        # Construct DB-specific URL for rate limiting
        base_url = settings.REDIS_URL.rsplit('/', 1)[0]
        rate_limit_url = f"{base_url}/{settings.REDIS_RATE_LIMIT_DB}"
        return redis.from_url(rate_limit_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to connect to Redis for rate limiting: {e}")
        return None

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed rate limiting middleware."""
    
    def __init__(self, app, requests_per_minute: int = 60, exclude_prefixes=None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.exclude_prefixes = exclude_prefixes or []
        self.redis = get_redis_client()
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip if Redis is unavailable
        if not self.redis:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path or ""
        
        # Skip excluded paths
        for prefix in self.exclude_prefixes:
            if path.startswith(prefix):
                return await call_next(request)
        
        try:
            # Use Redis INCR and EXPIRE for sliding window (1 minute)
            key = f"ratelimit:{client_ip}"
            current_count = self.redis.incr(key)
            
            if current_count == 1:
                self.redis.expire(key, 60)
            
            if current_count % 10 == 0:
                logger.debug(f"Rate limit check for {client_ip}: {current_count}/{self.requests_per_minute}")
            
            if current_count > self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for IP: {client_ip} (count: {current_count}, limit: {self.requests_per_minute})")
                return Response(
                    content='{"error": "Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json"
                )
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Fail open if Redis fails during request
            return await call_next(request)
        
        return await call_next(request)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling."""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            from api.core.error_handler import create_error_response
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
    from api.core.settings import settings
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
        exclude_prefixes=settings.RATE_LIMIT_EXCLUDE_PREFIXES
    )
    app.add_middleware(AuthenticationMiddleware) 
