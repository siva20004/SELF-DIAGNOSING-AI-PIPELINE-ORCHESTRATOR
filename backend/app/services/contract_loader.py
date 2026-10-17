import os
import re
from typing import Dict, Any, List, Optional
import yaml


CONTRACTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "contracts"
)

DEFAULT_CONTRACT_PATH = os.path.join(CONTRACTS_DIR, "sales_contract_v1.yaml")


def list_available_contracts() -> List[Dict[str, Any]]:
    """Lists all available YAML contract files with metadata."""
    contracts = []
    if not os.path.isdir(CONTRACTS_DIR):
        return contracts
    
    for fname in sorted(os.listdir(CONTRACTS_DIR)):
        if fname.endswith(".yaml") or fname.endswith(".yml"):
            path = os.path.join(CONTRACTS_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data:
                    name_key = fname.replace(".yaml", "").replace(".yml", "")
                    if "sales" in name_key:
                        short_id = "sales"
                        title = "Sales Transactions Contract"
                        desc = "Retail, e-commerce, and POS sales order records"
                    elif "attendance" in name_key:
                        short_id = "attendance"
                        title = "Student Attendance Report Contract"
                        desc = "Academic attendance records with session-wise markers (P/A)"
                    else:
                        short_id = "generic"
                        title = "Generic Tabular Dataset Contract"
                        desc = "Dynamic schema validation for arbitrary tabular datasets"
                    
                    contracts.append({
                        "id": short_id,
                        "filename": fname,
                        "title": title,
                        "description": desc,
                        "dataset": data.get("dataset", fname),
                        "contract_version": str(data.get("contract_version", "1.0")),
                        "contract_type": data.get("contract_type", short_id),
                        "schema_columns": list(data.get("schema", {}).keys()),
                        "has_attendance_config": "attendance_config" in data,
                    })
            except Exception:
                pass
    return contracts


def load_contract(contract_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads and parses a YAML data contract.
    Accepts: 'sales', 'attendance', 'generic', or a specific filename or path.
    Defaults to sales contract if omitted.
    """
    if not contract_name or contract_name.lower() in ("default", "sales"):
        contract_path = os.path.join(CONTRACTS_DIR, "sales_contract_v1.yaml")
    elif contract_name.lower() in ("attendance", "student_attendance"):
        contract_path = os.path.join(CONTRACTS_DIR, "attendance_contract.yaml")
    elif contract_name.lower() in ("generic", "custom"):
        contract_path = os.path.join(CONTRACTS_DIR, "generic_contract.yaml")
    else:
        # Check if contract_name is a direct file path or filename
        if os.path.isabs(contract_name) and os.path.exists(contract_name):
            contract_path = contract_name
        else:
            fname = contract_name if contract_name.endswith((".yaml", ".yml")) else f"{contract_name}.yaml"
            contract_path = os.path.join(CONTRACTS_DIR, fname)

    if not os.path.exists(contract_path):
        # Fallbacks
        alt_paths = [
            os.path.join(os.getcwd(), "backend", "app", "contracts", os.path.basename(contract_path)),
            os.path.join(os.getcwd(), os.path.basename(contract_path)),
            os.path.join(CONTRACTS_DIR, "sales_contract_v1.yaml"),
        ]
        for p in alt_paths:
            if os.path.exists(p):
                contract_path = p
                break

    if not os.path.exists(contract_path):
        raise FileNotFoundError(f"Contract file not found at {contract_path}")

    with open(contract_path, "r", encoding="utf-8") as f:
        contract_data = yaml.safe_load(f)

    if not contract_data:
        raise ValueError(f"Invalid contract in {contract_path}")

    # Set default contract_type if missing
    if "contract_type" not in contract_data:
        if "attendance" in contract_path:
            contract_data["contract_type"] = "attendance"
        elif "generic" in contract_path:
            contract_data["contract_type"] = "generic"
        else:
            contract_data["contract_type"] = "sales"

    return contract_data


def _norm(s: str) -> str:
    """Normalize string for fuzzy header matching."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower().strip())


def detect_contract_for_columns(columns: List[str]) -> Dict[str, Any]:
    """
    Inspects actual column names of an uploaded dataset and suggests the most
    suitable data contract (sales, attendance, or generic) with confidence and match evidence.
    """
    if not columns:
        return {
            "suggested_contract": "generic",
            "confidence": 0.0,
            "matched_columns": [],
            "unmatched_columns": [],
            "reason": "Dataset has no detectable columns.",
            "all_contracts": list_available_contracts(),
        }

    norm_cols = [_norm(c) for c in columns]
    col_set = set(norm_cols)

    # 1. Attendance Indicators
    attendance_keywords = {
        "sno", "regdno", "regno", "registrationnumber", "name", "studentname",
        "branch", "dept", "department", "vendor", "crtsec", "sec", "section",
        "crtroom", "room", "status", "hostel", "screeningtest", "grade"
    }
    attendance_summaries = {
        "totalconducted", "totalattended", "att", "attpct", "attendance", "attendancepercentage"
    }

    # Count time-range session patterns, e.g. "09:20-10:10"
    session_pattern = re.compile(r"^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$")
    session_cols = [c for c in columns if session_pattern.match(c.strip())]

    att_matches = [c for c in columns if _norm(c) in attendance_keywords]
    summary_matches = [c for c in columns if _norm(c) in attendance_summaries or "att" in _norm(c)]

    att_score = (len(att_matches) * 1.5) + (len(session_cols) * 3.0) + (len(summary_matches) * 2.0)
    att_confidence = min(round(att_score / max(len(columns), 1), 2), 1.0)

    # 2. Sales Indicators
    sales_keywords = {
        "transactionid", "customerid", "productid", "customername", "city",
        "state", "customersegment", "productname", "category", "quantity",
        "unitprice", "totalamount", "paymentmethod", "transactionstatus",
        "transactiondate", "sourcesystem"
    }
    sales_matches = [c for c in columns if _norm(c) in sales_keywords]
    sales_score = len(sales_matches) * 2.0
    sales_confidence = min(round(sales_score / max(len(columns), 1), 2), 1.0)

    # Decision
    if (len(session_cols) > 0 and len(att_matches) >= 2) or att_confidence > sales_confidence and att_confidence >= 0.25:
        matched = list(dict.fromkeys(att_matches + session_cols + summary_matches))
        unmatched = [c for c in columns if c not in matched]
        return {
            "suggested_contract": "attendance",
            "contract_title": "Student Attendance Report Contract",
            "confidence": att_confidence,
            "matched_columns": matched,
            "unmatched_columns": unmatched,
            "session_columns_detected": session_cols,
            "reason": f"Detected {len(session_cols)} attendance session columns and {len(att_matches)} student profile fields (e.g., {', '.join(att_matches[:4])}).",
            "all_contracts": list_available_contracts(),
        }
    elif sales_confidence >= 0.35:
        unmatched = [c for c in columns if c not in sales_matches]
        return {
            "suggested_contract": "sales",
            "contract_title": "Sales Transactions Contract",
            "confidence": sales_confidence,
            "matched_columns": sales_matches,
            "unmatched_columns": unmatched,
            "session_columns_detected": [],
            "reason": f"Detected {len(sales_matches)} sales transaction fields (e.g., {', '.join(sales_matches[:4])}).",
            "all_contracts": list_available_contracts(),
        }
    else:
        return {
            "suggested_contract": "generic",
            "contract_title": "Generic Tabular Dataset Contract",
            "confidence": 0.50,
            "matched_columns": [],
            "unmatched_columns": columns,
            "session_columns_detected": [],
            "reason": "Unfamiliar schema detected. Recommended generic tabular contract with custom rules.",
            "all_contracts": list_available_contracts(),
        }
