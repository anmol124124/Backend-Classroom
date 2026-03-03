from sqlalchemy import create_engine
# create_engine → creates a connection to the database

from sqlalchemy.ext.declarative import declarative_base
# declarative_base → base class that all DB models will inherit from

from sqlalchemy.orm import sessionmaker
# sessionmaker → used to create database sessions (connections)


# =====================================
# DATABASE URL
# =====================================

# This points to a SQLite database file named "course_era.db"
# SQLite stores data in a single file (simple and lightweight DB)
SQLALCHEMY_DATABASE_URL = "sqlite:///./course_era.db"


# =====================================
# DATABASE ENGINE
# =====================================

# Engine is the main connection manager to the database
# connect_args allows multiple threads to access SQLite safely
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)


# =====================================
# SESSION FACTORY
# =====================================

# SessionLocal is a factory that creates database sessions
# A session = one connection/interaction with the database
SessionLocal = sessionmaker(
    autocommit=False,  # Changes won't auto-save (we must call commit)
    autoflush=False,   # Changes won't auto-sync until we commit
    bind=engine        # Connect session to our engine
)


# =====================================
# BASE MODEL CLASS
# =====================================

# Base class that all models (User, Course, etc.) will inherit from
# SQLAlchemy uses this to create tables automatically
Base = declarative_base()


# =====================================
# GET DATABASE CONNECTION (DEPENDENCY)
# =====================================

def get_db():
    # Create a new database session
    db = SessionLocal()

    try:
        # Give this DB session to the API endpoint using it
        yield db

    finally:
        # Always close DB connection after request finishes
        db.close()