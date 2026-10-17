import React, { useState, useEffect } from 'react';
import { Play, Loader2, CheckCircle2, AlertTriangle, Cpu, ArrowRight, Download } from 'lucide-react';
import { executePipeline, getRunResults, getDownloadProcessedUrl } from '../services/api';
import PipelineResults from './PipelineResults';
import { formatIST } from '../utils/dateUtils';

export default function PipelineExecution({ dataset, validationResult, disabled, onNavigateToDiagnosis, onNavigateToHistory, autoExecute, onAutoExecuteDone }) {
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);
  const [pipelineResultsData, setPipelineResultsData] = useState(null);
  const [executionError, setExecutionError] = useState(null);

  const isUnlocked = validationResult && (
    validationResult.status === 'VALID' || 
    validationResult.status === 'VALID_WITH_WARNINGS' ||
    validationResult.status === 'NEEDS_MAPPING'
  );

  const handleExecute = async () => {
    const dId = dataset?.dataset_id || dataset?.id;
    if (!dId || !isUnlocked) return;

    setExecuting(true);
    setExecutionError(null);

    let contractToExecute = 'sales';
    const cType = (validationResult?.contract_type || '').toLowerCase();
    const cName = (validationResult?.contract_name || '').toLowerCase();
    const det = (typeof dataset?.suggested_contract === 'object' ? dataset?.suggested_contract?.suggested_contract : dataset?.suggested_contract || '').toLowerCase();

    if (cType.includes('attendance') || cName.includes('attendance') || cName.includes('student') || det.includes('attendance')) {
      contractToExecute = 'attendance';
    } else if (cType.includes('generic') || cName.includes('generic') || det.includes('generic')) {
      contractToExecute = 'generic';
    } else {
      contractToExecute = 'sales';
    }

    try {
      const execRes = await executePipeline(dId, contractToExecute);
      setExecutionResult(execRes);

      // Fetch comprehensive calculated results from database
      const fullResults = await getRunResults(execRes.run_id);
      setPipelineResultsData(fullResults);
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail;
      const runId = err.response?.headers?.['x-run-id'] || err.response?.data?.run_id || validationResult?.run_id || 'N/A';
      setExecutionError({
        message: typeof detail === 'string' ? detail : err.message || 'Pipeline execution failed',
        status: err.response?.status || 500,
        runId,
        timestamp: formatIST(new Date().toISOString()),
      });
    } finally {
      setExecuting(false);
    }
  };

  useEffect(() => {
    if (autoExecute && isUnlocked && !executing && !executionResult) {
      if (onAutoExecuteDone) onAutoExecuteDone();
      const el = document.getElementById('pipeline-execution-step3');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      handleExecute();
    }
  }, [autoExecute, isUnlocked]);

  return (
    <div id="pipeline-execution-step3" className={`section-card ${!isUnlocked || disabled ? 'section-disabled' : ''}`}>
      <div className="section-header">
        <div className="section-title-wrap">
          <span className="section-number">3</span>
          <div>
            <h2 className="section-title">PIPELINE EXECUTION & AUDITED RESULTS</h2>
            <p className="section-subtitle">
              Executes cleaning, transformation, calculation, aggregation, post-quality check, and PostgreSQL storage.
            </p>
          </div>
        </div>
        {pipelineResultsData && (
          <span className="badge badge-success">
            <CheckCircle2 size={14} style={{ marginRight: '4px' }} />
            COMPLETED
          </span>
        )}
      </div>

      <div className="section-body">
        {/* Execution trigger bar */}
        <div className="execution-action-bar">
          <div className="execution-status-info">
            <span className="exec-meta-label">Contract Pre-Check:</span>
            {validationResult?.status === 'VALID' || validationResult?.status === 'VALID_WITH_WARNINGS' ? (
              <span className="badge badge-success font-semibold">
                <CheckCircle2 size={14} style={{ marginRight: '4px' }} />
                CONTRACT VALID — READY TO EXECUTE
              </span>
            ) : validationResult?.status === 'NEEDS_MAPPING' ? (
              <span className="badge font-semibold" style={{ background: '#e0f2fe', color: '#0369a1', border: '1px solid #7dd3fc' }}>
                <CheckCircle2 size={14} style={{ marginRight: '4px' }} />
                MAPPING READY — UNLOCKED FOR EXECUTION
              </span>
            ) : (
              <span className="badge badge-neutral">
                {validationResult?.status === 'INVALID'
                  ? 'BLOCKED — VALIDATION FAILED'
                  : 'PENDING VALIDATION'}
              </span>
            )}
          </div>

          <button
            type="button"
            className="btn btn-execute"
            onClick={handleExecute}
            disabled={!isUnlocked || executing || disabled}
          >
            {executing ? (
              <>
                <Loader2 size={18} className="spinner" style={{ marginRight: '8px' }} />
                Executing Real Data Pipeline (7 Stages)...
              </>
            ) : (
              <>
                <Play size={18} style={{ marginRight: '8px' }} fill="currentColor" />
                Execute Pipeline
              </>
            )}
          </button>
        </div>

        {/* Failure Handling Display */}
        {executionError && (
          <div className="alert alert-danger" style={{ marginTop: '20px' }}>
            <AlertTriangle size={20} style={{ marginRight: '10px', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: '15px', marginBottom: '4px' }}>
                PIPELINE EXECUTION FAILED
              </div>
              <div>{executionError.message}</div>
              <div style={{ marginTop: '12px', fontSize: '12px', color: '#64748b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                <span>Run ID: <code>{executionError.runId}</code> | Timestamp: {executionError.timestamp}</span>
                {onNavigateToDiagnosis && executionError.runId && executionError.runId !== 'N/A' && (
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    style={{ background: '#dc2626', borderColor: '#b91c1c' }}
                    onClick={() => onNavigateToDiagnosis(executionError.runId)}
                  >
                    Diagnose Failure with AI (Phase 6) →
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Audited Results Section */}
        {pipelineResultsData && (
          <>
            {/* Download Processed Dataset Banner */}
            <div style={{
              marginTop: '20px',
              marginBottom: '16px',
              padding: '16px 20px',
              background: '#f0fdf4',
              border: '1px solid #86efac',
              borderRadius: '8px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '12px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={22} color="#16a34a" />
                <div>
                  <strong style={{ fontSize: '14px', color: '#166534' }}>
                    Pipeline Execution Succeeded — Processed Dataset Ready
                  </strong>
                  <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#15803d' }}>
                    All pipeline stages, domain transformations, calculations, and quality checks completed. Download the verified CSV artifact below.
                  </p>
                </div>
              </div>
              <a
                href={getDownloadProcessedUrl(pipelineResultsData.run_id)}
                className="btn btn-primary"
                style={{
                  background: '#16a34a',
                  borderColor: '#15803d',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  textDecoration: 'none',
                  fontWeight: 600,
                  fontSize: '13px',
                  padding: '9px 18px'
                }}
                target="_blank"
                rel="noopener noreferrer"
                download
              >
                <Download size={15} />
                Download Processed Dataset (.csv)
              </a>
            </div>

            <PipelineResults results={pipelineResultsData} dataset={dataset} />
            {onNavigateToHistory && (
              <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => onNavigateToHistory(pipelineResultsData.run_id)}
                >
                  View Run in Persistent History (Phase 5) →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
