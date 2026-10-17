import React, { useState, useEffect } from 'react';
import { ShieldCheck, ShieldX, Play, FileCode, CheckCircle, AlertTriangle, ArrowRight, Loader2, CalendarCog, Wrench, AlertOctagon, Sparkles } from 'lucide-react';
import { validateDataset, fixDateFormat, alignSchema } from '../services/api';
import ValidationErrors from './ValidationErrors';
import DataCorrectionModal from './DataCorrectionModal';

export default function ValidationPanel({ dataset, onValidationComplete, disabled, onNavigateToDiagnosis, onAutoResumeExecution }) {
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [fixingDate, setFixingDate] = useState(false);
  const [dateFixResult, setDateFixResult] = useState(null);
  const [aligningSchema, setAligningSchema] = useState(false);
  const [alignResult, setAlignResult] = useState(null);
  const [isCorrectionModalOpen, setIsCorrectionModalOpen] = useState(false);

  // Active contract selection (defaults to suggested_contract if present)
  const [contractName, setContractName] = useState('attendance');

  useEffect(() => {
    if (dataset?.suggested_contract) {
      const suggested = typeof dataset.suggested_contract === 'object'
        ? (dataset.suggested_contract.suggested_contract || 'attendance')
        : dataset.suggested_contract;
      setContractName(suggested);
    }
  }, [dataset?.dataset_id, dataset?.suggested_contract]);

  const handleValidate = async (targetContract = null) => {
    if (!dataset?.dataset_id) return;
    setValidating(true);
    setErrorMsg(null);
    setDateFixResult(null);

    const activeContract = targetContract || contractName;
    try {
      const result = await validateDataset(dataset.dataset_id, activeContract);
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

  const handleFixDateFormat = async () => {
    if (!dataset?.dataset_id) return;
    setFixingDate(true);
    setDateFixResult(null);

    try {
      const result = await fixDateFormat(dataset.dataset_id);
      setDateFixResult(result);
      // Auto re-validate after fixing
      setTimeout(() => handleValidate(), 800);
    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message || 'Date format fix failed';
      setErrorMsg(msg);
    } finally {
      setFixingDate(false);
    }
  };

  const handleMapFields = async () => {
    const dId = dataset?.dataset_id || dataset?.id;
    if (!dId) return;

    setAligningSchema(true);
    setErrorMsg(null);

    try {
      // 1. Automatically perform schema mapping between incoming source dataset and active contract schema
      const activeContract = contractName || 'sales';
      const result = await alignSchema(dId, activeContract);
      setAlignResult(result);

      // 2. Immediately trigger validation by executing Validate Dataset action
      const summary = await validateDataset(dId, activeContract);

      // 3. Update contract validation status to valid, clear invalid flag
      setValidationResult(summary);
      if (onValidationComplete) {
        onValidationComplete(summary);
      }

      // 4. Automatically resume pipeline execution under step 3
      if (summary.status === 'VALID' || summary.status === 'VALID_WITH_WARNINGS' || summary.status === 'NEEDS_MAPPING') {
        if (onAutoResumeExecution) {
          onAutoResumeExecution();
        }
      }
    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message || 'Schema mapping and validation failed';
      setErrorMsg(msg);
    } finally {
      setAligningSchema(false);
    }
  };

  const handleAlignSchema = handleMapFields;

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
          <span className={`badge ${
            validationResult.status === 'VALID' || validationResult.status === 'VALID_WITH_WARNINGS'
              ? 'badge-success'
              : validationResult.status === 'NEEDS_MAPPING'
              ? 'badge-warning'
              : 'badge-danger'
          }`}>
            {validationResult.status === 'VALID' || validationResult.status === 'VALID_WITH_WARNINGS' ? (
              <>
                <ShieldCheck size={14} style={{ marginRight: '4px' }} />
                VALID
              </>
            ) : validationResult.status === 'NEEDS_MAPPING' ? (
              <>
                <Wrench size={14} style={{ marginRight: '4px' }} />
                NEEDS MAPPING
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
        <div className="contract-info-bar" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <div className="contract-meta-item">
              <FileCode size={18} className="text-muted" />
              <div>
                <span className="meta-caption">Selected Data Contract:</span>
                <select
                  value={contractName}
                  onChange={(e) => {
                    const newC = e.target.value;
                    setContractName(newC);
                    if (dataset) handleValidate(newC);
                  }}
                  style={{
                    marginLeft: '6px',
                    padding: '4px 8px',
                    fontSize: '12.5px',
                    fontWeight: 600,
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    background: '#ffffff',
                    color: '#0f172a',
                    cursor: 'pointer'
                  }}
                >
                  <option value="attendance">Student Attendance (attendance_contract.yaml)</option>
                  <option value="sales">Sales Transactions (sales_contract_v1.yaml)</option>
                  <option value="generic">Generic Tabular (generic_contract.yaml)</option>
                </select>
              </div>
            </div>
            <div className="contract-meta-item">
              <div>
                <span className="meta-caption">Scope:</span>
                <span className="meta-highlight">
                  {contractName === 'attendance' ? 'student_attendance' : contractName === 'sales' ? 'sales_transactions' : 'generic_tabular'}
                </span>
              </div>
            </div>
            {dataset?.suggested_contract && (
              <span style={{
                fontSize: '11px',
                padding: '3px 8px',
                borderRadius: '12px',
                background: '#e0f2fe',
                color: '#0369a1',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                <Sparkles size={12} />
                Auto-Detected: {typeof dataset.suggested_contract === 'object' ? (dataset.suggested_contract.suggested_contract || 'attendance') : String(dataset.suggested_contract)}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {validationResult && (validationResult.status === 'NEEDS_MAPPING' || validationResult.status === 'INVALID' || (validationResult.mappable_columns && Object.keys(validationResult.mappable_columns).length > 0)) && (
              <button
                type="button"
                className="btn btn-warning"
                onClick={() => setIsCorrectionModalOpen(true)}
                style={{
                  background: '#f59e0b',
                  borderColor: '#d97706',
                  color: '#ffffff',
                  fontWeight: 600,
                  fontSize: '13px',
                  padding: '7px 14px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  borderRadius: '6px'
                }}
              >
                <Wrench size={15} />
                Review and Fix Data
              </button>
            )}

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleValidate()}
              disabled={disabled || validating || !dataset}
              style={{ fontSize: '13px', padding: '7px 16px' }}
            >
              {validating ? (
                <>
                  <Loader2 size={16} className="spinner" style={{ marginRight: '6px' }} />
                  Validating against {typeof contractName === 'string' ? contractName : 'contract'}...
                </>
              ) : (
                <>
                  <ShieldCheck size={16} style={{ marginRight: '6px' }} />
                  Validate Dataset
                </>
              )}
            </button>
          </div>
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
              <div className="summary-status-pill" style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                <div>
                  <span className="summary-pill-label">Contract Status</span>
                  <span className={`status-badge-large ${
                    validationResult.status === 'VALID' ? 'status-valid' : 
                    validationResult.status === 'VALID_WITH_WARNINGS' ? 'status-warning' :
                    validationResult.status === 'NEEDS_MAPPING' ? 'status-needs-mapping' : 'status-invalid'
                  }`} style={{
                    padding: '6px 14px',
                    borderRadius: '6px',
                    fontWeight: 700,
                    fontSize: '13px',
                    background: validationResult.status === 'VALID' ? '#dcfce7' :
                                validationResult.status === 'VALID_WITH_WARNINGS' ? '#fef3c7' :
                                validationResult.status === 'NEEDS_MAPPING' ? '#e0f2fe' : '#fee2e2',
                    color: validationResult.status === 'VALID' ? '#166534' :
                           validationResult.status === 'VALID_WITH_WARNINGS' ? '#b45309' :
                           validationResult.status === 'NEEDS_MAPPING' ? '#0369a1' : '#b91c1c',
                    border: `1px solid ${
                      validationResult.status === 'VALID' ? '#86efac' :
                      validationResult.status === 'VALID_WITH_WARNINGS' ? '#fcd34d' :
                      validationResult.status === 'NEEDS_MAPPING' ? '#7dd3fc' : '#fca5a5'
                    }`
                  }}>
                    {validationResult.status.replace(/_/g, ' ')}
                  </span>
                </div>
                {validationResult.status === 'NEEDS_MAPPING' && (
                  <button
                    type="button"
                    className="btn btn-primary btn-sm btn-map-fields"
                    onClick={handleMapFields}
                    disabled={aligningSchema || validating}
                    title="Automatically map columns to active contract and resume execution"
                    style={{
                      background: '#0284c7',
                      borderColor: '#0369a1',
                      color: '#ffffff',
                      fontWeight: 700,
                      padding: '6px 14px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      cursor: 'pointer',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                    }}
                  >
                    {aligningSchema ? (
                      <>
                        <Loader2 size={13} className="spinner" />
                        Mapping Fields...
                      </>
                    ) : (
                      <>
                        <Wrench size={13} />
                        Map Fields
                      </>
                    )}
                  </button>
                )}
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

            {/* Needs Mapping Banner */}
            {validationResult.status === 'NEEDS_MAPPING' && (
              <div style={{
                marginTop: '14px',
                padding: '14px 18px',
                background: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                flexWrap: 'wrap'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Wrench size={22} style={{ color: '#2563eb', flexShrink: 0 }} />
                  <div>
                    <strong style={{ color: '#1e40af', fontSize: '13px' }}>
                      Column Aliases Detected — Schema Mapping Required
                    </strong>
                    <p style={{ color: '#1d4ed8', fontSize: '12px', margin: '2px 0 0 0' }}>
                      {Object.keys(validationResult.mappable_columns || {}).length} column(s) match known aliases (e.g. {Object.entries(validationResult.mappable_columns || {}).slice(0, 3).map(([target, src]) => `${src} ➔ ${target}`).join(', ')}). Click <strong>Map Fields</strong> to automatically perform schema mapping and resume execution under Step 3, or click <strong>Configure Mapping</strong> to review transformations.
                    </p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleMapFields}
                    disabled={aligningSchema || validating}
                    style={{
                      background: '#0284c7',
                      borderColor: '#0369a1',
                      color: '#ffffff',
                      fontSize: '12.5px',
                      padding: '8px 16px',
                      fontWeight: 700,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      cursor: 'pointer'
                    }}
                  >
                    {aligningSchema ? (
                      <>
                        <Loader2 size={14} className="spinner" />
                        Mapping Fields...
                      </>
                    ) : (
                      <>
                        <Wrench size={14} />
                        Map Fields
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setIsCorrectionModalOpen(true)}
                    style={{
                      background: '#f8fafc',
                      borderColor: '#cbd5e1',
                      color: '#334155',
                      fontSize: '12px',
                      padding: '8px 14px',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      cursor: 'pointer'
                    }}
                  >
                    Configure Mapping
                  </button>
                </div>
              </div>
            )}

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

            {/* If Invalid, show Auto-Align Schema button if MISSING_REQUIRED_COLUMN exists */}
            {validationResult.status === 'INVALID' &&
              validationResult.required_column_checks?.failed > 0 && (
              <div style={{
                marginTop: '16px',
                padding: '14px 18px',
                background: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                flexWrap: 'wrap'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Wrench size={20} style={{ color: '#2563eb', flexShrink: 0 }} />
                  <div>
                    <strong style={{ color: '#1e40af', fontSize: '13px' }}>Schema Mismatch Detected ({validationResult.required_column_checks.failed} missing columns)</strong>
                    <p style={{ color: '#1d4ed8', fontSize: '12px', margin: '2px 0 0 0' }}>
                      Auto-align column aliases (e.g. date ➔ transaction_date, status ➔ transaction_status), compute total_amount, and complete required contract schema.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleAlignSchema}
                  disabled={aligningSchema}
                  style={{
                    whiteSpace: 'nowrap',
                    background: '#2563eb',
                    fontSize: '12.5px',
                    padding: '8px 16px'
                  }}
                >
                  {aligningSchema ? (
                    <>
                      <Loader2 size={14} className="spinner" style={{ marginRight: '6px' }} />
                      Aligning Schema...
                    </>
                  ) : (
                    <>
                      <Wrench size={14} style={{ marginRight: '6px' }} />
                      Auto-Align & Complete Schema
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Schema Align Success Message */}
            {alignResult && alignResult.status === 'SUCCESS' && (
              <div className="alert alert-success" style={{ marginTop: '12px' }}>
                <CheckCircle size={18} style={{ marginRight: '8px', flexShrink: 0 }} />
                <div>
                  <strong>Schema Aligned:</strong> Successfully aligned {alignResult.aligned_columns?.length || 0} column(s) ({alignResult.aligned_columns?.join(', ')}). Re-validating dataset...
                </div>
              </div>
            )}

            {/* AI Diagnosis and Remediation Gate Banner */}
            {validationResult.status === 'INVALID' && onNavigateToDiagnosis && (
              <div style={{
                marginTop: '14px',
                padding: '14px 18px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                flexWrap: 'wrap'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <AlertOctagon size={20} style={{ color: '#ef4444', flexShrink: 0 }} />
                  <div>
                    <strong style={{ color: '#991b1b', fontSize: '13px' }}>Automated AI Root Cause Diagnosis & Backfill Available</strong>
                    <p style={{ color: '#b91c1c', fontSize: '12px', margin: '2px 0 0 0' }}>
                      Validation Run ID: <code>{validationResult.run_id}</code>. Isolate root causes, analyze telemetry, and plan backfill execution.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => onNavigateToDiagnosis(validationResult.run_id)}
                  style={{
                    whiteSpace: 'nowrap',
                    background: '#dc2626',
                    borderColor: '#b91c1c',
                    fontSize: '12.5px',
                    padding: '8px 16px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <AlertOctagon size={14} />
                  Diagnose with AI (Phase 6) →
                </button>
              </div>
            )}

            {/* If Invalid, show Fix Date Format button if DATE_FORMAT_ERROR exists */}
            {validationResult.status === 'INVALID' && 
              validationResult.errors_preview?.some(e => e.error_type === 'DATE_FORMAT_ERROR') && (
              <div className="date-fix-banner" style={{
                marginTop: '16px',
                padding: '14px 18px',
                background: '#fffbeb',
                border: '1px solid #fde68a',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                flexWrap: 'wrap'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <CalendarCog size={20} style={{ color: '#d97706', flexShrink: 0 }} />
                  <div>
                    <strong style={{ color: '#92400e', fontSize: '13px' }}>Date Format Issue Detected</strong>
                    <p style={{ color: '#a16207', fontSize: '12px', margin: '2px 0 0 0' }}>
                      Dates are in non-standard format (e.g. <code style={{ background: '#fef3c7', padding: '1px 4px', borderRadius: '3px' }}>dd/mm/yyyy, mm/dd/yyyy</code>). 
                      Click to convert all dates to <code style={{ background: '#fef3c7', padding: '1px 4px', borderRadius: '3px' }}>yyyy-mm-dd</code> (ISO standard).
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleFixDateFormat}
                  disabled={fixingDate}
                  style={{ 
                    whiteSpace: 'nowrap',
                    background: '#d97706',
                    fontSize: '12.5px',
                    padding: '8px 16px'
                  }}
                >
                  {fixingDate ? (
                    <>
                      <Loader2 size={14} className="spinner" style={{ marginRight: '6px' }} />
                      Converting Dates...
                    </>
                  ) : (
                    <>
                      <CalendarCog size={14} style={{ marginRight: '6px' }} />
                      Fix Date Format
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Date Fix Success Message */}
            {dateFixResult && dateFixResult.converted_count > 0 && (
              <div className="alert alert-success" style={{ marginTop: '12px' }}>
                <CheckCircle size={18} style={{ marginRight: '8px', flexShrink: 0 }} />
                <div>
                  <strong>Date Format Fixed:</strong> {dateFixResult.converted_count.toLocaleString()} dates converted from dd/mm/yyyy → yyyy-mm-dd. Re-validating dataset...
                </div>
              </div>
            )}

            {/* If Invalid or Needs Mapping, render Evidence Table */}
            {(validationResult.status === 'INVALID' || validationResult.status === 'NEEDS_MAPPING') && validationResult.errors_preview?.length > 0 && (
              <ValidationErrors
                errors={validationResult.errors_preview}
                totalErrors={validationResult.validation_errors_count}
                rowsInvalid={validationResult.rows_invalid}
              />
            )}
          </div>
        )}
      </div>

      {/* Interactive Data Correction Modal */}
      {dataset && (
        <DataCorrectionModal
          isOpen={isCorrectionModalOpen}
          onClose={() => setIsCorrectionModalOpen(false)}
          datasetId={dataset.dataset_id}
          contractName={contractName}
          onCorrectionsApplied={(res) => {
            handleValidate();
          }}
        />
      )}
    </div>
  );
}
