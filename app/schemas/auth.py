"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=1000)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)
    phone: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str
    password: str = Field(min_length=8, max_length=255)


class UserOut(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str | None = None
    role: str

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    message: str
