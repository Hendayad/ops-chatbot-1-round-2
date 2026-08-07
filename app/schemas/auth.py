"""This file contains the authentication schema for the application."""

import re
from datetime import datetime

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)

from app.schemas.base import BaseResponse


class Token(BaseModel):
    """Token model for authentication."""

    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field(default="bearer", description="The type of token")
    expires_at: datetime = Field(..., description="The token expiration timestamp")


class TokenResponse(BaseResponse):
    """Response model for login endpoint."""

    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field(default="bearer", description="The type of token")
    expires_at: datetime = Field(..., description="When the token expires")
    role: str


class PublicCohort(BaseModel):
    """Safe cohort information exposed before authentication."""

    cohort_id: str = Field(..., description="Stable cohort identifier")
    name: str = Field(..., description="Human-readable cohort name")


class UserCreate(BaseModel):
    """Request model for learner registration."""

    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr = Field(..., description="User's email address")
    password: SecretStr = Field(
        ...,
        description="User's password",
        min_length=8,
        max_length=64,
    )
    username: str | None = Field(
        default=None,
        description="Optional username",
        max_length=50,
    )
    cohort_id: str = Field(..., min_length=1, max_length=100)

    @field_validator("first_name", "last_name", "cohort_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Trim required text fields and reject whitespace-only values."""
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("username")
    @classmethod
    def strip_optional_username(cls, value: str | None) -> str | None:
        """Trim optional username and convert blank input to None."""
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: SecretStr) -> SecretStr:
        """Validate password strength."""
        password = v.get_secret_value()

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", password):
            raise ValueError("Password must contain at least one number")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValueError("Password must contain at least one special character")

        return v


class UserResponse(BaseResponse):
    """Response model returned after successful registration."""

    id: int = Field(..., description="User's ID")
    email: str = Field(..., description="User's email address")
    username: str | None = Field(default=None, description="Optional username")
    first_name: str | None = Field(default=None, description="User's first name")
    last_name: str | None = Field(default=None, description="User's last name")
    cohort_id: str | None = Field(default=None, description="Assigned cohort")
    token: Token = Field(..., description="Authentication token")


class SessionResponse(BaseResponse):
    """Response model for session creation."""

    session_id: str = Field(..., description="The unique identifier for the chat session")
    name: str = Field(default="", description="Name of the session", max_length=100)
    token: Token = Field(..., description="The authentication token for the session")

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Sanitize the session name."""
        sanitized = re.sub(r'[<>{}[\]()\'"`]', "", v)
        return sanitized