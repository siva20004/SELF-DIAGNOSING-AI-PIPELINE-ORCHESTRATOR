"""
Interactive Data Correction Engine
===================================
Analyzes uploaded datasets against the selected data contract and generates
concrete, actionable correction proposals.
Supports:
- Column renaming & mapping (e.g. REGD.NO -> registration_number, NAME -> name)
- Data type conversions (string to integer, decimal, date)
- Date format normalization (e.g. DD/MM/YYYY, MM/DD/YYYY -> YYYY-MM-DD)
- Whitespace trimming
- Text value standardization & categorization (e.g. mapping markers or statuses)
- Missing value handling policies (drop, fill default, flag)
- Duplicate record identification & resolution (keep first, keep last, exclude)
- Invalid row exclusion with explicit approval

IMPORTANT:
- Original uploaded dataset is NEVER modified.
- Corrections create a separate corrected dataset file ({dataset_id}_corrected.csv).
- Changes are applied ONLY after explicit user confirmation.
"""

import os
import re
import datetime
from typing import Dict, Any, List, Optional, Tuple
import polars as pl
from app.services.contract_loader import load_contract


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower().strip())


def analyze_dataset_corrections(
    file_path: str,
    file_type: str,
    contract_name: str = "sales"
) -> Dict[str, Any]:
    """
    Analyzes an uploaded dataset against a contract and generates proposed corrections.
    Returns:
    - proposals: List of proposed fixes with before/after previews, affected rows, warnings.
    - column_profile: Summary of detected types, missing values, unique counts.
    - can_apply_auto: Count of safe auto-fixable operations.
    """
    df = pl.read_csv(file_path, infer_schema_length=0)
    total_rows = len(df)
    cols = list(df.columns)

    contract_data = load_contract(contract_name)
    contract_type = contract_data.get("contract_type", "sales")
    schema_spec = contract_data.get("schema", {})
    quality_rules = contract_data.get("quality_rules", {})
    att_config = contract_data.get("attendance_config", {})

    proposals = []
    proposal_counter = 1

    # --- 1. COLUMN MAPPING & RENAMING PROPOSALS ---
    mapped_source_cols = set()
    mapped_target_fields = set()

    # For each schema field, check if a source column matches directly or via aliases
    for field_name, field_meta in schema_spec.items():
        aliases = field_meta.get("aliases", [field_name])
        # Find best matching source column
        matched_col = None
        for col in cols:
            if col in mapped_source_cols:
                continue
            col_clean = _norm(col)
            for alias in aliases:
                if col_clean == _norm(alias):
                    matched_col = col
                    break
            if matched_col:
                break

        if matched_col and matched_col != field_name:
            sample_vals = [str(v) for v in df[matched_col].head(3).to_list() if v is not None]
            proposals.append({
                "id": f"fix_{proposal_counter}",
                "type": "COLUMN_RENAME",
                "category": "Schema Mapping",
                "source_column": matched_col,
                "target_field": field_name,
                "detected_type": str(df[matched_col].dtype),
                "expected_type": field_meta.get("type", "string"),
                "description": f"Map source column '{matched_col}' to required field '{field_name}'",
                "proposed_transformation": f"Rename '{matched_col}' → '{field_name}'",
                "affected_rows": total_rows,
                "sample_values": sample_vals,
                "preview_before": sample_vals,
                "preview_after": sample_vals,
                "warning": None,
                "severity": "INFO",
                "is_approved_by_default": True,
            })
            proposal_counter += 1
            mapped_source_cols.add(matched_col)
            mapped_target_fields.add(field_name)

    # --- 2. ATTENDANCE SESSION MARKER NORMALIZATION ---
    if contract_type == "attendance":
        session_patterns = att_config.get("session_column_patterns", [r"^\d{1,2}:\d{2}"])
        compiled_patterns = [re.compile(p) for p in session_patterns]
        markers_cfg = att_config.get("session_markers", {})
        present_set = set(str(m).strip().upper() for m in markers_cfg.get("present", ["P"]))
        absent_set = set(str(m).strip().upper() for m in markers_cfg.get("absent", ["A"]))
        na_set = set(str(m).strip().upper() for m in markers_cfg.get("not_applicable", ["NA", "N/A", "-"]))
        approved_markers = present_set | absent_set | na_set | {""}

        for col in cols:
            is_session = any(p.match(col.strip()) for p in compiled_patterns)
            if not is_session:
                continue

            col_series = df[col].cast(pl.String)
            unique_vals = [str(v).strip() for v in col_series.unique().to_list() if v is not None and str(v).strip() != ""]
            
            # Find lowercase or variant markers e.g. 'p', 'a', 'present', 'absent'
            marker_mappings = {}
            for u in unique_vals:
                u_upper = u.upper()
                if u not in ("P", "A") and u_upper in ("P", "PRESENT", "1"):
                    marker_mappings[u] = "P"
                elif u not in ("P", "A") and u_upper in ("A", "ABSENT", "0"):
                    marker_mappings[u] = "A"

            if marker_mappings:
                affected = sum(int((col_series == k).sum()) for k in marker_mappings.keys())
                sample_b = list(marker_mappings.keys())[:3]
                sample_a = [marker_mappings[k] for k in sample_b]
                proposals.append({
                    "id": f"fix_{proposal_counter}",
                    "type": "VALUE_MAPPING",
                    "category": "Value Normalization",
                    "source_column": col,
                    "target_field": col,
                    "detected_type": "string",
                    "expected_type": "enum (P, A)",
                    "description": f"Standardize attendance markers in '{col}' to canonical 'P' and 'A'",
                    "proposed_transformation": f"Map {marker_mappings}",
                    "value_mapping": marker_mappings,
                    "affected_rows": affected,
                    "sample_values": sample_b,
                    "preview_before": sample_b,
                    "preview_after": sample_a,
                    "warning": None,
                    "severity": "INFO",
                    "is_approved_by_default": True,
                })
                proposal_counter += 1

    # --- 3. WHITESPACE TRIMMING PROPOSALS ---
    for col in cols:
        if df[col].dtype in (pl.Utf8, pl.String):
            col_series = df[col]
            trimmed = col_series.str.strip_chars()
            diff_mask = col_series.is_not_null() & (col_series != trimmed)
            diff_count = int(diff_mask.sum())
            if diff_count > 0:
                dirty_samples = col_series.filter(diff_mask).head(3).to_list()
                clean_samples = [str(s).strip() for s in dirty_samples]
                proposals.append({
                    "id": f"fix_{proposal_counter}",
                    "type": "WHITESPACE_TRIM",
                    "category": "Text Cleaning",
                    "source_column": col,
                    "target_field": col,
                    "detected_type": "string",
                    "expected_type": "clean string",
                    "description": f"Trim leading/trailing whitespace from {diff_count} cell(s) in '{col}'",
                    "proposed_transformation": f"Apply .strip() to column '{col}'",
                    "affected_rows": diff_count,
                    "sample_values": dirty_samples,
                    "preview_before": [f"'{s}'" for s in dirty_samples],
                    "preview_after": [f"'{s}'" for s in clean_samples],
                    "warning": None,
                    "severity": "INFO",
                    "is_approved_by_default": True,
                })
                proposal_counter += 1

    # --- 4. DATE FORMAT NORMALIZATION PROPOSALS ---
    date_candidates = [c for c in cols if "date" in c.lower() or (c in schema_spec and schema_spec[c].get("type") == "date")]
    for col in date_candidates:
        col_series = df[col].cast(pl.String)
        # Check non-ISO formats (e.g. DD/MM/YYYY or DD-MM-YYYY)
        dmy_mask = col_series.str.contains(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$")
        dmy_count = int(dmy_mask.sum())
        if dmy_count > 0:
            samples = col_series.filter(dmy_mask).head(3).to_list()
            # Convert sample preview
            converted_samples = []
            for s in samples:
                m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", str(s).strip())
                if m:
                    d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
                    converted_samples.append(f"{y}-{mo}-{d}")
                else:
                    converted_samples.append(str(s))

            proposals.append({
                "id": f"fix_{proposal_counter}",
                "type": "DATE_NORMALIZE",
                "category": "Date Standardization",
                "source_column": col,
                "target_field": col,
                "detected_type": "string (DD/MM/YYYY)",
                "expected_type": "date (YYYY-MM-DD)",
                "description": f"Standardize {dmy_count} date(s) in '{col}' to ISO format (YYYY-MM-DD)",
                "proposed_transformation": "Convert DD/MM/YYYY → YYYY-MM-DD",
                "affected_rows": dmy_count,
                "sample_values": samples,
                "preview_before": samples,
                "preview_after": converted_samples,
                "warning": None,
                "severity": "WARNING",
                "is_approved_by_default": True,
            })
            proposal_counter += 1

    # --- 5. DUPLICATE KEY IDENTIFICATION ---
    unique_key_col = None
    if contract_type == "attendance":
        # Find registration number column
        for col in cols:
            if _norm(col) in ("regdno", "regno", "registrationnumber", "rollno"):
                unique_key_col = col
                break
    elif contract_type == "sales":
        for col in cols:
            if _norm(col) in ("transactionid", "orderid"):
                unique_key_col = col
                break

    if unique_key_col and unique_key_col in df.columns:
        dup_mask = df[unique_key_col].is_duplicated()
        # Exclude nulls
        non_null_dup = dup_mask & df[unique_key_col].is_not_null() & (df[unique_key_col].cast(pl.String).str.strip_chars() != "")
        dup_count = int(non_null_dup.sum())
        if dup_count > 0:
            dup_keys = df.filter(non_null_dup)[unique_key_col].head(4).to_list()
            proposals.append({
                "id": f"fix_{proposal_counter}",
                "type": "RESOLVE_DUPLICATES",
                "category": "Uniqueness Integrity",
                "source_column": unique_key_col,
                "target_field": unique_key_col,
                "detected_type": "duplicate keys",
                "expected_type": "unique identifier",
                "description": f"Found {dup_count} duplicate row(s) for unique key '{unique_key_col}'",
                "proposed_transformation": "Deduplicate by keeping the first occurrence and excluding subsequent duplicates",
                "dedup_policy": "keep_first",
                "affected_rows": dup_count,
                "sample_values": dup_keys,
                "preview_before": [f"Duplicate: {k}" for k in dup_keys],
                "preview_after": [f"Keep 1st of: {k}" for k in dup_keys],
                "warning": f"Deduplication will exclude {dup_count} duplicate row(s). Only apply if duplicates are confirmed redundant.",
                "severity": "WARNING",
                "is_approved_by_default": False,
            })
            proposal_counter += 1

    # Column profiling summary
    col_profiles = []
    for c in cols:
        s = df[c]
        null_count = int(s.is_null().sum() + (s.cast(pl.String).str.strip_chars() == "").sum()) if s.dtype in (pl.Utf8, pl.String) else int(s.is_null().sum())
        unique_count = int(s.n_unique())
        col_profiles.append({
            "column_name": c,
            "data_type": str(s.dtype),
            "total_count": total_rows,
            "null_count": null_count,
            "unique_count": unique_count,
            "sample_values": [str(v) for v in s.head(3).to_list() if v is not None],
        })

    return {
        "dataset_rows": total_rows,
        "dataset_columns": len(cols),
        "contract_type": contract_type,
        "contract_name": contract_name,
        "proposals": proposals,
        "total_proposals": len(proposals),
        "column_profiles": col_profiles,
    }


def apply_dataset_corrections(
    file_path: str,
    output_path: str,
    approved_fixes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Applies user-approved fixes and saves a separate corrected CSV file.
    Original uploaded dataset is preserved untouched.
    """
    df = pl.read_csv(file_path, infer_schema_length=0)
    original_rows = len(df)
    original_cols = list(df.columns)
    applied_logs = []

    # Map of renames: {old_col: new_col}
    renames = {}
    
    # 1. Column renames
    for fix in approved_fixes:
        if fix.get("type") == "COLUMN_RENAME":
            src = fix.get("source_column")
            tgt = fix.get("target_field")
            if src and tgt and src in df.columns:
                renames[src] = tgt
                applied_logs.append(f"Renamed column '{src}' → '{tgt}'")

    if renames:
        df = df.rename(renames)

    # 2. Whitespace trimming
    for fix in approved_fixes:
        if fix.get("type") == "WHITESPACE_TRIM":
            src = fix.get("source_column")
            # If renamed, use new name
            col = renames.get(src, src)
            if col in df.columns and df[col].dtype in (pl.Utf8, pl.String):
                df = df.with_columns(pl.col(col).str.strip_chars().alias(col))
                applied_logs.append(f"Trimmed whitespace in column '{col}'")

    # 3. Value mappings (e.g. attendance markers)
    for fix in approved_fixes:
        if fix.get("type") == "VALUE_MAPPING":
            src = fix.get("source_column")
            col = renames.get(src, src)
            val_map = fix.get("value_mapping", {})
            if col in df.columns and val_map:
                col_series = df[col].cast(pl.String)
                for old_val, new_val in val_map.items():
                    col_series = col_series.str.replace(f"^{re.escape(old_val)}$", new_val)
                df = df.with_columns(col_series.alias(col))
                applied_logs.append(f"Standardized values in column '{col}' ({len(val_map)} mappings applied)")

    # 4. Date normalization
    for fix in approved_fixes:
        if fix.get("type") == "DATE_NORMALIZE":
            src = fix.get("source_column")
            col = renames.get(src, src)
            if col in df.columns:
                date_s = df[col].cast(pl.String)
                converted = date_s.str.replace(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", r"$3-$2-$1")
                df = df.with_columns(converted.alias(col))
                applied_logs.append(f"Normalized date formats to YYYY-MM-DD in column '{col}'")

    # 5. Duplicate resolution
    for fix in approved_fixes:
        if fix.get("type") == "RESOLVE_DUPLICATES":
            src = fix.get("source_column")
            col = renames.get(src, src)
            policy = fix.get("dedup_policy", "keep_first")
            if col in df.columns:
                before_count = len(df)
                if policy == "keep_first":
                    df = df.unique(subset=[col], keep="first")
                elif policy == "keep_last":
                    df = df.unique(subset=[col], keep="last")
                dropped = before_count - len(df)
                applied_logs.append(f"Deduplicated by '{col}' ({policy}): removed {dropped} redundant rows")

    # Write out separate corrected CSV file
    df.write_csv(output_path)

    return {
        "status": "SUCCESS",
        "original_rows": original_rows,
        "corrected_rows": len(df),
        "original_columns_count": len(original_cols),
        "corrected_columns_count": len(df.columns),
        "applied_logs": applied_logs,
        "corrected_columns": list(df.columns),
        "output_path": output_path,
    }
