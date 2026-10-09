import os
import uuid
from typing import Optional, List, Tuple
import polars as pl
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.models.models import Dataset
from app.schemas.schemas import DatasetUploadResponse, DatasetPreviewResponse
from app.services.file_parsers import (
    detect_format,
    validate_file_safety,
    parse_to_dataframe,
    get_excel_sheets,
    SUPPORTED_EXTENSIONS,
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_dataset_file_path(dataset_id: str, db: Session) -> Tuple[str, str]:
    """
    Returns the absolute path to the normalized CSV file and the original file type.
    All non-CSV formats are normalized to CSV upon ingestion, so the validator
    and pipeline executor always receive a clean CSV file.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    # Check for the normalized CSV file first
    norm_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_normalized.csv")
    if os.path.exists(norm_path):
        return norm_path, "CSV"

    # Fallback to direct filename match (backward compatibility)
    file_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_{dataset.filename}")
    if os.path.exists(file_path):
        return file_path, dataset.file_type

    if os.path.exists(dataset.filename):
        return dataset.filename, dataset.file_type

    raise HTTPException(status_code=404, detail=f"Dataset file {dataset.filename} missing on disk")


def read_dataset_df(file_path: str, file_type: str) -> pl.DataFrame:
    """Reads dataset into a Polars DataFrame safely based on detected file type."""
    ft = file_type.upper()
    try:
        if ft == "CSV":
            return pl.read_csv(file_path, infer_schema_length=0, ignore_errors=False)
        elif ft == "PARQUET":
            return pl.read_parquet(file_path)
        elif ft == "JSON":
            try:
                return pl.read_json(file_path)
            except Exception:
                return pl.read_ndjson(file_path)
        else:
            return parse_to_dataframe(file_path, ft)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse {file_type} file: {str(e)}")


async def handle_file_upload(
    file: UploadFile,
    db: Session,
    sheet_name: Optional[str] = None
) -> DatasetUploadResponse:
    """
    Multi-format file upload handler.
    1. Validates file extension against supported registry.
    2. Streams file to disk safely with size checks.
    3. Detects available sheets for Excel.
    4. Parses the format into a normalized Polars DataFrame.
    5. Writes out a normalized CSV file so existing validator & executor work unchanged.
    6. Registers the dataset record in PostgreSQL.
    """
    filename = file.filename or "unknown.csv"

    # Step 1: Detect format
    try:
        file_format = detect_format(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    raw_saved_name = f"{dataset_id}_raw_{filename}"
    raw_target_path = os.path.join(UPLOAD_DIR, raw_saved_name)
    normalized_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_normalized.csv")

    # Step 2: Stream save to disk with size check
    file_size_bytes = 0
    try:
        with open(raw_target_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size_bytes += len(chunk)
                buffer.write(chunk)
    except Exception as e:
        if os.path.exists(raw_target_path):
            os.remove(raw_target_path)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    # Step 3: Safety check
    try:
        validate_file_safety(raw_target_path, file_size_bytes, filename)
    except ValueError as e:
        if os.path.exists(raw_target_path):
            os.remove(raw_target_path)
        raise HTTPException(status_code=400, detail=str(e))

    # Step 4: Multi-sheet check for Excel
    available_sheets = None
    selected_sheet = sheet_name
    if file_format in ("XLSX", "XLS"):
        try:
            available_sheets = get_excel_sheets(raw_target_path)
            if not selected_sheet and available_sheets:
                selected_sheet = available_sheets[0]
        except Exception as e:
            if os.path.exists(raw_target_path):
                os.remove(raw_target_path)
            raise HTTPException(status_code=400, detail=f"Excel inspection failed: {str(e)}")

    # Step 5: Parse and normalize to CSV
    extraction_notes = None
    try:
        df = parse_to_dataframe(raw_target_path, file_format, sheet_name=selected_sheet)
        rows_count = len(df)
        columns_count = len(df.columns)

        if rows_count == 0:
            raise ValueError("Parsed dataset contains 0 records.")
        if columns_count == 0:
            raise ValueError("Parsed dataset contains 0 columns.")

        # Write normalized CSV
        df.write_csv(normalized_path)

        # For backward compatibility with legacy endpoints expecting {dataset_id}_{filename}
        legacy_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_{filename}")
        if not os.path.exists(legacy_path):
            df.write_csv(legacy_path)

        extraction_notes = f"Successfully parsed {file_format} file ({rows_count:,} records, {columns_count} columns)."
        if file_format in ("XLSX", "XLS") and selected_sheet:
            extraction_notes += f" Sheet: '{selected_sheet}'."

    except ValueError as e:
        # Format-specific error message
        for p in (raw_target_path, normalized_path):
            if os.path.exists(p):
                os.remove(p)
        raise HTTPException(
            status_code=400,
            detail=f"{file_format} extraction error: {str(e)}"
        )
    except Exception as e:
        for p in (raw_target_path, normalized_path):
            if os.path.exists(p):
                os.remove(p)
        raise HTTPException(
            status_code=400,
            detail=f"Unable to process {file_format} file: {str(e)}"
        )

    # Step 6: Save DB record
    dataset_record = Dataset(
        id=dataset_id,
        filename=filename,
        file_type=file_format,
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
        status=dataset_record.status,
        available_sheets=available_sheets,
        selected_sheet=selected_sheet,
        extraction_notes=extraction_notes
    )


def get_dataset_preview(dataset_id: str, db: Session, limit: int = 15) -> DatasetPreviewResponse:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    file_path, file_type = get_dataset_file_path(dataset_id, db)

    # Preview from the normalized CSV file directly
    try:
        preview_df = pl.read_csv(file_path, n_rows=limit, infer_schema_length=0)
    except Exception:
        preview_df = read_dataset_df(file_path, file_type).head(limit)

    preview_rows = preview_df.to_dicts()

    return DatasetPreviewResponse(
        dataset_id=dataset.id,
        filename=dataset.filename,
        total_rows=dataset.rows_count,
        columns=preview_df.columns,
        preview_rows=preview_rows
    )
