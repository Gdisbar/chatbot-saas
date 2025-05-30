# =============================================================================
# app/auth/routes.py - Authentication Endpoints
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.auth.models import User, RefreshToken
from app.auth.utils import verify_password, get_password_hash, create_access_token, create_refresh_token, verify_token
from app.config import settings

auth_router = APIRouter()
security = HTTPBearer()


# Pydantic models
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    created_at: datetime


class RefreshTokenRequest(BaseModel):
    refresh_token: str


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = verify_token(token)
    user_id = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


@auth_router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@auth_router.post("/login", response_model=Token)
async def login_user(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )

    # Update last login
    user.last_login = datetime.utcnow()

    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_str = create_refresh_token()

    # Store refresh token
    refresh_token = RefreshToken(
        token=refresh_token_str,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )

    db.add(refresh_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer"
    }


@auth_router.post("/refresh", response_model=Token)
async def refresh_access_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == request.refresh_token,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        )
    )
    refresh_token = result.scalar_one_or_none()

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Create new tokens
    access_token = create_access_token(data={"sub": str(refresh_token.user_id)})
    new_refresh_token = create_refresh_token()

    # Revoke old refresh token
    refresh_token.is_revoked = True

    # Create new refresh token
    new_token_record = RefreshToken(
        token=new_refresh_token,
        user_id=refresh_token.user_id,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )

    db.add(new_token_record)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user
