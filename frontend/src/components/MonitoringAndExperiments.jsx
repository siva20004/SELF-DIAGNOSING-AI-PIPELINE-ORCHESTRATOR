import React, { useState, useEffect } from 'react';
import { BarChart3, Activity, Download, Play, CheckCircle2, TrendingUp, AlertCircle, RefreshCw, FlaskConical } from 'lucide-react';
import { getMonitoringDashboard, runExperiment, getExperimentCsvUrl } from '../services/api';

export default function MonitoringAndExperiments() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Experiment Execution
  const [runningExperiment, setRunningExperiment] = useState(false);
  const [experimentResult, setExperimentResult] = useState(null);
  const [activeExpType, setActiveExpType] = useState('diagnosis_accuracy');

  const fetchDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMonitoringDashboard();
      setDashboard(data);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load monitoring KPIs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const handleRunExperiment = async (expType) => {
    setActiveExpType(expType);
    setRunningExperiment(true);
    setError(null);
    try {
      const result = await runExperiment(expType, { trials: 15 });
      setExperimentResult(result);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Experiment run failed');
    } finally {
      setRunningExperiment(false);
    }
  };

  return (
    <div className="section-card">
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-title">
            <Activity size={18} style={{ marginRight: '8px', verticalAlign: 'middle', color: '#6366f1' }} />
            Operational Telemetry Monitoring & Reproducible Experiments (Phase 10)
          </div>
          <div className="section-subtitle">
            Real metrics calculated directly from database records, plus reproducible benchmark experiments with CSV exports.
          </div>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={fetchDashboard} disabled={loading}>
          <RefreshCw size={13} style={{ marginRight: '4px', animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh Metrics
        </button>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '15px' }}>
          {error}
        </div>
      )}

      {/* OPERATIONAL KPIS */}
      {dashboard && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px', marginBottom: '24px' }}>
          <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Total Pipeline Runs</div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b', marginTop: '4px' }}>
              {dashboard.total_runs}
            </div>
            <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
              {dashboard.success_count} Success • {dashboard.failure_count} Failed
            </div>
          </div>

          <div style={{ background: '#f0fdf4', padding: '14px', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
            <div style={{ fontSize: '11px', color: '#166534', textTransform: 'uppercase' }}>Success Rate</div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#15803d', marginTop: '4px' }}>
              {dashboard.success_rate_percent}%
            </div>
            <div style={{ fontSize: '12px', color: '#166534', marginTop: '2px' }}>
              Production SLA Target: &gt; 95%
            </div>
          </div>

          <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Total Rows Processed</div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b', marginTop: '4px' }}>
              {Number(dashboard?.total_rows_processed ?? 0).toLocaleString()}
            </div>
            <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
              Zero Fake Data
            </div>
          </div>

          <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Avg Run Duration</div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1e293b', marginTop: '4px' }}>
              {dashboard.avg_duration_seconds}s
            </div>
            <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
              Polars Vectorized
            </div>
          </div>

          <div style={{ background: '#eff6ff', padding: '14px', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
            <div style={{ fontSize: '11px', color: '#1e40af', textTransform: 'uppercase' }}>Recovery Succeeded</div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2563eb', marginTop: '4px' }}>
              {dashboard.recovery_success_count}
            </div>
            <div style={{ fontSize: '12px', color: '#1e40af', marginTop: '2px' }}>
              Automated Reruns
            </div>
          </div>
        </div>
      )}

      {/* REPRODUCIBLE BENCHMARK EXPERIMENTS SECTION */}
      <div style={{ borderTop: '2px solid #f1f5f9', paddingTop: '20px', marginTop: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FlaskConical size={18} color="#6366f1" />
              Empirical Benchmark Experiments (Phases 10.1 - 10.4)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#64748b' }}>
              Execute controlled evaluation scenarios and download generated raw trial CSV artifacts.
            </p>
          </div>
        </div>

        {/* Experiment trigger buttons */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', marginBottom: '20px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleRunExperiment('diagnosis_accuracy')}
            disabled={runningExperiment}
            style={{ textAlign: 'left', padding: '12px' }}
          >
            <div style={{ fontWeight: '600', fontSize: '13px' }}>Experiment A</div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>Rule vs AI Diagnosis Accuracy</div>
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleRunExperiment('backfill_efficiency')}
            disabled={runningExperiment}
            style={{ textAlign: 'left', padding: '12px' }}
          >
            <div style={{ fontWeight: '600', fontSize: '13px' }}>Experiment B</div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>Full vs Minimal Backfill Rerun</div>
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleRunExperiment('scheduling_cost')}
            disabled={runningExperiment}
            style={{ textAlign: 'left', padding: '12px' }}
          >
            <div style={{ fontWeight: '600', fontSize: '13px' }}>Experiment C</div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>FIFO vs Cost-Aware Optimizer</div>
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleRunExperiment('recovery_resilience')}
            disabled={runningExperiment}
            style={{ textAlign: 'left', padding: '12px' }}
          >
            <div style={{ fontWeight: '600', fontSize: '13px' }}>Experiment D</div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>Recovery Resilience & Retries</div>
          </button>
        </div>

        {/* EXPERIMENT RESULTS DISPLAY */}
        {runningExperiment ? (
          <div style={{ textAlign: 'center', padding: '30px', color: '#64748b', background: '#f8fafc', borderRadius: '8px' }}>
            Executing benchmark trials under controlled test conditions...
          </div>
        ) : experimentResult ? (
          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div>
                <strong style={{ fontSize: '15px' }}>{experimentResult.name}</strong>
                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                  Experiment ID: <code>{experimentResult.experiment_id}</code>
                </div>
              </div>

              <a
                href={getExperimentCsvUrl(experimentResult.experiment_id)}
                download
                target="_blank"
                rel="noreferrer"
                className="btn btn-primary btn-sm"
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Download size={13} />
                Download Raw CSV Results
              </a>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div style={{ background: '#ffffff', padding: '14px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase' }}>
                  Baseline Configuration
                </div>
                <pre style={{ fontSize: '12px', marginTop: '8px', background: '#f1f5f9', padding: '10px', borderRadius: '4px', overflowX: 'auto' }}>
                  {JSON.stringify(experimentResult.baseline_metrics, null, 2)}
                </pre>
              </div>

              <div style={{ background: '#f0fdf4', padding: '14px', borderRadius: '6px', border: '1px solid #bbf7d0' }}>
                <div style={{ fontSize: '11px', color: '#166534', fontWeight: 'bold', textTransform: 'uppercase' }}>
                  Proposed AI / Optimized Configuration
                </div>
                <pre style={{ fontSize: '12px', marginTop: '8px', background: '#ffffff', padding: '10px', borderRadius: '4px', overflowX: 'auto' }}>
                  {JSON.stringify(experimentResult.proposed_metrics, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
