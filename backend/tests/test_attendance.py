import os
import pytest
import polars as pl
from app.services.file_parsers import detect_header_row, parse_excel
from app.services.contract_loader import load_contract, detect_contract_for_columns
from app.services.validator import validate_dataset
from app.services.correction_engine import analyze_dataset_corrections, apply_dataset_corrections

def test_detect_header_row_with_title_banners():
    rows = [
        ["COLLEGE OF ENGINEERING & TECHNOLOGY", None, None],
        ["INFOSYS CAMPUS CONNECT TRAINING REPORT", None, None],
        ["S.NO", "NAME", "REGD.NO", "BRANCH", "09:20-10:10", "Total Conducted", "Total Attended"],
        ["1", "Alice", "Y23ACS001", "CSE", "P", "1", "1"],
        ["2", "Bob", "Y23ACS002", "ECE", "A", "1", "0"],
    ]
    detected_idx = detect_header_row(rows)
    assert detected_idx == 2

def test_detect_contract_for_attendance_columns():
    cols = ["S.NO", "NAME", "BRANCH", "DEPT", "VENDOR", "CRT SEC", "CRT ROOM", "STATUS", "REGD.NO", "09:20-10:10", "Total Conducted", "Total Attended", "Att (%)"]
    result = detect_contract_for_columns(cols)
    assert result["suggested_contract"] == "attendance"
    assert result["confidence"] > 0.5
    assert "NAME" in result["matched_columns"]
    assert "REGD.NO" in result["matched_columns"]

def test_attendance_contract_loading():
    contract = load_contract("attendance")
    assert contract["dataset"] == "student_attendance"
    assert contract["contract_type"] == "attendance"
    assert "session_markers" in contract["attendance_config"]
    assert "P" in contract["attendance_config"]["session_markers"]["present"]
    assert "A" in contract["attendance_config"]["session_markers"]["absent"]

def test_attendance_validation_and_recalculation(tmp_path):
    csv_file = tmp_path / "test_attendance.csv"
    csv_content = (
        "S.NO,NAME,REGD.NO,BRANCH,DEPT,VENDOR,CRT SEC,CRT ROOM,STATUS,09:20-10:10,10:20-11:10,Total Conducted,Total Attended,Att (%)\n"
        "1,Alice Kumar,230001,CSE,CSE,VendorA,A,101,ACTIVE,P,P,2,2,100.0\n"
        "2,Bob Singh,230002,ECE,ECE,VendorB,B,102,ACTIVE,P,A,2,1,50.0\n"
        "3,Charlie Rao,230003,MECH,MECH,VendorA,A,103,ACTIVE,A,A,2,0,0.0\n"
        "4,Zero Student,230004,CIVIL,CIVIL,VendorA,A,104,ACTIVE,NA,NA,0,0,0.0\n"
    )
    csv_file.write_text(csv_content)

    summary = validate_dataset(str(csv_file), "CSV", "TEST-ATT-RUN", contract_name="attendance")
    assert summary.rows_received == 4
    assert summary.rows_invalid == 0
    assert summary.status in ("VALID", "VALID_WITH_WARNINGS", "NEEDS_MAPPING")
    assert "registration_number" in summary.mappable_columns or "name" in summary.mappable_columns

def test_real_attendance_excel_file_if_present():
    real_path = r"c:\Users\dell\Downloads\Y23 INFOSYS SPECIFIC TRAINING ATT(07.10.2026).xlsx"
    if not os.path.exists(real_path):
        pytest.skip("Real test excel file not found in Downloads")

    df = parse_excel(real_path)
    assert len(df) == 2943
    assert "REGD.NO" in df.columns
    assert "NAME" in df.columns
    assert "Total Conducted" in df.columns
    assert "Total Attended" in df.columns
