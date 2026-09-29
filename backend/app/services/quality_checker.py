import polars as pl
from typing import Dict, Any, List


def run_quality_check(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Runs final quality checks on processed records:
    - transaction_id unique
    - quantity valid (1 <= quantity <= 20)
    - unit_price valid (>= 0)
    - total_amount valid (>= 0)
    - calculated_total matches total_amount
    - dates valid
    - required values present
    Computes validation score = Passed Checks / Total Checks * 100
    """
    total_records = len(df)
    if total_records == 0:
        return {"passed": True, "score": 100.0, "violations": []}

    violations: List[str] = []
    checks_passed = 0
    checks_total = 7  # 7 core dimensions checked across dataset

    # 1. Transaction ID Uniqueness
    dup_count = df.select(pl.col("transaction_id").is_duplicated().sum()).item()
    if dup_count == 0:
        checks_passed += 1
    else:
        violations.append(f"{dup_count} duplicate transaction_ids detected.")

    # 2. Quantity Range (1 <= q <= 20)
    invalid_q = df.filter((pl.col("quantity") < 1) | (pl.col("quantity") > 20)).height
    if invalid_q == 0:
        checks_passed += 1
    else:
        violations.append(f"{invalid_q} records have invalid quantity outside [1, 20].")

    # 3. Unit Price (>= 0)
    invalid_up = df.filter(pl.col("unit_price") < 0).height
    if invalid_up == 0:
        checks_passed += 1
    else:
        violations.append(f"{invalid_up} records have negative unit_price.")

    # 4. Total Amount (>= 0)
    invalid_tot = df.filter(pl.col("total_amount") < 0).height
    if invalid_tot == 0:
        checks_passed += 1
    else:
        violations.append(f"{invalid_tot} records have negative total_amount.")

    # 5. Calculation Match
    calc_mismatches = df.filter(
        (pl.col("total_amount") - pl.col("calculated_total")).abs() > 0.01
    ).height
    if calc_mismatches == 0:
        checks_passed += 1
    else:
        violations.append(f"{calc_mismatches} records have mismatch between total_amount and calculated_total.")

    # 6. Dates Valid
    invalid_dates = df.filter(
        ~pl.col("transaction_date").cast(pl.String).str.contains(r"^\d{4}-\d{2}-\d{2}$")
    ).height
    if invalid_dates == 0:
        checks_passed += 1
    else:
        violations.append(f"{invalid_dates} records have invalid date formats.")

    # 7. Required Values Present (nulls)
    has_nulls = False
    for col in ["transaction_id", "customer_id", "product_id", "quantity", "unit_price", "total_amount"]:
        if df.filter(pl.col(col).is_null()).height > 0:
            has_nulls = True
            violations.append(f"Column {col} contains null values.")
            break
    if not has_nulls:
        checks_passed += 1

    score = round((checks_passed / checks_total) * 100.0, 2)
    return {
        "passed": len(violations) == 0,
        "score": score,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "violations": violations,
    }
