from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# FastAPI → main framework
# Depends → for dependency injection (not heavily used here)

from database import engine, Base, SessionLocal
# engine → database connection engine
# Base → base class for all models
# SessionLocal → used to create DB sessions

from models import User, UserRole
# User → user table model
# UserRole → roles enum (ADMIN, TUTOR, STUDENT)

from auth import get_password_hash
# get_password_hash → hashes plain password before storing in DB

from routers import auth, users, meetings, signaling
# Import all route files (auth routes, user routes, course routes)

from sqlalchemy.orm import Session
# DB session type

from fastapi.middleware.cors import CORSMiddleware
# Middleware that allows frontend to call backend APIs


# =====================================
# CREATE DATABASE TABLES
# =====================================

# This creates all tables in database based on models
# Example: User table, Course table etc.
Base.metadata.create_all(bind=engine)


# =====================================
# CREATE FASTAPI APP
# =====================================

app = FastAPI(title="MeetNow")


# =====================================
# CORS CONFIGURATION
# =====================================

# This allows frontend (React app) to call this backend
# Without CORS, browser would block requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"],  # allow all HTTP methods (GET, POST etc.)
    allow_headers=["*"],  # allow all headers
)


# =====================================
# SEED DEMO USERS FUNCTION
# =====================================

# This function creates demo users automatically
# So we can test login without manually adding users
def seed_users():

    # Create DB session
    db = SessionLocal()

    try:
        # Demo users list
        users_to_seed = [
            {"email": "admin@gmail.com", "password": "adminpassword", "role": "admin"},
            {"email": "tutor@gmail.com", "password": "tutorpassword", "role": UserRole.TUTOR},
            {"email": "student@gmail.com", "password": "studentpassword", "role": UserRole.STUDENT},
            {"email": "student2@gmail.com", "password": "student2password", "role": UserRole.STUDENT},
        ]

        # Create admin user if it doesn't exist
        admin_user = db.query(User).filter(User.email == "admin@gmail.com").first()
        if not admin_user:
            hashed_password = get_password_hash("adminpassword")
            admin_user = User(
                username="admin",
                email="admin@gmail.com",
                password=hashed_password,
                role="admin"  # Role is a string in DB
            )
            db.add(admin_user)
            print("Admin user seeded.")

        # Seed Tutor
        tutor_user = db.query(User).filter(User.email == "tutor@gmail.com").first()
        if not tutor_user:
            tutor_user = User(
                username="tutor",
                email="tutor@gmail.com",
                password=get_password_hash("tutorpassword"),
                role="tutor"
            )
            db.add(tutor_user)

        # Seed Students
        student1 = db.query(User).filter(User.email == "student@gmail.com").first()
        if not student1:
            student1 = User(
                username="student1",
                email="student@gmail.com",
                password=get_password_hash("studentpassword"),
                role="student"
            )
            db.add(student1)
        
        # Save all users to database
        db.commit()

    except Exception as e:
        # If error happens → print error and rollback
        print(f"Error seeding users: {e}")
        db.rollback()

    finally:
        # Always close DB connection
        db.close()


# =====================================
# STARTUP EVENT
# =====================================

# This runs automatically when app starts
# It will create demo users
@app.on_event("startup")
async def startup_event():
    seed_users()


# =====================================
# INCLUDE ROUTERS
# =====================================

# Add all route files into main app
app.include_router(auth.router)     # login routes
app.include_router(users.router)    # user routes
app.include_router(meetings.router) # meeting routes
app.include_router(signaling.router) # signaling routes (WebSocket)

# =====================================
# SERVE FRONTEND (Single Tunnel Support)
# =====================================

# Get absolute path to the frontend/dist folder (relative to this file)
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

# Mount assets folder (CSS, JS)
if os.path.exists(os.path.join(frontend_dist, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

# Catch-all route to serve the SPA (React handles routing)
@app.get("/{rest_of_path:path}")
async def serve_frontend(request: Request, rest_of_path: str):
    # Don't intercept API or WebSocket calls that might have slipped through
    if rest_of_path.startswith("api/") or rest_of_path.startswith("ws/"):
        return {"detail": "Not Found"}
    
    # Serve index.html for all other paths
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend build not found. Please run 'npm run build' in the frontend directory."}


# =====================================
# ROOT ENDPOINT
# =====================================

# Simple test endpoint to check API running
@app.get("/")
async def root():
    return {"message": "Welcome to the MeetNow API"}