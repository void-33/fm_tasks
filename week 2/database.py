import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from logger import logger

# ─────────────────────────────────────────────
#  database.py — The Plumbing
#  This file does ONE job: connect Python to
#  PostgreSQL and provide a session (connection)
#  to every other part of the app that needs it.
# ─────────────────────────────────────────────

# Load variables from your .env file into Python
# After this line, os.getenv() can read them
load_dotenv()

# ── Build the connection string ──────────────
# SQLAlchemy needs a URL in this format:
# postgresql://user:password@host:port/database
#
# We read each part from .env
DB_USER     = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST     = os.getenv("POSTGRES_HOST", "localhost")  # default: localhost
DB_PORT     = os.getenv("POSTGRES_PORT", "5432")
DB_NAME     = os.getenv("POSTGRES_DB")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

logger.info(f"Connecting to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")

# ── Create the Engine ────────────────────────
# The engine is the actual connection to the DB.
# Think of it as the main water pipe coming into
# your house — everything else branches from it.
try:
    engine = create_engine(DATABASE_URL)
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# ── Create a SessionLocal class ──────────────
# A "session" is like a temporary conversation
# with the database. You open it, do your queries,
# then close it. Each API request gets its own session.
SessionLocal = sessionmaker(
    autocommit=False,  # don't save automatically — we control when
    autoflush=False,   # don't send queries until we say so
    bind=engine        # use our engine (connection)
)

# ── Base class for models ────────────────────
# All our database table definitions (models.py)
# will inherit from this Base class
Base = declarative_base()


# ── Dependency function ──────────────────────
# This function is used by router.py to get a
# database session for each incoming request.
# The "yield" makes it automatically close the
# session when the request is done — like a
# self-closing door!
def get_db():
    db = SessionLocal()
    try:
        logger.debug("Database session opened")
        yield db
    finally:
        db.close()
        logger.debug("Database session closed")