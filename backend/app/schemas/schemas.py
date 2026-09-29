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
