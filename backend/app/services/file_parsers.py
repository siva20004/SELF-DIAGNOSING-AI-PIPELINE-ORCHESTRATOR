"""
Multi-Format File Parser Module
================================
Converts uploaded files of any supported format into a normalized CSV file
that the existing pipeline (validator, pipeline_executor) can process unchanged.

Supported formats: CSV, XLSX/XLS, JSON, PDF, TXT, DOCX, XML

Architecture:
  Upload → detect_format() → parse_to_csv() → normalized CSV on disk
  → existing ingestion/validation/pipeline flows work unchanged
"""

import os
import re
import csv
import io
import json
import tempfile
from typing import Tuple, List, Dict, Any, Optional

import polars as pl


# ============================================================
# SUPPORTED FORMATS REGISTRY
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".csv": "CSV",
    ".xlsx": "XLSX",
    ".xls": "XLS",
    ".json": "JSON",
    ".pdf": "PDF",
    ".txt": "TXT",
    ".docx": "DOCX",
    ".xml": "XML",
    ".parquet": "PARQUET",
    ".pq": "PARQUET",
}

FORMAT_LABELS = [
    "CSV", "Excel (XLSX/XLS)", "JSON", "PDF", "TXT", "DOCX", "XML", "Parquet"
]

MAX_FILE_SIZE_MB = 200  # 200 MB limit


def records_to_dataframe(records: List[Dict[str, Any]]) -> pl.DataFrame:
    """
    Safely constructs a Polars DataFrame from a list of dicts with all columns
    explicitly typed as pl.String. This guarantees 100% compatibility with the
    downstream validation engine which expects raw string representation.
    """
    if not records:
        return pl.DataFrame()
    cols = []
    for r in records:
        for k in r.keys():
            if k not in cols:
                cols.append(k)
    data = {c: [str(r.get(c, "") if r.get(c) is not None else "") for r in records] for c in cols}
    return pl.DataFrame(data, schema={c: pl.String for c in cols})


def detect_format(filename: str) -> str:
    """Detect the file format from extension. Raises ValueError if unsupported."""
    ext = os.path.splitext(filename)[1].lower()
    fmt = SUPPORTED_EXTENSIONS.get(ext)
    if not fmt:
        supported = ", ".join(sorted(set(SUPPORTED_EXTENSIONS.values())))
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported formats: {supported}"
        )
    return fmt


def validate_file_safety(file_path: str, file_size: int, filename: str):
    """Security checks: file size, filename sanitization."""
    if file_size == 0:
        raise ValueError("Uploaded file is empty (0 bytes).")
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"File exceeds maximum size of {MAX_FILE_SIZE_MB} MB.")
    # Sanitize: reject path traversal
    base = os.path.basename(filename)
    if base != filename and ".." in filename:
        raise ValueError("Invalid filename detected (path traversal attempt).")


# ============================================================
# FORMAT PARSERS — each returns a Polars DataFrame
# ============================================================

def parse_csv(file_path: str) -> pl.DataFrame:
    """Parse CSV file. Already native to the existing pipeline."""
    return pl.read_csv(file_path, infer_schema_length=0)


def parse_excel(file_path: str, sheet_name: Optional[str] = None) -> pl.DataFrame:
    """Parse XLSX/XLS file using openpyxl via Polars."""
    try:
        import openpyxl
    except ImportError:
        raise ValueError("openpyxl is required for Excel support. Install with: pip install openpyxl")

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    except Exception as e:
        raise ValueError(f"Cannot open Excel file: {str(e)}")

    available_sheets = wb.sheetnames
    if not available_sheets:
        wb.close()
        raise ValueError("Excel workbook contains no sheets.")

    # Pick sheet
    if sheet_name:
        if sheet_name not in available_sheets:
            wb.close()
            raise ValueError(
                f"Sheet '{sheet_name}' not found. Available sheets: {', '.join(available_sheets)}"
            )
        ws = wb[sheet_name]
    else:
        ws = wb[available_sheets[0]]

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 2:
        raise ValueError("Excel sheet has no data rows (needs at least a header row and one data row).")

    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
    data_rows = []
    for row in rows[1:]:
        record = {}
        for i, val in enumerate(row):
            col = headers[i] if i < len(headers) else f"col_{i}"
            record[col] = str(val) if val is not None else ""
        data_rows.append(record)

    if not data_rows:
        raise ValueError("Excel sheet contains headers but no data rows.")

    return records_to_dataframe(data_rows)


