"""
Authentication and authorization system for Sign Glove API.
Handles JWT tokens, password hashing, and role-based access control.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
import logging

logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme (do not auto-error so we can return 401 consistently)
security = HTTPBearer(auto_error=False)

# User roles
class UserRole:
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

# Pydantic models
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    role: str = UserRole.USER
    disabled: bool = False

class UserInDB(User):
    hashed_password: str

ROUTE_PERMISSIONS = {
    # Admin routes
    "/admin": UserRole.ADMIN,
    "/training/trigger": UserRole.ADMIN,
    "/training/": UserRole.ADMIN,
    "/api/admin": UserRole.ADMIN,
    "/api/training/trigger": UserRole.ADMIN,
    "/api/training/": UserRole.ADMIN,

    # User routes (can read/write data)
    "/gestures": UserRole.USER,
    "/predict": UserRole.USER,
    "/sensor-data": UserRole.USER,
    "/upload": UserRole.USER,
    "/api/gestures": UserRole.USER,
    "/api/predict": UserRole.USER,
    "/api/sensor-data": UserRole.USER,
    "/api/upload": UserRole.USER,

    # Viewer routes (read-only)
    "/dashboard": UserRole.VIEWER,
    "/training-results": UserRole.VIEWER,
    "/history": UserRole.VIEWER,
    "/live-predict": UserRole.VIEWER,
    "/api/dashboard": UserRole.VIEWER,
    "/api/training-results": UserRole.VIEWER,
    "/api/history": UserRole.VIEWER,
    "/api/live-predict": UserRole.VIEWER,
}

def get_required_role_for_path(path: str) -> str:
    """Get required role for a given API path."""
    for route, role in ROUTE_PERMISSIONS.items():
        if path.startswith(route):
            return role
    return UserRole.VIEWER  # Default to viewer for unknown routes

# Default users (in production, these should be in database)
DEFAULT_USERS = {
    "admin": {
        "username": "admin",
        "email": "admin@signglove.com",
        "role": UserRole.ADMIN,
        "hashed_password": pwd_context.hash("admin123"),
        "disabled": False
    },
    "user": {
        "username": "user",
        "email": "user@signglove.com", 
        "role": UserRole.USER,
        "hashed_password": pwd_context.hash("user123"),
        "disabled": False
    },
    "viewer": {
        "username": "viewer",
        "email": "viewer@signglove.com",
        "role": UserRole.VIEWER,
        "hashed_password": pwd_context.hash("viewer123"),
        "disabled": False
    }
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)

def get_user(username: str) -> Optional[UserInDB]:
    """Get user from database (or default users for now)."""
    if username in DEFAULT_USERS:
        user_dict = DEFAULT_USERS[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate user with username and password."""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if user.disabled:
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or not credentials.credentials:
        # No Authorization header provided
        raise credentials_exception
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "access":
            raise credentials_exception
            
        token_data = TokenData(username=username, role=payload.get("role"))
    except JWTError:
        raise credentials_exception
    
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(required_role: str):
    """Dependency to require specific user role."""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role == UserRole.ADMIN:
            return current_user  # Admin has access to everything
        
        if required_role == UserRole.USER and current_user.role in [UserRole.USER, UserRole.VIEWER]:
            return current_user
        
        if required_role == UserRole.VIEWER and current_user.role == UserRole.VIEWER:
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return role_checker

# Role-based dependencies
require_admin = require_role(UserRole.ADMIN)
require_user = require_role(UserRole.USER)
require_viewer = require_role(UserRole.VIEWER)

