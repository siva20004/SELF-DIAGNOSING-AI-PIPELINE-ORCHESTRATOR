import uuid
import re
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
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
    sheet_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Receives actual file (CSV, XLSX/XLS, JSON, PDF, TXT, DOCX, XML, Parquet),
    saves safely, parses format, normalizes to tabular dataset, calculates
    exact row/column counts and file size, and records in PostgreSQL.
    """
    return await handle_file_upload(file, db, sheet_name=sheet_name)


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


@router.post("/datasets/{dataset_id}/select-sheet", response_model=DatasetUploadResponse)
def select_sheet(
    dataset_id: str,
    sheet_name: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Re-normalizes an uploaded Excel workbook with a different selected sheet.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    if dataset.file_type not in ("XLSX", "XLS"):
        raise HTTPException(status_code=400, detail="Sheet selection is only applicable to Excel workbooks.")

    from app.services.ingestion import UPLOAD_DIR
    from app.services.file_parsers import parse_to_dataframe, get_excel_sheets

    raw_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_raw_{dataset.filename}")
    if not os.path.exists(raw_path):
        raise HTTPException(status_code=404, detail="Original Excel file is no longer available.")

    try:
        available_sheets = get_excel_sheets(raw_path)
        if sheet_name not in available_sheets:
            raise HTTPException(
                status_code=400,
                detail=f"Sheet '{sheet_name}' not found. Available sheets: {', '.join(available_sheets)}"
            )

        df = parse_to_dataframe(raw_path, dataset.file_type, sheet_name=sheet_name)
        norm_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_normalized.csv")
        df.write_csv(norm_path)

        # Update dataset record
        dataset.rows_count = len(df)
        dataset.columns_count = len(df.columns)
        db.commit()
        db.refresh(dataset)

        return DatasetUploadResponse(
            dataset_id=dataset.id,
            filename=dataset.filename,
            file_type=dataset.file_type,
            file_size_bytes=dataset.file_size_bytes,
            rows=dataset.rows_count,
            columns=dataset.columns_count,
            status=dataset.status,
            available_sheets=available_sheets,
            selected_sheet=sheet_name,
            extraction_notes=f"Loaded sheet '{sheet_name}' ({len(df):,} records, {len(df.columns)} columns)."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load sheet '{sheet_name}': {str(e)}")



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
# DATE FORMAT FIX ENDPOINT
# ==========================================

@router.post("/datasets/{dataset_id}/fix-date-format")
def fix_date_format(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """
    Universal date format fixer across ALL file formats (CSV, Excel, JSON, PDF, TXT, DOCX, XML).
    Converts transaction_date from any format (dd/mm/yyyy, mm/dd/yyyy, m/d/yyyy, yyyy/mm/dd, etc.)
    into ISO standard yyyy-mm-dd, overwrites the normalized file, and returns the converted count.
    """
    from datetime import datetime
    import polars as pl
    from app.services.ingestion import UPLOAD_DIR

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    # Locate normalized CSV file on disk
    norm_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_normalized.csv")
    legacy_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_{dataset.filename}")
    
    target_path = norm_path if os.path.exists(norm_path) else legacy_path
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail=f"Dataset file missing on disk")

    df = pl.read_csv(target_path, infer_schema_length=0)

    if "transaction_date" not in df.columns:
        raise HTTPException(status_code=400, detail="Column 'transaction_date' not found in dataset.")

    col = df["transaction_date"].cast(pl.String)

    def convert_date_val(val: Optional[str]) -> str:
        if not val:
            return ""
        s = str(val).strip()
        if not s:
            return ""

        # Strip any leading letter artifacts like 'D ', 'd ', etc.
        s = re.sub(r"^[^\d]+", "", s).strip()
        # Strip time component if present
        s = re.split(r"[\sT]", s)[0]

        # Already valid ISO YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s

        # Check YYYY/MM/DD or YYYY.MM.DD
        m_ymd = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", s)
        if m_ymd:
            y, m, d = int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3))
            try:
                return datetime(y, m, d).strftime("%Y-%m-%d")
            except Exception:
                pass

        # Check D/M/Y or M/D/Y (1-2 digit month/day, 2-4 digit year)
        m_dmy = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})$", s)
        if m_dmy:
            p1, p2, p3 = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            if p3 < 100:
                p3 += 2000
            if p1 > 12:  # p1 must be day, p2 is month
                day, month, year = p1, p2, p3
            elif p2 > 12:  # p2 must be day, p1 is month
                month, day, year = p1, p2, p3
            else:
                month, day, year = p1, p2, p3
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except Exception:
                try:
                    return datetime(year, day, month).strftime("%Y-%m-%d")
                except Exception:
                    pass

        return s

    raw_dates = col.to_list()
    converted_dates = [convert_date_val(d) for d in raw_dates]
    
    # Count how many dates were changed
    converted_count = sum(1 for orig, conv in zip(raw_dates, converted_dates) if orig != conv and conv)

    if converted_count == 0:
        return {
            "dataset_id": dataset_id,
            "converted_count": 0,
            "message": "No non-standard dates found. All dates are already in ISO format."
        }

    new_series = pl.Series("transaction_date", converted_dates, dtype=pl.String)
    df = df.with_columns(new_series)

    # Overwrite both normalized CSV and legacy file so preview & pipeline stay synced
    for p in (norm_path, legacy_path):
        try:
            df.write_csv(p)
        except Exception:
            pass

    return {
        "dataset_id": dataset_id,
        "converted_count": converted_count,
        "total_rows": len(df),
        "message": f"Successfully converted {converted_count:,} dates to ISO standard (yyyy-mm-dd)."
    }


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