def get_excel_sheets(file_path: str) -> List[str]:
    """Return list of sheet names in an Excel workbook."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True)
        sheets = wb.sheetnames
        wb.close()
        return sheets
    except Exception as e:
        raise ValueError(f"Cannot read Excel workbook: {str(e)}")


def parse_json_file(file_path: str) -> pl.DataFrame:
    """Parse JSON file — supports array of objects or {key: [...]} wrapper."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON file: {str(e)}")
    except UnicodeDecodeError:
        raise ValueError("JSON file has invalid encoding. Expected UTF-8.")

    records = None

    # Case 1: top-level array of objects
    if isinstance(data, list):
        records = data
    # Case 2: object with an array value
    elif isinstance(data, dict):
        # Find the first key whose value is a list of dicts
        for key, val in data.items():
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                records = val
                break
        if records is None:
            # Maybe it's a single record
            if all(not isinstance(v, (dict, list)) for v in data.values()):
                records = [data]
            else:
                raise ValueError(
                    "Cannot interpret JSON structure as tabular data. "
                    "Expected an array of objects or {\"key\": [{...}, ...]}."
                )
    else:
        raise ValueError("JSON root must be an array of objects or a containing object.")

    if not records:
        raise ValueError("JSON contains no records.")

    if not isinstance(records[0], dict):
        raise ValueError("JSON records must be objects (key-value pairs), not scalars.")

    # Convert all values to strings for consistency with CSV-based pipeline
    str_records = []
    for rec in records:
        str_records.append({k: str(v) if v is not None else "" for k, v in rec.items()})

    return records_to_dataframe(str_records)


def parse_pdf(file_path: str) -> pl.DataFrame:
    """Extract tabular data from PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ValueError("pdfplumber is required for PDF support. Install with: pip install pdfplumber")

    try:
        pdf = pdfplumber.open(file_path)
    except Exception as e:
        raise ValueError(f"Cannot open PDF file: {str(e)}")

    all_rows = []
    headers = None

    try:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row_idx, row in enumerate(table):
                        if row is None:
                            continue
                        cleaned = [str(cell).strip() if cell else "" for cell in row]
                        if headers is None:
                            headers = cleaned
                        else:
                            all_rows.append(cleaned)
            else:
                # Try extracting text and parsing as delimiter-separated
                text = page.extract_text()
                if text:
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    for line in lines:
                        # Try tab, pipe, or multi-space as delimiters
                        if "\t" in line:
                            parts = [p.strip() for p in line.split("\t")]
                        elif "|" in line:
                            parts = [p.strip() for p in line.split("|") if p.strip()]
                        else:
                            parts = re.split(r"\s{2,}", line)

                        if len(parts) >= 3:
                            if headers is None:
                                headers = parts
                            else:
                                all_rows.append(parts)
    finally:
        pdf.close()

    if headers is None or not all_rows:
        raise ValueError(
            "PDF extraction failed. No tabular data could be detected. "
            "Possible reasons: scanned image PDF, no table structure, or unsupported PDF layout."
        )

    # Normalize row lengths to match headers
    data_rows = []
    for row in all_rows:
        record = {}
        for i, col in enumerate(headers):
            record[col] = row[i] if i < len(row) else ""
        data_rows.append(record)

    if not data_rows:
        raise ValueError("PDF tables detected but no data rows found.")

    return records_to_dataframe(data_rows)


def parse_txt(file_path: str) -> pl.DataFrame:
    """Parse structured text files — auto-detect delimiter or key=value format."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                content = f.read()
        except Exception:
            raise ValueError("TXT file has invalid encoding. Expected UTF-8 or Latin-1.")

    lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
    if not lines:
        raise ValueError("TXT file is empty — no lines found.")

    # Strategy 1: key=value format (e.g. "transaction_id=T001, customer_id=C101")
    if "=" in lines[0] and "," in lines[0]:
        records = []
        for line_num, line in enumerate(lines):
            pairs = [p.strip() for p in line.split(",")]
            record = {}
            for pair in pairs:
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    record[key.strip()] = val.strip()
            if record:
                records.append(record)

        if records:
            return records_to_dataframe(records)

    # Strategy 2: CSV-like with auto-detected delimiter
    for delimiter in [",", "\t", "|", ";"]:
        first_line = lines[0]
        if delimiter in first_line:
            parts = [p.strip() for p in first_line.split(delimiter) if p.strip()]
            if len(parts) >= 3:
                try:
                    f_io = io.StringIO(content)
                    reader = csv.DictReader(f_io, delimiter=delimiter)
                    records = [row for row in reader]
                    if records and len(records) > 0:
                        str_records = [{k.strip() if k else "": str(v).strip() if v else "" for k, v in r.items()} for r in records]
                        return records_to_dataframe(str_records)
                except Exception:
                    continue

    raise ValueError(
        "Cannot reliably interpret this TXT file as structured data. "
        "Supported TXT formats: CSV-like (comma/tab/pipe/semicolon delimited) or key=value per line. "
        "Please convert to a supported structured format."
    )


