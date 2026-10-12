from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class DatasetUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    rows: int
    columns: int
    status: str
    available_sheets: Optional[List[str]] = None
    selected_sheet: Optional[str] = None
    extraction_notes: Optional[str] = None



class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    filename: str
    total_rows: int
    columns: List[str]
    preview_rows: List[Dict[str, Any]]


class ValidationErrorItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    row_number: Optional[int] = None
    column_name: Optional[str] = None
    error_type: str
    actual_value: Optional[str] = None
    expected_rule: Optional[str] = None
    severity: str = "ERROR"


class CheckCategoryStats(BaseModel):
    passed: int
    failed: int
    total: int


class ValidationSummary(BaseModel):
    status: str  # "VALID" or "INVALID"
    run_id: str
    contract_version: str
    rows_received: int
    rows_valid: int
    rows_invalid: int
    validation_errors_count: int
    required_column_checks: CheckCategoryStats
    type_checks: CheckCategoryStats
    range_checks: CheckCategoryStats
    enum_checks: CheckCategoryStats
    pattern_checks: CheckCategoryStats
    duplicate_checks: CheckCategoryStats
    cross_field_checks: CheckCategoryStats
    errors_preview: List[ValidationErrorItem] = []


class PipelineTaskItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    rows_input: int
    rows_output: int
    error_message: Optional[str] = None


class PipelineExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    status: str
    pipeline_name: str
    dataset_id: str
    contract_version: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    rows_received: int
    rows_valid: int
    rows_invalid: int
    rows_processed: int
    rows_rejected: int
    error_message: Optional[str] = None
    tasks: List[PipelineTaskItem] = []


class SalesByCityItem(BaseModel):
    city: str
    total_sales: float
    total_quantity: int
    transaction_count: int


class SalesByCategoryItem(BaseModel):
    category: str
    total_sales: float
    total_quantity: int
    transaction_count: int


class SalesByDateItem(BaseModel):
    transaction_date: str
    total_sales: float
    total_quantity: int
    transaction_count: int


class PipelineMetrics(BaseModel):
    total_sales: float
    total_quantity: int
    transaction_count: int
    average_transaction_value: float
    validation_score: float


class PipelineResultsResponse(BaseModel):
    run_id: str
    status: str
    pipeline_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    rows_received: int
    rows_processed: int
    rows_rejected: int
    metrics: PipelineMetrics
    sales_by_city: List[SalesByCityItem]
    sales_by_category: List[SalesByCategoryItem]
    sales_by_date: List[SalesByDateItem]
    tasks: List[PipelineTaskItem]


class UserRegisterRequest(BaseModel):
    first_name: str
    last_name: str
    country: str = "United States"
    email: str
    password: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    country: str
    email: str
    created_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


# ==========================================
# PHASE 5: RUN HISTORY & PERSISTENCE SCHEMAS
# ==========================================

class RunHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    pipeline_name: str
    dataset_id: str
    filename: Optional[str] = None
    file_format: Optional[str] = "CSV"
    dataset_fingerprint: Optional[str] = None
    contract_version: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    status: str
    rows_received: int
    rows_processed: int
    rows_invalid: int
    rows_rejected: int
    error_message: Optional[str] = None


class RunHistoryResponse(BaseModel):
    runs: List[RunHistoryItem]
    total_count: int


class RunArtifactsResponse(BaseModel):
    run_id: str
    dataset_id: str
    filename: str
    file_format: str
    artifact_path: Optional[str] = None
    row_count: int
    column_count: int
    fingerprint: Optional[str] = None
    config: Dict[str, Any] = {}
    sample_records: List[Dict[str, Any]] = []


class RunLogsResponse(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    tasks: List[PipelineTaskItem]
    error_message: Optional[str] = None
    raw_logs: List[str] = []


# ==========================================
# PHASE 6: FAILURE & AI DIAGNOSIS SCHEMAS
# ==========================================

class RankedCauseItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    cause: str
    confidence: float
    evidence: List[str]
    model_version: str


class FailureDiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    failure_id: str
    run_id: str
    failed_task_name: Optional[str] = None
    failure_category: str
    error_message: Optional[str] = None
    ranked_causes: List[RankedCauseItem]
    evidence: List[str]
    diagnosis_method: str
    model_version: str
    suggested_action: Optional[str] = None
    created_at: datetime


# ==========================================
# PHASE 7: BACKFILL PLANNING SCHEMAS
# ==========================================

class BackfillPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    failure_id: str
    run_id: str
    failed_task: str
    affected_partitions: List[str]
    selected_tasks: List[str]
    execution_order: List[str]
    estimated_runtime_seconds: float
    estimated_cost_usd: float
    rationale: Optional[str] = None
    status: str
    created_at: datetime


# ==========================================
# PHASE 8: COST-AWARE SCHEDULING SCHEMAS
# ==========================================

class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schedule_id: str
    plan_id: str
    run_id: str
    resource_profile: str
    estimated_runtime_seconds: float
    estimated_cost_usd: float
    budget_limit_usd: Optional[float] = None
    deadline_seconds: Optional[float] = None
    optimization_objective: str
    baseline_comparison: Dict[str, Any] = {}
    selection_rationale: Optional[str] = None
    status: str
    created_at: datetime


# ==========================================
# PHASE 9: RECOVERY EXECUTION SCHEMAS
# ==========================================

class RecoveryRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recovery_id: str
    plan_id: str
    schedule_id: Optional[str] = None
    original_run_id: str
    new_run_id: Optional[str] = None
    status: str
    current_task: Optional[str] = None
    retry_count: int
    max_retries: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    contract_validation_status: Optional[str] = None
    output_validation_status: Optional[str] = None
    task_states: Dict[str, str] = {}
    logs_text: Optional[str] = None
    error_message: Optional[str] = None


# ==========================================
# PHASE 10: MONITORING & EXPERIMENTS SCHEMAS
# ==========================================

class MonitoringDashboardResponse(BaseModel):
    total_runs: int
    success_count: int
    failure_count: int
    success_rate_percent: float
    total_rows_processed: int
    avg_duration_seconds: float
    total_estimated_cost_usd: float
    failure_categories: Dict[str, int]
    avg_diagnosis_latency_ms: float
    recovery_success_count: int
    recovery_failure_count: int
    recent_runs: List[RunHistoryItem]


class ExperimentRunRequest(BaseModel):
    experiment_type: str  # diagnosis_accuracy, backfill_efficiency, scheduling_cost, recovery_resilience
    config: Dict[str, Any] = {}


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    experiment_id: str
    experiment_type: str
    name: str
    config: Dict[str, Any]
    baseline_metrics: Dict[str, Any]
    proposed_metrics: Dict[str, Any]
    raw_csv_path: Optional[str] = None
    created_at: datetime


