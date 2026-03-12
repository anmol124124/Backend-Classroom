from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import enum

# UserRole - Same roles as in models, used for data validation
class UserRole(str, enum.Enum):
    TUTOR = "tutor"
    STUDENT = "student"

# UserBase - Base schema with common user fields
class UserBase(BaseModel):
    email: EmailStr  # Email validation - must be valid format
    role: str # Keep as str to handle 'admin' in responses if needed, but signup uses UserRole enum

class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole

# UserCreate - Schema for creating a new user (includes password)
class UserCreate(UserBase):
    password: str

class UserSignupInfo(BaseModel):
    username: str
    email: EmailStr
    role: str

class SignupResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserSignupInfo

# UserLogin - Schema for login request (only email and password needed)
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# UserResponse - Schema for returning user info (never includes password for security)
class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True  # Allows conversion from database model to schema

# Token - Schema for API response after successful login
class Token(BaseModel):
    access_token: str  # The JWT token to use for future requests
    token_type: str

# TokenData - Schema for data extracted from JWT token
class TokenData(BaseModel):
    email: Optional[str] = None  # Email from token
    role: Optional[str] = None   # Role from token


# MeetingBase - Base schema for meetings
class MeetingBase(BaseModel):
    title: str

# MeetingCreate - Schema for creating a new meeting
class MeetingCreate(MeetingBase):
    pass

# MeetingResponse - Schema for returning meeting info
class MeetingResponse(MeetingBase):
    id: int
    room_id: str
    meeting_url: str
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


