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
    rows_rejected = Column(BigInteger, default=0)
    error_message = Column(Text, nullable=True)

    dataset = relationship("Dataset", back_populates="runs")
    tasks = relationship("PipelineTask", back_populates="run", cascade="all, delete-orphan")
    transactions = relationship("ProcessedTransaction", back_populates="run", cascade="all, delete-orphan")
    aggregates = relationship("SalesAggregate", back_populates="run", cascade="all, delete-orphan")


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

