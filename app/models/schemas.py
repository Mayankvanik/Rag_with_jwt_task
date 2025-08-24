from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username must be 3-50 characters")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    is_admin: bool = Field(False, description="Admin privileges flag")

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: bool = True
    is_admin: bool = False

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=8, description="Password must be at least 8 characters")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    username: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, description="New password must be at least 8 characters")

    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserList(BaseModel):
    users: List[UserResponse]
    total: int

class APIResponse(BaseModel):
    message: str
    success: bool = True
    data: Optional[dict] = None