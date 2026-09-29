import io
import uuid
import datetime
from typing import Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
import polars as pl
import psycopg2

from app.database.session import DATABASE_URL
from app.models.models import (
    Dataset,
    PipelineRun,
    PipelineTask,
    SalesAggregate,
)
from app.schemas.schemas import (
    PipelineExecutionResponse,
    PipelineTaskItem,
    PipelineResultsResponse,
    PipelineMetrics,
    SalesByCityItem,
    SalesByCategoryItem,
    SalesByDateItem,
)
from app.services.ingestion import get_dataset_file_path, read_dataset_df
from app.services.contract_loader import load_contract
from app.services.validator import validate_dataset
from app.services.cleaner import clean_dataset
from app.services.transformer import transform_dataset
from app.services.calculator import calculate_dataset
from app.services.aggregator import aggregate_dataset
from app.services.quality_checker import run_quality_check


def execute_pipeline(dataset_id: str, db: Session) -> PipelineExecutionResponse:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    file_path, file_type = get_dataset_file_path(dataset_id, db)
    contract_data = load_contract()
    contract_version = str(contract_data.get("contract_version", "1.0"))

    # Generate dynamic unique run_id e.g. RUN-YYYYMMDD-HHMMSS-XXXX
    now = datetime.datetime.utcnow()
    run_id = f"RUN-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

    pipeline_run = PipelineRun(
        run_id=run_id,
        pipeline_name="Sales_Transaction_Pipeline",
        dataset_id=dataset_id,
        contract_version=contract_version,
        started_at=now,
        status="RUNNING",
        rows_received=dataset.rows_count,
        rows_valid=0,
        rows_invalid=0,
        rows_processed=0,
        rows_rejected=0,
    )
    db.add(pipeline_run)
    db.commit()
    db.refresh(pipeline_run)

    tasks_log = []

    def record_task_start(task_name: str) -> PipelineTask:
        task = PipelineTask(
            run_id=run_id,
            task_name=task_name,
            status="RUNNING",
            started_at=datetime.datetime.utcnow(),
            rows_input=0,
            rows_output=0,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def record_task_complete(task: PipelineTask, status: str, rows_in: int, rows_out: int, err: str = None):
        task.status = status
        task.completed_at = datetime.datetime.utcnow()
        task.rows_input = rows_in
        task.rows_output = rows_out
        task.error_message = err
        db.commit()
        db.refresh(task)
        tasks_log.append(task)

    try:
        # STAGE 1: VALIDATION
        val_task = record_task_start("VALIDATION")
        val_summary = validate_dataset(file_path, file_type, run_id, db, contract_data)

        if val_summary.status != "VALID":
            record_task_complete(
                val_task,
                status="FAILED",
                rows_in=val_summary.rows_received,
                rows_out=val_summary.rows_valid,
                err=f"Data contract validation failed: {val_summary.validation_errors_count} errors across {val_summary.rows_invalid} rows."
            )
            pipeline_run.status = "FAILED"
            pipeline_run.completed_at = datetime.datetime.utcnow()
            pipeline_run.rows_valid = val_summary.rows_valid
            pipeline_run.rows_invalid = val_summary.rows_invalid
            pipeline_run.rows_rejected = val_summary.rows_invalid
            pipeline_run.error_message = val_task.error_message
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=f"PIPELINE EXECUTION BLOCKED: Dataset validation failed with {val_summary.validation_errors_count} errors."
            )

        record_task_complete(
            val_task,
            status="SUCCESS",
            rows_in=val_summary.rows_received,
            rows_out=val_summary.rows_valid
        )
        pipeline_run.rows_valid = val_summary.rows_valid
        pipeline_run.rows_invalid = 0
        db.commit()

        # Load raw dataframe for execution stages
        df = read_dataset_df(file_path, file_type)

        # STAGE 2: CLEANING
        clean_task = record_task_start("CLEANING")
        cleaned_df, clean_in, clean_out = clean_dataset(df)
        record_task_complete(clean_task, "SUCCESS", clean_in, clean_out)

        # STAGE 3: TRANSFORMATION
        trans_task = record_task_start("TRANSFORMATION")
        trans_df, trans_in, trans_out = transform_dataset(cleaned_df)
        record_task_complete(trans_task, "SUCCESS", trans_in, trans_out)

        # STAGE 4: CALCULATION
        calc_task = record_task_start("CALCULATION")
        calc_df, calc_in, calc_out = calculate_dataset(trans_df)
        record_task_complete(calc_task, "SUCCESS", calc_in, calc_out)

        # STAGE 5: AGGREGATION
        agg_task = record_task_start("AGGREGATION")
        agg_result = aggregate_dataset(calc_df)
        agg_rows_out = len(agg_result["sales_by_city"]) + len(agg_result["sales_by_category"]) + len(agg_result["sales_by_date"])
        record_task_complete(agg_task, "SUCCESS", len(calc_df), agg_rows_out)

        # STAGE 6: FINAL QUALITY CHECK
        qc_task = record_task_start("QUALITY_CHECK")
        qc_result = run_quality_check(calc_df)
        if not qc_result["passed"]:
            err_msg = "; ".join(qc_result["violations"])
            record_task_complete(qc_task, "FAILED", len(calc_df), 0, err=err_msg)
            pipeline_run.status = "FAILED"
            pipeline_run.completed_at = datetime.datetime.utcnow()
            pipeline_run.error_message = err_msg
            db.commit()
            raise HTTPException(status_code=500, detail=f"Pipeline final quality check failed: {err_msg}")
        record_task_complete(qc_task, "SUCCESS", len(calc_df), len(calc_df))

        # STAGE 7: DATABASE STORAGE
        db_task = record_task_start("DATABASE_STORAGE")
        # Prepare calc_df with run_id column
        storage_df = calc_df.with_columns(pl.lit(run_id).alias("run_id"))
        
        # Ensure column ordering matches table
        target_cols = [
            "transaction_id", "customer_id", "product_id", "customer_name", "city",
            "state", "customer_segment", "product_name", "category", "quantity",
            "unit_price", "total_amount", "calculated_total", "payment_method",
            "transaction_status", "transaction_date", "source_system", "run_id"
        ]
        storage_df = storage_df.select(target_cols)

        # High performance streaming bulk copy to PostgreSQL
        csv_buffer = io.BytesIO()
        storage_df.write_csv(csv_buffer)
        csv_buffer.seek(0)

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        copy_sql = f"""
            COPY processed_transactions (
                {', '.join(target_cols)}
            ) FROM STDIN WITH CSV HEADER
        """
        cur.copy_expert(copy_sql, csv_buffer)
        conn.commit()
        cur.close()
        conn.close()

        # Store aggregates in sales_aggregates
        for item in agg_result["sales_by_city"]:
            db.add(SalesAggregate(
                run_id=run_id,
                aggregation_type="city",
                group_key=item["city"],
                transaction_count=item["transaction_count"],
                total_quantity=item["total_quantity"],
                total_sales=item["total_sales"]
            ))

        for item in agg_result["sales_by_category"]:
            db.add(SalesAggregate(
                run_id=run_id,
                aggregation_type="category",
                group_key=item["category"],
                transaction_count=item["transaction_count"],
                total_quantity=item["total_quantity"],
                total_sales=item["total_sales"]
            ))

        for item in agg_result["sales_by_date"]:
            db.add(SalesAggregate(
                run_id=run_id,
                aggregation_type="date",
                group_key=item["transaction_date"],
                transaction_count=item["transaction_count"],
                total_quantity=item["total_quantity"],
                total_sales=item["total_sales"]
            ))

        # Overall aggregate record
        db.add(SalesAggregate(
            run_id=run_id,
            aggregation_type="overall",
            group_key="TOTAL",
            transaction_count=agg_result["metrics"]["transaction_count"],
            total_quantity=agg_result["metrics"]["total_quantity"],
            total_sales=agg_result["metrics"]["total_sales"]
        ))
        db.commit()

        record_task_complete(db_task, "SUCCESS", len(storage_df), len(storage_df))

        # Finalize Pipeline Run
        completed_at = datetime.datetime.utcnow()
        duration = (completed_at - now).total_seconds()
        pipeline_run.status = "SUCCESS"
        pipeline_run.completed_at = completed_at
        pipeline_run.rows_processed = len(storage_df)
        pipeline_run.rows_rejected = 0
        db.commit()
        db.refresh(pipeline_run)

        # Load fresh tasks
        db_tasks = db.query(PipelineTask).filter(PipelineTask.run_id == run_id).order_by(PipelineTask.id).all()

        return PipelineExecutionResponse(
            run_id=pipeline_run.run_id,
            status=pipeline_run.status,
            pipeline_name=pipeline_run.pipeline_name,
            dataset_id=pipeline_run.dataset_id,
            contract_version=pipeline_run.contract_version,
            started_at=pipeline_run.started_at,
            completed_at=pipeline_run.completed_at,
            duration_seconds=round(duration, 2),
            rows_received=pipeline_run.rows_received,
            rows_valid=pipeline_run.rows_valid,
            rows_invalid=pipeline_run.rows_invalid,
            rows_processed=pipeline_run.rows_processed,
            rows_rejected=pipeline_run.rows_rejected,
            error_message=pipeline_run.error_message,
            tasks=[PipelineTaskItem.model_validate(t) for t in db_tasks]
        )

    except HTTPException:
        raise
    except Exception as e:
        pipeline_run.status = "FAILED"
        pipeline_run.completed_at = datetime.datetime.utcnow()
        pipeline_run.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Pipeline execution failure: {str(e)}")


