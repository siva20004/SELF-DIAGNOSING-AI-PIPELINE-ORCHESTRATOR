import os
import pytest
import polars as pl
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal, init_db
from app.models.models import Dataset
from app.services.validator import validate_dataset
from app.services.file_parsers import align_dataframe_schema
from app.services.contract_loader import load_contract

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()

def test_needs_mapping_detection_and_auto_mapping_flow(tmp_path):
    # 1. Create a dataset with column aliases that needs mapping
    # Aliases: trans_id -> transaction_id, cust_id -> customer_id, qty -> quantity, price -> unit_price, date -> transaction_date
    test_csv = tmp_path / "sales_needs_mapping.csv"
    df_raw = pl.DataFrame({
        "trans_id": ["T10000001", "T10000002", "T10000003"],
        "cust_id": ["C100001", "C100002", "C100003"],
        "customer_name": ["Alice", "Bob", "Charlie"],
        "product_id": ["P101", "P102", "P103"],
        "product_name": ["Item A", "Item B", "Item C"],
        "category": ["Electronics", "Electronics", "Electronics"],
        "qty": ["2", "1", "3"],
        "price": ["10.00", "25.00", "15.00"],
        "total_amount": ["20.00", "25.00", "45.00"],
        "payment_method": ["CARD", "UPI", "WALLET"],
        "status": ["COMPLETED", "COMPLETED", "COMPLETED"],
        "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "city": ["Mumbai", "Delhi", "Bengaluru"],
        "state": ["Maharashtra", "Delhi", "Karnataka"],
        "customer_segment": ["Regular", "Premium", "Enterprise"],
        "source_system": ["POS", "WEB", "MOBILE"],
    })
    df_raw.write_csv(str(test_csv))

    contract = load_contract("sales")

    # 2. Validate original dataset -> should detect mappable columns and status = NEEDS_MAPPING
    summary = validate_dataset(
        file_path=str(test_csv),
        file_type="CSV",
        run_id="VAL-TEST-MAPPING-1",
        contract_data=contract,
        contract_name="sales"
    )
    assert summary.status == "NEEDS_MAPPING"
    assert len(summary.mappable_columns) > 0
    assert "transaction_id" in summary.mappable_columns
    assert summary.mappable_columns["transaction_id"] == "trans_id"
    assert "quantity" in summary.mappable_columns
    assert summary.mappable_columns["quantity"] == "qty"

    # 3. Perform schema alignment (Map Fields)
    aligned_df, added_or_fixed = align_dataframe_schema(df_raw)
    assert "transaction_id" in aligned_df.columns
    assert "quantity" in aligned_df.columns
    assert "unit_price" in aligned_df.columns
    assert "transaction_date" in aligned_df.columns
    assert "transaction_status" in aligned_df.columns

    aligned_csv = tmp_path / "sales_aligned.csv"
    aligned_df.write_csv(str(aligned_csv))

    # 4. Immediately trigger validation on aligned dataset -> should be VALID, clearing invalid flag
    reval_summary = validate_dataset(
        file_path=str(aligned_csv),
        file_type="CSV",
        run_id="VAL-TEST-MAPPING-2",
        contract_data=contract,
        contract_name="sales"
    )
    assert reval_summary.status == "VALID"
    assert reval_summary.rows_invalid == 0
    assert reval_summary.rows_valid == 3
    assert reval_summary.validation_errors_count == 0
