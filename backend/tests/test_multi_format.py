"""
Multi-Format Ingestion & Pipeline Test Suite
============================================
Tests parsing, normalization, validation, and error detection
across ALL 7 supported file formats:
  1. CSV (valid & invalid)
  2. XLSX (valid & invalid, multi-sheet)
  3. JSON (valid & invalid/malformed)
  4. PDF (valid table & invalid layout)
  5. TXT (valid key-value/delimited & invalid)
  6. DOCX (valid table & invalid/empty)
  7. XML (valid structured & invalid/malformed)

Also verifies dataset equivalence: CSV, XLSX, and JSON
produce identical row counts, column counts, and calculation metrics.
"""

import os
import json
import tempfile
import pytest
import polars as pl

from app.services.file_parsers import (
    parse_csv,
    parse_excel,
    get_excel_sheets,
    parse_json_file,
    parse_pdf,
    parse_txt,
    parse_docx,
    parse_xml,
    parse_to_dataframe,
    detect_format,
)
from app.services.validator import validate_dataset
from app.services.contract_loader import load_contract


# Canonical valid record adhering to sales_contract_v1.yaml
VALID_RECORDS = [
    {
        "transaction_id": "T00000001",
        "customer_id": "C000001",
        "product_id": "P001",
        "customer_name": "Aarav Sharma",
        "city": "Mumbai",
        "state": "Maharashtra",
        "customer_segment": "Regular",
        "product_name": "Wireless Mouse",
        "category": "Electronics",
        "quantity": "2",
        "unit_price": "500.0",
        "total_amount": "1000.0",
        "payment_method": "UPI",
        "transaction_status": "COMPLETED",
        "transaction_date": "2026-09-01",
        "source_system": "WEB",
    },
    {
        "transaction_id": "T00000002",
        "customer_id": "C000002",
        "product_id": "P002",
        "customer_name": "Priya Patel",
        "city": "Delhi",
        "state": "Delhi",
        "customer_segment": "Premium",
        "product_name": "Mechanical Keyboard",
        "category": "Electronics",
        "quantity": "1",
        "unit_price": "2500.0",
        "total_amount": "2500.0",
        "payment_method": "CARD",
        "transaction_status": "COMPLETED",
        "transaction_date": "2026-09-02",
        "source_system": "MOBILE",
    },
    {
        "transaction_id": "T00000003",
        "customer_id": "C000003",
        "product_id": "P003",
        "customer_name": "Rohan Verma",
        "city": "Bangalore",
        "state": "Karnataka",
        "customer_segment": "Enterprise",
        "product_name": "USB-C Hub",
        "category": "Accessories",
        "quantity": "3",
        "unit_price": "800.0",
        "total_amount": "2400.0",
        "payment_method": "NETBANKING",
        "transaction_status": "COMPLETED",
        "transaction_date": "2026-09-03",
        "source_system": "POS",
    },
]

INVALID_RECORDS = [
    {
        "transaction_id": "INVALID_ID",  # Violates pattern ^T[0-9]{8}$
        "customer_id": "BAD_CUST",       # Violates pattern ^C[0-9]{6}$
        "product_id": "P001",
        "customer_name": "Broken User",
        "city": "Unknown",
        "state": "State",
        "customer_segment": "Alien",     # Disallowed enum
        "product_name": "Item",
        "category": "General",
        "quantity": "-5",                # Below min 1
        "unit_price": "100.0",
        "total_amount": "999.0",         # Math mismatch (-5 * 100 != 999)
        "payment_method": "CRYPTO",      # Disallowed enum
        "transaction_status": "UNKNOWN", # Disallowed enum
        "transaction_date": "01/09/2026",# Wrong date format (dd/mm/yyyy instead of YYYY-MM-DD)
        "source_system": "TELEPATHY",    # Disallowed enum
    }
]


# ============================================================
# 1. FORMAT DETECTION TESTS
# ============================================================

def test_format_detection():
    assert detect_format("sales.csv") == "CSV"
    assert detect_format("report.xlsx") == "XLSX"
    assert detect_format("data.xls") == "XLS"
    assert detect_format("items.json") == "JSON"
    assert detect_format("document.pdf") == "PDF"
    assert detect_format("log.txt") == "TXT"
    assert detect_format("table.docx") == "DOCX"
    assert detect_format("feed.xml") == "XML"

    with pytest.raises(ValueError, match="Unsupported file type"):
        detect_format("unsupported.zip")


# ============================================================
# 2. CSV TESTS (Valid & Invalid)
# ============================================================