def parse_docx(file_path: str) -> pl.DataFrame:
    """Extract table data from DOCX files."""
    try:
        from docx import Document
    except ImportError:
        raise ValueError("python-docx is required for DOCX support. Install with: pip install python-docx")

    try:
        doc = Document(file_path)
    except Exception as e:
        raise ValueError(f"Cannot open DOCX file: {str(e)}")

    if not doc.tables:
        raise ValueError(
            "DOCX file contains no tables. "
            "The system can only extract tabular data from DOCX files. "
            "Please ensure the document contains a data table."
        )

    # Use the first table with enough columns
    target_table = None
    for table in doc.tables:
        if len(table.rows) >= 2 and len(table.columns) >= 3:
            target_table = table
            break

    if target_table is None:
        target_table = doc.tables[0]

    rows = target_table.rows
    if len(rows) < 2:
        raise ValueError("DOCX table has no data rows (needs at least a header row and one data row).")

    headers = [cell.text.strip() for cell in rows[0].cells]
    data_rows = []
    for row in rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        record = {}
        for i, col in enumerate(headers):
            record[col] = cells[i] if i < len(cells) else ""
        data_rows.append(record)

    if not data_rows:
        raise ValueError("DOCX table contains headers but no data rows.")

    return records_to_dataframe(data_rows)


def parse_xml(file_path: str) -> pl.DataFrame:
    """Parse structured XML datasets with repeating record elements."""
    try:
        from lxml import etree
    except ImportError:
        raise ValueError("lxml is required for XML support. Install with: pip install lxml")

    try:
        tree = etree.parse(file_path)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid XML file: {str(e)}")
    except Exception as e:
        raise ValueError(f"Cannot open XML file: {str(e)}")

    root = tree.getroot()

    # Find repeating child elements (records)
    child_tags = {}
    for child in root:
        tag = etree.QName(child.tag).localname if "}" in child.tag else child.tag
        child_tags[tag] = child_tags.get(tag, 0) + 1

    if not child_tags:
        raise ValueError("XML file has no child elements under root.")

    # The record element is the most frequently repeating child
    record_tag = max(child_tags, key=child_tags.get)

    records = []
    for elem in root:
        tag = etree.QName(elem.tag).localname if "}" in elem.tag else elem.tag
        if tag != record_tag:
            continue
        record = {}
        for field in elem:
            field_tag = etree.QName(field.tag).localname if "}" in field.tag else field.tag
            record[field_tag] = (field.text or "").strip()
        if record:
            records.append(record)

    if not records:
        raise ValueError("XML file has no parseable record elements.")

    return records_to_dataframe(records)


# ============================================================
# UNIFIED PARSER ENTRY POINT
# ============================================================

def parse_to_dataframe(
    file_path: str,
    file_format: str,
    sheet_name: Optional[str] = None
) -> pl.DataFrame:
    """
    Master parser: converts any supported format into a Polars DataFrame.
    All values are kept as strings for consistency with the existing
    CSV-based validation pipeline (which uses infer_schema_length=0).
    """
    fmt = file_format.upper()

    if fmt == "CSV":
        return parse_csv(file_path)
    elif fmt in ("XLSX", "XLS"):
        return parse_excel(file_path, sheet_name=sheet_name)
    elif fmt == "JSON":
        return parse_json_file(file_path)
    elif fmt == "PARQUET":
        return pl.read_parquet(file_path)
    elif fmt == "PDF":
        return parse_pdf(file_path)
    elif fmt == "TXT":
        return parse_txt(file_path)
    elif fmt == "DOCX":
        return parse_docx(file_path)
    elif fmt == "XML":
        return parse_xml(file_path)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def normalize_to_csv(file_path: str, file_format: str, output_path: str,
                     sheet_name: Optional[str] = None) -> Tuple[int, int]:
    """
    Parse any supported format and write a normalized CSV file.
    Returns (row_count, column_count).
    """
    df = parse_to_dataframe(file_path, file_format, sheet_name=sheet_name)
    df.write_csv(output_path)
    return len(df), len(df.columns)
