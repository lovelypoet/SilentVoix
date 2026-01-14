from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
from jose import jwt, JWTError
from passlib.context import CryptContext
from core.settings import settings
from core.database import users_collection

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserPublic(BaseModel):
    id: str
    email: EmailStr
    role: Literal["guest", "editor", "admin"]

COOKIE_NAME = "access_token"

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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    # Prefer Authorization header
    auth_header = request.headers.get("authorization")
    token = None
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    # Fallback to cookie
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
    await ensure_default_editor()
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

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "success"}

@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return {"id": str(user.get("_id")), "email": user["email"], "role": user.get("role", "guest")}

# Expose utilities for other routers
get_current_user_dep = get_current_user
role_required_dep = role_required
role_or_internal_dep = role_or_internal
