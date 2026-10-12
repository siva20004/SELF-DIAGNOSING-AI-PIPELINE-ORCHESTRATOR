from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Numeric,
    DateTime,
    Date,
    Text,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship
from app.database.session import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(64), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(32), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    rows_count = Column(BigInteger, nullable=False)
    columns_count = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    status = Column(String(32), nullable=False, default="UPLOADED")

    runs = relationship("PipelineRun", back_populates="dataset", cascade="all, delete-orphan")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    run_id = Column(String(64), primary_key=True, index=True)
    pipeline_name = Column(String(128), nullable=False, default="Sales_Transaction_Pipeline")
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    contract_version = Column(String(32), nullable=False, default="1.0")
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default="RUNNING")
    rows_received = Column(BigInteger, default=0)
    rows_valid = Column(BigInteger, default=0)
    rows_invalid = Column(BigInteger, default=0)
    rows_processed = Column(BigInteger, default=0)
    error_message = Column(Text, nullable=True)
    file_format = Column(String(32), default="CSV", nullable=False)
    dataset_fingerprint = Column(String(128), nullable=True)
    config_json = Column(Text, nullable=True)
    artifact_path = Column(String(255), nullable=True)

    dataset = relationship("Dataset", back_populates="runs")
    tasks = relationship("PipelineTask", back_populates="run", cascade="all, delete-orphan")
    transactions = relationship("ProcessedTransaction", back_populates="run", cascade="all, delete-orphan")
    aggregates = relationship("SalesAggregate", back_populates="run", cascade="all, delete-orphan")
    diagnoses = relationship("FailureDiagnosisRecord", back_populates="run", cascade="all, delete-orphan")
    backfill_plans = relationship("BackfillPlanRecord", back_populates="run", cascade="all, delete-orphan")



class PipelineTask(Base):
    __tablename__ = "pipeline_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    task_name = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="RUNNING")
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    rows_input = Column(BigInteger, default=0)
    rows_output = Column(BigInteger, default=0)
    error_message = Column(Text, nullable=True)

    run = relationship("PipelineRun", back_populates="tasks")


class ValidationErrorRecord(Base):
    __tablename__ = "validation_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    row_number = Column(BigInteger, nullable=True)
    column_name = Column(String(128), nullable=True)
    error_type = Column(String(64), nullable=False)
    actual_value = Column(Text, nullable=True)
    expected_rule = Column(Text, nullable=True)
    severity = Column(String(32), default="ERROR")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ProcessedTransaction(Base):
    __tablename__ = "processed_transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    product_id = Column(String(64), nullable=False)
    customer_name = Column(String(255), nullable=False)
    city = Column(String(128), nullable=False, index=True)
    state = Column(String(128), nullable=False)
    customer_segment = Column(String(64), nullable=False)
    product_name = Column(String(255), nullable=False)
    category = Column(String(128), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    calculated_total = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(64), nullable=False)
    transaction_status = Column(String(64), nullable=False)
    transaction_date = Column(Date, nullable=False, index=True)
    source_system = Column(String(64), nullable=False)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)

    run = relationship("PipelineRun", back_populates="transactions")


class SalesAggregate(Base):
    __tablename__ = "sales_aggregates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    aggregation_type = Column(String(64), nullable=False)  # 'city', 'category', 'date', 'overall'
    group_key = Column(String(128), nullable=False)
    transaction_count = Column(BigInteger, nullable=False)
    total_quantity = Column(BigInteger, nullable=False)
    total_sales = Column(Numeric(14, 2), nullable=False)
    run = relationship("PipelineRun", back_populates="aggregates")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    country = Column(String(128), nullable=False, default="United States")
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)


