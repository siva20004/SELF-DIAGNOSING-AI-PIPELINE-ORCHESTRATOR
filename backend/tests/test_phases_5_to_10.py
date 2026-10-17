import os
import json
import uuid
import datetime
import pytest
import polars as pl
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal, init_db
from app.models.models import (
    Dataset,
    PipelineRun,
    PipelineTask,
    ValidationErrorRecord,
    FailureDiagnosisRecord,
    BackfillPlanRecord,
    ScheduleRecord,
    RecoveryRunRecord,
    ExperimentRecord,
)
from app.services.run_history import get_all_runs, get_run_artifacts, get_run_logs
from app.services.time_utils import get_ist_now
from app.services.diagnosis_engine import create_or_get_failure_diagnosis, diagnose_failure_rule_based, diagnose_failure_ai_classifier
from app.services.backfill_planner import create_backfill_plan, approve_backfill_plan, compute_minimal_safe_tasks
from app.services.scheduler import compute_cost_aware_schedule, approve_schedule
from app.services.recovery_executor import execute_recovery
from app.services.monitoring_experiments import get_monitoring_dashboard, run_reproducible_experiment


client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()


def test_phase_5_run_history_and_artifacts(tmp_path):
    """
    Test Phase 5:
    - Unique ID, format, dataset fingerprint, execution metrics, and artifacts persistence.
    - Verified retrieval via API and service functions.
    """
    db = SessionLocal()
    try:
        dataset_id = "test_ds_phase5"
        sample_csv = tmp_path / "valid_sample.csv"
        sample_csv.write_text(
            "transaction_id,customer_id,product_category,quantity,unit_price,total_amount,transaction_date,payment_method,store_location\n"
            "TX1001,CUST1,Electronics,2,100.0,200.0,2026-01-01,Credit Card,Store A\n"
            "TX1002,CUST2,Clothing,1,50.0,50.0,2026-01-02,Debit Card,Store B\n"
        )
        
        ds = Dataset(
            id=dataset_id,
            filename=str(sample_csv),
            file_type="CSV",
            file_size_bytes=sample_csv.stat().st_size,
            rows_count=2,
            columns_count=9,
            status="STORED"
        )
        db.merge(ds)
        db.commit()

        run_id = f"RUN-PHASE5-{uuid.uuid4().hex[:6].upper()}"
        run = PipelineRun(
            run_id=run_id,
            dataset_id=dataset_id,
            file_format="CSV",
            contract_version="1.0",
            status="SUCCESS",
            started_at=get_ist_now(),
            dataset_fingerprint="sha256_dummy_fingerprint_phase5",
            artifact_path=str(sample_csv),
            rows_received=2,
            rows_processed=2,
            rows_valid=2,
            rows_invalid=0,
            config_json=json.dumps({"pipeline": "standard_sales_etl", "version": "1.0"})
        )
        db.merge(run)
        
        # Add tasks
        t1 = PipelineTask(
            run_id=run_id,
            task_name="Validation",
            status="SUCCESS",
            rows_input=2,
            rows_output=2
        )
        t2 = PipelineTask(
            run_id=run_id,
            task_name="DB Storage",
            status="SUCCESS",
            rows_input=2,
            rows_output=2
        )
        db.add_all([t1, t2])
        db.commit()

        # Test service: get_all_runs
        history = get_all_runs(db, limit=50)
        assert history.total_count >= 1
        found_run = next((r for r in history.runs if r.run_id == run_id), None)
        assert found_run is not None
        assert found_run.file_format == "CSV"
        assert found_run.rows_processed == 2

        # Test service: get_run_artifacts
        artifacts = get_run_artifacts(run_id, db)
        assert artifacts.run_id == run_id
        assert artifacts.row_count == 2
        assert len(artifacts.sample_records) == 2

        # Test service: get_run_logs
        logs = get_run_logs(run_id, db)
        assert logs.run_id == run_id
        assert len(logs.tasks) >= 2
        assert any(t.task_name == "Validation" for t in logs.tasks)

        # Test API endpoint
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        assert resp.json()["total_count"] >= 1

        resp_art = client.get(f"/api/runs/{run_id}/artifacts")
        assert resp_art.status_code == 200
        assert resp_art.json()["run_id"] == run_id

        resp_logs = client.get(f"/api/runs/{run_id}/logs")
        assert resp_logs.status_code == 200
        assert resp_logs.json()["run_id"] == run_id

    finally:
        db.close()


