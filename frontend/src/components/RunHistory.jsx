import React, { useState, useEffect } from 'react';
import { History, Eye, FileText, CheckCircle2, XCircle, Clock, Database, Download, RefreshCw, AlertTriangle, Cpu, GitBranch, ShieldCheck, ArrowRight, Activity, Sparkles } from 'lucide-react';
import { listRuns, getRunArtifacts, getRunLogs, getRunInspectionDetails, getDownloadProcessedUrl } from '../services/api';
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
  const [inspectionDetails, setInspectionDetails] = useState(null);
  const [activeModalTab, setActiveModalTab] = useState('artifacts'); // 'artifacts', 'logs', or 'diagnosis'
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
    setInspectionDetails(null);
    try {
      const [artData, logData, detailsData] = await Promise.all([
        getRunArtifacts(runId).catch(() => null),
        getRunLogs(runId).catch(() => null),
        getRunInspectionDetails(runId).catch(() => null),
      ]);
      setArtifacts(artData);
      setLogs(logData);
      setInspectionDetails(detailsData);
      if (detailsData?.has_diagnosis || detailsData?.has_recovery || detailsData?.is_recovery_run) {
        setActiveModalTab('diagnosis');
      } else {
        setActiveModalTab('artifacts');
      }
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
    setInspectionDetails(null);
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
            <div style={{ padding: '18px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Database size={18} color="#3b82f6" />
                  Run Inspection: <span style={{ fontFamily: 'monospace' }}>{selectedRunId}</span>
                </h3>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <a
                  href={getDownloadProcessedUrl(selectedRunId)}
                  className="btn btn-primary btn-sm"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: '#16a34a',
                    borderColor: '#15803d',
                    color: '#ffffff',
                    textDecoration: 'none',
                    fontWeight: 600,
                    fontSize: '12.5px',
                    padding: '6px 14px'
                  }}
                  target="_blank"
                  rel="noopener noreferrer"
                  download
                >
                  <Download size={14} />
                  Download Processed Dataset (.csv)
                </a>
                <button type="button" onClick={closeModal} className="btn btn-secondary btn-sm">✕ Close</button>
              </div>
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
                Stored Artifacts & Output
              </button>
              <button
                type="button"
                onClick={() => setActiveModalTab('diagnosis')}
                style={{
                  padding: '12px 18px', border: 'none', background: 'transparent',
                  borderBottom: activeModalTab === 'diagnosis' ? '3px solid #8b5cf6' : '3px solid transparent',
                  fontWeight: activeModalTab === 'diagnosis' ? '600' : '400',
                  color: activeModalTab === 'diagnosis' ? '#1e293b' : '#64748b', cursor: 'pointer',
                  display: 'inline-flex', alignItems: 'center', gap: '6px'
                }}
              >
                <Cpu size={14} color="#8b5cf6" />
                AI Diagnosis & Changes
                {(inspectionDetails?.has_diagnosis || inspectionDetails?.has_recovery || inspectionDetails?.is_recovery_run) && (
                  <span style={{ background: '#f3e8ff', color: '#7e22ce', fontSize: '10px', fontWeight: 700, padding: '2px 6px', borderRadius: '10px' }}>
                    AI REPAIRED
                  </span>
                )}
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
              ) : activeModalTab === 'diagnosis' ? (
                <div>
                  {/* AI Overview Banner */}
                  <div style={{
                    padding: '14px 18px',
                    borderRadius: '8px',
                    background: inspectionDetails?.is_recovery_run ? '#f5f3ff' : '#f0fdf4',
                    border: inspectionDetails?.is_recovery_run ? '1px solid #ddd6fe' : '1px solid #bbf7d0',
                    marginBottom: '20px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '12px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {inspectionDetails?.is_recovery_run ? <Sparkles size={20} color="#7c3aed" /> : <ShieldCheck size={20} color="#16a34a" />}
                      <div>
                        <strong style={{ fontSize: '13.5px', color: inspectionDetails?.is_recovery_run ? '#5b21b6' : '#166534' }}>
                          {inspectionDetails?.is_recovery_run 
                            ? 'AI Recovery Execution: Self-Healed & Validated' 
                            : 'Standard Pipeline Execution: 100% Contract Compliant'}
                        </strong>
                        <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#64748b' }}>
                          {inspectionDetails?.is_recovery_run 
                            ? 'This run was recovered using AI Diagnosis, minimal safe DAG backfill planning, and automatic data repair.'
                            : 'This execution passed all contract rules and quality assertions without failure.'}
                        </p>
                      </div>
                    </div>
                    <a
                      href={getDownloadProcessedUrl(selectedRunId)}
                      className="btn btn-secondary btn-sm"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                      target="_blank"
                      rel="noopener noreferrer"
                      download
                    >
                      <Download size={13} />
                      Download Processed Dataset
                    </a>
                  </div>

                  {/* Diagnosis Details (if available) */}
                  {inspectionDetails?.diagnosis ? (
                    <div style={{ marginBottom: '20px', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' }}>
                      <div style={{ background: '#f8fafc', padding: '12px 16px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Cpu size={15} color="#8b5cf6" />
                          Phase 6: AI Root Cause Diagnosis
                        </span>
                        <span className="badge badge-neutral" style={{ fontSize: '11px' }}>
                          {inspectionDetails.diagnosis.diagnosis_method || 'AI Calibrated Classifier'} (v{inspectionDetails.diagnosis.model_version || '1.0'})
                        </span>
                      </div>
                      <div style={{ padding: '16px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '14px' }}>
                          <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '10px 14px', borderRadius: '6px' }}>
                            <div style={{ fontSize: '11px', color: '#991b1b', textTransform: 'uppercase', fontWeight: 600 }}>Failure Category</div>
                            <div style={{ fontWeight: 700, color: '#dc2626', marginTop: '4px', fontSize: '13px' }}>
                              {inspectionDetails.diagnosis.failure_category}
                            </div>
                          </div>
                          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', padding: '10px 14px', borderRadius: '6px' }}>
                            <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Failed Task</div>
                            <div style={{ fontWeight: 600, marginTop: '4px', fontSize: '13px' }}>
                              {inspectionDetails.diagnosis.failed_task_name || 'VALIDATION'}
                            </div>
                          </div>
                        </div>

                        {inspectionDetails.diagnosis.error_message && (
                          <div style={{ marginBottom: '14px', fontSize: '12.5px', color: '#334155' }}>
                            <strong>Root Cause Analysis:</strong>
                            <div style={{ background: '#f8fafc', padding: '10px 12px', borderRadius: '6px', marginTop: '4px', border: '1px solid #e2e8f0', fontFamily: 'monospace', fontSize: '11.5px' }}>
                              {inspectionDetails.diagnosis.error_message}
                            </div>
                          </div>
                        )}

                        {inspectionDetails.diagnosis.suggested_action && (
                          <div style={{ marginBottom: '14px', fontSize: '12.5px', color: '#166534', background: '#f0fdf4', padding: '10px 12px', borderRadius: '6px', border: '1px solid #bbf7d0' }}>
                            <strong>AI Recommended Action:</strong> {inspectionDetails.diagnosis.suggested_action}
                          </div>
                        )}

                        {inspectionDetails.diagnosis.ranked_causes?.length > 0 && (
                          <div>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '8px' }}>
                              Ranked Hypotheses & Confidence Scores:
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                              {inspectionDetails.diagnosis.ranked_causes.map((rc, idx) => (
                                <div key={idx} style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: '12px', fontWeight: 500 }}>{rc.cause}</span>
                                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#2563eb', background: '#dbeafe', padding: '2px 8px', borderRadius: '10px' }}>
                                    {Math.round((rc.confidence || 0) * 100)}% Confidence
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}

                  {/* Recovery Changes Details (if available) */}
                  {inspectionDetails?.recovery ? (
                    <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden', marginBottom: '20px' }}>
                      <div style={{ background: '#f8fafc', padding: '12px 16px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <GitBranch size={15} color="#059669" />
                          Phases 7–9: Backfill Execution & What Changed
                        </span>
                        <span className="badge badge-success" style={{ fontSize: '11px' }}>
                          {inspectionDetails.recovery.status}
                        </span>
                      </div>
                      <div style={{ padding: '16px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '14px' }}>
                          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '10px 14px', borderRadius: '6px' }}>
                            <div style={{ fontSize: '11px', color: '#166534', textTransform: 'uppercase', fontWeight: 600 }}>Contract Validation</div>
                            <div style={{ fontWeight: 700, color: '#16a34a', marginTop: '4px', fontSize: '13px' }}>
                              ✓ {inspectionDetails.recovery.contract_validation_status}
                            </div>
                          </div>
                          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '10px 14px', borderRadius: '6px' }}>
                            <div style={{ fontSize: '11px', color: '#166534', textTransform: 'uppercase', fontWeight: 600 }}>Output Integrity</div>
                            <div style={{ fontWeight: 700, color: '#16a34a', marginTop: '4px', fontSize: '13px' }}>
                              ✓ {inspectionDetails.recovery.output_validation_status}
                            </div>
                          </div>
                          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', padding: '10px 14px', borderRadius: '6px' }}>
                            <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Duration</div>
                            <div style={{ fontWeight: 600, marginTop: '4px', fontSize: '13px' }}>
                              {inspectionDetails.recovery.duration_seconds ? `${inspectionDetails.recovery.duration_seconds}s` : 'Completed'}
                            </div>
                          </div>
                        </div>

                        {inspectionDetails.recovery.plan_rationale && (
                          <div style={{ marginBottom: '14px', fontSize: '12.5px', color: '#334155' }}>
                            <strong>Backfill Strategy & Rationale:</strong>
                            <p style={{ margin: '4px 0 0 0', color: '#64748b', fontSize: '12px' }}>
                              {inspectionDetails.recovery.plan_rationale}
                            </p>
                          </div>
                        )}

                        {inspectionDetails.recovery.selected_tasks?.length > 0 && (
                          <div style={{ marginBottom: '14px' }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '6px' }}>
                              Minimal Safe Set of Tasks Re-executed:
                            </div>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              {inspectionDetails.recovery.selected_tasks.map((task, idx) => (
                                <span key={idx} className="badge badge-primary" style={{ fontSize: '11px' }}>
                                  {idx + 1}. {task}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {inspectionDetails.recovery.logs_text && (
                          <div>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '6px' }}>
                              Recovery Execution Logs:
                            </div>
                            <pre style={{
                              background: '#0f172a', color: '#f8fafc', padding: '12px', borderRadius: '6px',
                              fontSize: '11px', maxHeight: '160px', overflowY: 'auto', fontFamily: 'monospace'
                            }}>
                              {inspectionDetails.recovery.logs_text}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}

                  {/* Direct First-Pass Run without failure */}
                  {!inspectionDetails?.diagnosis && !inspectionDetails?.recovery && (
                    <div style={{
                      padding: '30px',
                      textAlign: 'center',
                      background: '#f8fafc',
                      borderRadius: '8px',
                      border: '1px solid #e2e8f0'
                    }}>
                      <ShieldCheck size={36} color="#16a34a" style={{ margin: '0 auto 10px auto' }} />
                      <h4 style={{ margin: '0 0 6px 0', fontSize: '15px' }}>Direct First-Pass Execution</h4>
                      <p style={{ color: '#64748b', fontSize: '12.5px', maxWidth: '500px', margin: '0 auto 16px auto' }}>
                        This run satisfied 100% of data contract specifications, schemas, allowed ranges, and arithmetic assertions on the first attempt without needing AI diagnosis or recovery backfilling.
                      </p>
                      <a
                        href={getDownloadProcessedUrl(selectedRunId)}
                        className="btn btn-primary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                        target="_blank"
                        rel="noopener noreferrer"
                        download
                      >
                        <Download size={14} />
                        Download Final Processed Dataset (.csv)
                      </a>
                    </div>
                  )}
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
                    <div style={{ marginBottom: '20px', padding: '10px 14px', background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '6px', fontSize: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                      <div>
                        <strong>Durable Artifact Location:</strong> <code>{artifacts.artifact_path}</code>
                      </div>
                      <a
                        href={getDownloadProcessedUrl(selectedRunId)}
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}
                        target="_blank"
                        rel="noopener noreferrer"
                        download
                      >
                        <Download size={13} />
                        Download CSV
                      </a>
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
