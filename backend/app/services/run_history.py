import os
import json
import hashlib
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException
import polars as pl

from app.models.models import (
    PipelineRun,
    Dataset,
    PipelineTask,
    ValidationErrorRecord,
    SalesAggregate,
)
from app.schemas.schemas import (
    RunHistoryItem,
    RunHistoryResponse,
    RunArtifactsResponse,
    RunLogsResponse,
    PipelineTaskItem,
)


def compute_file_fingerprint(file_path: str) -> str:
    """Computes a quick deterministic SHA-256 fingerprint from the file content."""
    if not os.path.exists(file_path):
        return "unknown_fingerprint"
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read up to 256KB for fast hashing on large files
        chunk = f.read(262144)
        hasher.update(chunk)
    return hasher.hexdigest()[:16]


def get_all_runs(
    db: Session,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> RunHistoryResponse:
    """
    Retrieves historical pipeline runs from PostgreSQL.
    Preserves run history across restarts and browser refreshes.
    """
    query = db.query(PipelineRun).join(Dataset, PipelineRun.dataset_id == Dataset.id, isouter=True)

    if status_filter:
        query = query.filter(PipelineRun.status == status_filter.upper())

    total_count = query.count()
    runs = query.order_by(desc(PipelineRun.started_at)).offset(offset).limit(limit).all()

    items = []
    for r in runs:
        duration = None
        if r.started_at and r.completed_at:
            duration = round((r.completed_at - r.started_at).total_seconds(), 2)

        filename = r.dataset.filename if r.dataset else "unknown"
        file_format = getattr(r, "file_format", None) or (r.dataset.file_type if r.dataset else "CSV")
        fingerprint = getattr(r, "dataset_fingerprint", None) or (compute_file_fingerprint(r.artifact_path) if getattr(r, "artifact_path", None) else None)

        items.append(
            RunHistoryItem(
                run_id=r.run_id,
                pipeline_name=r.pipeline_name,
                dataset_id=r.dataset_id,
                filename=filename,
                file_format=file_format,
                dataset_fingerprint=fingerprint,
                contract_version=r.contract_version,
                started_at=r.started_at,
                completed_at=r.completed_at,
                duration_seconds=duration,
                status=r.status,
                rows_received=r.rows_received or 0,
                rows_processed=r.rows_processed or 0,
                rows_invalid=r.rows_invalid or 0,
                rows_rejected=getattr(r, "rows_rejected", None) or (r.rows_invalid or 0),
                error_message=r.error_message,
            )
        )

    return RunHistoryResponse(runs=items, total_count=total_count)


def get_run_artifacts(run_id: str, db: Session) -> RunArtifactsResponse:
    """
    Retrieves stored transformation/aggregation outputs or durable references to stored artifacts.
    """
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    dataset = db.query(Dataset).filter(Dataset.id == run.dataset_id).first()
    filename = dataset.filename if dataset else "unknown"
    file_format = getattr(run, "file_format", None) or (dataset.file_type if dataset else "CSV")
    fingerprint = getattr(run, "dataset_fingerprint", None)
    artifact_path = getattr(run, "artifact_path", None)

    # Load configuration
    config = {}
    if getattr(run, "config_json", None):
        try:
            config = json.loads(run.config_json)
        except Exception:
            config = {"raw": run.config_json}

    # Fetch sample rows if normalized file exists
    sample_records = []
    if artifact_path and os.path.exists(artifact_path):
        try:
            df = pl.read_csv(artifact_path, n_rows=10, infer_schema_length=0)
            sample_records = df.to_dicts()
        except Exception:
            sample_records = []

    return RunArtifactsResponse(
        run_id=run.run_id,
        dataset_id=run.dataset_id,
        filename=filename,
        file_format=file_format,
        artifact_path=artifact_path,
        row_count=run.rows_processed or run.rows_received or 0,
        column_count=dataset.columns_count if dataset else 0,
        fingerprint=fingerprint,
        config=config,
        sample_records=sample_records,
    )


def get_run_logs(run_id: str, db: Session) -> RunLogsResponse:
    """
    Retrieves task-by-task execution logs and telemetry for a specific run.
    """
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    tasks = db.query(PipelineTask).filter(PipelineTask.run_id == run_id).order_by(PipelineTask.id.asc()).all()

    duration = None
    if run.started_at and run.completed_at:
        duration = round((run.completed_at - run.started_at).total_seconds(), 2)

    raw_logs = []
    raw_logs.append(f"[{run.started_at.isoformat()}] Pipeline '{run.pipeline_name}' started for dataset {run.dataset_id} (Contract v{run.contract_version})")

    for t in tasks:
        t_duration = round((t.completed_at - t.started_at).total_seconds(), 3) if t.completed_at and t.started_at else 0.0
        raw_logs.append(
            f"[{t.started_at.isoformat()}] TASK [{t.task_name}]: {t.status} | In: {t.rows_input:,} | Out: {t.rows_output:,} | Duration: {t_duration}s"
        )
        if t.error_message:
            raw_logs.append(f"[{t.completed_at.isoformat() if t.completed_at else 'ERROR'}] TASK [{t.task_name}] ERROR: {t.error_message}")

    if run.completed_at:
        raw_logs.append(f"[{run.completed_at.isoformat()}] Pipeline finished with status: {run.status} (Processed {run.rows_processed:,} rows)")
    if run.error_message:
        raw_logs.append(f"PIPELINE CRITICAL ERROR: {run.error_message}")

    return RunLogsResponse(
        run_id=run.run_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=duration,
        tasks=[PipelineTaskItem.model_validate(t) for t in tasks],
        error_message=run.error_message,
        raw_logs=raw_logs,
    )