class FailureDiagnosisRecord(Base):
    __tablename__ = "failure_diagnoses"

    failure_id = Column(String(64), primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    failed_task_name = Column(String(64), nullable=True)
    failure_category = Column(String(64), nullable=False)  # Schema violation, Missing required columns, Invalid values, Upstream failure, etc.
    error_message = Column(Text, nullable=True)
    ranked_causes_json = Column(Text, nullable=False)  # JSON list of {cause, confidence, evidence, model_version}
    evidence_json = Column(Text, nullable=False)  # JSON list of evidence items & violations
    diagnosis_method = Column(String(64), nullable=False, default="rule_based_baseline")
    model_version = Column(String(32), nullable=False, default="1.0")
    suggested_action = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("PipelineRun", back_populates="diagnoses")


class BackfillPlanRecord(Base):
    __tablename__ = "backfill_plans"

    plan_id = Column(String(64), primary_key=True, index=True)
    failure_id = Column(String(64), nullable=False, index=True)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    failed_task = Column(String(64), nullable=False)
    affected_partitions_json = Column(Text, nullable=False)  # JSON list of affected partitions/dates/cities
    selected_tasks_json = Column(Text, nullable=False)  # Minimal safe set of tasks to rerun
    execution_order_json = Column(Text, nullable=False)  # Ordered execution steps
    estimated_runtime_seconds = Column(Numeric(10, 2), nullable=False, default=0.0)
    estimated_cost_usd = Column(Numeric(12, 6), nullable=False, default=0.0)
    rationale = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING_APPROVAL")  # PENDING_APPROVAL, APPROVED, REJECTED, EXECUTED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("PipelineRun", back_populates="backfill_plans")
    schedules = relationship("ScheduleRecord", back_populates="plan", cascade="all, delete-orphan")


class ScheduleRecord(Base):
    __tablename__ = "backfill_schedules"

    schedule_id = Column(String(64), primary_key=True, index=True)
    plan_id = Column(String(64), ForeignKey("backfill_plans.plan_id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(String(64), nullable=False, index=True)
    resource_profile = Column(String(64), nullable=False)  # Economy, Standard, Performance
    estimated_runtime_seconds = Column(Numeric(10, 2), nullable=False)
    estimated_cost_usd = Column(Numeric(12, 6), nullable=False)
    budget_limit_usd = Column(Numeric(10, 4), nullable=True)
    deadline_seconds = Column(Numeric(10, 2), nullable=True)
    optimization_objective = Column(String(64), nullable=False, default="minimize_cost")
    baseline_comparison_json = Column(Text, nullable=True)
    selection_rationale = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="SCHEDULED")  # SCHEDULED, APPROVED, EXECUTED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    plan = relationship("BackfillPlanRecord", back_populates="schedules")
    recoveries = relationship("RecoveryRunRecord", back_populates="schedule", cascade="all, delete-orphan")


class RecoveryRunRecord(Base):
    __tablename__ = "recovery_runs"

    recovery_id = Column(String(64), primary_key=True, index=True)
    plan_id = Column(String(64), nullable=False, index=True)
    schedule_id = Column(String(64), ForeignKey("backfill_schedules.schedule_id", ondelete="SET NULL"), nullable=True, index=True)
    original_run_id = Column(String(64), nullable=False, index=True)
    new_run_id = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="PENDING")  # PENDING, RUNNING, SUCCEEDED, FAILED
    current_task = Column(String(64), nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Numeric(10, 2), nullable=True)
    contract_validation_status = Column(String(32), nullable=True)
    output_validation_status = Column(String(32), nullable=True)
    task_states_json = Column(Text, nullable=True)
    logs_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    schedule = relationship("ScheduleRecord", back_populates="recoveries")


class ExperimentRecord(Base):
    __tablename__ = "benchmark_experiments"

    experiment_id = Column(String(64), primary_key=True, index=True)
    experiment_type = Column(String(64), nullable=False)  # diagnosis_accuracy, backfill_efficiency, scheduling_cost, recovery_resilience
    name = Column(String(128), nullable=False)
    config_json = Column(Text, nullable=False)
    baseline_metrics_json = Column(Text, nullable=False)
    proposed_metrics_json = Column(Text, nullable=False)
    raw_csv_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


