import requests
import time

def run_e2e():
    t0 = time.time()
    print("Uploading sales_transactions_1M_valid.csv (129 MB)...")
    with open("sales_transactions_1M_valid.csv", "rb") as f:
        res = requests.post("http://localhost:8000/api/datasets/upload", files={"file": f})
    upload_elapsed = time.time() - t0
    print(f"Upload response: {res.status_code} in {upload_elapsed:.2f}s")
    data = res.json()
    print("Dataset info:", data)
    ds_id = data["dataset_id"]

    # Preview
    res = requests.get(f"http://localhost:8000/api/datasets/{ds_id}/preview")
    preview = res.json()
    print(f"Preview columns count: {len(preview['columns'])}, preview rows: {len(preview['preview_rows'])}")

    # Validate
    t1 = time.time()
    print("Validating 1,000,000 records...")
    res = requests.post(f"http://localhost:8000/api/datasets/{ds_id}/validate")
    val_elapsed = time.time() - t1
    val = res.json()
    print(f"Validation response: {res.status_code} in {val_elapsed:.2f}s")
    print("Validation status:", val["status"])
    print("Rows received:", val["rows_received"])
    print("Rows valid:", val["rows_valid"])
    print("Rows invalid:", val["rows_invalid"])
    print("Validation errors count:", val["validation_errors_count"])

    # Execute Pipeline
    t2 = time.time()
    print("Executing full pipeline for 1,000,000 records...")
    res = requests.post(f"http://localhost:8000/api/datasets/{ds_id}/execute")
    exec_elapsed = time.time() - t2
    print(f"Execute response: {res.status_code} in {exec_elapsed:.2f}s")
    exec_data = res.json()
    run_id = exec_data["run_id"]
    print("Pipeline Run ID:", run_id)
    print("Status:", exec_data["status"])
    print("Rows processed:", exec_data["rows_processed"])
    print("Tasks count:", len(exec_data["tasks"]))
    for t in exec_data["tasks"]:
        print(f"  - {t['task_name']}: {t['status']} (In: {t['rows_input']}, Out: {t['rows_output']})")

    # Fetch Results
    res = requests.get(f"http://localhost:8000/api/runs/{run_id}/results")
    results = res.json()
    print("KPI Metrics:", results["metrics"])
    print("Top 3 Cities by Sales:")
    for c in results["sales_by_city"][:3]:
        print(" ", c)
    print("Top 3 Categories by Sales:")
    for cat in results["sales_by_category"][:3]:
        print(" ", cat)

if __name__ == "__main__":
    run_e2e()