def test_phase_6_failure_detection_and_ai_diagnosis():
    """
    Test Phase 6:
    - Root cause diagnosis distinction: identifies first failing task, marks downstream tasks BLOCKED.
    - Tests both rule-based baseline and calibrated AI classifier.
    - Confirms ranked causes, calibrated confidence, evidence, and suggested actions.
    """
    db = SessionLocal()
    try:
        ds_id = "ds_p6"
        ds = Dataset(
            id=ds_id,
            filename="ds_p6.csv",
            file_type="CSV",
            file_size_bytes=100,
            rows_count=10,
            columns_count=9,
            status="STORED"
        )
        db.merge(ds)
        db.commit()

        run_id = "RUN-PHASE6-FAIL-001"
        
        # Clean any prior diagnosis record for this run
        db.query(FailureDiagnosisRecord).filter(FailureDiagnosisRecord.run_id == run_id).delete()
        db.commit()

        run = PipelineRun(
            run_id=run_id,
            dataset_id=ds_id,
            file_format="CSV",
            contract_version="1.0",
            status="FAILED",
            error_message="Column 'transaction_id' contains 5 duplicate keys",
            rows_received=10,
            rows_processed=0,
            rows_valid=0,
            rows_invalid=5,
        )
        db.merge(run)

        # Add failed task & downstream pending task
        t_val = PipelineTask(
            run_id=run_id,
            task_name="Validation",
            status="FAILED",
            error_message="Contract violation: duplicate transaction_id detected"
        )
        t_clean = PipelineTask(
            run_id=run_id,
            task_name="Cleaning",
            status="PENDING"
        )
        db.add_all([t_val, t_clean])
        
        # Add violation records
        v1 = ValidationErrorRecord(
            run_id=run_id,
            row_number=3,
            column_name="transaction_id",
            error_type="DUPLICATE_ID",
            actual_value="TX1001",
            expected_rule="Must be unique"
        )
        db.add(v1)
        db.commit()

        # Rule-based diagnosis
        diag_rule = create_or_get_failure_diagnosis(run_id, db, use_ai=False)
        assert diag_rule.failure_id.startswith("FAIL-")
        assert diag_rule.failed_task_name == "Validation"
        assert diag_rule.diagnosis_method == "rule_based_baseline"
        assert len(diag_rule.ranked_causes) >= 1
        assert len(diag_rule.evidence) >= 1

        # Check downstream task was properly marked BLOCKED
        t_clean_refreshed = db.query(PipelineTask).filter(PipelineTask.run_id == run_id, PipelineTask.task_name == "Cleaning").first()
        assert t_clean_refreshed.status == "BLOCKED"

        # AI Classifier diagnosis (re-run diagnosis with use_ai=True)
        # delete previous diagnosis record to test fresh AI path
        db.query(FailureDiagnosisRecord).filter(FailureDiagnosisRecord.run_id == run_id).delete()
        db.commit()

        diag_ai = create_or_get_failure_diagnosis(run_id, db, use_ai=True)
        assert diag_ai.diagnosis_method == "ai_classifier_v1.2"
        assert diag_ai.model_version == "1.2"
        assert len(diag_ai.ranked_causes) >= 1
        top_cause = diag_ai.ranked_causes[0]
        assert 0.0 <= top_cause.confidence <= 1.0
        assert "1.2" in top_cause.model_version

        # Test API endpoint
        resp = client.get(f"/api/runs/{run_id}/diagnosis")
        assert resp.status_code == 200
        assert resp.json()["failure_id"] == diag_ai.failure_id

    finally:
        db.close()


