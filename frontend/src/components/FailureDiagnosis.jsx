import React, { useState, useEffect } from 'react';
import { AlertOctagon, Cpu, ArrowRight, ShieldAlert, CheckCircle, RefreshCw, Layers } from 'lucide-react';
import { diagnoseRun, getRunDiagnosis } from '../services/api';

export default function FailureDiagnosis({ runId, onProceedToBackfill }) {
  const [diagnosis, setDiagnosis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useAi, setUseAi] = useState(true);

  const fetchOrRunDiagnosis = async (aiMode = useAi) => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    try {
      // First attempt to get existing, otherwise execute diagnose
      let data;
      try {
        data = await getRunDiagnosis(runId);
      } catch {
        data = await diagnoseRun(runId, aiMode);
      }
      setDiagnosis(data);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Diagnosis failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (runId) {
      fetchOrRunDiagnosis(useAi);
    }
  }, [runId]);

  if (!runId) {
    return (
      <div className="section-card" style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
        <AlertOctagon size={36} color="#94a3b8" style={{ marginBottom: '12px' }} />
        <h3>No Failed Pipeline Run Selected</h3>
        <p style={{ fontSize: '13px' }}>Select a failed run from the "Run History" tab to trigger automated AI root cause diagnosis.</p>
      </div>
    );
  }

  return (
    <div className="section-card">
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-title">
            <AlertOctagon size={18} style={{ marginRight: '8px', verticalAlign: 'middle', color: '#ef4444' }} />
            Failure Detection & AI Root Cause Diagnosis (Phase 6)
          </div>
          <div className="section-subtitle">
            First failing task identification with downstream task blocking and calibrated AI classifier diagnosis.
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={useAi}
              onChange={(e) => {
                setUseAi(e.target.checked);
                fetchOrRunDiagnosis(e.target.checked);
              }}
            />
            Use Calibrated AI Classifier (v1.2)
          </label>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => fetchOrRunDiagnosis(useAi)}
            disabled={loading}
          >
            <RefreshCw size={12} style={{ marginRight: '4px', animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Re-Diagnose
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '15px' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
          Evaluating error telemetry and running calibrated diagnostic classifier...
        </div>
      ) : diagnosis ? (
        <div>
          {/* Top failure summary banner */}
          <div style={{
            background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px',
            padding: '16px 20px', marginBottom: '20px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span className="badge badge-error" style={{ marginBottom: '8px', display: 'inline-block' }}>
                  {diagnosis.failure_category}
                </span>
                <h3 style={{ margin: '4px 0', fontSize: '16px', color: '#991b1b' }}>
                  Root Cause Task: <strong>{diagnosis.failed_task_name || 'Validation Stage'}</strong>
                </h3>
                <div style={{ fontSize: '13px', color: '#b91c1c', marginTop: '4px' }}>
                  {diagnosis.error_message}
                </div>
              </div>
              <div style={{ textAlign: 'right', fontSize: '11px', color: '#64748b' }}>
                <div>Failure ID: <code>{diagnosis.failure_id}</code></div>
                <div>Method: <strong>{diagnosis.diagnosis_method}</strong></div>
                <div>Model Version: <strong>{diagnosis.model_version}</strong></div>
              </div>
            </div>
          </div>

          {/* Ranked Root Causes */}
          <h4 style={{ margin: '20px 0 10px 0', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Cpu size={16} color="#3b82f6" />
            Ranked Probable Root Causes (Calibrated Confidence):
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '25px' }}>
            {diagnosis.ranked_causes && diagnosis.ranked_causes.map((c, i) => (
              <div
                key={i}
                style={{
                  border: i === 0 ? '2px solid #3b82f6' : '1px solid #e2e8f0',
                  borderRadius: '8px', padding: '14px 18px', background: i === 0 ? '#eff6ff' : '#ffffff'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontWeight: '600', fontSize: '14px', color: i === 0 ? '#1e40af' : '#1e293b' }}>
                    #{i + 1} {c.cause}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ width: '100px', height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ width: `${Math.round(c.confidence * 100)}%`, height: '100%', background: i === 0 ? '#2563eb' : '#64748b' }} />
                    </div>
                    <span style={{ fontWeight: 'bold', fontSize: '13px', minWidth: '45px', textAlign: 'right' }}>
                      {Math.round(c.confidence * 100)}%
                    </span>
                  </div>
                </div>
                {c.evidence && c.evidence.length > 0 && (
                  <ul style={{ margin: '6px 0 0 0', paddingLeft: '20px', fontSize: '12px', color: '#475569' }}>
                    {c.evidence.map((ev, eIdx) => (
                      <li key={eIdx}>{ev}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>

          {/* Suggested Remediation & Next Step Action */}
          <div style={{
            background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px',
            padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
          }}>
            <div>
              <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', fontWeight: 'bold' }}>
                Automated Remediation Suggestion:
              </div>
              <div style={{ fontSize: '14px', fontWeight: '500', color: '#0f172a', marginTop: '4px' }}>
                {diagnosis.suggested_action || 'Proceed to selective backfill planning to rerun affected partitions.'}
              </div>
            </div>

            {onProceedToBackfill && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => onProceedToBackfill(diagnosis.failure_id)}
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                Plan Selective Backfill (Phase 7)
                <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
