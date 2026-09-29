import React, { useState } from 'react';
import { Play, Loader2, CheckCircle2, AlertTriangle, Cpu, ArrowRight } from 'lucide-react';
import { executePipeline, getRunResults } from '../services/api';
import PipelineResults from './PipelineResults';

export default function PipelineExecution({ dataset, validationResult, disabled }) {
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);
  const [pipelineResultsData, setPipelineResultsData] = useState(null);
  const [executionError, setExecutionError] = useState(null);

  const isUnlocked = validationResult && validationResult.status === 'VALID';

  const handleExecute = async () => {
    if (!dataset?.dataset_id || !isUnlocked) return;

    setExecuting(true);
    setExecutionError(null);

    try {
      const execRes = await executePipeline(dataset.dataset_id);
      setExecutionResult(execRes);

      // Fetch comprehensive calculated results from database
      const fullResults = await getRunResults(execRes.run_id);
      setPipelineResultsData(fullResults);
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail;
      setExecutionError({
        message: typeof detail === 'string' ? detail : err.message || 'Pipeline execution failed',
        status: err.response?.status || 500,
        runId: err.response?.data?.run_id || 'N/A',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className={`section-card ${!isUnlocked || disabled ? 'section-disabled' : ''}`}>
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
            {isUnlocked ? (
              <span className="badge badge-success font-semibold">
                <CheckCircle2 size={14} style={{ marginRight: '4px' }} />
                CONTRACT VALID — READY TO EXECUTE
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
              <div style={{ marginTop: '8px', fontSize: '12px', color: '#64748b' }}>
                Run ID: <code>{executionError.runId}</code> | Timestamp: {executionError.timestamp}
              </div>
            </div>
          </div>
        )}

        {/* Audited Results Section */}
        {pipelineResultsData && (
          <PipelineResults results={pipelineResultsData} />
        )}
      </div>
    </div>
  );
}
