import os
import uuid
import polars as pl
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.models.models import Dataset
from app.schemas.schemas import DatasetUploadResponse, DatasetPreviewResponse

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_dataset_file_path(dataset_id: str, db: Session) -> tuple[str, str]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    
    file_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_{dataset.filename}")
    if not os.path.exists(file_path):
        # check if it exists in current dir directly
        if os.path.exists(dataset.filename):
            file_path = dataset.filename
        else:
            raise HTTPException(status_code=404, detail=f"Dataset file {dataset.filename} missing on disk")
    return file_path, dataset.file_type


def read_dataset_df(file_path: str, file_type: str) -> pl.DataFrame:
    """Reads dataset into a Polars DataFrame safely based on detected file type."""
    ft = file_type.upper()
    try:
        if ft == "CSV":
            return pl.read_csv(file_path, infer_schema_length=10000, ignore_errors=False)
        elif ft == "PARQUET":
            return pl.read_parquet(file_path)
        elif ft == "JSON":
            try:
                return pl.read_json(file_path)
            except Exception:
                return pl.read_ndjson(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse {file_type} file: {str(e)}")


async def handle_file_upload(file: UploadFile, db: Session) -> DatasetUploadResponse:
    filename = file.filename or "unknown.csv"
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".csv":
        file_type = "CSV"
    elif ext in [".parquet", ".pq"]:
        file_type = "PARQUET"
    elif ext == ".json":
        file_type = "JSON"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Only CSV, JSON, and Parquet are supported."
        )

    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    saved_filename = f"{dataset_id}_{filename}"
    target_path = os.path.join(UPLOAD_DIR, saved_filename)

    file_size_bytes = 0
    try:
        with open(target_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size_bytes += len(chunk)
                buffer.write(chunk)
    except Exception as e:
        if os.path.exists(target_path):
            os.remove(target_path)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    if file_size_bytes == 0:
        if os.path.exists(target_path):
            os.remove(target_path)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Read actual data to get exact row and column counts
    try:
        df = read_dataset_df(target_path, file_type)
        rows_count = len(df)
        columns_count = len(df.columns)
    except HTTPException:
        if os.path.exists(target_path):
            os.remove(target_path)
        raise
    except Exception as e:
        if os.path.exists(target_path):
            os.remove(target_path)
        raise HTTPException(status_code=400, detail=f"Corrupted or unreadable dataset file: {str(e)}")

    dataset_record = Dataset(
        id=dataset_id,
        filename=filename,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        rows_count=rows_count,
        columns_count=columns_count,
        status="UPLOADED"
    )

    db.add(dataset_record)
    db.commit()
    db.refresh(dataset_record)

    return DatasetUploadResponse(
        dataset_id=dataset_record.id,
        filename=dataset_record.filename,
        file_type=dataset_record.file_type,
        file_size_bytes=dataset_record.file_size_bytes,
        rows=dataset_record.rows_count,
        columns=dataset_record.columns_count,
        status=dataset_record.status
    )


def get_dataset_preview(dataset_id: str, db: Session, limit: int = 15) -> DatasetPreviewResponse:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    file_path, file_type = get_dataset_file_path(dataset_id, db)
    
    # Read limited rows for preview without loading millions into memory
    ft = file_type.upper()
    if ft == "CSV":
        preview_df = pl.read_csv(file_path, n_rows=limit)
    elif ft == "PARQUET":
        preview_df = pl.read_parquet(file_path, n_rows=limit)
    elif ft == "JSON":
        try:
            preview_df = pl.read_json(file_path).head(limit)
        except Exception:
            preview_df = pl.read_ndjson(file_path, n_rows=limit)
    else:
        preview_df = read_dataset_df(file_path, file_type).head(limit)

    preview_rows = preview_df.to_dicts()

    return DatasetPreviewResponse(
        dataset_id=dataset.id,
        filename=dataset.filename,
        total_rows=dataset.rows_count,
        columns=preview_df.columns,
        preview_rows=preview_rows
    )
