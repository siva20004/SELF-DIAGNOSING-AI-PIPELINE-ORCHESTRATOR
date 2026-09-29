import React, { useState } from 'react';
import { ShieldCheck, ShieldX, Play, FileCode, CheckCircle, AlertTriangle, ArrowRight, Loader2 } from 'lucide-react';
import { validateDataset } from '../services/api';
import ValidationErrors from './ValidationErrors';

export default function ValidationPanel({ dataset, onValidationComplete, disabled }) {
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const handleValidate = async () => {
    if (!dataset?.dataset_id) return;
    setValidating(true);
    setErrorMsg(null);

    try {
      const result = await validateDataset(dataset.dataset_id);
      setValidationResult(result);
      onValidationComplete(result);
    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message || 'Validation request failed';
      setErrorMsg(msg);
    } finally {
      setValidating(false);
    }
  };

  const getCheckStatusBadge = (stats) => {
    if (!stats || stats.total === 0) {
      return <span className="badge badge-neutral">0 / 0</span>;
    }
    if (stats.failed === 0) {
      return (
        <span className="badge badge-success">
          {stats.passed.toLocaleString()} / {stats.total.toLocaleString()} Passed
        </span>
      );
    }
    return (
      <span className="badge badge-danger">
        {stats.failed.toLocaleString()} Failed
      </span>
    );
  };

  return (
    <div className={`section-card ${disabled ? 'section-disabled' : ''}`}>
      <div className="section-header">
        <div className="section-title-wrap">
          <span className="section-number">2</span>
          <div>
            <h2 className="section-title">DATA CONTRACT VALIDATION</h2>
            <p className="section-subtitle">
              Strict schema & semantic quality enforcement against the versioned YAML contract before any pipeline execution.
            </p>
          </div>
        </div>
        {validationResult && (
          <span className={`badge ${validationResult.status === 'VALID' ? 'badge-success' : 'badge-danger'}`}>
            {validationResult.status === 'VALID' ? (
              <>
                <ShieldCheck size={14} style={{ marginRight: '4px' }} />
                VALID
              </>
            ) : (
              <>
                <ShieldX size={14} style={{ marginRight: '4px' }} />
                INVALID
              </>
            )}
          </span>
        )}
      </div>

      <div className="section-body">
        {/* Contract Info Box */}
        <div className="contract-info-bar">
          <div className="contract-meta-item">
            <FileCode size={18} className="text-muted" />
            <div>
              <span className="meta-caption">Active Contract:</span>
              <span className="meta-highlight">sales_contract_v1.yaml</span>
            </div>
          </div>
          <div className="contract-meta-item">
            <div>
              <span className="meta-caption">Version:</span>
              <span className="meta-highlight">1.0</span>
            </div>
          </div>
          <div className="contract-meta-item">
            <div>
              <span className="meta-caption">Dataset Scope:</span>
              <span className="meta-highlight">sales_transactions</span>
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleValidate}
            disabled={disabled || validating || !dataset}
          >
            {validating ? (
              <>
                <Loader2 size={16} className="spinner" style={{ marginRight: '6px' }} />
                Validating Dataset against Contract...
              </>
            ) : (
              <>
                <ShieldCheck size={16} style={{ marginRight: '6px' }} />
                Validate Dataset
              </>
            )}
          </button>
        </div>

        {errorMsg && (
          <div className="alert alert-danger" style={{ marginTop: '16px' }}>
            <AlertTriangle size={18} style={{ marginRight: '8px', flexShrink: 0 }} />
            <div>
              <strong>Validation Engine Error:</strong> {errorMsg}
            </div>
          </div>
        )}

        {/* Validation Results Summary */}
        {validationResult && (
          <div className="validation-summary-box">
            <div className="summary-banner-row">
              <div className="summary-status-pill">
                <span className="summary-pill-label">Contract Status</span>
                <span className={`status-badge-large ${validationResult.status === 'VALID' ? 'status-valid' : 'status-invalid'}`}>
                  {validationResult.status}
                </span>
              </div>
              <div className="summary-stat-group">
                <div className="stat-box">
                  <span className="stat-label">Rows Received</span>
                  <span className="stat-value">{validationResult.rows_received.toLocaleString()}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Rows Valid</span>
                  <span className="stat-value text-success">{validationResult.rows_valid.toLocaleString()}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Rows Invalid</span>
                  <span className={`stat-value ${validationResult.rows_invalid > 0 ? 'text-danger' : 'text-success'}`}>
                    {validationResult.rows_invalid.toLocaleString()}
                  </span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">Total Errors</span>
                  <span className={`stat-value ${validationResult.validation_errors_count > 0 ? 'text-danger' : 'text-success'}`}>
                    {validationResult.validation_errors_count.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Check Breakdown Grid */}
            <div className="checks-grid">
              <div className="check-card">
                <div className="check-card-title">Required Columns Checks</div>
                <div className="check-card-detail">{getCheckStatusBadge(validationResult.required_column_checks)}</div>
              </div>
              <div className="check-card">
                <div className="check-card-title">Data Type Checks</div>
                <div className="check-card-detail">{getCheckStatusBadge(validationResult.type_checks)}</div>
              </div>
              <div className="check-card">
                <div className="check-card-title">Numeric Range Checks</div>
                <div className="check-card-detail">{getCheckStatusBadge(validationResult.range_checks)}</div>
              </div>
              <div className="check-card">
                <div className="check-card-title">Enum / Allowed Values Checks</div>
                <div className="check-card-detail">{getCheckStatusBadge(validationResult.enum_checks)}</div>
              </div>
              <div className="check-card">
                <div className="check-card-title">Regex / Pattern Checks</div>
                <div className="check-card-detail">{getCheckStatusBadge(validationResult.pattern_checks)}</div>
              </div>
              <div className="check-card">
                <div className="check-card-title">Duplicate ID Checks</div>
                <div className="check-card-detail">{getCheckStatusBadge(validationResult.duplicate_checks)}</div>
              </div>
              <div className="check-card">
                <div className="check-card-title">Cross-Field Math Checks</div>
                <div className="check-card-detail">{getCheckStatusBadge(validationResult.cross_field_checks)}</div>
              </div>
            </div>

            {/* If Valid, display success message */}
            {validationResult.status === 'VALID' && (
              <div className="alert alert-success" style={{ marginTop: '16px' }}>
                <CheckCircle size={18} style={{ marginRight: '8px', flexShrink: 0 }} />
                <div>
                  <strong>Data Contract Verification Passed:</strong> All {validationResult.rows_received.toLocaleString()} rows satisfy 100% of schema definitions, numeric ranges, enum restrictions, and arithmetic rules. Pipeline execution is now unlocked.
                </div>
              </div>
            )}

            {/* If Invalid, render full Evidence Table */}
            {validationResult.status === 'INVALID' && (
              <ValidationErrors
                errors={validationResult.errors_preview}
                totalErrors={validationResult.validation_errors_count}
                rowsInvalid={validationResult.rows_invalid}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
