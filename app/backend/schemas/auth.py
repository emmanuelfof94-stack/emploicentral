from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LocalRegisterRequest(BaseModel):
    """Request body for local email/password registration."""

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: Optional[str] = None


class LocalLoginRequest(BaseModel):
    """Request body for local email/password login."""

    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    """Request body for changing the password of the current local account."""

    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class LocalAuthResponse(BaseModel):
    """Response body for local auth (login/register)."""

    token: str
    expires_at: int
    token_type: str = "Bearer"


class UserResponse(BaseModel):
    id: str  # Now a string UUID (platform sub)
    email: str
    name: Optional[str] = None
    role: str = "user"  # user/admin
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlatformTokenExchangeRequest(BaseModel):
    """Request body for exchanging Platform token for app token."""

    platform_token: str


class TokenExchangeResponse(BaseModel):
    """Response body for issued application token."""

    token: str
