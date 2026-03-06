from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal, List
from jose import jwt, JWTError
from passlib.context import CryptContext
from core.settings import settings
from core.database import users_collection

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class AlertChannels(BaseModel):
    in_app: bool = True
    email: bool = False
    slack: bool = False

class QuietHours(BaseModel):
    enabled: bool = False
    start: str = "22:00"
    end: str = "07:00"
    timezone: str = "UTC"

class DashboardDefaults(BaseModel):
    window: str = "24h"
    refresh_seconds: int = 30
    segment_filter: str = "all"

class OperatorPreferences(BaseModel):
    alert_channels: AlertChannels = Field(default_factory=AlertChannels)
    alert_min_severity: Literal["warning", "critical"] = "warning"
    quiet_hours: QuietHours = Field(default_factory=QuietHours)
    dashboard_defaults: DashboardDefaults = Field(default_factory=DashboardDefaults)

class AccessScope(BaseModel):
    environments: List[str] = Field(default_factory=lambda: ["production"])
    models: List[str] = Field(default_factory=list)

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    operator_preferences: Optional[OperatorPreferences] = None
    access_scope: Optional[AccessScope] = None

class UserPublic(BaseModel):
    id: str
    email: EmailStr
    role: Literal["guest", "editor", "admin"]
    display_name: Optional[str] = None
    operator_preferences: OperatorPreferences = Field(default_factory=OperatorPreferences)
    access_scope: AccessScope = Field(default_factory=AccessScope)

COOKIE_NAME = "access_token"

def _normalized_operator_preferences(raw: Optional[dict]) -> dict:
    if isinstance(raw, dict):
        try:
            return OperatorPreferences(**raw).model_dump()
        except Exception:
            pass
    return OperatorPreferences().model_dump()

def _normalized_access_scope(raw: Optional[dict]) -> dict:
    if isinstance(raw, dict):
        try:
            data = AccessScope(**raw).model_dump()
            data["environments"] = [str(v).strip().lower() for v in data.get("environments", []) if str(v).strip()]
            data["models"] = [str(v).strip() for v in data.get("models", []) if str(v).strip()]
            return data
        except Exception:
            pass
    return AccessScope().model_dump()

async def get_user_by_email(email: str) -> Optional[dict]:
    return await users_collection.find_one({"email": email})

async def create_user(email: str, password: str, role: str = "editor") -> str:
    hashed = pwd_context.hash(password)
    doc = {"email": email, "password_hash": hashed, "role": role, "created_at": datetime.now(timezone.utc)}
    result = await users_collection.insert_one(doc)
    return str(result.inserted_id)

async def ensure_default_editor():
    if settings.DEFAULT_EDITOR_EMAIL and settings.DEFAULT_EDITOR_PASSWORD:
        existing = await users_collection.find_one({"email": settings.DEFAULT_EDITOR_EMAIL})
        if not existing:
            await create_user(settings.DEFAULT_EDITOR_EMAIL, settings.DEFAULT_EDITOR_PASSWORD, role="editor")

async def ensure_default_users():
    """
    Seed default users once in development-like environments.
    Uses existence checks by email, so it is safe to call repeatedly.
    """
    if not settings.AUTO_SEED_DEFAULT_USERS:
        return

    default_users = [
        (settings.DEFAULT_ADMIN_EMAIL, settings.DEFAULT_ADMIN_PASSWORD, "admin"),
        (settings.DEFAULT_EDITOR_EMAIL, settings.DEFAULT_EDITOR_PASSWORD, "editor"),
        (settings.DEFAULT_GUEST_EMAIL, settings.DEFAULT_GUEST_PASSWORD, "guest"),
    ]

    for email, password, role in default_users:
        if not email or not password:
            continue
        existing = await users_collection.find_one({"email": email})
        if not existing:
            await create_user(email, password, role=role)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("authorization")
    token = None
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    
    if not token:
        token = request.cookies.get(COOKIE_NAME)
        
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    user = await users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    return user

def role_required(min_role: Literal["guest", "editor", "admin"]):
    order = {"guest": 0, "editor": 1, "admin": 2}
    async def dependency(user: dict = Depends(get_current_user)):
        user_role = user.get("role", "guest")
        if order[user_role] < order[min_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency

# Allow internal calls (e.g., from same service/scripts) via X-API-KEY header
# If header matches SECRET_KEY, bypass role checks; else require min_role
def role_or_internal(min_role: Literal["guest", "editor", "admin"]):
    order = {"guest": 0, "editor": 1, "admin": 2}
    async def dependency(request: Request):
        api_key = request.headers.get("x-api-key")
        if api_key and api_key == settings.SECRET_KEY:
            return {"role": "admin", "email": "internal@local"}
        # fallback to user auth
        user = await get_current_user(request)
        user_role = user.get("role", "guest")
        if order[user_role] < order[min_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency

@router.post("/login")
async def login(data: LoginRequest, response: Response):
    await ensure_default_users()
    user = await get_user_by_email(data.email)
    if not user or not pwd_context.verify(data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user["email"], "role": user.get("role", "guest")})
    # httpOnly cookie (best-effort; frontend primarily uses Authorization header)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return {"status": "success", "access_token": token, "token_type": "bearer"}

@router.post("/register")
async def register(data: RegisterRequest):
    await ensure_default_users()

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = await get_user_by_email(data.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    user_id = await create_user(data.email, data.password, role="guest")
    return {
        "status": "success",
        "message": "Account created successfully",
        "user_id": user_id
    }

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "success"}

@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return {
        "id": str(user.get("_id")),
        "email": user["email"],
        "role": user.get("role", "guest"),
        "display_name": user.get("display_name"),
        "operator_preferences": _normalized_operator_preferences(user.get("operator_preferences")),
        "access_scope": _normalized_access_scope(user.get("access_scope")),
    }

@router.put("/me")
async def update_me(data: UpdateProfileRequest, response: Response, user: dict = Depends(get_current_user)):
    update_fields = {}
    email_changed = False

    if data.display_name is not None:
        update_fields["display_name"] = data.display_name.strip()

    if data.email is not None and data.email != user.get("email"):
        existing = await get_user_by_email(data.email)
        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")
        update_fields["email"] = data.email
        email_changed = True

    if data.operator_preferences is not None:
        update_fields["operator_preferences"] = data.operator_preferences.model_dump()

    if data.access_scope is not None:
        scoped = data.access_scope.model_dump()
        scoped["environments"] = [str(v).strip().lower() for v in scoped.get("environments", []) if str(v).strip()]
        scoped["models"] = [str(v).strip() for v in scoped.get("models", []) if str(v).strip()]
        update_fields["access_scope"] = scoped

    if update_fields:
        await users_collection.update_one({"_id": user["_id"]}, {"$set": update_fields})

    updated_user = await users_collection.find_one({"_id": user["_id"]})
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")

    result = {
        "id": str(updated_user.get("_id")),
        "email": updated_user["email"],
        "role": updated_user.get("role", "guest"),
        "display_name": updated_user.get("display_name"),
        "operator_preferences": _normalized_operator_preferences(updated_user.get("operator_preferences")),
        "access_scope": _normalized_access_scope(updated_user.get("access_scope")),
    }

    if email_changed:
        token = create_access_token({"sub": updated_user["email"], "role": updated_user.get("role", "guest")})
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
        result["access_token"] = token

    return result

# Expose utilities for other routers
get_current_user_dep = get_current_user
role_required_dep = role_required
role_or_internal_dep = role_or_internal
