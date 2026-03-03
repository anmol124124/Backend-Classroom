from fastapi import APIRouter, Depends, HTTPException, status
# APIRouter → used to group related routes
# Depends → allows FastAPI to automatically provide things like DB or user
# HTTPException → used to throw errors
# status → contains standard HTTP status codes (201, 404, etc.)

from sqlalchemy.orm import Session
# Session → used to communicate with the database

from typing import List
# List → used for type hinting when returning multiple items

from database import get_db
# Function that gives us a database connection

from models import User, Course, UserRole
# User → user table model
# Course → course table model
# UserRole → enum that defines roles (ADMIN, TUTOR, STUDENT)

from auth import check_role
# check_role → function that checks if logged-in user has required role

from schemas import Course as CourseSchema, CourseCreate
# CourseSchema → response format for returning course data
# CourseCreate → format for creating/updating course data


# Create a router for course-related endpoints
router = APIRouter(
    prefix="/courses",  # All endpoints will start with /courses
    tags=["courses"]    # Group name in Swagger docs
)


# ===========================
# CREATE COURSE (ADMIN ONLY)
# ===========================
@router.post("/", response_model=CourseSchema, status_code=status.HTTP_201_CREATED)
async def create_course(
    course: CourseCreate,  # Incoming data from request body (title + description)
    db: Session = Depends(get_db),  # Get database connection automatically
    admin_user: User = Depends(check_role([UserRole.ADMIN]))  # Only ADMIN can access
):
    """
    Create a new course (Admin only).
    """

    # Create a new course object in memory (not saved yet)
    db_course = Course(title=course.title, description=course.description)

    # Add the course to the database session
    db.add(db_course)

    # Save changes permanently in database
    db.commit()

    # Refresh object to get auto-generated fields (like ID)
    db.refresh(db_course)

    # Return the newly created course
    return db_course


# ===========================
# GET ALL COURSES
# ===========================
@router.get("/", response_model=List[CourseSchema])
async def read_all_courses(
    db: Session = Depends(get_db),  # Get DB connection
    admin_user: User = Depends(
        check_role([UserRole.ADMIN, UserRole.TUTOR, UserRole.STUDENT])
    )  # All logged-in users can view
):
    """
    View all courses (All authenticated users can access).
    """

    # Fetch and return all courses from database
    return db.query(Course).all()


# ===========================
# UPDATE COURSE
# ===========================
@router.put("/{course_id}", response_model=CourseSchema)
async def update_course(
    course_id: int,  # Course ID from URL
    course_update: CourseCreate,  # New data coming from request body
    db: Session = Depends(get_db),  # DB connection
    admin_user: User = Depends(
        check_role([UserRole.ADMIN, UserRole.TUTOR])
    )  # Only ADMIN and TUTOR can edit
):
    """
    Edit an existing course (Admin and Tutor).
    """

    # Find course in database by ID
    db_course = db.query(Course).filter(Course.id == course_id).first()

    # If course not found → return 404 error
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Update course fields with new values
    db_course.title = course_update.title
    db_course.description = course_update.description

    # Save updated data
    db.commit()

    # Refresh to get updated values
    db.refresh(db_course)

    # Return updated course
    return db_course


# ===========================
# DELETE COURSE (ADMIN ONLY)
# ===========================
@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: int,  # Course ID from URL
    db: Session = Depends(get_db),  # DB connection
    admin_user: User = Depends(check_role([UserRole.ADMIN]))  # Only ADMIN can delete
):
    """
    Delete a course (Admin only).
    """

    # Find the course by ID
    db_course = db.query(Course).filter(Course.id == course_id).first()

    # If course not found → return 404
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Print message for debugging (optional)
    print(f"Deleting course with ID: {course_id}")

    # Remove the course from database
    db.delete(db_course)

    # Save changes permanently
    db.commit()

    # Print confirmation (optional debug)
    print(f"Course {course_id} deleted successfully")

    # 204 means success but no response body
    return None