"""
Cost-Aware Scheduling Engine (Phase 8)
======================================
Evaluates resource profiles (Economy, Standard, Performance) subject to budget
and deadline constraints. Compares the selected optimal schedule against a FIFO baseline.
"""

import json
import uuid
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.models import (
    BackfillPlanRecord,
    ScheduleRecord,
)
from app.schemas.schemas import ScheduleResponse


# Documented Resource Profiles & Cost Models
RESOURCE_PROFILES = {
    "Economy (0.5 vCPU, 1 GB RAM)": {
        "id": "economy_0.5vcpu",
        "duration_multiplier": 1.75,
        "rate_usd_per_sec": 0.000020,
        "description": "Cost-optimized execution suitable for low-priority batch backfills without strict deadlines."
    },
    "Standard (1.0 vCPU, 2 GB RAM)": {
        "id": "standard_1.0vcpu",
        "duration_multiplier": 1.00,
        "rate_usd_per_sec": 0.000040,
        "description": "Default balanced compute container matching production pipeline execution specifications."
    },
    "Performance (2.0 vCPU, 4 GB RAM)": {
        "id": "performance_2.0vcpu",
        "duration_multiplier": 0.55,
        "rate_usd_per_sec": 0.000085,
        "description": "High-throughput parallelized execution prioritizing fastest recovery and tight deadlines."
    }
}


