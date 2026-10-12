import React, { useState, useEffect } from 'react';
import { Layers, ShieldCheck, CheckCircle2, DollarSign, Clock, ArrowRight, Play, Check } from 'lucide-react';
import { planBackfill, approveBackfill, scheduleBackfill, approveSchedule, startRecovery, getRecoveryStatus } from '../services/api';

export default function BackfillAndRecovery({ failureId, onCompleteRecovery }) {
  const [currentFailureId, setCurrentFailureId] = useState(failureId);
  const [plan, setPlan] = useState(null);
  const [schedule, setSchedule] = useState(null);
  const [recovery, setRecovery] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Scheduling options
  const [objective, setObjective] = useState('minimize_cost');

  useEffect(() => {
    if (failureId) {
      setCurrentFailureId(failureId);
      handleGeneratePlan(failureId);
    }
  }, [failureId]);

  const handleGeneratePlan = async (fId) => {
    if (!fId) return;
    setLoading(true);
    setError(null);
    try {
      const planData = await planBackfill(fId);
      setPlan(planData);
      setSchedule(null);
      setRecovery(null);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to create backfill plan');
    } finally {
      setLoading(false);
    }
  };

  const handleApprovePlan = async () => {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const approved = await approveBackfill(plan.plan_id);
      setPlan(approved);
      // Auto-compute optimal schedule
      const sched = await scheduleBackfill(approved.plan_id, objective);
      setSchedule(sched);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to approve backfill plan');
    } finally {
      setLoading(false);
    }
  };

  const handleRecomputeSchedule = async (newObj) => {
    setObjective(newObj);
    if (!plan || plan.status !== 'APPROVED') return;
    setLoading(true);
    try {
      const sched = await scheduleBackfill(plan.plan_id, newObj);
      setSchedule(sched);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveScheduleAndRecover = async () => {
    if (!schedule || !plan) return;
    setLoading(true);
    setError(null);
    try {
      await approveSchedule(schedule.schedule_id);
      const rec = await startRecovery(plan.plan_id, schedule.schedule_id);
      setRecovery(rec);
      if (onCompleteRecovery) onCompleteRecovery(rec);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to execute recovery');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="section-card">
      <div className="section-header">
        <div className="section-title">
          <Layers size={18} style={{ marginRight: '8px', verticalAlign: 'middle', color: '#10b981' }} />
          Backfill Planning, Cost Scheduling & Recovery (Phases 7, 8, 9)
        </div>
        <div className="section-subtitle">
          Minimal safe task computation with user approval gates, constraint optimization vs. FIFO baseline, and idempotent recovery execution.
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '15px' }}>
          {error}
        </div>
      )}

      {!plan && (
        <div style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
          <p>No active failure selected for planning.</p>
          <div style={{ display: 'inline-flex', gap: '8px', marginTop: '10px' }}>
            <input
              type="text"
              placeholder="Enter Failure ID (e.g. FAIL-XXXX)"
              value={currentFailureId || ''}
              onChange={(e) => setCurrentFailureId(e.target.value)}
              className="input-field"
              style={{ width: '220px' }}
            />
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => handleGeneratePlan(currentFailureId)}
              disabled={loading || !currentFailureId}
            >
              Generate Plan
            </button>
          </div>
        </div>
      )}

      {/* PHASE 7: BACKFILL PLAN */}
      {plan && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '18px', marginBottom: '20px', background: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <span className="badge badge-meta" style={{ marginRight: '8px' }}>Phase 7 Plan</span>
              <strong style={{ fontSize: '15px' }}>Minimal Safe Backfill Plan</strong>
              <code style={{ marginLeft: '10px', fontSize: '12px' }}>{plan.plan_id}</code>
            </div>
            <span className={`badge ${plan.status === 'APPROVED' ? 'badge-success' : 'badge-warning'}`}>
              Status: {plan.status}
            </span>
          </div>

          <div style={{ fontSize: '13px', color: '#475569', marginBottom: '14px', background: '#f8fafc', padding: '10px 14px', borderRadius: '6px' }}>
            {plan.rationale}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
            <div style={{ background: '#f1f5f9', padding: '10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>FAILED STAGE</div>
              <strong style={{ color: '#ef4444' }}>{plan.failed_task}</strong>
            </div>
            <div style={{ background: '#f1f5f9', padding: '10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>MINIMAL SAFE TASKS</div>
              <strong>{plan.selected_tasks?.length} Tasks</strong>
            </div>
            <div style={{ background: '#f1f5f9', padding: '10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>EST. RUNTIME</div>
              <strong>{plan.estimated_runtime_seconds}s</strong>
            </div>
            <div style={{ background: '#f1f5f9', padding: '10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>EST. COMPUTE COST</div>
              <strong>${plan.estimated_cost_usd?.toFixed(6)}</strong>
            </div>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#64748b', marginBottom: '6px' }}>Execution Sequence:</div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {plan.execution_order?.map((t, idx) => (
                <span key={idx} className="badge badge-meta" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span>{idx + 1}.</span> {t}
                </span>
              ))}
            </div>
          </div>

          {plan.status !== 'APPROVED' && (
            <div style={{ textAlign: 'right', borderTop: '1px solid #f1f5f9', paddingTop: '12px' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleApprovePlan}
                disabled={loading}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: '#059669', borderColor: '#047857' }}
              >
                <Check size={14} />
                Approve Backfill Plan (User Gate)
              </button>
            </div>
          )}
        </div>
      )}

      {/* PHASE 8: COST-AWARE SCHEDULING */}
      {plan?.status === 'APPROVED' && schedule && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '18px', marginBottom: '20px', background: '#f8fafc' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div>
              <span className="badge badge-meta" style={{ marginRight: '8px' }}>Phase 8 Scheduler</span>
              <strong style={{ fontSize: '15px' }}>Cost-Aware Optimizer vs. FIFO Baseline</strong>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <select
                value={objective}
                onChange={(e) => handleRecomputeSchedule(e.target.value)}
                className="input-field"
                style={{ fontSize: '12px', padding: '4px 8px' }}
              >
                <option value="minimize_cost">Objective: Minimize Cost</option>
                <option value="minimize_time">Objective: Minimize Time</option>
                <option value="balanced">Objective: Balanced</option>
              </select>
            </div>
          </div>

          {/* FIFO vs Optimizer comparison card */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '14px' }}>
            <div style={{ background: '#ffffff', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 'bold' }}>FIFO BASELINE (STANDARD 1.0 vCPU)</div>
              <div style={{ marginTop: '6px', fontSize: '14px' }}>
                Est. Runtime: <strong>{schedule.baseline_comparison?.baseline_runtime_seconds}s</strong>
              </div>
              <div style={{ fontSize: '14px' }}>
                Est. Cost: <strong>${schedule.baseline_comparison?.baseline_cost_usd?.toFixed(6)}</strong>
              </div>
            </div>

            <div style={{ background: '#ecfdf5', padding: '12px', borderRadius: '6px', border: '1px solid #a7f3d0' }}>
              <div style={{ fontSize: '11px', color: '#047857', fontWeight: 'bold' }}>SELECTED OPTIMAL PROFILE</div>
              <div style={{ marginTop: '4px', fontSize: '14px', fontWeight: 'bold', color: '#065f46' }}>
                {schedule.resource_profile}
              </div>
              <div style={{ fontSize: '13px', marginTop: '4px' }}>
                Est. Runtime: <strong>{schedule.estimated_runtime_seconds}s</strong> • Est. Cost: <strong>${schedule.estimated_cost_usd?.toFixed(6)}</strong>
              </div>
              {schedule.baseline_comparison?.cost_reduction_percent > 0 && (
                <div style={{ fontSize: '12px', color: '#059669', fontWeight: 'bold', marginTop: '4px' }}>
                  ✦ Cost Savings: {schedule.baseline_comparison.cost_reduction_percent}% vs. FIFO
                </div>
              )}
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleApproveScheduleAndRecover}
              disabled={loading}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <Play size={14} />
              Authorize & Execute Recovery (Phase 9)
            </button>
          </div>
        </div>
      )}

      {/* PHASE 9: RECOVERY PROGRESS & VALIDATION */}
      {recovery && (
        <div style={{ border: '2px solid #10b981', borderRadius: '8px', padding: '18px', background: '#f0fdf4' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={18} color="#059669" />
              <strong style={{ fontSize: '15px', color: '#065f46' }}>Recovery Run: {recovery.recovery_id}</strong>
            </div>
            <span className={`badge ${recovery.status === 'SUCCEEDED' ? 'badge-success' : 'badge-error'}`}>
              {recovery.status}
            </span>
          </div>

          <div style={{ fontSize: '13px', color: '#047857', marginBottom: '12px' }}>
            Recovery duration: <strong>{recovery.duration_seconds}s</strong> • New Run ID: <code>{recovery.new_run_id}</code>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px', marginBottom: '14px' }}>
            <div style={{ background: '#ffffff', padding: '10px', borderRadius: '6px', border: '1px solid #d1fae5' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>CONTRACT VALIDATION</div>
              <strong style={{ color: '#059669' }}>{recovery.contract_validation_status}</strong>
            </div>
            <div style={{ background: '#ffffff', padding: '10px', borderRadius: '6px', border: '1px solid #d1fae5' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>OUTPUT QUALITY AUDIT</div>
              <strong style={{ color: '#059669' }}>{recovery.output_validation_status}</strong>
            </div>
          </div>

          {recovery.logs_text && (
            <pre style={{ background: '#0f172a', color: '#f8fafc', padding: '12px', borderRadius: '6px', fontSize: '11px', maxHeight: '180px', overflowY: 'auto' }}>
              {recovery.logs_text}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