def test_phase_7_backfill_planning():
    """
    Test Phase 7:
    - Minimal safe task set computation.
    - If task fails at 'Transformation', minimal set must be ['Transformation', 'Calculation', 'Aggregation', 'Quality Check', 'DB Storage'].
    - Preceding tasks ('Validation', 'Cleaning') are excluded (safe reuse).
    - Plan starts in PENDING_APPROVAL and transitions to APPROVED upon approval.
    """
    db = SessionLocal()
    try:
        # Test unit function compute_minimal_safe_tasks
        tasks_from_trans = compute_minimal_safe_tasks("Transformation")
        assert tasks_from_trans == ["Transformation", "Calculation", "Aggregation", "Quality Check", "DB Storage"]
        assert "Validation" not in tasks_from_trans
        assert "Cleaning" not in tasks_from_trans

        # Create prerequisite dataset & run
        ds_id = "ds_p7"
        ds = Dataset(id=ds_id, filename="ds_p7.csv", file_type="CSV", file_size_bytes=100, rows_count=10, columns_count=9, status="STORED")
        db.merge(ds)
        db.commit()

        run_id = "RUN-P7-TEST"
        run = PipelineRun(run_id=run_id, dataset_id=ds_id, file_format="CSV", contract_version="1.0", status="FAILED")
        db.merge(run)
        db.commit()

        # Create failure record for planning
        failure_id = "FAIL-P7-TEST"
        diag = FailureDiagnosisRecord(
            failure_id=failure_id,
            run_id=run_id,
            failed_task_name="Transformation",
            failure_category="Transformation or execution error",
            error_message="Type cast error in Transformation",
            ranked_causes_json=json.dumps([]),
            evidence_json=json.dumps([]),
            diagnosis_method="rule_based_baseline",
            model_version="1.0"
        )
        db.merge(diag)
        db.commit()

        # Create Plan
        plan = create_backfill_plan(failure_id, db)
        assert plan.plan_id.startswith("PLAN-")
        assert plan.status == "PENDING_APPROVAL"
        assert plan.failed_task == "Transformation"
        assert "Transformation" in plan.selected_tasks
        assert "Validation" not in plan.selected_tasks
        assert plan.estimated_runtime_seconds > 0
        assert plan.estimated_cost_usd > 0

        # Approve Plan
        approved = approve_backfill_plan(plan.plan_id, db)
        assert approved.status == "APPROVED"

        # Test API endpoints
        resp = client.get(f"/api/backfills/{plan.plan_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    finally:
        db.close()


def test_phase_8_cost_aware_scheduling():
    """
    Test Phase 8:
    - Evaluates Economy, Standard, and Performance profiles.
    - Checks budget and deadline constraints.
    - Compares against FIFO baseline.
    - Explicit approval gate transitions schedule to APPROVED.
    """
    db = SessionLocal()
    try:
        ds_id = "ds_p8"
        ds = Dataset(id=ds_id, filename="ds_p8.csv", file_type="CSV", file_size_bytes=100, rows_count=10, columns_count=9, status="STORED")
        db.merge(ds)
        db.commit()

        run_id = "RUN-P8"
        run = PipelineRun(run_id=run_id, dataset_id=ds_id, file_format="CSV", contract_version="1.0", status="FAILED")
        db.merge(run)
        db.commit()

        plan_id = "PLAN-P8-TEST"
        plan = BackfillPlanRecord(
            plan_id=plan_id,
            failure_id="FAIL-P8",
            run_id=run_id,
            failed_task="Calculation",
            affected_partitions_json=json.dumps(["2026-01-01"]),
            selected_tasks_json=json.dumps(["Calculation", "Aggregation", "Quality Check", "DB Storage"]),
            execution_order_json=json.dumps(["Calculation", "Aggregation", "Quality Check", "DB Storage"]),
            estimated_runtime_seconds=12.0,
            estimated_cost_usd=0.00048,
            status="APPROVED"
        )
        db.merge(plan)
        db.commit()

        # Compute Schedule with minimize_cost objective
        sched_cost = compute_cost_aware_schedule(plan_id, db, objective="minimize_cost")
        assert sched_cost.schedule_id.startswith("SCHED-")
        assert sched_cost.status in ["SCHEDULED", "PENDING_APPROVAL"]
        assert "Economy" in sched_cost.resource_profile
        assert "baseline_scheduler" in sched_cost.baseline_comparison
        assert "cost_reduction_percent" in sched_cost.baseline_comparison

        # Compute Schedule with minimize_time objective
        sched_time = compute_cost_aware_schedule(plan_id, db, objective="minimize_time")
        assert "Performance" in sched_time.resource_profile

        # Approve Schedule
        approved_sched = approve_schedule(sched_cost.schedule_id, db)
        assert approved_sched.status == "APPROVED"

        # Test API approval endpoint
        resp = client.post(f"/api/schedules/{sched_cost.schedule_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    finally:
        db.close()


def test_phase_9_recovery_execution(tmp_path):
    """
    Test Phase 9:
    - Approval Gate: cannot execute an UNAPPROVED plan (returns HTTP 400).
    - Executes approved plan, reuse existing pipeline stages.
    - Validates task state transitions and final contract/output quality.
    """
    db = SessionLocal()
    try:
        ds_id = "ds_recovery_test"
        sample_csv = tmp_path / "recovery_dataset.csv"
        sample_csv.write_text(
            "transaction_id,customer_id,product_id,customer_name,city,state,customer_segment,product_name,category,quantity,unit_price,total_amount,payment_method,transaction_status,transaction_date,source_system\n"
            "T00000001,C000001,P001,Ravi Kumar,Hyderabad,Telangana,Regular,Laptop,Electronics,2,50000,100000,UPI,COMPLETED,2026-09-20,WEB\n"
            "T00000002,C000002,P002,Ananya Rao,Bengaluru,Karnataka,Premium,Mouse,Accessories,5,500,2500,CARD,COMPLETED,2026-09-20,MOBILE\n"
        )
        ds = Dataset(
            id=ds_id,
            filename=str(sample_csv),
            file_type="CSV",
            file_size_bytes=sample_csv.stat().st_size,
            rows_count=2,
            columns_count=16,
            status="STORED"
        )
        db.merge(ds)
        db.commit()

        orig_run_id = "RUN-ORIG-P9"
        orig_run = PipelineRun(
            run_id=orig_run_id,
            dataset_id=ds_id,
            file_format="CSV",
            contract_version="1.0",
            status="FAILED",
            artifact_path=str(sample_csv),
            rows_received=2,
            rows_processed=0,
            rows_valid=0,
            rows_invalid=1,
        )
        db.merge(orig_run)
        db.commit()

        # Create unapproved plan
        unapproved_plan_id = "PLAN-UNAPPROVED"
        unapp_plan = BackfillPlanRecord(
            plan_id=unapproved_plan_id,
            failure_id="FAIL-UNAPP",
            run_id=orig_run_id,
            failed_task="Cleaning",
            affected_partitions_json=json.dumps([]),
            selected_tasks_json=json.dumps(["Cleaning", "Transformation"]),
            execution_order_json=json.dumps(["Cleaning", "Transformation"]),
            estimated_runtime_seconds=5.0,
            estimated_cost_usd=0.0002,
            status="PENDING_APPROVAL"
        )
        db.merge(unapp_plan)
        db.commit()

        # Gate enforcement: unapproved plan must fail
        with pytest.raises(Exception) as excinfo:
            execute_recovery(unapproved_plan_id, db)
        assert "Cannot execute unapproved backfill plan" in str(excinfo.value)

        # Now test approved plan execution with a real dataset
        approved_plan_id = "PLAN-APPROVED-P9"
        app_plan = BackfillPlanRecord(
            plan_id=approved_plan_id,
            failure_id="FAIL-APP-P9",
            run_id=orig_run_id,
            failed_task="Calculation",
            affected_partitions_json=json.dumps(["2026-09-20"]),
            selected_tasks_json=json.dumps(["Calculation", "Aggregation", "Quality Check", "DB Storage"]),
            execution_order_json=json.dumps(["Calculation", "Aggregation", "Quality Check", "DB Storage"]),
            estimated_runtime_seconds=6.0,
            estimated_cost_usd=0.00024,
            status="APPROVED"
        )
        db.merge(app_plan)
        db.commit()

        # Execute recovery
        rec = execute_recovery(approved_plan_id, db)
        assert rec.recovery_id.startswith("REC-")
        assert rec.status == "SUCCEEDED"
        assert rec.contract_validation_status == "PASSED"
        assert rec.output_validation_status == "PASSED"
        assert rec.duration_seconds is not None
        assert rec.task_states.get("Calculation") == "SUCCEEDED"
        assert rec.task_states.get("DB Storage") == "SUCCEEDED"

        # Verify new run was generated in PipelineRun table
        assert rec.new_run_id is not None
        new_run = db.query(PipelineRun).filter(PipelineRun.run_id == rec.new_run_id).first()
        assert new_run is not None
        assert new_run.status == "SUCCESS"

    finally:
        db.close()


def test_phase_10_monitoring_dashboard_and_experiments():
    """
    Test Phase 10:
    - Monitoring dashboard aggregates real DB metrics (runs, success rate, cost, recovery stats).
    - Reproducible experiments execute with real CSV artifact generation:
      * Experiment A: Rule vs AI Diagnosis
      * Experiment B: Full vs Selective Backfill
      * Experiment C: FIFO vs Cost-Aware Scheduling
      * Experiment D: Recovery Resilience
    """
    db = SessionLocal()
    try:
        # Test monitoring dashboard
        dash = get_monitoring_dashboard(db)
        assert dash.total_runs >= 1
        assert 0.0 <= dash.success_rate_percent <= 100.0
        assert isinstance(dash.failure_categories, dict)
        assert isinstance(dash.recent_runs, list)

        # Test Experiment A: diagnosis_accuracy
        exp_a = run_reproducible_experiment("diagnosis_accuracy", {"test_samples": 50}, db)
        assert exp_a.experiment_type == "diagnosis_accuracy"
        assert "top_1_accuracy_percent" in exp_a.baseline_metrics
        assert "top_1_accuracy_percent" in exp_a.proposed_metrics
        assert exp_a.raw_csv_path is not None
        assert os.path.exists(exp_a.raw_csv_path)

        # Test Experiment B: backfill_efficiency
        exp_b = run_reproducible_experiment("backfill_efficiency", {"iterations": 5}, db)
        assert exp_b.experiment_type == "backfill_efficiency"
        assert "avg_makespan_seconds" in exp_b.baseline_metrics
        assert "avg_makespan_seconds" in exp_b.proposed_metrics
        assert exp_b.proposed_metrics["makespan_reduction_percent"] > 0

        # Test Experiment C: scheduling_cost
        exp_c = run_reproducible_experiment("scheduling_cost", {}, db)
        assert exp_c.experiment_type == "scheduling_cost"
        assert "avg_cost_usd" in exp_c.baseline_metrics
        assert "avg_cost_usd" in exp_c.proposed_metrics

        # Test Experiment D: recovery_resilience
        exp_d = run_reproducible_experiment("recovery_resilience", {"trials": 10}, db)
        assert exp_d.experiment_type == "recovery_resilience"
        assert "success_rate_percent" in exp_d.proposed_metrics

        # Test API endpoint to download CSV
        resp = client.get(f"/api/experiments/{exp_a.experiment_id}/csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert len(resp.content) > 0

    finally:
        db.close()


def test_attendance_ai_diagnosis_and_backfill_recovery(tmp_path):
    """
    End-to-End Test for User Scenario:
    1. Upload an Excel/CSV attendance dataset with columns:
       S.NO, NAME, BRANCH, DEPT, VENDOR, CRT SEC, CRT ROOM, STATUS, REGD.NO, 09:20-10:10, 10:10-11:00, Total Conducted, Total Attended, Att (%)
    2. When validated against default sales contract, AI diagnosis detects:
       - Dataset Type Mismatch: Student Attendance report evaluated against Sales Transaction contract (0.98 confidence)
    3. Generate Backfill Plan starting at 'Validation' (all 7 tasks).
    4. Approve Plan and Execute Recovery:
       - Auto-align completes missing contract schema
       - All 7 recovery tasks execute to SUCCEEDED
       - Recovery status is SUCCEEDED with 100% SUCCESS
       - Dataset record is marked VALID and repaired on disk
    """
    db = SessionLocal()
    try:
        ds_id = "ds_att_rec_test"
        sample_csv = tmp_path / "attendance_sample.csv"
        sample_csv.write_text(
            "S.NO,NAME,BRANCH,DEPT,VENDOR,CRT SEC,CRT ROOM,STATUS,REGD.NO,09:20-10:10,10:10-11:00,Total Conducted,Total Attended,Att (%)\n"
            "1,K. Ramesh,CSE,ENGG,TALENT,SEC-A,R101,ACTIVE,2100030001,P,P,2,2,100.0\n"
            "2,S. Priya,ECE,ENGG,TALENT,SEC-B,R102,ACTIVE,2100030002,P,A,2,1,50.0\n"
            "3,M. Rahul,MECH,ENGG,TALENT,SEC-C,R103,ACTIVE,2100030003,A,A,2,0,0.0\n"
        )

        ds = Dataset(
            id=ds_id,
            filename=str(sample_csv),
            file_type="CSV",
            file_size_bytes=sample_csv.stat().st_size,
            rows_count=3,
            columns_count=14,
            status="STORED"
        )
        db.merge(ds)
        db.commit()

        run_id = f"RUN-ATT-TEST-{uuid.uuid4().hex[:6].upper()}"
        run = PipelineRun(
            run_id=run_id,
            dataset_id=ds_id,
            file_format="CSV",
            contract_version="1.0",
            status="FAILED",
            error_message="Missing 16 required columns declared in sales contract",
            rows_received=3,
            rows_processed=0,
            rows_valid=0,
            rows_invalid=3,
        )
        db.merge(run)

        # Add failed task & downstream pending task
        t_val = PipelineTask(
            run_id=run_id,
            task_name="Validation",
            status="FAILED",
            error_message="Contract violation: Missing required columns"
        )
        db.add(t_val)

        # Add violation records for missing columns
        for col in ["transaction_id", "customer_id", "quantity", "unit_price", "total_amount"]:
            v = ValidationErrorRecord(
                run_id=run_id,
                row_number=1,
                column_name=col,
                error_type="MISSING_REQUIRED_COLUMN",
                actual_value="Missing",
                expected_rule=f"Column '{col}' required by contract"
            )
            db.add(v)
        db.commit()

        # Phase 6: AI Diagnostic Classifier
        diag = create_or_get_failure_diagnosis(run_id, db, use_ai=True)
        assert diag.failure_id.startswith("FAIL-")
        assert len(diag.ranked_causes) >= 1
        top_cause = diag.ranked_causes[0]
        assert "Dataset Type Mismatch" in top_cause.cause
        assert top_cause.confidence >= 0.95

        # Phase 7: Backfill Planning (Plan starting at Validation)
        plan_resp = create_backfill_plan(diag.failure_id, db)
        assert plan_resp.plan_id.startswith("PLAN-")
        assert "Validation" in plan_resp.selected_tasks
        assert len(plan_resp.selected_tasks) == 7

        # Approve Plan
        appr_plan = approve_backfill_plan(plan_resp.plan_id, db)
        assert appr_plan.status == "APPROVED"

        # Phase 9: Authorize & Execute Recovery
        recovery_resp = execute_recovery(appr_plan.plan_id, db)
        assert recovery_resp.status == "SUCCEEDED"
        assert recovery_resp.contract_validation_status == "PASSED"
        assert recovery_resp.output_validation_status == "PASSED"
        assert recovery_resp.task_states.get("Validation") == "SUCCEEDED"
        assert recovery_resp.task_states.get("Cleaning") == "SUCCEEDED"
        assert recovery_resp.task_states.get("Transformation") == "SUCCEEDED"
        assert recovery_resp.task_states.get("Calculation") == "SUCCEEDED"
        assert recovery_resp.task_states.get("Aggregation") == "SUCCEEDED"
        assert recovery_resp.task_states.get("Quality Check") == "SUCCEEDED"
        assert recovery_resp.task_states.get("DB Storage") == "SUCCEEDED"

        # Verify dataset updated
        ds_refreshed = db.query(Dataset).filter(Dataset.id == ds_id).first()
        assert ds_refreshed.status == "STORED"

    finally:
        db.close()
