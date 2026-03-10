import os
# Used to read environment variables (like SECRET_KEY)

from datetime import datetime, timedelta
# Used for time calculations (token expiry)

from typing import Optional
# Optional → means a value may or may not be provided

from jose import JWTError, jwt
# jose.jwt → used to create and verify JWT tokens
# JWTError → handles token errors

from passlib.context import CryptContext
# Used to hash and verify passwords securely

from fastapi import Depends, HTTPException, status
# Depends → FastAPI automatically provides things (user, db etc.)
# HTTPException → used to throw errors
# status → HTTP status codes

from fastapi.security import OAuth2PasswordBearer
# Used to extract token from Authorization header (Bearer token)

from sqlalchemy.orm import Session
# Database session

from database import get_db
# Function that gives database connection

from models import User
# User table model


# ================================
# CONFIGURATION VALUES
# ================================

# Secret key used to sign JWT tokens
# IMPORTANT: Change this in production
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-this-in-production")

# Algorithm used to sign JWT
ALGORITHM = "HS256"

# Token validity time (30 minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ================================
# PASSWORD HASHING SETUP
# ================================

# This creates a password hashing tool using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# This tells FastAPI to expect a Bearer token in Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# ================================
# PASSWORD FUNCTIONS
# ================================

# Check if entered password matches stored hashed password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# Convert plain password into hashed password
def get_password_hash(password):
    return pwd_context.hash(password)


# ================================
# CREATE JWT TOKEN
# ================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    # Copy the data (like email, role)
    to_encode = data.copy()
    
    if expires_delta:
        # If custom expiry provided
        expire = datetime.utcnow() + expires_delta
    else:
        # Default expiry = 15 minutes
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    # Add expiry time into token payload
    to_encode.update({"exp": expire})
    
    # Create JWT token using secret key
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ================================
# GET CURRENT LOGGED-IN USER
# ================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),  # Get token from header
    db: Session = Depends(get_db)         # Get DB connection
):
    # Error to throw if token invalid
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Get email stored inside token
        email: str = payload.get("sub")

        # If email missing → invalid token
        if email is None:
            raise credentials_exception

    except JWTError:
        # Token expired or tampered
        raise credentials_exception
    
    # Find user in database using email
    user = db.query(User).filter(User.email == email).first()

    # If user not found → invalid
    if user is None:
        raise credentials_exception

    # Return logged-in user
    return user


# ================================
# ROLE CHECK FUNCTION
# ================================

def check_role(roles: list):
    # This function returns another function (dependency)
    async def role_checker(current_user: User = Depends(get_current_user)):

        # If user's role is not allowed
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have enough permissions to access this resource"
            )

        # If role is valid → allow access
        return current_user

    return role_checker