def get_pipeline_results(run_id: str, db: Session) -> PipelineResultsResponse:
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")

    tasks = db.query(PipelineTask).filter(PipelineTask.run_id == run_id).order_by(PipelineTask.id).all()
    aggregates = db.query(SalesAggregate).filter(SalesAggregate.run_id == run_id).all()

    sales_by_city = [
        SalesByCityItem(
            city=agg.group_key,
            total_sales=float(agg.total_sales),
            total_quantity=agg.total_quantity,
            transaction_count=agg.transaction_count
        )
        for agg in aggregates if agg.aggregation_type == "city"
    ]
    sales_by_city.sort(key=lambda x: x.total_sales, reverse=True)

    sales_by_category = [
        SalesByCategoryItem(
            category=agg.group_key,
            total_sales=float(agg.total_sales),
            total_quantity=agg.total_quantity,
            transaction_count=agg.transaction_count
        )
        for agg in aggregates if agg.aggregation_type == "category"
    ]
    sales_by_category.sort(key=lambda x: x.total_sales, reverse=True)

    sales_by_date = [
        SalesByDateItem(
            transaction_date=agg.group_key,
            total_sales=float(agg.total_sales),
            total_quantity=agg.total_quantity,
            transaction_count=agg.transaction_count
        )
        for agg in aggregates if agg.aggregation_type == "date"
    ]
    sales_by_date.sort(key=lambda x: x.transaction_date)

    overall = next((agg for agg in aggregates if agg.aggregation_type == "overall"), None)
    total_sales = float(overall.total_sales) if overall else 0.0
    total_quantity = overall.total_quantity if overall else 0
    transaction_count = overall.transaction_count if overall else 0
    avg_tx_val = round(total_sales / transaction_count, 2) if transaction_count > 0 else 0.0

    duration = None
    if run.completed_at and run.started_at:
        duration = round((run.completed_at - run.started_at).total_seconds(), 2)

    return PipelineResultsResponse(
        run_id=run.run_id,
        status=run.status,
        pipeline_name=run.pipeline_name,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=duration,
        rows_received=run.rows_received,
        rows_processed=run.rows_processed,
        rows_rejected=run.rows_rejected,
        metrics=PipelineMetrics(
            total_sales=total_sales,
            total_quantity=total_quantity,
            transaction_count=transaction_count,
            average_transaction_value=avg_tx_val,
            validation_score=100.0 if run.status == "SUCCESS" else 0.0
        ),
        sales_by_city=sales_by_city,
        sales_by_category=sales_by_category,
        sales_by_date=sales_by_date,
        tasks=[PipelineTaskItem.model_validate(t) for t in tasks]
    )
