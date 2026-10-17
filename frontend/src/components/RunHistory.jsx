import React, { useState, useEffect } from 'react';
import { History, Eye, FileText, CheckCircle2, XCircle, Clock, Database, Download, RefreshCw, AlertTriangle } from 'lucide-react';
import { listRuns, getRunArtifacts, getRunLogs } from '../services/api';
import { formatIST } from '../utils/dateUtils';

export default function RunHistory({ onSelectRunForDiagnosis }) {
  const [runs, setRuns] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Selected modal details
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [artifacts, setArtifacts] = useState(null);
  const [logs, setLogs] = useState(null);
  const [activeModalTab, setActiveModalTab] = useState('artifacts'); // 'artifacts' or 'logs'
  const [modalLoading, setModalLoading] = useState(false);

  const fetchRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listRuns(50, 0);
      setRuns(data.runs || []);
      setTotalCount(data.total_count || 0);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load run history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const handleOpenRun = async (runId) => {
    setSelectedRunId(runId);
    setModalLoading(true);
    setArtifacts(null);
    setLogs(null);
    try {
      const [artData, logData] = await Promise.all([
        getRunArtifacts(runId).catch(() => null),
        getRunLogs(runId).catch(() => null),
      ]);
      setArtifacts(artData);
      setLogs(logData);
    } catch (err) {
      console.error(err);
    } finally {
      setModalLoading(false);
    }
  };

  const closeModal = () => {
    setSelectedRunId(null);
    setArtifacts(null);
    setLogs(null);
  };

  return (
    <div className="section-card">
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-title">
            <History size={18} style={{ marginRight: '8px', verticalAlign: 'middle', color: '#3b82f6' }} />
            Pipeline Run History & Persistent Artifacts (Phase 5)
          </div>
          <div className="section-subtitle">
            All executions persisted in PostgreSQL across restarts and refreshes. Inspect execution artifacts, dataset fingerprints, and task telemetry.
          </div>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={fetchRuns} disabled={loading}>
          <RefreshCw size={13} style={{ marginRight: '4px', animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '15px' }}>
          <AlertTriangle size={16} style={{ marginRight: '6px' }} />
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
          Loading historical pipeline runs from PostgreSQL...
        </div>
      ) : runs.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
          No runs recorded yet. Upload a dataset and execute the pipeline to record durable runs.
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                <th style={{ padding: '10px 12px' }}>Run ID</th>
                <th style={{ padding: '10px 12px' }}>Format</th>
                <th style={{ padding: '10px 12px' }}>Dataset / File</th>
                <th style={{ padding: '10px 12px' }}>Started At (IST)</th>
                <th style={{ padding: '10px 12px' }}>Duration</th>
                <th style={{ padding: '10px 12px' }}>Processed</th>
                <th style={{ padding: '10px 12px' }}>Status</th>
                <th style={{ padding: '10px 12px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const isSuccess = r.status === 'SUCCESS';
                const isFailed = r.status === 'FAILED';
                return (
                  <tr key={r.run_id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontWeight: 'bold' }}>
                      {r.run_id}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span className="badge badge-meta" style={{ fontSize: '11px' }}>
                        {r.file_format || 'CSV'}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.filename}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#64748b' }}>
                      {formatIST(r.started_at)}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {r.duration_seconds ? `${r.duration_seconds}s` : '-'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {r.rows_processed ? r.rows_processed.toLocaleString() : 0} rows
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span
                        className={`badge ${isSuccess ? 'badge-success' : isFailed ? 'badge-error' : 'badge-meta'}`}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      >
                        {isSuccess ? <CheckCircle2 size={12} /> : isFailed ? <XCircle size={12} /> : <Clock size={12} />}
                        {r.status}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ marginRight: '6px' }}
                        onClick={() => handleOpenRun(r.run_id)}
                      >
                        <Eye size={12} style={{ marginRight: '4px' }} />
                        Inspect
                      </button>
                      {isFailed && onSelectRunForDiagnosis && (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          style={{ background: '#dc2626', borderColor: '#b91c1c' }}
                          onClick={() => onSelectRunForDiagnosis(r.run_id)}
                        >
                          Diagnose
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* INSPECT RUN MODAL */}
      {selectedRunId && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(15, 23, 42, 0.65)', backdropFilter: 'blur(3px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-container" style={{
            background: '#ffffff', borderRadius: '12px', width: '90%', maxWidth: '850px',
            maxHeight: '85vh', display: 'flex', flexDirection: 'column', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.2)'
          }}>
            {/* Modal Header */}
            <div style={{ padding: '18px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Database size={18} color="#3b82f6" />
                  Run Inspection: <span style={{ fontFamily: 'monospace' }}>{selectedRunId}</span>
                </h3>
              </div>
              <button type="button" onClick={closeModal} className="btn btn-secondary btn-sm">✕ Close</button>
            </div>

            {/* Modal Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', background: '#f8fafc', padding: '0 24px' }}>
              <button
                type="button"
                onClick={() => setActiveModalTab('artifacts')}
                style={{
                  padding: '12px 18px', border: 'none', background: 'transparent',
                  borderBottom: activeModalTab === 'artifacts' ? '3px solid #3b82f6' : '3px solid transparent',
                  fontWeight: activeModalTab === 'artifacts' ? '600' : '400',
                  color: activeModalTab === 'artifacts' ? '#1e293b' : '#64748b', cursor: 'pointer'
                }}
              >
                Stored Artifacts & Fingerprint
              </button>
              <button
                type="button"
                onClick={() => setActiveModalTab('logs')}
                style={{
                  padding: '12px 18px', border: 'none', background: 'transparent',
                  borderBottom: activeModalTab === 'logs' ? '3px solid #3b82f6' : '3px solid transparent',
                  fontWeight: activeModalTab === 'logs' ? '600' : '400',
                  color: activeModalTab === 'logs' ? '#1e293b' : '#64748b', cursor: 'pointer'
                }}
              >
                Execution Telemetry & Task Logs
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
              {modalLoading ? (
                <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                  Loading execution metadata and telemetry...
                </div>
              ) : activeModalTab === 'artifacts' ? (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '15px', marginBottom: '20px' }}>
                    <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Dataset File</div>
                      <div style={{ fontWeight: '600', marginTop: '4px' }}>{artifacts?.filename || 'Unknown'}</div>
                    </div>
                    <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Format & Rows</div>
                      <div style={{ fontWeight: '600', marginTop: '4px' }}>
                        {artifacts?.file_format} • {artifacts?.row_count?.toLocaleString()} rows
                      </div>
                    </div>
                    <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Dataset Fingerprint (SHA-256)</div>
                      <div style={{ fontWeight: '600', marginTop: '4px', fontFamily: 'monospace', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {artifacts?.fingerprint || 'Not recorded'}
                      </div>
                    </div>
                  </div>

                  {artifacts?.artifact_path && (
                    <div style={{ marginBottom: '20px', padding: '10px 14px', background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '6px', fontSize: '12px' }}>
                      <strong>Durable Artifact Location:</strong> <code>{artifacts.artifact_path}</code>
                    </div>
                  )}

                  <h4 style={{ margin: '16px 0 8px 0', fontSize: '14px' }}>Output Sample Records (First 5 Rows):</h4>
                  {artifacts?.sample_records && artifacts.sample_records.length > 0 ? (
                    <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                      <table className="data-table" style={{ width: '100%', fontSize: '12px' }}>
                        <thead>
                          <tr style={{ background: '#f1f5f9' }}>
                            {Object.keys(artifacts.sample_records[0]).map((k) => (
                              <th key={k} style={{ padding: '8px' }}>{k}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {artifacts.sample_records.map((r, i) => (
                            <tr key={i}>
                              {Object.values(r).map((v, j) => (
                                <td key={j} style={{ padding: '8px' }}>{String(v)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ color: '#64748b', fontSize: '13px' }}>No sample records captured for this run.</div>
                  )}
                </div>
              ) : (
                <div>
                  <h4 style={{ margin: '0 0 12px 0', fontSize: '14px' }}>Task Execution DAG:</h4>
                  {logs?.tasks && logs.tasks.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
                      {logs.tasks.map((t, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            padding: '10px 14px', borderRadius: '6px', border: '1px solid #e2e8f0',
                            background: t.status === 'SUCCESS' ? '#f0fdf4' : t.status === 'FAILED' ? '#fef2f2' : t.status === 'BLOCKED' ? '#fffbeb' : '#f8fafc'
                          }}
                        >
                          <div>
                            <span style={{ fontWeight: '600' }}>{idx + 1}. {t.task_name}</span>
                            <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '10px' }}>
                              ({t.task_type || 'PIPELINE_STAGE'})
                            </span>
                            {t.error_message && (
                              <div style={{ color: '#dc2626', fontSize: '12px', marginTop: '4px' }}>
                                Error: {t.error_message}
                              </div>
                            )}
                          </div>
                          <span className={`badge ${t.status === 'SUCCESS' ? 'badge-success' : t.status === 'FAILED' ? 'badge-error' : 'badge-meta'}`}>
                            {t.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: '#64748b' }}>No tasks found for this run.</div>
                  )}

                  {logs?.raw_logs && logs.raw_logs.length > 0 && (
                    <div>
                      <h4 style={{ margin: '16px 0 8px 0', fontSize: '14px' }}>Raw Execution Telemetry:</h4>
                      <pre style={{
                        background: '#0f172a', color: '#f8fafc', padding: '14px', borderRadius: '8px',
                        fontSize: '11px', maxHeight: '200px', overflowY: 'auto', fontFamily: 'monospace'
                      }}>
                        {logs.raw_logs.join('\n')}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
