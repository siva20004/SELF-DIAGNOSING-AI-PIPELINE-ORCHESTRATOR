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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pipeline_user:pipeline_pass@localhost:5432/orchestrator_db")

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
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
    )
    Base.metadata.create_all(bind=engine)
