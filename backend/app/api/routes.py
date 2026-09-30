import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.models import Dataset, PipelineRun, PipelineTask, ValidationErrorRecord
from app.schemas.schemas import (
    DatasetUploadResponse,
    DatasetPreviewResponse,
    ValidationSummary,
    ValidationErrorItem,
    PipelineExecutionResponse,
    PipelineTaskItem,
    PipelineResultsResponse,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    AuthResponse,
)
from app.services.ingestion import handle_file_upload, get_dataset_preview, get_dataset_file_path
from app.services.contract_loader import load_contract
from app.services.validator import validate_dataset
from app.services.pipeline_executor import execute_pipeline, get_pipeline_results
from app.services.auth import register_user, login_user, get_user_by_id

router = APIRouter(prefix="/api", tags=["Pipeline Orchestrator"])


@router.post("/datasets/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Receives actual file (CSV, JSON, Parquet), saves safely, reads metadata,
    calculates exact row/column counts and file size, records in PostgreSQL.
    """
    return await handle_file_upload(file, db)


@router.get("/datasets/{dataset_id}", response_model=DatasetUploadResponse)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves metadata of an uploaded dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return DatasetUploadResponse(
        dataset_id=dataset.id,
        filename=dataset.filename,
        file_type=dataset.file_type,
        file_size_bytes=dataset.file_size_bytes,
        rows=dataset.rows_count,
        columns=dataset.columns_count,
        status=dataset.status
    )


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def get_preview(
    dataset_id: str,
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Fetches a preview sample of rows from the uploaded dataset."""
    return get_dataset_preview(dataset_id, db, limit=limit)


@router.post("/datasets/{dataset_id}/validate", response_model=ValidationSummary)
def validate_dataset_endpoint(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """
    Validates the dataset against the YAML data contract.
    Records errors in PostgreSQL and returns exact check summary.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    file_path, file_type = get_dataset_file_path(dataset_id, db)
    contract_data = load_contract()

    # Create a unique validation run ID
    val_run_id = f"VAL-{uuid.uuid4().hex[:10].upper()}"

    summary = validate_dataset(
        file_path=file_path,
        file_type=file_type,
        run_id=val_run_id,
        db=db,
        contract_data=contract_data
    )
    return summary


@router.get("/runs/{run_id}", response_model=PipelineExecutionResponse)
def get_run(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves pipeline run status and task overview."""
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    tasks = db.query(PipelineTask).filter(PipelineTask.run_id == run_id).order_by(PipelineTask.id).all()
    duration = None
    if run.completed_at and run.started_at:
        duration = round((run.completed_at - run.started_at).total_seconds(), 2)

    return PipelineExecutionResponse(
        run_id=run.run_id,
        status=run.status,
        pipeline_name=run.pipeline_name,
        dataset_id=run.dataset_id,
        contract_version=run.contract_version,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=duration,
        rows_received=run.rows_received,
        rows_valid=run.rows_valid,
        rows_invalid=run.rows_invalid,
        rows_processed=run.rows_processed,
        rows_rejected=run.rows_rejected,
        error_message=run.error_message,
        tasks=[PipelineTaskItem.model_validate(t) for t in tasks]
    )


@router.get("/runs/{run_id}/validation-errors", response_model=List[ValidationErrorItem])
def get_validation_errors(
    run_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Retrieves paginated validation errors recorded in PostgreSQL for a run."""
    errors = (
        db.query(ValidationErrorRecord)
        .filter(ValidationErrorRecord.run_id == run_id)
        .order_by(ValidationErrorRecord.row_number.asc().nulls_first())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [ValidationErrorItem.model_validate(e) for e in errors]


@router.post("/datasets/{dataset_id}/execute", response_model=PipelineExecutionResponse)
def execute_pipeline_endpoint(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """
    Executes the 7 pipeline stages sequentially:
    Validation -> Cleaning -> Transformation -> Calculation -> Aggregation -> Quality Check -> DB Storage
    """
    return execute_pipeline(dataset_id, db)


@router.get("/runs/{run_id}/tasks", response_model=List[PipelineTaskItem])
def get_run_tasks(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves all pipeline tasks and their execution statuses."""
    tasks = db.query(PipelineTask).filter(PipelineTask.run_id == run_id).order_by(PipelineTask.id).all()
    if not tasks:
        raise HTTPException(status_code=404, detail=f"No tasks found for run {run_id}")
    return [PipelineTaskItem.model_validate(t) for t in tasks]


@router.get("/runs/{run_id}/results", response_model=PipelineResultsResponse)
def get_run_results(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves final calculated metrics, city/category/date aggregates, and tasks."""
    return get_pipeline_results(run_id, db)


# ==========================================
# AUTHENTICATION ENDPOINTS
# ==========================================

@router.post("/auth/register", response_model=AuthResponse)
def register(
    data: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """Registers a new user with hashed password and stores in PostgreSQL."""
    return register_user(db, data)


@router.post("/auth/login", response_model=AuthResponse)
def login(
    data: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """Authenticates an existing user and returns token and user profile."""
    return login_user(db, data)


@router.get("/auth/me/{user_id}", response_model=UserResponse)
def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Fetches user profile by ID."""
    return get_user_by_id(db, user_id)

