import React from 'react';
import { AlertOctagon, ShieldAlert } from 'lucide-react';

export default function ValidationErrors({ errors, totalErrors, rowsInvalid }) {
  if (!errors || errors.length === 0) return null;

  return (
    <div className="validation-errors-container">
      <div className="blocked-banner">
        <div className="blocked-banner-icon">
          <AlertOctagon size={24} />
        </div>
        <div className="blocked-banner-content">
          <div className="blocked-title">PIPELINE EXECUTION BLOCKED — DATA CONTRACT VIOLATIONS DETECTED</div>
          <div className="blocked-desc">
            The dataset violates the strict data contract rules defined in <code className="contract-code">sales_contract_v1.yaml</code>. 
            Execution is safely halted until input quality is rectified. Found <strong>{totalErrors}</strong> total contract violations across <strong>{rowsInvalid}</strong> invalid records.
          </div>
        </div>
      </div>

      <div className="errors-table-card">
        <div className="errors-table-header">
          <div className="errors-table-title">
            <ShieldAlert size={16} style={{ marginRight: '6px' }} />
            Validation Evidence Table (Showing {errors.length} of {totalErrors} recorded violations)
          </div>
          <span className="errors-table-subtitle">All violations recorded into PostgreSQL table: <code>validation_errors</code></span>
        </div>

        <div className="table-responsive">
          <table className="enterprise-table error-table">
            <thead>
              <tr>
                <th style={{ width: '60px' }}>#</th>
                <th style={{ width: '90px' }}>Row</th>
                <th style={{ width: '160px' }}>Column</th>
                <th style={{ width: '190px' }}>Error Type</th>
                <th>Actual Value</th>
                <th>Expected Rule</th>
                <th style={{ width: '90px' }}>Severity</th>
              </tr>
            </thead>
            <tbody>
              {errors.map((err, idx) => (
                <tr key={idx} className="error-row">
                  <td className="row-num">{idx + 1}</td>
                  <td className="font-mono">{err.row_number !== null ? err.row_number : '—'}</td>
                  <td><code className="col-tag">{err.column_name || 'Schema'}</code></td>
                  <td>
                    <span className="badge badge-error-type">{err.error_type}</span>
                  </td>
                  <td className="cell-actual font-mono">
                    {err.actual_value !== null && err.actual_value !== undefined ? (
                      <span className="actual-badge">{String(err.actual_value)}</span>
                    ) : (
                      <span className="null-tag">NULL</span>
                    )}
                  </td>
                  <td className="cell-expected">{err.expected_rule}</td>
                  <td>
                    <span className={`badge ${err.severity === 'CRITICAL' ? 'badge-critical' : 'badge-danger'}`}>
                      {err.severity}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
