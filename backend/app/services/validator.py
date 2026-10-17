import os
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
import polars as pl
from app.services.contract_loader import load_contract, detect_contract_for_columns
from app.schemas.schemas import ValidationSummary, ValidationErrorItem, CheckCategoryStats
from app.models.models import ValidationErrorRecord
from sqlalchemy.orm import Session

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

def _get_ist_now() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower().strip())


def validate_dataset(
    file_path: str,
    file_type: str,
    run_id: str,
    db: Session = None,
    contract_data: Dict[str, Any] = None,
    contract_name: str = None
) -> ValidationSummary:
    """
    Contract-Agnostic Vectorized Validation Engine.
    Validates any uploaded tabular dataset against its configured data contract
    (Sales, Attendance, or Generic).
    
    Returns structured ValidationSummary with:
    - Status: VALID, INVALID, or NEEDS_MAPPING
    - Required & optional fields check
    - Missing & unexpected columns
    - Row-level error items with exact row numbers and violation values
    - Categorical check counters
    """
    # Read raw dataset
    ft = file_type.upper()
    try:
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
            df = pl.read_csv(file_path, infer_schema_length=0)
    except Exception as e:
        raise ValueError(f"Failed to read dataset file: {str(e)}")

    total_rows = len(df)
    cols = list(df.columns)

    # Auto-normalize date columns to standard ISO YYYY-MM-DD
    target_date_cols = [
        c for c in cols 
        if _norm(c) in ("transactiondate", "date", "orderdate", "txndate")
    ]
    date_modified = False
    for dt_col in target_date_cols:
        from app.services.time_utils import normalize_date_val
        raw_vals = df[dt_col].cast(pl.String).to_list()
        norm_vals = [normalize_date_val(v) for v in raw_vals]
        if norm_vals != raw_vals:
            df = df.with_columns(pl.Series(dt_col, norm_vals, dtype=pl.String))
            date_modified = True

    if date_modified and ("_normalized.csv" in file_path or "uploads" in file_path or "temp" in file_path.lower() or "tmp" in file_path.lower()):
        try:
            df.write_csv(file_path)
        except Exception:
            pass

    # If contract_data not provided, auto-detect or load specified
    if contract_data is None:
        if contract_name:
            contract_data = load_contract(contract_name)
        else:
            detection = detect_contract_for_columns(cols)
            contract_data = load_contract(detection["suggested_contract"])

    contract_type = contract_data.get("contract_type", "sales")
    dataset_name = contract_data.get("dataset", "dataset")
    contract_version = str(contract_data.get("contract_version", "1.0"))
    schema_spec = contract_data.get("schema", {})
    quality_rules = contract_data.get("quality_rules", {})
    att_config = contract_data.get("attendance_config", {})

    errors: List[ValidationErrorItem] = []
    invalid_row_set = set()

    # --- 1. COLUMN AUDIT & ALIAS RESOLUTION ---
    missing_columns = []
    mappable_columns = {}
    matched_source_cols = set()

    from app.services.file_parsers import HEADER_FRAGMENTS_MAP

    for col_name, col_meta in schema_spec.items():
        is_required = col_meta.get("required", False)
        base_aliases = col_meta.get("aliases", [col_name])
        fragments = HEADER_FRAGMENTS_MAP.get(col_name, []) if contract_type == "sales" else []
        aliases = list(dict.fromkeys(base_aliases + fragments))
        
        # Check direct presence (exact or case/whitespace-insensitive match)
        direct_match = None
        for c in cols:
            if _norm(c) == _norm(col_name):
                direct_match = c
                break

        if direct_match:
            matched_source_cols.add(direct_match)
        else:
            # Check if an alias exists in the source file
            alias_match = None
            for c in cols:
                clean_c = _norm(c)
                if any(clean_c == _norm(a) or (len(_norm(a)) >= 4 and _norm(a) in clean_c) for a in aliases):
                    alias_match = c
                    break
            
            if alias_match:
                mappable_columns[col_name] = alias_match
                matched_source_cols.add(alias_match)
            elif is_required:
                missing_columns.append(col_name)

    # Check unexpected columns
    unexpected_columns = []
    session_cols_found = []
    if contract_type == "attendance":
        session_patterns = att_config.get("session_column_patterns", [r"^\d{1,2}:\d{2}"])
        compiled = [re.compile(p) for p in session_patterns]
        summary_cfg = att_config.get("summary_columns", {})
        summary_aliases = set()
        for sm_list in summary_cfg.values():
            summary_aliases.update(_norm(a) for a in sm_list)

        for c in cols:
            if any(p.match(c.strip()) for p in compiled):
                session_cols_found.append(c)
                matched_source_cols.add(c)
            elif _norm(c) in summary_aliases or "att" in _norm(c):
                matched_source_cols.add(c)
            elif c not in matched_source_cols:
                unexpected_columns.append(c)
    else:
        for c in cols:
            if c not in matched_source_cols and _norm(c) not in [_norm(k) for k in schema_spec.keys()]:
                unexpected_columns.append(c)

    # Required column stats
    req_keys = [k for k, v in schema_spec.items() if v.get("required", False)]
    total_req = len(req_keys)
    failed_req = len(missing_columns)
    passed_req = max(0, total_req - failed_req)

    # Record errors for genuinely missing required columns
    for mc in missing_columns:
        errors.append(
            ValidationErrorItem(
                row_number=None,
                column_name=mc,
                error_type="MISSING_REQUIRED_COLUMN",
                actual_value="Column Missing",
                expected_rule=f"Required column '{mc}' not found in uploaded file",
                severity="CRITICAL",
            )
        )

    # Determine early status if schema mismatch
    status = "VALID"
    if missing_columns:
        status = "INVALID"
    elif mappable_columns:
        status = "NEEDS_MAPPING"

    # Category counters
    type_checks_total = 0
    type_checks_failed = 0
    range_checks_total = 0
    range_checks_failed = 0
    enum_checks_total = 0
    enum_checks_failed = 0
    pattern_checks_total = 0
    pattern_checks_failed = 0
    dup_checks_total = total_rows
    dup_checks_failed = 0
    cross_field_total = total_rows
    cross_field_failed = 0

    # Helper to resolve actual column name in dataframe
    def get_actual_col(field_key: str) -> Optional[str]:
        if field_key in cols:
            return field_key
        return mappable_columns.get(field_key)

    # --- 2. NULL & EMPTY CHECKS ---
    for field_name, field_meta in schema_spec.items():
        act_col = get_actual_col(field_name)
        if not act_col or act_col not in cols:
            continue

        if field_meta.get("required", False) or not quality_rules.get("null_values_allowed", True):
            type_checks_total += total_rows
            col_series = df[act_col]
            null_mask = col_series.is_null()
            if col_series.dtype in (pl.Utf8, pl.String):
                null_mask = null_mask | (col_series.cast(pl.String).str.strip_chars() == "")

            null_indices = null_mask.arg_true().to_list()
            if null_indices:
                type_checks_failed += len(null_indices)
                for idx in null_indices[:50]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=act_col,
                            error_type="NULL_VALUE_NOT_ALLOWED",
                            actual_value="NULL or Empty",
                            expected_rule=f"Field '{field_name}' must not be null/empty",
                            severity="ERROR",
                        )
                    )

    # --- 3. PATTERN CHECKS ---
    for field_name, field_meta in schema_spec.items():
        pat = field_meta.get("pattern")
        act_col = get_actual_col(field_name)
        if pat and act_col and act_col in cols:
            pattern_checks_total += total_rows
            col_s = df[act_col].cast(pl.String)
            valid_mask = col_s.str.contains(pat)
            invalid_indices = (~valid_mask).arg_true().to_list()
            if invalid_indices:
                pattern_checks_failed += len(invalid_indices)
                for idx in invalid_indices[:50]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=act_col,
                            error_type="PATTERN_ERROR",
                            actual_value=str(col_s[idx]),
                            expected_rule=f"Pattern: {pat}",
                            severity="ERROR",
                        )
                    )
        elif not pat and field_meta.get("type") == "date" and act_col and act_col in cols:
            pattern_checks_total += total_rows
            col_s = df[act_col].cast(pl.String)
            valid_mask = col_s.str.contains(r"^\d{4}-\d{2}-\d{2}$")
            invalid_indices = (~valid_mask).arg_true().to_list()
            if invalid_indices:
                pattern_checks_failed += len(invalid_indices)
                for idx in invalid_indices[:50]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=act_col,
                            error_type="DATE_FORMAT_ERROR",
                            actual_value=str(col_s[idx]),
                            expected_rule="Date must follow ISO standard YYYY-MM-DD",
                            severity="ERROR",
                        )
                    )

    # --- 4. ENUM CHECKS ---
    for field_name, field_meta in schema_spec.items():
        allowed = field_meta.get("allowed_values")
        act_col = get_actual_col(field_name)
        if allowed and act_col and act_col in cols:
            enum_checks_total += total_rows
            col_s = df[act_col].cast(pl.String)
            valid_mask = col_s.is_in(allowed)
            invalid_indices = (~valid_mask).arg_true().to_list()
            if invalid_indices:
                enum_checks_failed += len(invalid_indices)
                for idx in invalid_indices[:50]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=act_col,
                            error_type="ENUM_ERROR",
                            actual_value=str(col_s[idx]),
                            expected_rule=f"Allowed: {', '.join(allowed)}",
                            severity="ERROR",
                        )
                    )

    # --- 5. ATTENDANCE CONTRACT SPECIFIC CHECKS ---
    if contract_type == "attendance":
        # A. Unique registration number check
        reg_col = get_actual_col("registration_number")
        if reg_col and reg_col in cols and quality_rules.get("registration_number_unique", True):
            s_reg = df[reg_col].cast(pl.String).str.strip_chars()
            non_empty_mask = (s_reg != "") & s_reg.is_not_null()
            dup_mask = s_reg.is_duplicated() & non_empty_mask
            dup_indices = dup_mask.arg_true().to_list()
            if dup_indices:
                dup_checks_failed = len(dup_indices)
                for idx in dup_indices[:50]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=reg_col,
                            error_type="DUPLICATE_REGISTRATION_NUMBER",
                            actual_value=str(s_reg[idx]),
                            expected_rule="Student registration number must be unique",
                            severity="ERROR",
                        )
                    )

        # B. Attendance session markers check
        markers_cfg = att_config.get("session_markers", {})
        present_markers = set(str(m).strip().upper() for m in markers_cfg.get("present", ["P", "PRESENT", "1"]))
        absent_markers = set(str(m).strip().upper() for m in markers_cfg.get("absent", ["A", "ABSENT", "0"]))
        na_markers = set(str(m).strip().upper() for m in markers_cfg.get("not_applicable", ["NA", "N/A", "-", "", "HOLIDAY", "CANCELLED", "NONE", "NULL"]))
        all_allowed_markers = present_markers | absent_markers | na_markers

        if quality_rules.get("validate_attendance_markers", True) and session_cols_found:
            for sc in session_cols_found:
                enum_checks_total += total_rows
                sc_series = df[sc].cast(pl.String).str.strip_chars().str.to_uppercase()
                invalid_markers_mask = ~sc_series.is_in(list(all_allowed_markers)) & (sc_series != "") & sc_series.is_not_null()
                inv_indices = invalid_markers_mask.arg_true().to_list()
                if inv_indices:
                    enum_checks_failed += len(inv_indices)
                    for idx in inv_indices[:20]:
                        r_num = idx + 1
                        invalid_row_set.add(r_num)
                        errors.append(
                            ValidationErrorItem(
                                row_number=r_num,
                                column_name=sc,
                                error_type="INVALID_ATTENDANCE_MARKER",
                                actual_value=str(df[sc][idx]),
                                expected_rule=f"Marker must be one of: {', '.join(sorted(present_markers | absent_markers | {'NA'}))}",
                                severity="WARNING",
                            )
                        )

    # --- 6. SALES CONTRACT SPECIFIC CHECKS ---
    elif contract_type == "sales":
        # A. Unique transaction_id
        tx_col = get_actual_col("transaction_id")
        if tx_col and tx_col in cols and quality_rules.get("transaction_id_unique", True):
            dup_mask = df[tx_col].is_duplicated() & df[tx_col].is_not_null()
            dup_indices = dup_mask.arg_true().to_list()
            if dup_indices:
                dup_checks_failed = len(dup_indices)
                for idx in dup_indices[:50]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=tx_col,
                            error_type="DUPLICATE_ID",
                            actual_value=str(df[tx_col][idx]),
                            expected_rule="transaction_id must be unique across dataset",
                            severity="ERROR",
                        )
                    )

        # B. Numeric range checks on quantity, unit_price, total_amount
        q_col = get_actual_col("quantity")
        if q_col and q_col in cols:
            type_checks_total += total_rows
            q_raw = df[q_col].cast(pl.String)
            int_mask = q_raw.str.contains(r"^-?\d+$")
            inv_int = (~int_mask).arg_true().to_list()
            if inv_int:
                type_checks_failed += len(inv_int)
                for idx in inv_int[:20]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=q_col,
                            error_type="TYPE_ERROR",
                            actual_value=str(q_raw[idx]),
                            expected_rule="Expected integer",
                            severity="ERROR",
                        )
                    )

            range_checks_total += total_rows
            q_int = q_raw.cast(pl.Int64, strict=False)
            min_q = schema_spec.get("quantity", {}).get("min", 1)
            max_q = schema_spec.get("quantity", {}).get("max", 20)
            viol_q_min = (int_mask & (q_int < min_q)).arg_true().to_list()
            if viol_q_min:
                range_checks_failed += len(viol_q_min)
                for idx in viol_q_min[:20]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=q_col,
                            error_type="MIN_VALUE",
                            actual_value=str(q_raw[idx]),
                            expected_rule=f"Minimum value {min_q}",
                            severity="ERROR",
                        )
                    )
            viol_q_max = (int_mask & (q_int > max_q)).arg_true().to_list()
            if viol_q_max:
                range_checks_failed += len(viol_q_max)
                for idx in viol_q_max[:20]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=q_col,
                            error_type="MAX_VALUE",
                            actual_value=str(q_raw[idx]),
                            expected_rule=f"Maximum value {max_q}",
                            severity="ERROR",
                        )
                    )

        # C. Price check
        p_col = get_actual_col("unit_price")
        if p_col and p_col in cols:
            type_checks_total += total_rows
            p_raw = df[p_col].cast(pl.String)
            p_mask = p_raw.str.contains(r"^-?\d+(\.\d+)?$")
            inv_p = (~p_mask).arg_true().to_list()
            if inv_p:
                type_checks_failed += len(inv_p)
                for idx in inv_p[:20]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=p_col,
                            error_type="TYPE_ERROR",
                            actual_value=str(p_raw[idx]),
                            expected_rule="Expected numeric decimal",
                            severity="ERROR",
                        )
                    )

        # D. Cross-field calculation check
        tot_col = get_actual_col("total_amount")
        if (
            quality_rules.get("total_amount_equals_quantity_times_unit_price", False)
            and q_col and q_col in cols
            and p_col and p_col in cols
            and tot_col and tot_col in cols
        ):
            q_s = df[q_col].cast(pl.Float64, strict=False)
            p_s = df[p_col].cast(pl.Float64, strict=False)
            tot_s = df[tot_col].cast(pl.Float64, strict=False)
            valid_math = q_s.is_not_null() & p_s.is_not_null() & tot_s.is_not_null()
            calc_diff = (tot_s - (q_s * p_s)).abs()
            mismatch_indices = (valid_math & (calc_diff > 0.05)).arg_true().to_list()
            if mismatch_indices:
                cross_field_failed = len(mismatch_indices)
                for idx in mismatch_indices[:20]:
                    r_num = idx + 1
                    invalid_row_set.add(r_num)
                    expected_calc = round(q_s[idx] * p_s[idx], 2)
                    errors.append(
                        ValidationErrorItem(
                            row_number=r_num,
                            column_name=tot_col,
                            error_type="CALCULATION_MISMATCH",
                            actual_value=str(tot_s[idx]),
                            expected_rule=f"Expected {expected_calc} ({q_col} * {p_col})",
                            severity="ERROR",
                        )
                    )

    # Determine final validation status
    critical_errors = [e for e in errors if e.severity == "CRITICAL"]
    standard_errors = [e for e in errors if e.severity == "ERROR"]
    warnings = [e for e in errors if e.severity == "WARNING"]

    rows_invalid_count = len(invalid_row_set)
    rows_valid_count = max(0, total_rows - rows_invalid_count)

    if critical_errors:
        status = "INVALID"
    elif mappable_columns:
        status = "NEEDS_MAPPING"
    elif standard_errors:
        status = "INVALID"
    elif warnings:
        status = "VALID_WITH_WARNINGS"
    else:
        status = "VALID"

    summary = ValidationSummary(
        status=status,
        run_id=run_id,
        contract_version=contract_version,
        contract_name=dataset_name,
        contract_type=contract_type,
        rows_received=total_rows,
        rows_valid=rows_valid_count,
        rows_invalid=rows_invalid_count,
        validation_errors_count=len(errors),
        required_column_checks=CheckCategoryStats(passed=passed_req, failed=failed_req, total=total_req),
        type_checks=CheckCategoryStats(passed=max(0, type_checks_total - type_checks_failed), failed=type_checks_failed, total=type_checks_total),
        range_checks=CheckCategoryStats(passed=max(0, range_checks_total - range_checks_failed), failed=range_checks_failed, total=range_checks_total),
        enum_checks=CheckCategoryStats(passed=max(0, enum_checks_total - enum_checks_failed), failed=enum_checks_failed, total=enum_checks_total),
        pattern_checks=CheckCategoryStats(passed=max(0, pattern_checks_total - pattern_checks_failed), failed=pattern_checks_failed, total=pattern_checks_total),
        duplicate_checks=CheckCategoryStats(passed=max(0, dup_checks_total - dup_checks_failed), failed=dup_checks_failed, total=dup_checks_total),
        cross_field_checks=CheckCategoryStats(passed=max(0, cross_field_total - cross_field_failed), failed=cross_field_failed, total=cross_field_total),
        errors_preview=errors[:200],
        missing_columns=missing_columns,
        unexpected_columns=unexpected_columns,
        mappable_columns=mappable_columns,
        warnings_count=len(warnings),
    )

    if db is not None:
        save_validation_errors(db, run_id, errors)

    return summary


def save_validation_errors(db: Session, run_id: str, errors: List[ValidationErrorItem]):
    """Persists validation errors with IST timestamps."""
    db.query(ValidationErrorRecord).filter(ValidationErrorRecord.run_id == run_id).delete()
    db.commit()

    ist_now = _get_ist_now()
    records = [
        ValidationErrorRecord(
            run_id=run_id,
            row_number=err.row_number,
            column_name=err.column_name,
            error_type=err.error_type,
            actual_value=err.actual_value,
            expected_rule=err.expected_rule,
            severity=err.severity,
            created_at=ist_now,
        )
        for err in errors
    ]
    if records:
        db.bulk_save_objects(records)
        db.commit()