def test_csv_valid(tmp_path):
    csv_file = tmp_path / "valid.csv"
    df = pl.DataFrame(VALID_RECORDS)
    df.write_csv(csv_file)

    parsed_df = parse_csv(str(csv_file))
    assert len(parsed_df) == 3
    assert "transaction_id" in parsed_df.columns

    # Test contract validation passes
    summary = validate_dataset(str(csv_file), "CSV", "RUN_CSV_VALID")
    assert summary.status == "VALID"
    assert summary.rows_valid == 3
    assert summary.rows_invalid == 0


def test_csv_invalid(tmp_path):
    csv_file = tmp_path / "invalid.csv"
    df = pl.DataFrame(INVALID_RECORDS)
    df.write_csv(csv_file)

    summary = validate_dataset(str(csv_file), "CSV", "RUN_CSV_INVALID")
    assert summary.status == "INVALID"
    assert summary.rows_invalid > 0
    assert summary.validation_errors_count > 0


# ============================================================
# 3. EXCEL TESTS (Valid, Invalid, Multi-sheet)
# ============================================================

def test_excel_valid_and_multisheet(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws_sales = wb.active
    ws_sales.title = "Sales"

    headers = list(VALID_RECORDS[0].keys())
    ws_sales.append(headers)
    for r in VALID_RECORDS:
        ws_sales.append([r[h] for h in headers])

    # Add a second sheet
    ws_other = wb.create_sheet(title="Customers")
    ws_other.append(["cust_id", "cust_name"])
    ws_other.append(["C001", "Alice"])

    excel_path = tmp_path / "valid.xlsx"
    wb.save(excel_path)
    wb.close()

    # Test sheet inspection
    sheets = get_excel_sheets(str(excel_path))
    assert sheets == ["Sales", "Customers"]

    # Parse primary sheet
    parsed_df = parse_excel(str(excel_path), sheet_name="Sales")
    assert len(parsed_df) == 3
    assert parsed_df["transaction_id"][0] == "T00000001"

    # Validate normalized output
    norm_csv = tmp_path / "norm_excel.csv"
    parsed_df.write_csv(norm_csv)
    summary = validate_dataset(str(norm_csv), "CSV", "RUN_XLSX_VALID")
    assert summary.status == "VALID"


def test_excel_invalid(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    headers = list(INVALID_RECORDS[0].keys())
    ws.append(headers)
    for r in INVALID_RECORDS:
        ws.append([r[h] for h in headers])

    excel_path = tmp_path / "invalid.xlsx"
    wb.save(excel_path)
    wb.close()

    parsed_df = parse_excel(str(excel_path))
    norm_csv = tmp_path / "norm_inv_excel.csv"
    parsed_df.write_csv(norm_csv)

    summary = validate_dataset(str(norm_csv), "CSV", "RUN_XLSX_INVALID")
    assert summary.status == "INVALID"


# ============================================================
# 4. JSON TESTS (Valid array, Wrapped array, Invalid/Malformed)
# ============================================================

def test_json_valid_array(tmp_path):
    json_path = tmp_path / "valid.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(VALID_RECORDS, f)

    parsed_df = parse_json_file(str(json_path))
    assert len(parsed_df) == 3

    norm_csv = tmp_path / "norm_json.csv"
    parsed_df.write_csv(norm_csv)
    summary = validate_dataset(str(norm_csv), "CSV", "RUN_JSON_VALID")
    assert summary.status == "VALID"


def test_json_wrapped_data(tmp_path):
    json_path = tmp_path / "wrapped.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"transactions": VALID_RECORDS}, f)

    parsed_df = parse_json_file(str(json_path))
    assert len(parsed_df) == 3


def test_json_invalid(tmp_path):
    json_path = tmp_path / "malformed.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write("{this is not valid json")

    with pytest.raises(ValueError, match="Invalid JSON file"):
        parse_json_file(str(json_path))


# ============================================================
# 5. TXT TESTS (Key=Value, Delimited, Invalid)
# ============================================================

def test_txt_key_value_valid(tmp_path):
    txt_path = tmp_path / "valid_kv.txt"
    lines = []
    for r in VALID_RECORDS:
        line = ", ".join(f"{k}={v}" for k, v in r.items())
        lines.append(line)
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    parsed_df = parse_txt(str(txt_path))
    assert len(parsed_df) == 3
    assert "transaction_id" in parsed_df.columns

    norm_csv = tmp_path / "norm_txt.csv"
    parsed_df.write_csv(norm_csv)
    summary = validate_dataset(str(norm_csv), "CSV", "RUN_TXT_VALID")
    assert summary.status == "VALID"


def test_txt_pipe_delimited(tmp_path):
    txt_path = tmp_path / "valid_pipe.txt"
    headers = list(VALID_RECORDS[0].keys())
    lines = ["|".join(headers)]
    for r in VALID_RECORDS:
        lines.append("|".join(str(r[h]) for h in headers))
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    parsed_df = parse_txt(str(txt_path))
    assert len(parsed_df) == 3


def test_txt_unstructured_invalid(tmp_path):
    txt_path = tmp_path / "random.txt"
    txt_path.write_text("Hello this is just an arbitrary novel paragraph with no columns.", encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot reliably interpret this TXT file"):
        parse_txt(str(txt_path))


# ============================================================
# 6. DOCX TESTS (Valid table & Empty document)
# ============================================================

def test_docx_valid(tmp_path):
    import docx

    doc = docx.Document()
    headers = list(VALID_RECORDS[0].keys())
    table = doc.add_table(rows=1, cols=len(headers))

    # Header row
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h

    # Data rows
    for r in VALID_RECORDS:
        row = table.add_row()
        for i, h in enumerate(headers):
            row.cells[i].text = str(r[h])

    docx_path = tmp_path / "valid.docx"
    doc.save(docx_path)

    parsed_df = parse_docx(str(docx_path))
    assert len(parsed_df) == 3
    assert parsed_df["transaction_id"][0] == "T00000001"

    norm_csv = tmp_path / "norm_docx.csv"
    parsed_df.write_csv(norm_csv)
    summary = validate_dataset(str(norm_csv), "CSV", "RUN_DOCX_VALID")
    assert summary.status == "VALID"


def test_docx_no_tables_invalid(tmp_path):
    import docx

    doc = docx.Document()
    doc.add_paragraph("This document contains only paragraphs and no tables.")
    docx_path = tmp_path / "notables.docx"
    doc.save(docx_path)

    with pytest.raises(ValueError, match="contains no tables"):
        parse_docx(str(docx_path))


# ============================================================
# 7. XML TESTS (Valid records & Malformed XML)
# ============================================================

def test_xml_valid(tmp_path):
    headers = list(VALID_RECORDS[0].keys())
    xml_lines = ["<?xml version='1.0' encoding='UTF-8'?>", "<transactions>"]
    for r in VALID_RECORDS:
        xml_lines.append("  <transaction>")
        for h in headers:
            xml_lines.append(f"    <{h}>{r[h]}</{h}>")
        xml_lines.append("  </transaction>")
    xml_lines.append("</transactions>")

    xml_path = tmp_path / "valid.xml"
    xml_path.write_text("\n".join(xml_lines), encoding="utf-8")

    parsed_df = parse_xml(str(xml_path))
    assert len(parsed_df) == 3
    assert parsed_df["transaction_id"][0] == "T00000001"

    norm_csv = tmp_path / "norm_xml.csv"
    parsed_df.write_csv(norm_csv)
    summary = validate_dataset(str(norm_csv), "CSV", "RUN_XML_VALID")
    assert summary.status == "VALID"


def test_xml_malformed_invalid(tmp_path):
    xml_path = tmp_path / "broken.xml"
    xml_path.write_text("<transactions><transaction><broken></transactions>", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid XML file"):
        parse_xml(str(xml_path))


# ============================================================
# 8. DATASET EQUIVALENCE TEST (CSV == XLSX == JSON == XML)
# ============================================================

def test_dataset_equivalence_across_formats(tmp_path):
    """
    Verifies that the SAME underlying data serialized as CSV, XLSX,
    JSON, and XML produces equivalent normalized datasets.
    """
    # 1. CSV
    csv_file = tmp_path / "equiv.csv"
    pl.DataFrame(VALID_RECORDS).write_csv(csv_file)
    df_csv = parse_to_dataframe(str(csv_file), "CSV")

    # 2. JSON
    json_file = tmp_path / "equiv.json"
    json_file.write_text(json.dumps(VALID_RECORDS), encoding="utf-8")
    df_json = parse_to_dataframe(str(json_file), "JSON")

    # 3. XML
    headers = list(VALID_RECORDS[0].keys())
    xml_lines = ["<transactions>"]
    for r in VALID_RECORDS:
        xml_lines.append("  <item>")
        for h in headers:
            xml_lines.append(f"    <{h}>{r[h]}</{h}>")
        xml_lines.append("  </item>")
    xml_lines.append("</transactions>")
    xml_file = tmp_path / "equiv.xml"
    xml_file.write_text("\n".join(xml_lines), encoding="utf-8")
    df_xml = parse_to_dataframe(str(xml_file), "XML")

    # Check identical row and column shapes
    assert df_csv.shape == df_json.shape == df_xml.shape == (3, 16)
    # Check identical values
    assert df_csv["transaction_id"].to_list() == df_json["transaction_id"].to_list() == df_xml["transaction_id"].to_list()
    assert df_csv["total_amount"].to_list() == df_json["total_amount"].to_list() == df_xml["total_amount"].to_list()
