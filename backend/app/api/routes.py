import uuid
import re
import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.models import (
    Dataset,
    PipelineRun,
    PipelineTask,
    ValidationErrorRecord,
    FailureDiagnosisRecord,
    BackfillPlanRecord,
    ScheduleRecord,
    RecoveryRunRecord,
    ExperimentRecord,
    User,
    UserActivity,
)
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
    RecordVisitRequest,
    UserActivityStatsResponse,
    RunHistoryResponse,
    RunArtifactsResponse,
    RunLogsResponse,
    FailureDiagnosisResponse,
    BackfillPlanResponse,
    ScheduleResponse,
    RecoveryRunResponse,
    MonitoringDashboardResponse,
    ExperimentRunRequest,
    ExperimentResponse,
)
from app.services.ingestion import handle_file_upload, get_dataset_preview, get_dataset_file_path
from app.services.contract_loader import (
    load_contract,
    list_available_contracts,
    detect_contract_for_columns,
)
from app.services.validator import validate_dataset
from app.services.pipeline_executor import execute_pipeline, get_pipeline_results
from app.services.attendance_executor import execute_attendance_pipeline
from app.services.correction_engine import (
    analyze_dataset_corrections,
    apply_dataset_corrections,
)
from app.schemas.schemas import (
    DataCorrectionProposal,
    DataCorrectionAnalysisResponse,
    ApplyCorrectionsRequest,
    ApplyCorrectionsResponse,
)
from app.services.auth import (
    register_user,
    login_user,
    get_user_by_id,
    record_user_activity,
    get_user_activity_stats,
)
from app.services.run_history import get_all_runs, get_run_artifacts, get_run_logs
from app.services.diagnosis_engine import create_or_get_failure_diagnosis
from app.services.backfill_planner import create_backfill_plan, approve_backfill_plan
from app.services.scheduler import compute_cost_aware_schedule, approve_schedule
from app.services.recovery_executor import execute_recovery
from app.services.monitoring_experiments import get_monitoring_dashboard, run_reproducible_experiment, EXPERIMENTS_DIR

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

def get_ist_now():
    """Returns current datetime in Indian Standard Time (IST, UTC+05:30)."""
    return datetime.now(IST).replace(tzinfo=None)

router = APIRouter(prefix="/api", tags=["Pipeline Orchestrator"])


# ==========================================
# CONTRACT DISCOVERY & AUTO-DETECTION
# ==========================================

@router.get("/contracts")
def get_contracts():
    """Returns all available YAML contracts with metadata."""
    return list_available_contracts()


