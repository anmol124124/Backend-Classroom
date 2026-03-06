# Import tools we need from FastAPI
from fastapi import APIRouter, Depends, HTTPException, status

# Import Session to talk to the database
from sqlalchemy.orm import Session

# Import uuid to generate unique room names
import uuid

# Import database connection function
from database import get_db

# Import database models (tables)
from models import Meeting, User, UserRole

# Import authentication and role-checking functions
from auth import get_current_user, check_role

# Import request and response data formats (schemas)
from schemas import MeetingCreate, MeetingResponse


# Create a router for all meeting-related endpoints
# prefix="/meetings" means every route here starts with /meetings
router = APIRouter(
    prefix="/meetings",
    tags=["meetings"]  # Helps organize endpoints in Swagger docs
)


# This endpoint creates a new meeting
# It responds with MeetingResponse format
# It returns HTTP 201 status when successful
@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    meeting: MeetingCreate,  # Data sent from the user (title etc.)
    db: Session = Depends(get_db),  # Connect to database
    current_user: User = Depends(check_role(["admin"]))  
):
    """
    Create a new meeting (Admin only).
    Generates a unique room name automatically.
    """
    
    # Generate a unique room name using uuid4
    # uuid4 creates a random unique string like: 'a3f5e9c0-...'
    room_id = str(uuid.uuid4())
    
    # Create a new Meeting object (but not saved yet)
    db_meeting = Meeting(
        title=meeting.title,          # Take title from request
        room_id=room_id,              # Use generated unique room ID
        created_by=current_user.id      # Save which user created it
    )
    
    # Add the new meeting to the database session
    db.add(db_meeting)
    
    # Save (commit) changes to the database
    db.commit()
    
    # Refresh the object to get updated values (like auto-generated ID)
    db.refresh(db_meeting)
    
    # Return the newly created meeting
    return db_meeting


# This endpoint returns all meetings
# Accessible by Admin, Tutor, and Student
@router.get("/", response_model=list[MeetingResponse])
async def read_all_meetings(
    db: Session = Depends(get_db),  # Connect to database
    current_user: User = Depends(check_role(["admin", "tutor", "student"]))
    # Allow multiple roles to access
):
    """
    View all meetings (All authenticated users can access).
    """
    
    # Query database and return all meeting records
    return db.query(Meeting).all()


# This endpoint returns a single meeting by its room_id
@router.get("/room/{room_id}", response_model=MeetingResponse)
async def read_meeting_by_room(
    room_id: str,  # Room ID comes from URL path
    db: Session = Depends(get_db),  # Connect to database
    current_user: User = Depends(check_role(["admin", "tutor", "student"]))
):
    """
    Get meeting details by Room ID.
    """
    meeting = db.query(Meeting).filter(Meeting.room_id == room_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


# This endpoint returns a single meeting by its ID
@router.get("/{meeting_id}", response_model=MeetingResponse)
async def read_meeting(
    meeting_id: int,  # ID comes from URL path
    db: Session = Depends(get_db),  # Connect to database
    current_user: User = Depends(check_role(["admin", "tutor", "student"]))
    # Allow multiple roles to access
):
    """
    Get meeting details by ID.
    """
    
    # Search for meeting in database where id matches
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    
    # If no meeting is found, return 404 error
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Return the meeting details
    return meeting


# This endpoint deletes a meeting by its ID
@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a meeting (Owner or Admin).
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Check if user is owner or admin (string check for admin)
    if meeting.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this meeting")

    db.delete(meeting)
    db.commit()
    return None


@router.post("/{room_id}/join")
async def join_meeting(
    room_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify and join a meeting.
    """
    meeting = db.query(Meeting).filter(Meeting.room_id == room_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return {
        "message": "Successfully joined meeting",
        "meeting": {
            "title": meeting.title,
            "room_id": meeting.room_id,
            "url": meeting.meeting_url
        },
        "user": {
            "username": current_user.username,
            "role": current_user.role
        }
    }


@router.get("/{room_id}/participants")
async def get_meeting_participants(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get all active participants in a meeting.
    """
    participants, presenter = manager.get_participants(room_id)
    
    return {
        "room_id": room_id,
        "participants": participants,
        "presenter": presenter
    }