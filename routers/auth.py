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

from schemas import Token, SignupRequest, SignupResponse
# Defines the structure of the response (what the API will return)


router = APIRouter(
    prefix="/auth",  # All routes will start with /auth (example: /auth/login)
    tags=["auth"]    # Groups these routes under "auth" in Swagger docs
)


# Signup endpoint - Create a new user (tutor/student only)
@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password before saving
    from auth import get_password_hash
    hashed_pass = get_password_hash(request.password)

    # Create new user instance
    new_user = User(
        username=request.username,
        email=request.email,
        password=hashed_pass,
        role=request.role.value
    )

    # Save to database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate a JWT access token immediately for new user
    # 24 hours expiry for initial access
    access_token_expires = timedelta(hours=24)
    
    access_token = create_access_token(
        data={
            "sub": new_user.email,
            "user_id": new_user.id,
            "email": new_user.email,
            "role": new_user.role
        },
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role
        }
    }


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