@router.get("/contracts/{contract_name}")
def get_contract_detail(contract_name: str):
    """Retrieves full specification of a data contract."""
    try:
        return load_contract(contract_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/datasets/{dataset_id}/detect-contract")
def detect_dataset_contract(dataset_id: str, db: Session = Depends(get_db)):
    """
    Inspects actual columns of an uploaded dataset and recommends the most
    suitable data contract (sales, attendance, generic) with match evidence.
    """
    file_path, file_type = get_dataset_file_path(dataset_id, db)
    import polars as pl
    df_head = pl.read_csv(file_path, n_rows=5, infer_schema_length=0)
    return detect_contract_for_columns(list(df_head.columns))


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
    contract_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Validates the dataset against the specified (or auto-detected) YAML data contract.
    Records errors in PostgreSQL with IST timestamps and returns exact check summary.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    file_path, file_type = get_dataset_file_path(dataset_id, db)

    # If no contract specified by user, auto-detect based on actual uploaded columns
    if not contract_name or contract_name.lower() in ("auto", "default", "none"):
        import polars as pl
        df_head = pl.read_csv(file_path, n_rows=5, infer_schema_length=0)
        detection = detect_contract_for_columns(list(df_head.columns))
        contract_name = detection["suggested_contract"]

    contract_data = load_contract(contract_name)

    # Create a unique validation run ID
    val_run_id = f"VAL-{uuid.uuid4().hex[:10].upper()}"

    summary = validate_dataset(
        file_path=file_path,
        file_type=file_type,
        run_id=val_run_id,
        db=db,
        contract_data=contract_data,
        contract_name=contract_name
    )

    if summary.status == "INVALID":
        from app.services.run_history import compute_file_fingerprint
        from app.services.diagnosis_engine import create_or_get_failure_diagnosis

        now_ist = get_ist_now()
        pipeline_title = "Student_Attendance_Pipeline" if contract_name == "attendance" else "Sales_Transaction_Pipeline"
        err_msg = f"Contract validation failed: {summary.validation_errors_count} violation(s) across {summary.rows_invalid} row(s)."
        failed_run = PipelineRun(
            run_id=val_run_id,
            pipeline_name=pipeline_title,
            dataset_id=dataset_id,
            contract_version=summary.contract_version,
            started_at=now_ist,
            completed_at=now_ist,
            status="FAILED",
            rows_received=summary.rows_received,
            rows_valid=summary.rows_valid,
            rows_invalid=summary.rows_invalid,
            rows_processed=0,
            rows_rejected=summary.rows_invalid,
            file_format=file_type,
            dataset_fingerprint=compute_file_fingerprint(file_path),
            config_json=json.dumps({"pipeline": pipeline_title, "contract": contract_name}),
            artifact_path=file_path,
            error_message=err_msg
        )
        db.add(failed_run)

        val_task = PipelineTask(
            run_id=val_run_id,
            task_name="VALIDATION",
            status="FAILED",
            started_at=now_ist,
            completed_at=now_ist,
            rows_input=summary.rows_received,
            rows_output=summary.rows_valid,
            error_message=err_msg
        )
        db.add(val_task)
        db.commit()

        try:
            create_or_get_failure_diagnosis(val_run_id, db, use_ai=True)
        except Exception as diag_err:
            print(f"Auto-diagnosis notice: {diag_err}")

    return summary


# ==========================================
# INTERACTIVE DATA CORRECTION WORKFLOW
# ==========================================

@router.get("/datasets/{dataset_id}/corrections/analyze", response_model=DataCorrectionAnalysisResponse)
def analyze_corrections_endpoint(
    dataset_id: str,
    contract_name: Optional[str] = Query("sales"),
    db: Session = Depends(get_db)
):
    """
    Analyzes an uploaded dataset against the contract and proposes specific corrections
    (column mappings, marker standardizations, whitespace trims, date conversions)
    with before/after preview samples. Does NOT alter any data.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    file_path, file_type = get_dataset_file_path(dataset_id, db)
    return analyze_dataset_corrections(file_path, file_type, contract_name=contract_name)


@router.post("/datasets/{dataset_id}/corrections/apply", response_model=ApplyCorrectionsResponse)
def apply_corrections_endpoint(
    dataset_id: str,
    req: ApplyCorrectionsRequest,
    db: Session = Depends(get_db)
):
    """
    Applies user-approved corrections to create a separate corrected dataset file.
    The original uploaded file is NEVER modified.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    from app.services.ingestion import UPLOAD_DIR
    raw_path, file_type = get_dataset_file_path(dataset_id, db)
    corrected_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_corrected.csv")

    result = apply_dataset_corrections(raw_path, corrected_path, req.approved_fixes)

    # Update dataset record metadata to match corrected dimensions
    dataset.rows_count = result["corrected_rows"]
    dataset.columns_count = result["corrected_columns_count"]
    db.commit()

    return result


@router.post("/datasets/{dataset_id}/align-schema")
def align_dataset_schema_endpoint(
    dataset_id: str,
    contract_name: Optional[str] = Query("sales"),
    db: Session = Depends(get_db)
):
    """
    Intelligently reconciles column aliases (e.g. date -> transaction_date, status -> transaction_status, qty -> quantity,
    REGD.NO -> registration_number, CRT SEC -> section), standardizes formats, and aligns to the selected contract schema.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    from app.services.ingestion import UPLOAD_DIR, get_dataset_file_path, read_dataset_df
    from app.services.file_parsers import align_dataframe_schema
    from app.services.contract_loader import load_contract

    file_path, file_type = get_dataset_file_path(dataset_id, db)
    df = read_dataset_df(file_path, file_type)

    c_name = (contract_name or "sales").lower()
    try:
        contract_data = load_contract(c_name)
    except Exception:
        contract_data = load_contract("sales")

    c_type = contract_data.get("contract_type", c_name)

    if c_type == "attendance":
        # Align attendance column aliases to canonical names
        schema_spec = contract_data.get("schema", {})
        rename_map = {}
        added_or_fixed = []
        for target_field, field_meta in schema_spec.items():
            aliases = field_meta.get("aliases", [target_field])
            for c in df.columns:
                if c == target_field:
                    continue
                clean_c = re.sub(r"[^a-zA-Z0-9]", "", c.lower().strip())
                for a in aliases:
                    clean_a = re.sub(r"[^a-zA-Z0-9]", "", a.lower().strip())
                    if clean_c == clean_a:
                        rename_map[c] = target_field
                        added_or_fixed.append(f"{c} ➔ {target_field}")
                        break
                if c in rename_map:
                    break
        aligned_df = df.rename(rename_map) if rename_map else df
    else:
        aligned_df, added_or_fixed = align_dataframe_schema(df)

    # Save aligned dataframe directly to normalized CSV path
    norm_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_normalized.csv")
    aligned_df.write_csv(norm_path)

    corr_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_corrected.csv")
    if os.path.exists(corr_path):
        aligned_df.write_csv(corr_path)

    legacy_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_{dataset.filename}")
    if os.path.exists(legacy_path):
        aligned_df.write_csv(legacy_path)

    dataset.columns_count = len(aligned_df.columns)
    dataset.rows_count = len(aligned_df)
    dataset.status = "VALID"
    db.commit()

    return {
        "status": "SUCCESS",
        "dataset_id": dataset_id,
        "contract_name": contract_name or "sales",
        "aligned_columns": added_or_fixed,
        "total_columns": len(aligned_df.columns),
        "total_rows": len(aligned_df)
    }


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
        rows_processed=run.rows_processed or 0,
        rows_rejected=getattr(run, "rows_rejected", 0) or (run.rows_invalid or 0),
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


@router.post("/datasets/{dataset_id}/execute")
def execute_pipeline_endpoint(
    dataset_id: str,
    contract_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Executes the real processing pipeline stages sequentially:
    Supports Sales pipeline and Attendance pipeline with 100% real calculations.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    file_path, file_type = get_dataset_file_path(dataset_id, db)

    if not contract_name or contract_name.lower() in ("auto", "default", "none"):
        import polars as pl
        df_head = pl.read_csv(file_path, n_rows=5, infer_schema_length=0)
        det = detect_contract_for_columns(list(df_head.columns))
        contract_name = det["suggested_contract"]

    if contract_name == "attendance":
        return execute_attendance_pipeline(dataset_id, db, contract_name="attendance")
    else:
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


@router.get("/runs/{run_id}/results")
def get_run_results(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves final calculated metrics, aggregates, and tasks (sales or attendance)."""
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")

    if run.pipeline_name == "Student_Attendance_Pipeline" or (run.config_json and "attendance" in run.config_json):
        from app.services.attendance_executor import execute_attendance_pipeline
        return execute_attendance_pipeline(run.dataset_id, db, contract_name="attendance")

    return get_pipeline_results(run_id, db)


# ==========================================
# EXPORT & DOWNLOAD ENDPOINTS
# ==========================================

@router.get("/runs/{run_id}/download/processed")
def download_processed_dataset(run_id: str, db: Session = Depends(get_db)):
    """Downloads the final processed dataset as CSV across regular and recovery runs."""
    from fastapi.responses import FileResponse, Response
    from app.services.ingestion import UPLOAD_DIR
    import io, os

    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    
    # 1. If run has artifact_path and it exists
    if run and run.artifact_path and os.path.exists(run.artifact_path):
        filename = f"{run.run_id}_processed_dataset.csv"
        return FileResponse(run.artifact_path, filename=filename, media_type="text/csv")
    
    # 2. Check candidate filenames in UPLOAD_DIR
    candidate_names = [
        f"{run_id}_processed_transactions.csv",
        f"{run_id}_processed_attendance.csv",
        f"{run_id}_processed_dataset.csv",
    ]
    for c_name in candidate_names:
        c_path = os.path.join(UPLOAD_DIR, c_name)
        if os.path.exists(c_path):
            return FileResponse(c_path, filename=f"{run_id}_processed.csv", media_type="text/csv")

    # 3. If it's a recovery run, check the recovery record
    from app.models.models import RecoveryRunRecord
    rec = db.query(RecoveryRunRecord).filter(
        (RecoveryRunRecord.new_run_id == run_id) | (RecoveryRunRecord.recovery_id == run_id)
    ).first()
    if rec and rec.original_run_id:
        orig_run = db.query(PipelineRun).filter(PipelineRun.run_id == rec.original_run_id).first()
        if orig_run and orig_run.artifact_path and os.path.exists(orig_run.artifact_path):
            return FileResponse(orig_run.artifact_path, filename=f"{run_id}_processed.csv", media_type="text/csv")

    # 4. If dataset_id exists on run, return normalized or corrected CSV
    if run and run.dataset_id:
        norm_path = os.path.join(UPLOAD_DIR, f"{run.dataset_id}_normalized.csv")
        if os.path.exists(norm_path):
            return FileResponse(norm_path, filename=f"{run.run_id}_processed.csv", media_type="text/csv")

    # 5. Query PostgreSQL processed_transactions for this run_id
    try:
        from app.models.models import ProcessedTransaction
        txs = db.query(ProcessedTransaction).filter(ProcessedTransaction.run_id == run_id).all()
        if txs:
            import csv
            buf = io.StringIO()
            writer = csv.writer(buf)
            cols = [
                "transaction_id", "customer_id", "product_id", "customer_name", "city",
                "state", "customer_segment", "product_name", "category", "quantity",
                "unit_price", "total_amount", "calculated_total", "payment_method",
                "transaction_status", "transaction_date", "source_system", "run_id"
            ]
            writer.writerow(cols)
            for t in txs:
                writer.writerow([getattr(t, c, "") for c in cols])
            return Response(
                content=buf.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={run_id}_processed.csv"}
            )
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Processed output artifact file not found for this run.")


@router.get("/runs/{run_id}/inspection-details")
def get_inspection_details(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns comprehensive inspection details:
    - Pipeline run telemetry & status
    - Detailed AI failure diagnosis & root cause isolation
    - Backfill plan, DAG strategy, and rationale
    - AI recovery execution state, validation transitions, and exact changes made
    - Direct download metadata for processed dataset
    """
    import json
    from app.models.models import (
        PipelineRun, PipelineTask, FailureDiagnosisRecord,
        BackfillPlanRecord, RecoveryRunRecord
    )

    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    
    # Check if this run is a recovery run or has an associated recovery
    recovery_rec = db.query(RecoveryRunRecord).filter(
        (RecoveryRunRecord.new_run_id == run_id) | (RecoveryRunRecord.original_run_id == run_id)
    ).first()

    # Find diagnosis for this run or original run
    diag_run_id = run_id
    if recovery_rec and recovery_rec.original_run_id:
        diag_run_id = recovery_rec.original_run_id

    diagnosis = db.query(FailureDiagnosisRecord).filter(
        FailureDiagnosisRecord.run_id == diag_run_id
    ).first()

    backfill_plan = None
    if recovery_rec and recovery_rec.plan_id:
        backfill_plan = db.query(BackfillPlanRecord).filter(
            BackfillPlanRecord.plan_id == recovery_rec.plan_id
        ).first()

    if not backfill_plan and run:
        backfill_plan = db.query(BackfillPlanRecord).filter(
            BackfillPlanRecord.run_id == run_id
        ).first()

    if not diagnosis and backfill_plan and backfill_plan.failure_id:
        diagnosis = db.query(FailureDiagnosisRecord).filter(
            FailureDiagnosisRecord.failure_id == backfill_plan.failure_id
        ).first()

    # Build AI Diagnosis data
    diag_data = None
    if diagnosis:
        ranked = json.loads(diagnosis.ranked_causes_json) if diagnosis.ranked_causes_json else []
        evidence = json.loads(diagnosis.evidence_json) if diagnosis.evidence_json else []
        diag_data = {
            "failure_id": diagnosis.failure_id,
            "run_id": diagnosis.run_id,
            "failed_task_name": diagnosis.failed_task_name,
            "failure_category": diagnosis.failure_category,
            "error_message": diagnosis.error_message,
            "diagnosis_method": diagnosis.diagnosis_method,
            "model_version": diagnosis.model_version,
            "suggested_action": diagnosis.suggested_action,
            "ranked_causes": ranked,
            "evidence": evidence,
            "created_at": str(diagnosis.created_at) if diagnosis.created_at else None,
        }

    # Build Recovery / What Changed data
    recovery_data = None
    if recovery_rec:
        task_states = json.loads(recovery_rec.task_states_json) if recovery_rec.task_states_json else {}
        selected_tasks = json.loads(backfill_plan.selected_tasks_json) if (backfill_plan and backfill_plan.selected_tasks_json) else list(task_states.keys())
        affected_parts = json.loads(backfill_plan.affected_partitions_json) if (backfill_plan and backfill_plan.affected_partitions_json) else []

        recovery_data = {
            "recovery_id": recovery_rec.recovery_id,
            "plan_id": recovery_rec.plan_id,
            "original_run_id": recovery_rec.original_run_id,
            "new_run_id": recovery_rec.new_run_id,
            "status": recovery_rec.status,
            "contract_validation_status": recovery_rec.contract_validation_status or "PASSED",
            "output_validation_status": recovery_rec.output_validation_status or "PASSED",
            "task_states": task_states,
            "selected_tasks": selected_tasks,
            "affected_partitions": affected_parts,
            "plan_rationale": backfill_plan.rationale if backfill_plan else "Automated backfill recovery executed.",
            "duration_seconds": float(recovery_rec.duration_seconds) if recovery_rec.duration_seconds else None,
            "logs_text": recovery_rec.logs_text,
            "started_at": str(recovery_rec.started_at) if recovery_rec.started_at else None,
            "completed_at": str(recovery_rec.completed_at) if recovery_rec.completed_at else None,
        }

    # Summary of changes
    changes = []
    if diagnosis:
        changes.append({
            "stage": "AI Root Cause Diagnosis",
            "type": "ROOT_CAUSE_ISOLATION",
            "title": f"Detected: {diagnosis.failure_category}",
            "detail": diagnosis.error_message or diagnosis.suggested_action or "Issue isolated by AI Classifier."
        })
    if backfill_plan:
        changes.append({
            "stage": "AI Backfill Planning",
            "type": "EXECUTION_PLAN",
            "title": "Minimal Safe Execution Plan",
            "detail": backfill_plan.rationale or f"Selected tasks to rerun: {backfill_plan.selected_tasks_json}"
        })
    if recovery_rec:
        changes.append({
            "stage": "AI Recovery Execution",
            "type": "DATA_REPAIR",
            "title": f"Recovery Status: {recovery_rec.status}",
            "detail": f"Contract Validation: {recovery_rec.contract_validation_status or 'PASSED'} | Output Quality: {recovery_rec.output_validation_status or 'PASSED'}. Output rows persisted."
        })

    return {
        "run_id": run_id,
        "pipeline_name": run.pipeline_name if run else "Pipeline Run",
        "status": run.status if run else "UNKNOWN",
        "is_recovery_run": bool(recovery_rec or run_id.startswith("RUN-REC-")),
        "has_diagnosis": bool(diag_data),
        "diagnosis": diag_data,
        "has_recovery": bool(recovery_data),
        "recovery": recovery_data,
        "changes_summary": changes,
        "download_url": f"/api/runs/{run_id}/download/processed",
        "rows_processed": run.rows_processed if run else 0,
    }


@router.get("/runs/{run_id}/download/validation-errors")
def download_validation_errors(run_id: str, db: Session = Depends(get_db)):
    """Downloads all recorded validation errors as a structured CSV report."""
    from fastapi.responses import Response
    import io, csv
    errors = db.query(ValidationErrorRecord).filter(ValidationErrorRecord.run_id == run_id).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Row Number", "Column Name", "Error Type", "Actual Value", "Expected Rule", "Severity", "Timestamp"])
    for e in errors:
        writer.writerow([e.row_number, e.column_name, e.error_type, e.actual_value, e.expected_rule, e.severity, str(e.created_at)])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={run_id}_validation_errors.csv"}
    )


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

    from app.services.time_utils import normalize_date_val
    raw_dates = col.to_list()
    converted_dates = [normalize_date_val(d) for d in raw_dates]
    
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
# AUTHENTICATION & USER ACTIVITY AUDIT ENDPOINTS
# ==========================================

@router.post("/auth/register", response_model=AuthResponse)
def register(
    data: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Registers a new user with hashed password and stores in PostgreSQL/Neon with audit logging."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")
    return register_user(db, data, ip=client_ip, user_agent=user_agent)


@router.post("/auth/login", response_model=AuthResponse)
def login(
    data: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticates an existing user and records login timestamp, count, IP, and audit trail in PostgreSQL/Neon."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")
    return login_user(db, data, ip=client_ip, user_agent=user_agent)


@router.post("/auth/record-visit")
def record_visit(
    data: RecordVisitRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Records a website visit event in PostgreSQL/Neon and increments user visit counter."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")
    details = json.dumps(data.details) if data.details else None
    act = record_user_activity(
        db=db,
        activity_type="VISIT",
        user_id=data.user_id,
        email=data.email,
        ip=client_ip,
        user_agent=user_agent,
        page_url=data.page_url or "/",
        details_json=details
    )
    return {"status": "SUCCESS", "activity_id": act.id, "timestamp": act.timestamp}


@router.post("/auth/logout")
def logout(
    request: Request,
    user_id: Optional[int] = Query(None),
    email: Optional[str] = Query(None),
    reason: Optional[str] = Query("MANUAL"),
    db: Session = Depends(get_db)
):
    """Logs a logout or session expiration event in PostgreSQL/Neon."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")
    act_type = "SESSION_EXPIRED" if reason == "SESSION_EXPIRED" else "LOGOUT"
    act = record_user_activity(
        db=db,
        activity_type=act_type,
        user_id=user_id,
        email=email,
        ip=client_ip,
        user_agent=user_agent,
        page_url="/auth/logout",
        details_json=f'{{"reason": "{reason}"}}'
    )
    return {"status": "SUCCESS", "activity_id": act.id}


@router.get("/auth/activities", response_model=UserActivityStatsResponse)
def get_activities(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Returns aggregated audit report of users, visits, logins, and timestamps from PostgreSQL/Neon."""
    return get_user_activity_stats(db, limit=limit)


@router.get("/auth/me/{user_id}", response_model=UserResponse)
def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Fetches user profile by ID."""
    return get_user_by_id(db, user_id)


# ==========================================
# PHASE 5: RUN HISTORY & ARTIFACTS ENDPOINTS
# ==========================================

@router.get("/runs", response_model=RunHistoryResponse)
def list_runs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Retrieves persistent run history across restarts."""
    return get_all_runs(db, limit=limit, offset=offset)


@router.get("/runs/{run_id}/artifacts", response_model=RunArtifactsResponse)
def get_artifacts(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Fetches durable execution artifacts, dataset fingerprint, and outputs for a run."""
    return get_run_artifacts(run_id, db)


@router.get("/runs/{run_id}/logs", response_model=RunLogsResponse)
def get_logs(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Fetches complete task-by-task execution logs and telemetry for a run."""
    return get_run_logs(run_id, db)


# ==========================================
# PHASE 6: FAILURE DETECTION & AI DIAGNOSIS
# ==========================================

@router.post("/runs/{run_id}/diagnose", response_model=FailureDiagnosisResponse)
def diagnose_run(
    run_id: str,
    use_ai: bool = Query(True, description="Whether to use the calibrated AI classifier (True) or baseline rules (False)"),
    db: Session = Depends(get_db)
):
    """
    Performs root cause failure diagnosis for a pipeline run.
    Identifies the first failing task and ranks probable causes with calibrated confidence.
    """
    return create_or_get_failure_diagnosis(run_id, db, use_ai=use_ai)


@router.get("/runs/{run_id}/diagnosis", response_model=Optional[FailureDiagnosisResponse])
def get_run_diagnosis(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves an existing failure diagnosis for a pipeline run."""
    record = db.query(FailureDiagnosisRecord).filter(FailureDiagnosisRecord.run_id == run_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"No diagnosis found for run {run_id}")
    
    import json
    ranked = json.loads(record.ranked_causes_json) if record.ranked_causes_json else []
    evidence = json.loads(record.evidence_json) if record.evidence_json else []
    
    from app.schemas.schemas import RankedCauseItem
    return FailureDiagnosisResponse(
        failure_id=record.failure_id,
        run_id=record.run_id,
        failed_task_name=record.failed_task_name,
        failure_category=record.failure_category,
        error_message=record.error_message,
        ranked_causes=[RankedCauseItem(**c) for c in ranked],
        evidence=evidence,
        diagnosis_method=record.diagnosis_method,
        model_version=record.model_version,
        suggested_action=record.suggested_action,
        created_at=record.created_at,
    )


# ==========================================
# PHASE 7: BACKFILL PLANNING ENDPOINTS
# ==========================================

@router.post("/failures/{failure_id}/plan-backfill", response_model=BackfillPlanResponse)
def plan_backfill(
    failure_id: str,
    db: Session = Depends(get_db)
):
    """
    Generates a backfill plan calculating minimal safe set of tasks and affected partitions.
    Status starts in PENDING_APPROVAL.
    """
    return create_backfill_plan(failure_id, db)


@router.post("/backfills/{plan_id}/approve", response_model=BackfillPlanResponse)
def approve_backfill(
    plan_id: str,
    db: Session = Depends(get_db)
):
    """
    Explicit user approval gate for executing a backfill plan.
    Transitions status to APPROVED.
    """
    return approve_backfill_plan(plan_id, db)


@router.get("/backfills/{plan_id}", response_model=BackfillPlanResponse)
def get_backfill_plan(
    plan_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves details of a backfill plan."""
    plan = db.query(BackfillPlanRecord).filter(BackfillPlanRecord.plan_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Backfill plan {plan_id} not found")
    
    import json
    return BackfillPlanResponse(
        plan_id=plan.plan_id,
        failure_id=plan.failure_id,
        run_id=plan.run_id,
        failed_task=plan.failed_task,
        affected_partitions=json.loads(plan.affected_partitions_json) if plan.affected_partitions_json else [],
        selected_tasks=json.loads(plan.selected_tasks_json) if plan.selected_tasks_json else [],
        execution_order=json.loads(plan.execution_order_json) if plan.execution_order_json else [],
        estimated_runtime_seconds=plan.estimated_runtime_seconds,
        estimated_cost_usd=plan.estimated_cost_usd,
        rationale=plan.rationale,
        status=plan.status,
        created_at=plan.created_at,
    )


# ==========================================
# PHASE 8: COST-AWARE SCHEDULING ENDPOINTS
# ==========================================

@router.post("/backfills/{plan_id}/schedule", response_model=ScheduleResponse)
def schedule_backfill(
    plan_id: str,
    objective: str = Query("minimize_cost", description="minimize_cost, minimize_time, or balanced"),
    budget_limit_usd: Optional[float] = Query(None),
    deadline_seconds: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Schedules an approved backfill plan with optimal resource profiles and compares with FIFO baseline.
    """
    return compute_cost_aware_schedule(
        plan_id=plan_id,
        db=db,
        objective=objective,
        budget_limit_usd=budget_limit_usd,
        deadline_seconds=deadline_seconds,
    )


@router.post("/schedules/{schedule_id}/approve", response_model=ScheduleResponse)
def approve_sched(
    schedule_id: str,
    db: Session = Depends(get_db)
):
    """Explicit user approval gate for a schedule."""
    return approve_schedule(schedule_id, db)


# ==========================================
# PHASE 9: RECOVERY EXECUTION ENDPOINTS
# ==========================================

@router.post("/backfills/{plan_id}/recover", response_model=RecoveryRunResponse)
def start_recovery(
    plan_id: str,
    schedule_id: Optional[str] = Query(None),
    max_retries: int = Query(3),
    db: Session = Depends(get_db)
):
    """
    Executes controlled recovery. Enforces plan approval check before running.
    Tracks state transitions and performs contract & output quality validation.
    """
    return execute_recovery(
        plan_id=plan_id,
        db=db,
        schedule_id=schedule_id,
        max_retries=max_retries,
    )


@router.get("/recoveries/{recovery_id}", response_model=RecoveryRunResponse)
def get_recovery_status(
    recovery_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves recovery execution progress and state."""
    rec = db.query(RecoveryRunRecord).filter(RecoveryRunRecord.recovery_id == recovery_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recovery run {recovery_id} not found")
    
    import json
    return RecoveryRunResponse(
        recovery_id=rec.recovery_id,
        plan_id=rec.plan_id,
        schedule_id=rec.schedule_id,
        original_run_id=rec.original_run_id,
        new_run_id=rec.new_run_id,
        status=rec.status,
        current_task=rec.current_task,
        retry_count=rec.retry_count,
        max_retries=rec.max_retries,
        started_at=rec.started_at,
        completed_at=rec.completed_at,
        duration_seconds=rec.duration_seconds,
        contract_validation_status=rec.contract_validation_status,
        output_validation_status=rec.output_validation_status,
        task_states=json.loads(rec.task_states_json) if rec.task_states_json else {},
        logs_text=rec.logs_text,
        error_message=rec.error_message,
    )


# ==========================================
# PHASE 10: MONITORING & EXPERIMENTS ENDPOINTS
# ==========================================

@router.get("/monitoring/dashboard", response_model=MonitoringDashboardResponse)
def monitoring_dashboard(
    db: Session = Depends(get_db)
):
    """Returns operational KPIs aggregated directly from actual database runs."""
    return get_monitoring_dashboard(db)


@router.post("/experiments/run", response_model=ExperimentResponse)
def run_experiment(
    req: ExperimentRunRequest,
    db: Session = Depends(get_db)
):
    """
    Executes reproducible benchmark experiment:
    - diagnosis_accuracy (Experiment A)
    - backfill_efficiency (Experiment B)
    - scheduling_cost (Experiment C)
    - recovery_resilience (Experiment D)
    """
    return run_reproducible_experiment(
        experiment_type=req.experiment_type,
        config=req.config,
        db=db
    )


@router.get("/experiments/{experiment_id}/csv")
def download_experiment_csv(
    experiment_id: str,
    db: Session = Depends(get_db)
):
    """Downloads raw CSV metrics artifact for an experiment."""
    from fastapi.responses import FileResponse
    exp = db.query(ExperimentRecord).filter(ExperimentRecord.experiment_id == experiment_id).first()
    if not exp or not exp.raw_csv_path or not os.path.exists(exp.raw_csv_path):
        raise HTTPException(status_code=404, detail=f"Experiment CSV artifact for {experiment_id} not found")
    
    return FileResponse(
        path=exp.raw_csv_path,
        media_type="text/csv",
        filename=os.path.basename(exp.raw_csv_path)
    )


