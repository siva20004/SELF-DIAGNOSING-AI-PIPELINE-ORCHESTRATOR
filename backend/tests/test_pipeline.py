import os
import pytest
import polars as pl
from app.services.contract_loader import load_contract
from app.services.validator import validate_dataset
from app.services.cleaner import clean_dataset
from app.services.transformer import transform_dataset
from app.services.calculator import calculate_dataset
from app.services.aggregator import aggregate_dataset
from app.services.quality_checker import run_quality_check
from app.database.session import SessionLocal, init_db
from app.services.pipeline_executor import execute_pipeline, get_pipeline_results
from app.models.models import Dataset, PipelineRun, ProcessedTransaction, SalesAggregate


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()


def test_contract_loading():
    contract = load_contract()
    assert contract is not None
    assert contract.get("dataset") == "sales_transactions"
    assert contract.get("contract_version") == "1.0"
    schema = contract.get("schema", {})
    assert "transaction_id" in schema
    assert "quantity" in schema
    assert "unit_price" in schema
    assert "total_amount" in schema
    quality_rules = contract.get("quality_rules", {})
    assert quality_rules.get("total_amount_equals_quantity_times_unit_price") is True
    assert quality_rules.get("transaction_id_unique") is True
    assert quality_rules.get("null_values_allowed") is False


def test_invalid_dataset_validation():
    # Test with the provided sales_transactions_invalid_test.csv
    file_path = "sales_transactions_invalid_test.csv"
    if not os.path.exists(file_path):
        file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sales_transactions_invalid_test.csv")
    
    summary = validate_dataset(file_path, "CSV", "TEST-INVALID-RUN")
    assert summary.status == "INVALID"
    assert summary.rows_received == 10
    assert summary.rows_invalid > 0
    assert summary.validation_errors_count >= 8

    # Verify specific error types exist in detected errors
    error_types = {e.error_type for e in summary.errors_preview}
    assert "TYPE_ERROR" in error_types or "DATE_FORMAT_ERROR" in error_types
    assert "ENUM_ERROR" in error_types
    assert "PATTERN_ERROR" in error_types
    assert "MIN_VALUE" in error_types or "MAX_VALUE" in error_types
    assert "DUPLICATE_ID" in error_types
    assert "CALCULATION_MISMATCH" in error_types
    assert "NULL_VALUE_NOT_ALLOWED" in error_types


def test_missing_column_validation(tmp_path):
    # Create CSV missing transaction_date
    bad_csv = tmp_path / "missing_col.csv"
    bad_csv.write_text(
        "transaction_id,customer_id,product_id,customer_name,city,state,customer_segment,product_name,category,quantity,unit_price,total_amount,payment_method,transaction_status,source_system\n"
        "T00000001,C000001,P001,John Doe,Hyderabad,Telangana,Regular,Laptop,Electronics,1,1000,1000,UPI,COMPLETED,WEB\n"
    )
    summary = validate_dataset(str(bad_csv), "CSV", "TEST-MISSING-COL")
    assert summary.status == "INVALID"
    assert any(e.error_type == "MISSING_REQUIRED_COLUMN" and e.column_name == "transaction_date" for e in summary.errors_preview)


def test_cleaning_stage():
    df = pl.DataFrame({
        "transaction_id": [" T00000001 "],
        "city": ["  Hyderabad  "],
        "quantity": [5]
    })
    cleaned, in_rows, out_rows = clean_dataset(df)
    assert in_rows == 1
    assert out_rows == 1
    assert cleaned["transaction_id"][0] == "T00000001"
    assert cleaned["city"][0] == "Hyderabad"
    assert cleaned["quantity"][0] == 5


def test_transformation_stage():
    df = pl.DataFrame({
        "quantity": ["5"],
        "unit_price": ["100.50"],
        "total_amount": ["502.50"],
        "transaction_date": ["2026-09-20 00:00:00"]
    })
    transformed, in_rows, out_rows = transform_dataset(df)
    assert transformed["quantity"].dtype in (pl.Int32, pl.Int64)
    assert transformed["unit_price"].dtype == pl.Float64
    assert transformed["total_amount"].dtype == pl.Float64
    assert transformed["transaction_date"][0] == "2026-09-20"


def test_calculation_stage():
    df = pl.DataFrame({
        "quantity": [3, 2],
        "unit_price": [150.0, 50.0],
        "total_amount": [450.0, 100.0]
    })
    calc, in_rows, out_rows = calculate_dataset(df)
    assert "calculated_total" in calc.columns
    assert "calculation_difference" in calc.columns
    assert calc["calculated_total"][0] == 450.0
    assert calc["calculation_difference"][0] == 0.0


