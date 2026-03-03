from fastapi import APIRouter, Depends
# APIRouter → used to group related routes (like user routes)
# Depends → lets FastAPI automatically provide things (like DB or current user)

from sqlalchemy.orm import Session
# Session → used to communicate with the database

from database import get_db
# Function that gives a database connection

from models import User, UserRole
# User → user table model
# UserRole → roles enum (ADMIN, TUTOR, STUDENT etc.)

from auth import get_current_user, check_role
# get_current_user → gets logged-in user from JWT token
# check_role → checks if user has required role

from schemas import UserResponse
# UserResponse → defines how user data will be returned in API response

from typing import List
# List → used for returning multiple users


# Create a router for user-related endpoints
router = APIRouter(
    prefix="/users",  # All routes will start with /users
    tags=["users"]    # Group name in Swagger docs
)


# =====================================
# GET CURRENT LOGGED-IN USER
# =====================================
@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_user)  # Automatically gets logged-in user from token
):
    """
    Get current logged-in user info.
    Any authenticated user can call this.
    """

    # Simply return the current logged-in user
    return current_user


# =====================================
# GET ALL USERS (ADMIN ONLY)
# =====================================
@router.get("/", response_model=List[UserResponse])
async def read_all_users(
    db: Session = Depends(get_db),  # Get database connection
    admin_user: User = Depends(check_role([UserRole.ADMIN]))  # Only ADMIN can access
):
    """
    Get all users (Admin only).
    Returns a list of all users in the system.
    """

    # Fetch all users from database and return them
    return db.query(User).all()