import os
import re
import datetime
from typing import Dict, Any, List, Tuple
import polars as pl
from app.services.contract_loader import load_contract
from app.schemas.schemas import ValidationSummary, ValidationErrorItem, CheckCategoryStats
from app.models.models import ValidationErrorRecord
from sqlalchemy.orm import Session


def validate_dataset(
    file_path: str,
    file_type: str,
    run_id: str,
    db: Session = None,
    contract_data: Dict[str, Any] = None
) -> ValidationSummary:
    if contract_data is None:
        contract_data = load_contract()

    schema_spec = contract_data.get("schema", {})
    quality_rules = contract_data.get("quality_rules", {})
    contract_version = str(contract_data.get("contract_version", "1.0"))

    # Read raw dataset with infer_schema_length=0 to keep original string representation for rigorous type checking
    ft = file_type.upper()
    if ft == "CSV":
        df = pl.read_csv(file_path, infer_schema_length=0)
    elif ft == "PARQUET":
        df = pl.read_parquet(file_path)
    elif ft == "JSON":
        try:
            df = pl.read_json(file_path)
        except Exception:
            df = pl.read_ndjson(file_path)
    else:
        raise ValueError(f"Unsupported file type {file_type}")

    total_rows = len(df)
    cols = df.columns

    errors: List[ValidationErrorItem] = []
    invalid_row_set = set()

    # 1. Required Columns Check
    req_cols_passed = 0
    req_cols_failed = 0
    total_req_cols = 0
    for col_name, col_meta in schema_spec.items():
        if col_meta.get("required", False):
            total_req_cols += 1
            if col_name not in cols:
                req_cols_failed += 1
                errors.append(
                    ValidationErrorItem(
                        row_number=None,
                        column_name=col_name,
                        error_type="MISSING_REQUIRED_COLUMN",
                        actual_value="Missing",
                        expected_rule=f"Column '{col_name}' required by contract",
                        severity="CRITICAL"
                    )
                )
            else:
                req_cols_passed += 1

    if req_cols_failed > 0:
        # If required columns are missing, return early with invalid status
        summary = ValidationSummary(
            status="INVALID",
            run_id=run_id,
            contract_version=contract_version,
            rows_received=total_rows,
            rows_valid=0,
            rows_invalid=total_rows,
            validation_errors_count=len(errors),
            required_column_checks=CheckCategoryStats(passed=req_cols_passed, failed=req_cols_failed, total=total_req_cols),
            type_checks=CheckCategoryStats(passed=0, failed=0, total=0),
            range_checks=CheckCategoryStats(passed=0, failed=0, total=0),
            enum_checks=CheckCategoryStats(passed=0, failed=0, total=0),
            pattern_checks=CheckCategoryStats(passed=0, failed=0, total=0),
            duplicate_checks=CheckCategoryStats(passed=0, failed=0, total=0),
            cross_field_checks=CheckCategoryStats(passed=0, failed=0, total=0),
            errors_preview=errors[:100]
        )
        if db:
            save_validation_errors(db, run_id, errors)
        return summary

    # Row-level and column checks
    # Use vectorized mask detection for fast validation on 1M rows
    type_checks_total = 0
    type_checks_failed = 0

    range_checks_total = 0
    range_checks_failed = 0

    enum_checks_total = 0
    enum_checks_failed = 0

    pattern_checks_total = 0
    pattern_checks_failed = 0

    null_rules = not quality_rules.get("null_values_allowed", True)

    # 1. Null and Empty String checks
    for col_name, col_meta in schema_spec.items():
        if col_name in cols and (col_meta.get("required", False) or null_rules):
            col_series = df[col_name]
            null_mask = col_series.is_null()
            if col_series.dtype == pl.Utf8 or col_series.dtype == pl.String:
                null_mask = null_mask | (col_series.str.strip_chars() == "")

            null_indices = null_mask.arg_true().to_list()
            if null_indices:
                type_checks_failed += len(null_indices)
                for idx in null_indices:
                    row_num = idx + 1
                    invalid_row_set.add(row_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=row_num,
                            column_name=col_name,
                            error_type="NULL_VALUE_NOT_ALLOWED",
                            actual_value="NULL" if col_series[idx] is None else "'' (Empty)",
                            expected_rule=f"Column '{col_name}' must not be null/empty",
                            severity="ERROR"
                        )
                    )
            type_checks_total += total_rows

    # 2. Pattern Checks
    for col_name, col_meta in schema_spec.items():
        pat = col_meta.get("pattern")
        if pat and col_name in cols:
            pattern_checks_total += total_rows
            col_series = df[col_name].cast(pl.String)
            # Polars regex pattern match
            valid_mask = col_series.str.contains(pat)
            invalid_indices = (~valid_mask).arg_true().to_list()
            if invalid_indices:
                pattern_checks_failed += len(invalid_indices)
                for idx in invalid_indices:
                    row_num = idx + 1
                    invalid_row_set.add(row_num)
                    val = str(col_series[idx])
                    errors.append(
                        ValidationErrorItem(
                            row_number=row_num,
                            column_name=col_name,
                            error_type="PATTERN_ERROR",
                            actual_value=val,
                            expected_rule=f"Pattern: {pat}",
                            severity="ERROR"
                        )
                    )

    # 3. Enum Checks
    for col_name, col_meta in schema_spec.items():
        allowed = col_meta.get("allowed_values")
        if allowed and col_name in cols:
            enum_checks_total += total_rows
            allowed_set = set(allowed)
            col_series = df[col_name].cast(pl.String)
            valid_mask = col_series.is_in(allowed)
            invalid_indices = (~valid_mask).arg_true().to_list()
            if invalid_indices:
                enum_checks_failed += len(invalid_indices)
                for idx in invalid_indices:
                    row_num = idx + 1
                    invalid_row_set.add(row_num)
                    val = str(col_series[idx])
                    errors.append(
                        ValidationErrorItem(
                            row_number=row_num,
                            column_name=col_name,
                            error_type="ENUM_ERROR",
                            actual_value=val,
                            expected_rule=f"Must be one of: {', '.join(allowed)}",
                            severity="ERROR"
                        )
                    )

    # 4. Type & Range Checks
    # Integer check for 'quantity'
    if "quantity" in cols:
        type_checks_total += total_rows
        q_raw = df["quantity"].cast(pl.String)
        # Check integer format
        int_valid_mask = q_raw.str.contains(r"^-?\d+$")
        invalid_int_indices = (~int_valid_mask).arg_true().to_list()
        if invalid_int_indices:
            type_checks_failed += len(invalid_int_indices)
            for idx in invalid_int_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="quantity",
                        error_type="TYPE_ERROR",
                        actual_value=str(q_raw[idx]),
                        expected_rule="Expected integer",
                        severity="ERROR"
                    )
                )

        # Range checks on valid ints
        range_checks_total += total_rows
        q_int_series = q_raw.cast(pl.Int64, strict=False)
        q_min = schema_spec.get("quantity", {}).get("min", 1)
        q_max = schema_spec.get("quantity", {}).get("max", 20)
        
        # Check min
        min_viol_indices = (int_valid_mask & (q_int_series < q_min)).arg_true().to_list()
        if min_viol_indices:
            range_checks_failed += len(min_viol_indices)
            for idx in min_viol_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="quantity",
                        error_type="MIN_VALUE",
                        actual_value=str(q_raw[idx]),
                        expected_rule=f">= {q_min}",
                        severity="ERROR"
                    )
                )

        # Check max
        max_viol_indices = (int_valid_mask & (q_int_series > q_max)).arg_true().to_list()
        if max_viol_indices:
            range_checks_failed += len(max_viol_indices)
            for idx in max_viol_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="quantity",
                        error_type="MAX_VALUE",
                        actual_value=str(q_raw[idx]),
                        expected_rule=f"<= {q_max}",
                        severity="ERROR"
                    )
                )

    # Number check for unit_price
    if "unit_price" in cols:
        type_checks_total += total_rows
        up_raw = df["unit_price"].cast(pl.String)
        num_valid_mask = up_raw.str.contains(r"^-?\d+(\.\d+)?$")
        invalid_num_indices = (~num_valid_mask).arg_true().to_list()
        if invalid_num_indices:
            type_checks_failed += len(invalid_num_indices)
            for idx in invalid_num_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="unit_price",
                        error_type="TYPE_ERROR",
                        actual_value=str(up_raw[idx]),
                        expected_rule="Expected number",
                        severity="ERROR"
                    )
                )
        
        range_checks_total += total_rows
        up_float_series = up_raw.cast(pl.Float64, strict=False)
        up_min = schema_spec.get("unit_price", {}).get("min", 0)
        up_min_indices = (num_valid_mask & (up_float_series < up_min)).arg_true().to_list()
        if up_min_indices:
            range_checks_failed += len(up_min_indices)
            for idx in up_min_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="unit_price",
                        error_type="MIN_VALUE",
                        actual_value=str(up_raw[idx]),
                        expected_rule=f">= {up_min}",
                        severity="ERROR"
                    )
                )

    # Number check for total_amount
    if "total_amount" in cols:
        type_checks_total += total_rows
        tot_raw = df["total_amount"].cast(pl.String)
        tot_num_valid_mask = tot_raw.str.contains(r"^-?\d+(\.\d+)?$")
        invalid_tot_indices = (~tot_num_valid_mask).arg_true().to_list()
        if invalid_tot_indices:
            type_checks_failed += len(invalid_tot_indices)
            for idx in invalid_tot_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="total_amount",
                        error_type="TYPE_ERROR",
                        actual_value=str(tot_raw[idx]),
                        expected_rule="Expected number",
                        severity="ERROR"
                    )
                )
        
        range_checks_total += total_rows
        tot_float_series = tot_raw.cast(pl.Float64, strict=False)
        tot_min = schema_spec.get("total_amount", {}).get("min", 0)
        tot_min_indices = (tot_num_valid_mask & (tot_float_series < tot_min)).arg_true().to_list()
        if tot_min_indices:
            range_checks_failed += len(tot_min_indices)
            for idx in tot_min_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="total_amount",
                        error_type="MIN_VALUE",
                        actual_value=str(tot_raw[idx]),
                        expected_rule=f">= {tot_min}",
                        severity="ERROR"
                    )
                )

    # Date check for transaction_date
    if "transaction_date" in cols:
        type_checks_total += total_rows
        td_raw = df["transaction_date"].cast(pl.String)
        # Check standard ISO format YYYY-MM-DD
        date_pattern_mask = td_raw.str.contains(r"^\d{4}-\d{2}-\d{2}$")
        date_fail_indices = (~date_pattern_mask).arg_true().to_list()
        if date_fail_indices:
            type_checks_failed += len(date_fail_indices)
            for idx in date_fail_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="transaction_date",
                        error_type="DATE_FORMAT_ERROR",
                        actual_value=str(td_raw[idx]),
                        expected_rule="Expected ISO date (YYYY-MM-DD)",
                        severity="ERROR"
                    )
                )

    # 5. Duplicate Validation
    duplicate_checks_total = total_rows
    duplicate_checks_failed = 0
    if quality_rules.get("transaction_id_unique", False) and "transaction_id" in cols:
        dup_mask = df["transaction_id"].is_duplicated()
        dup_indices = dup_mask.arg_true().to_list()
        if dup_indices:
            duplicate_checks_failed = len(dup_indices)
            for idx in dup_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="transaction_id",
                        error_type="DUPLICATE_ID",
                        actual_value=str(df["transaction_id"][idx]),
                        expected_rule="transaction_id must be unique across dataset",
                        severity="ERROR"
                    )
                )

    # 6. Cross-Field Validation (quantity * unit_price == total_amount)
    cross_field_total = total_rows
    cross_field_failed = 0
    if (
        quality_rules.get("total_amount_equals_quantity_times_unit_price", False)
        and "quantity" in cols
        and "unit_price" in cols
        and "total_amount" in cols
    ):
        q_s = df["quantity"].cast(pl.Float64, strict=False)
        up_s = df["unit_price"].cast(pl.Float64, strict=False)
        tot_s = df["total_amount"].cast(pl.Float64, strict=False)
        
        valid_math_mask = q_s.is_not_null() & up_s.is_not_null() & tot_s.is_not_null()
        calc_tot = q_s * up_s
        diff = (tot_s - calc_tot).abs()
        mismatch_mask = valid_math_mask & (diff > 0.01)
        mismatch_indices = mismatch_mask.arg_true().to_list()
        if mismatch_indices:
            cross_field_failed = len(mismatch_indices)
            for idx in mismatch_indices:
                row_num = idx + 1
                invalid_row_set.add(row_num)
                expected_calc = calc_tot[idx]
                errors.append(
                    ValidationErrorItem(
                        row_number=row_num,
                        column_name="total_amount",
                        error_type="CALCULATION_MISMATCH",
                        actual_value=str(tot_s[idx]),
                        expected_rule=f"Expected {expected_calc:.2f} (quantity {q_s[idx]} * unit_price {up_s[idx]})",
                        severity="ERROR"
                    )
                )

    rows_invalid_count = len(invalid_row_set)
    rows_valid_count = total_rows - rows_invalid_count
    is_valid = (len(errors) == 0 and rows_invalid_count == 0)

    summary = ValidationSummary(
        status="VALID" if is_valid else "INVALID",
        run_id=run_id,
        contract_version=contract_version,
        rows_received=total_rows,
        rows_valid=rows_valid_count,
        rows_invalid=rows_invalid_count,
        validation_errors_count=len(errors),
        required_column_checks=CheckCategoryStats(
            passed=req_cols_passed,
            failed=req_cols_failed,
            total=total_req_cols
        ),
        type_checks=CheckCategoryStats(
            passed=max(0, type_checks_total - type_checks_failed),
            failed=type_checks_failed,
            total=type_checks_total
        ),
        range_checks=CheckCategoryStats(
            passed=max(0, range_checks_total - range_checks_failed),
            failed=range_checks_failed,
            total=range_checks_total
        ),
        enum_checks=CheckCategoryStats(
            passed=max(0, enum_checks_total - enum_checks_failed),
            failed=enum_checks_failed,
            total=enum_checks_total
        ),
        pattern_checks=CheckCategoryStats(
            passed=max(0, pattern_checks_total - pattern_checks_failed),
            failed=pattern_checks_failed,
            total=pattern_checks_total
        ),
        duplicate_checks=CheckCategoryStats(
            passed=max(0, duplicate_checks_total - duplicate_checks_failed),
            failed=duplicate_checks_failed,
            total=duplicate_checks_total
        ),
        cross_field_checks=CheckCategoryStats(
            passed=max(0, cross_field_total - cross_field_failed),
            failed=cross_field_failed,
            total=cross_field_total
        ),
        errors_preview=errors[:200]
    )

    if db is not None:
        save_validation_errors(db, run_id, errors)

    return summary


def save_validation_errors(db: Session, run_id: str, errors: List[ValidationErrorItem]):
    # Delete old errors for this run if any
    db.query(ValidationErrorRecord).filter(ValidationErrorRecord.run_id == run_id).delete()
    db.commit()

    records = [
        ValidationErrorRecord(
            run_id=run_id,
            row_number=err.row_number,
            column_name=err.column_name,
            error_type=err.error_type,
            actual_value=err.actual_value,
            expected_rule=err.expected_rule,
            severity=err.severity,
            created_at=datetime.datetime.utcnow()
        )
        for err in errors
    ]
    # Bulk insert
    db.bulk_save_objects(records)
    db.commit()