def test_aggregation_stage():
    df = pl.DataFrame({
        "transaction_id": ["T1", "T2", "T3"],
        "city": ["Hyderabad", "Hyderabad", "Bengaluru"],
        "category": ["Electronics", "Electronics", "Audio"],
        "transaction_date": ["2026-09-20", "2026-09-20", "2026-09-21"],
        "quantity": [2, 3, 1],
        "unit_price": [100.0, 200.0, 500.0],
        "total_amount": [200.0, 600.0, 500.0],
        "calculated_total": [200.0, 600.0, 500.0]
    })
    agg = aggregate_dataset(df)
    metrics = agg["metrics"]
    assert metrics["total_sales"] == 1300.0
    assert metrics["total_quantity"] == 6
    assert metrics["transaction_count"] == 3
    assert metrics["average_transaction_value"] == round(1300.0 / 3, 2)

    # Check city aggregation
    hyd = next((c for c in agg["sales_by_city"] if c["city"] == "Hyderabad"), None)
    assert hyd is not None
    assert hyd["total_sales"] == 800.0
    assert hyd["total_quantity"] == 5
    assert hyd["transaction_count"] == 2


def test_quality_check():
    df = pl.DataFrame({
        "transaction_id": ["T00000001", "T00000002"],
        "customer_id": ["C000001", "C000002"],
        "product_id": ["P001", "P002"],
        "quantity": [2, 5],
        "unit_price": [100.0, 200.0],
        "total_amount": [200.0, 1000.0],
        "calculated_total": [200.0, 1000.0],
        "transaction_date": ["2026-09-20", "2026-09-21"]
    })
    qc = run_quality_check(df)
    assert qc["passed"] is True
    assert qc["score"] == 100.0


def test_pipeline_execution_and_persistence(tmp_path):
    # Create small valid test dataset
    valid_csv = tmp_path / "sample_valid.csv"
    valid_csv.write_text(
        "transaction_id,customer_id,product_id,customer_name,city,state,customer_segment,product_name,category,quantity,unit_price,total_amount,payment_method,transaction_status,transaction_date,source_system\n"
        "T00000001,C000001,P001,Ravi Kumar,Hyderabad,Telangana,Regular,Laptop,Electronics,2,50000,100000,UPI,COMPLETED,2026-09-20,WEB\n"
        "T00000002,C000002,P002,Ananya Rao,Bengaluru,Karnataka,Premium,Mouse,Accessories,5,500,2500,CARD,COMPLETED,2026-09-20,MOBILE\n"
    )

    db = SessionLocal()
    try:
        # Register dataset in db
        dataset_id = "ds_test_valid"
        db.query(Dataset).filter(Dataset.id == dataset_id).delete()
        db.commit()

        dataset_record = Dataset(
            id=dataset_id,
            filename=str(valid_csv),
            file_type="CSV",
            file_size_bytes=os.path.getsize(valid_csv),
            rows_count=2,
            columns_count=16,
            status="UPLOADED"
        )
        db.add(dataset_record)
        db.commit()

        # Execute pipeline
        response = execute_pipeline(dataset_id, db)
        assert response.status == "SUCCESS"
        assert response.rows_processed == 2
        assert response.rows_valid == 2
        assert response.rows_rejected == 0
        assert len(response.tasks) == 7

        # Verify PostgreSQL database records
        tx_count = db.query(ProcessedTransaction).filter(ProcessedTransaction.run_id == response.run_id).count()
        assert tx_count == 2

        agg_count = db.query(SalesAggregate).filter(SalesAggregate.run_id == response.run_id).count()
        assert agg_count > 0

        # Retrieve results via get_pipeline_results
        results = get_pipeline_results(response.run_id, db)
        assert results.metrics.total_sales == 102500.0
        assert results.metrics.total_quantity == 7
        assert results.metrics.transaction_count == 2

    finally:
        db.close()


def test_user_registration_and_login():
    from app.services.auth import register_user, login_user
    from app.schemas.schemas import UserRegisterRequest, UserLoginRequest
    from app.models.models import User

    db = SessionLocal()
    test_email = "tester_demo@example.com"
    try:
        # Clean up if exists
        db.query(User).filter(User.email == test_email).delete()
        db.commit()

        # 1. Register
        reg_data = UserRegisterRequest(
            first_name="Jane",
            last_name="Doe",
            country="United States",
            email=test_email,
            password="secretPassword123"
        )
        auth_resp = register_user(db, reg_data)
        assert auth_resp.user.email == test_email
        assert auth_resp.user.first_name == "Jane"
        assert auth_resp.token.startswith("agy_")

        # Verify password is encrypted in database (not plain text)
        db_user = db.query(User).filter(User.email == test_email).first()
        assert db_user is not None
        assert db_user.hashed_password != "secretPassword123"

        # 2. Login
        login_data = UserLoginRequest(
            email=test_email,
            password="secretPassword123"
        )
        login_resp = login_user(db, login_data)
        assert login_resp.user.email == test_email
        assert login_resp.token.startswith("agy_")

        # 3. Invalid Login Check
        with pytest.raises(Exception):
            login_user(db, UserLoginRequest(email=test_email, password="wrongPassword"))

        # Clean up
        db.query(User).filter(User.email == test_email).delete()
        db.commit()
    finally:
        db.close()

