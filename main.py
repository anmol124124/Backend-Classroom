from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Load environment variables from .env file
load_dotenv()

from database import engine, Base, SessionLocal, get_db
from models import User, UserRole
from auth import get_password_hash
from routers import auth, users, meetings, signaling
from fastapi.middleware.cors import CORSMiddleware

# =====================================
# CREATE DATABASE TABLES
# =====================================
Base.metadata.create_all(bind=engine)

# =====================================
# CREATE FASTAPI APP
# =====================================
app = FastAPI(title="MeetNow")

# =====================================
# SERVE ADMIN DASHBOARD (Priority Mount)
# =====================================
admin_dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "admin-dashboard")
if os.path.exists(admin_dashboard_dir):
    app.mount("/admin-portal", StaticFiles(directory=admin_dashboard_dir, html=True), name="admin_portal")

# =====================================
# CORS CONFIGURATION
# =====================================
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # Allows all origins while still supporting credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================
# SEED DEMO USERS FUNCTION
# =====================================
def seed_users():
    db = SessionLocal()
    try:
        users_to_seed = [
            {"email": "admin@gmail.com", "password": "adminpassword", "role": "admin"},
            {"email": "tutor@gmail.com", "password": "tutorpassword", "role": UserRole.TUTOR},
            {"email": "student@gmail.com", "password": "studentpassword", "role": UserRole.STUDENT},
        ]

        admin_user = db.query(User).filter(User.email == "admin@gmail.com").first()
        if not admin_user:
            db.add(User(
                username="admin",
                email="admin@gmail.com",
                password=get_password_hash("adminpassword"),
                role="admin"
            ))
            print("Admin user seeded.")

        tutor_user = db.query(User).filter(User.email == "tutor@gmail.com").first()
        if not tutor_user:
            db.add(User(
                username="tutor",
                email="tutor@gmail.com",
                password=get_password_hash("tutorpassword"),
                role="tutor"
            ))

        student1 = db.query(User).filter(User.email == "student@gmail.com").first()
        if not student1:
            db.add(User(
                username="student1",
                email="student@gmail.com",
                password=get_password_hash("studentpassword"),
                role="student"
            ))
        
        db.commit()
    except Exception as e:
        print(f"Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    seed_users()

# =====================================
# INCLUDE ROUTERS
# =====================================
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(meetings.router)
app.include_router(signaling.router)




# =====================================
# SERVE SDK
# =====================================
sdk_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdk")

@app.get("/sdk.js")
async def get_sdk_js():
    sdk_file_path = os.path.join(sdk_dir, "sdk.js")
    if os.path.exists(sdk_file_path):
        return FileResponse(sdk_file_path)
    return {"error": "SDK file not found"}

if os.path.exists(sdk_dir):
    app.mount("/sdk", StaticFiles(directory=sdk_dir), name="sdk")

# =====================================
# MEETING ALIAS ROUTE (Auto-Creation)
# =====================================
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

@app.get("/meeting/{meeting_id}")
async def meeting_page_alias(request: Request, meeting_id: str, db: Session = Depends(get_db)):
    # Check if meeting exists, if not create it automatically
    from models import Meeting
    meeting = db.query(Meeting).filter(Meeting.room_id == meeting_id).first()
    
    if not meeting:
        # Get a default owner (admin) for auto-created meetings
        admin_user = db.query(User).filter(User.email == "admin@gmail.com").first()
        new_meeting = Meeting(
            title=f"Meeting: {meeting_id}",
            room_id=meeting_id,
            created_by=admin_user.id if admin_user else 1
        )
        db.add(new_meeting)
        db.commit()
        db.refresh(new_meeting)
        print(f"Auto-created meeting: {meeting_id}")

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        from routers.meetings import read_meeting_by_room
        return await read_meeting_by_room(meeting_id, db)
    
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend build not found"}

# =====================================
# HEALTH CHECK
# =====================================
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "meeting-microservice"}

# =====================================
# ROOT ENDPOINT
# =====================================
@app.get("/")
async def root():
    return {"message": "Welcome to the MeetNow API"}

# =====================================
# SERVE FRONTEND
# =====================================
if os.path.exists(os.path.join(frontend_dist, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

@app.get("/{rest_of_path:path}")
async def serve_frontend(request: Request, rest_of_path: str):
    # API paths and Admin Portal that should NOT be handled by the frontend SPA
    exclude_prefixes = ["/auth", "/users", "/meetings", "/ws", "/admin", "/health", "/admin-portal"]
    full_path = request.url.path
    if any(full_path.startswith(p) for p in exclude_prefixes):
        return {"detail": "Not Found"}
    
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend build not found"}