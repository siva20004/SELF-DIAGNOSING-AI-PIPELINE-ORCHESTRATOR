import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Try finding .env in current dir, backend dir, or root dir
env_paths = [
    Path(".env"),
    Path("backend/.env"),
    Path(__file__).resolve().parent.parent.parent / ".env",
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)
        break

_raw_url = os.getenv("DATABASE_URL", "postgresql://pipeline_user:pipeline_pass@localhost:5432/orchestrator_db")

# Normalize cloud postgres URLs (convert postgres:// to postgresql://)
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)
elif _raw_url.startswith("postgresql+psycopg2://"):
    _raw_url = _raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)

# Clean URL for direct psycopg2 connections (e.g. COPY expert)
RAW_DATABASE_URL = _raw_url

# SQLAlchemy URL: explicitly specify +psycopg2 dialect driver so SQLAlchemy doesn't look for 'psycopg' (psycopg 3)
if RAW_DATABASE_URL.startswith("postgresql://") and not RAW_DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = RAW_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    DATABASE_URL = RAW_DATABASE_URL

# Configure SQLAlchemy engine with pooling and pre-ping
connect_args = {}
if "sslmode=require" in DATABASE_URL:
    connect_args["sslmode"] = "require"

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models.models import (
        Dataset,
        PipelineRun,
        PipelineTask,
        ValidationErrorRecord,
        ProcessedTransaction,
        SalesAggregate,
        User,
    )
    Base.metadata.create_all(bind=engine)
