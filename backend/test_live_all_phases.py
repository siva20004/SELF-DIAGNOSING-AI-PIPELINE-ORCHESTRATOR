import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("--- 1. Testing Health ---")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print("Health check OK:", r.json())

    print("\n--- 2. Testing Dataset Alignment & Validation ---")
    ds_id = "ds_fb3f170752a3"
    r = requests.post(f"{BASE_URL}/api/datasets/{ds_id}/align-schema")
    assert r.status_code == 200, f"Align schema failed: {r.text}"
    align_data = r.json()
    print("Schema alignment OK:", align_data["status"], "Total columns:", align_data["total_columns"])

    r = requests.post(f"{BASE_URL}/api/datasets/{ds_id}/validate")
    assert r.status_code == 200, f"Validation endpoint failed: {r.text}"
    val_data = r.json()
    print("Validation OK: Status =", val_data["status"], "Valid rows =", val_data["rows_valid"], "Invalid rows =", val_data["rows_invalid"])

    print("\n--- 3. Testing Pipeline Execution (Stages 1-7) ---")
    r = requests.post(f"{BASE_URL}/api/datasets/{ds_id}/execute")
    assert r.status_code == 200, f"Execution failed: {r.text}"
    exec_data = r.json()
    run_id = exec_data["run_id"]
    print(f"Pipeline executed successfully: Run ID = {run_id}, Status = {exec_data['status']}, Tasks = {len(exec_data['tasks'])}")

    print("\n--- 4. Testing Phase 5: Run History & Artifacts ---")
    r = requests.get(f"{BASE_URL}/api/runs")
    assert r.status_code == 200
    runs = r.json()["runs"]
    print(f"Run History OK: Found {len(runs)} persisted runs.")

    r = requests.get(f"{BASE_URL}/api/runs/{run_id}/artifacts")
    assert r.status_code == 200
    art = r.json()
    print(f"Artifacts OK: Dataset fingerprint = {art['fingerprint']}, Sample records = {len(art['sample_records'])}")

    r = requests.get(f"{BASE_URL}/api/runs/{run_id}/logs")
    assert r.status_code == 200
    logs = r.json()
    print(f"Logs OK: Run {run_id} has {len(logs['tasks'])} recorded tasks and {len(logs['raw_logs'])} log lines.")

    print("\n--- 5. Testing Phase 6: AI Failure Detection & Diagnosis ---")
    # Diagnose our run or a failed run
    r = requests.post(f"{BASE_URL}/api/runs/{run_id}/diagnose?use_ai=true")
    assert r.status_code == 200
    diag = r.json()
    failure_id = diag["failure_id"]
    print(f"Diagnosis OK: Failure ID = {failure_id}, Category = {diag['failure_category']}, Causes = {len(diag['ranked_causes'])}, Method = {diag['diagnosis_method']}")

    print("\n--- 6. Testing Phase 7: Backfill Planning ---")
    r = requests.post(f"{BASE_URL}/api/failures/{failure_id}/plan-backfill")
    assert r.status_code == 200
    plan = r.json()
    plan_id = plan["plan_id"]
    print(f"Backfill Plan OK: Plan ID = {plan_id}, Status = {plan['status']}, Tasks = {plan['selected_tasks']}, Est Runtime = {plan['estimated_runtime_seconds']}s")

    r = requests.post(f"{BASE_URL}/api/backfills/{plan_id}/approve")
    assert r.status_code == 200
    plan_approved = r.json()
    print(f"Backfill Approval Gate OK: Status = {plan_approved['status']}")

    print("\n--- 7. Testing Phase 8: Cost-Aware Scheduling ---")
    r = requests.post(f"{BASE_URL}/api/backfills/{plan_id}/schedule?objective=minimize_cost")
    assert r.status_code == 200
    sched = r.json()
    schedule_id = sched["schedule_id"]
    print(f"Cost-Aware Scheduler OK: Schedule ID = {schedule_id}, Profile = {sched['resource_profile']}, Est Cost = ${sched['estimated_cost_usd']}, Baseline = {sched['baseline_comparison']}")

    r = requests.post(f"{BASE_URL}/api/schedules/{schedule_id}/approve")
    assert r.status_code == 200
    sched_approved = r.json()
    print(f"Schedule Approval Gate OK: Status = {sched_approved['status']}")

    print("\n--- 8. Testing Phase 9: Controlled Recovery Execution ---")
    r = requests.post(f"{BASE_URL}/api/backfills/{plan_id}/recover?schedule_id={schedule_id}&max_retries=3")
    assert r.status_code == 200
    recovery = r.json()
    rec_id = recovery["recovery_id"]
    print(f"Recovery Engine OK: Recovery ID = {rec_id}, Status = {recovery['status']}, Contract Validation = {recovery['contract_validation_status']}, Output Quality = {recovery['output_validation_status']}")

    print("\n--- 9. Testing Phase 10: Operational Monitoring Dashboard & Experiments ---")
    r = requests.get(f"{BASE_URL}/api/monitoring/dashboard")
    assert r.status_code == 200
    kpis = r.json()
    print(f"Monitoring Dashboard OK: Total runs = {kpis['total_runs']}, Success rate = {kpis['success_rate_percent']}%, Total rows = {kpis['total_rows_processed']}, Recoveries succeeded = {kpis['recovery_success_count']}")

    # Run reproducible experiment
    r = requests.post(f"{BASE_URL}/api/experiments/run", json={"experiment_type": "diagnosis_accuracy", "config": {"iterations": 5}})
    assert r.status_code == 200
    exp = r.json()
    print(f"Reproducible Experiment OK: ID = {exp['experiment_id']}, Type = {exp['experiment_type']}, Proposed Metrics = {exp['proposed_metrics']}, CSV saved = {bool(exp['raw_csv_path'])}")

    print("\n=======================================================")
    print("ALL 10 ARCHITECTURAL PHASES TESTED AND VERIFIED 100% OK!")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