def compute_cost_aware_schedule(
    plan_id: str,
    db: Session,
    objective: str = "minimize_cost",
    budget_limit_usd: Optional[float] = None,
    deadline_seconds: Optional[float] = None,
) -> ScheduleResponse:
    """
    Schedules an approved backfill plan according to optimization objective and constraints.
    """
    plan = db.query(BackfillPlanRecord).filter(BackfillPlanRecord.plan_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Backfill plan {plan_id} not found")

    base_runtime = float(plan.estimated_runtime_seconds)

    # Evaluate all candidate profiles
    candidates = {}
    for profile_name, spec in RESOURCE_PROFILES.items():
        dur = round(base_runtime * spec["duration_multiplier"], 2)
        cost = round(dur * spec["rate_usd_per_sec"], 6)

        feasible = True
        warnings = []
        if budget_limit_usd is not None and cost > budget_limit_usd:
            feasible = False
            warnings.append(f"Exceeds budget limit of ${budget_limit_usd:.4f}")
        if deadline_seconds is not None and dur > deadline_seconds:
            feasible = False
            warnings.append(f"Exceeds deadline of {deadline_seconds}s")

        candidates[profile_name] = {
            "runtime_seconds": dur,
            "cost_usd": cost,
            "feasible": feasible,
            "warnings": warnings,
            "spec": spec
        }

    # FIFO Baseline is always Standard profile without constraints
    fifo_baseline = {
        "profile": "Standard (1.0 vCPU, 2 GB RAM)",
        "runtime_seconds": candidates["Standard (1.0 vCPU, 2 GB RAM)"]["runtime_seconds"],
        "cost_usd": candidates["Standard (1.0 vCPU, 2 GB RAM)"]["cost_usd"],
    }

    # Select optimal candidate
    selected_profile = None
    if objective == "minimize_cost":
        # Sort by cost ascending among feasible candidates
        feasible_candidates = [k for k, v in candidates.items() if v["feasible"]]
        if feasible_candidates:
            selected_profile = min(feasible_candidates, key=lambda k: candidates[k]["cost_usd"])
        else:
            selected_profile = min(candidates.keys(), key=lambda k: candidates[k]["cost_usd"])
    elif objective in ("minimize_duration", "minimize_time"):
        feasible_candidates = [k for k, v in candidates.items() if v["feasible"]]
        if feasible_candidates:
            selected_profile = min(feasible_candidates, key=lambda k: candidates[k]["runtime_seconds"])
        else:
            selected_profile = min(candidates.keys(), key=lambda k: candidates[k]["runtime_seconds"])
    else:  # balanced
        selected_profile = "Standard (1.0 vCPU, 2 GB RAM)"

    chosen = candidates[selected_profile]
    cost_diff_pct = round(((fifo_baseline["cost_usd"] - chosen["cost_usd"]) / max(0.000001, fifo_baseline["cost_usd"])) * 100, 1)
    time_diff_pct = round(((fifo_baseline["runtime_seconds"] - chosen["runtime_seconds"]) / max(0.001, fifo_baseline["runtime_seconds"])) * 100, 1)

    baseline_comparison = {
        "baseline_scheduler": "FIFO Fixed-Resource (Standard)",
        "baseline_runtime_seconds": fifo_baseline["runtime_seconds"],
        "baseline_cost_usd": fifo_baseline["cost_usd"],
        "proposed_profile": selected_profile,
        "proposed_runtime_seconds": chosen["runtime_seconds"],
        "proposed_cost_usd": chosen["cost_usd"],
        "cost_reduction_percent": cost_diff_pct,
        "runtime_speedup_percent": time_diff_pct,
        "candidate_evaluations": {
            k: {"runtime": v["runtime_seconds"], "cost": v["cost_usd"], "feasible": v["feasible"]}
            for k, v in candidates.items()
        }
    }

    rationale = (
        f"Selected '{selected_profile}' under '{objective}' optimization. "
        f"Compared to FIFO baseline: {cost_diff_pct}% cost delta and {time_diff_pct}% runtime speedup. "
        f"{'Note: Constraints satisfied.' if chosen['feasible'] else 'Warning: Constraints partially violated; minimal violation chosen.'}"
    )

    schedule_id = f"SCHED-{uuid.uuid4().hex[:8].upper()}"

    sched_record = ScheduleRecord(
        schedule_id=schedule_id,
        plan_id=plan.plan_id,
        run_id=plan.run_id,
        resource_profile=selected_profile,
        estimated_runtime_seconds=chosen["runtime_seconds"],
        estimated_cost_usd=chosen["cost_usd"],
        budget_limit_usd=budget_limit_usd,
        deadline_seconds=deadline_seconds,
        optimization_objective=objective,
        baseline_comparison_json=json.dumps(baseline_comparison),
        selection_rationale=rationale,
        status="SCHEDULED",
        created_at=datetime.datetime.utcnow(),
    )

    db.add(sched_record)
    db.commit()
    db.refresh(sched_record)

    return ScheduleResponse(
        schedule_id=sched_record.schedule_id,
        plan_id=sched_record.plan_id,
        run_id=sched_record.run_id,
        resource_profile=sched_record.resource_profile,
        estimated_runtime_seconds=float(sched_record.estimated_runtime_seconds),
        estimated_cost_usd=float(sched_record.estimated_cost_usd),
        budget_limit_usd=float(sched_record.budget_limit_usd) if sched_record.budget_limit_usd is not None else None,
        deadline_seconds=float(sched_record.deadline_seconds) if sched_record.deadline_seconds is not None else None,
        optimization_objective=sched_record.optimization_objective,
        baseline_comparison=baseline_comparison,
        selection_rationale=sched_record.selection_rationale,
        status=sched_record.status,
        created_at=sched_record.created_at,
    )


def approve_schedule(schedule_id: str, db: Session) -> ScheduleResponse:
    """
    Approves a schedule to authorize recovery execution.
    """
    sched = db.query(ScheduleRecord).filter(ScheduleRecord.schedule_id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    sched.status = "APPROVED"
    db.commit()
    db.refresh(sched)

    comparison = json.loads(sched.baseline_comparison_json) if sched.baseline_comparison_json else {}

    return ScheduleResponse(
        schedule_id=sched.schedule_id,
        plan_id=sched.plan_id,
        run_id=sched.run_id,
        resource_profile=sched.resource_profile,
        estimated_runtime_seconds=float(sched.estimated_runtime_seconds),
        estimated_cost_usd=float(sched.estimated_cost_usd),
        budget_limit_usd=float(sched.budget_limit_usd) if sched.budget_limit_usd is not None else None,
        deadline_seconds=float(sched.deadline_seconds) if sched.deadline_seconds is not None else None,
        optimization_objective=sched.optimization_objective,
        baseline_comparison=comparison,
        selection_rationale=sched.selection_rationale,
        status=sched.status,
        created_at=sched.created_at,
    )
