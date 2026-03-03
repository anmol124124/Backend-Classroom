from fastapi import APIRouter, Depends, HTTPException, status
# APIRouter → used to group related routes (like auth routes)
# Depends → lets FastAPI automatically provide things (like DB connection)
# HTTPException → used to throw errors
# status → contains standard HTTP status codes (401, 200, etc.)

from fastapi.security import OAuth2PasswordRequestForm
# Standard login form that accepts username and password
# Here we are using the "username" field to send email

from sqlalchemy.orm import Session
# Database session type (used to talk to the database)

from datetime import timedelta
# Used to calculate time (we’ll use it for token expiry)

from database import get_db
# Function that gives us a database connection

from models import User
# User table model (represents uslisteners in the database)

from auth import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
# verify_password → checks if password is correct
# create_access_token → creates a JWT token
# ACCESS_TOKEN_EXPIRE_MINUTES → defines how long the token is valid

from schemas import Token
# Defines the structure of the response (what the API will return)


# Create a router for authentication-related APIs
router = APIRouter(
    prefix="/auth",  # All routes will start with /auth (example: /auth/login)
    tags=["auth"]    # Groups these routes under "auth" in Swagger docs
)


# Login endpoint → user logs in and receives a JWT token
@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),  # Gets username + password from request
    db: Session = Depends(get_db)  # Automatically gets database connection
):

    # Look for the user in the database using email
    # (form_data.username is being used as email)
    user = db.query(User).filter(User.email == form_data.username).first()

    # If user does not exist OR password is incorrect
    if not user or not verify_password(form_data.password, user.password):
        # Return 401 Unauthorized error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",  # Error message
            headers={"WWW-Authenticate": "Bearer"},  # Indicates token-based authentication
        )

    # Set how long the token will be valid (example: 30 minutes)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Create the JWT token
    access_token = create_access_token(
        data={
            "sub": user.email,  # Store user email inside token
            "role": user.role   # Store user role inside token (admin/user)
        },
        expires_delta=access_token_expires
    )

    # Return the token to the frontend
    return {
        "access_token": access_token,  # The generated JWT token
        "token_type": "bearer"         # Token type (Bearer authentication)
    }