import React, { useState, useEffect } from 'react';
import { 
  Wrench, 
  X, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowRight, 
  Check, 
  Loader2, 
  ShieldAlert, 
  Sparkles,
  Info
} from 'lucide-react';
import { analyzeCorrections, applyCorrections } from '../services/api';

export default function DataCorrectionModal({ 
  isOpen, 
  onClose, 
  datasetId, 
  contractName = 'attendance', 
  onCorrectionsApplied 
}) {
  const [loading, setLoading] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [selectedFixes, setSelectedFixes] = useState({});
  const [applying, setApplying] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    if (isOpen && datasetId) {
      loadAnalysis();
    }
  }, [isOpen, datasetId, contractName]);

  const loadAnalysis = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await analyzeCorrections(datasetId, contractName);
      setAnalysisData(data);
      // Default-check all auto-fixable proposals
      const initial = {};
      (data.proposals || []).forEach(p => {
        initial[p.id] = p.auto_fixable !== false;
      });
      setSelectedFixes(initial);
    } catch (err) {
      console.error('Failed to analyze corrections:', err);
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to analyze corrections');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const proposals = analysisData?.proposals || [];
  const selectedCount = Object.values(selectedFixes).filter(Boolean).length;

  const toggleFix = (id) => {
    setSelectedFixes(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const toggleAll = (selectAll) => {
    const updated = {};
    proposals.forEach(p => {
      updated[p.id] = selectAll;
    });
    setSelectedFixes(updated);
  };

  const handleApply = async () => {
    const approvedProposals = proposals.filter(p => selectedFixes[p.id]);
    if (approvedProposals.length === 0) {
      setErrorMsg('Please select at least one correction to apply.');
      return;
    }

    setApplying(true);
    setErrorMsg(null);
    try {
      const result = await applyCorrections(datasetId, approvedProposals);
      onCorrectionsApplied(result);
      onClose();
    } catch (err) {
      console.error('Failed to apply corrections:', err);
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to apply corrections');
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="modal-backdrop" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.75)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '20px'
    }}>
      <div className="modal-content" style={{
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '850px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 24px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#f8fafc'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              background: '#3b82f6',
              color: '#ffffff',
              padding: '6px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Wrench size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700, color: '#0f172a' }}>
                Review and Fix Data Before Execution
              </h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#64748b' }}>
                Contract: <strong>{analysisData?.contract_name || contractName}</strong> ({analysisData?.contract_type || 'auto'}) • Total Rows: {analysisData?.total_rows?.toLocaleString() || 0}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={applying}
            style={{
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: '#64748b',
              padding: '4px'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Notice Banner */}
        <div style={{
          padding: '10px 24px',
          background: '#eff6ff',
          borderBottom: '1px solid #dbeafe',
          fontSize: '12px',
          color: '#1e40af',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Info size={16} style={{ flexShrink: 0 }} />
          <span>
            Original uploaded file is <strong>never modified</strong>. Approved fixes are saved to an isolated corrected dataset file and re-validated automatically.
          </span>
        </div>

        {/* Body */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <Loader2 size={32} className="spinner" style={{ color: '#3b82f6', margin: '0 auto 12px auto' }} />
              <p style={{ color: '#64748b', fontSize: '14px', fontWeight: 500 }}>
                Analyzing dataset columns and rules against contract...
              </p>
            </div>
          ) : errorMsg ? (
            <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
              <AlertTriangle size={18} style={{ marginRight: '8px', flexShrink: 0 }} />
              <div>{errorMsg}</div>
            </div>
          ) : proposals.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <CheckCircle2 size={40} style={{ color: '#10b981', margin: '0 auto 12px auto' }} />
              <h4 style={{ margin: '0 0 6px 0', fontSize: '16px', color: '#0f172a' }}>
                No Data Corrections Needed
              </h4>
              <p style={{ color: '#64748b', fontSize: '13px' }}>
                All columns, formats, and values in this dataset already comply with the selected contract schema.
              </p>
            </div>
          ) : (
            <div>
              {/* Batch Controls */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '14px',
                paddingBottom: '10px',
                borderBottom: '1px solid #f1f5f9'
              }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>
                  {proposals.length} Proposed Correction{proposals.length > 1 ? 's' : ''} ({selectedCount} selected)
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => toggleAll(true)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#2563eb',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    Select All
                  </button>
                  <span style={{ color: '#cbd5e1' }}>|</span>
                  <button
                    type="button"
                    onClick={() => toggleAll(false)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#64748b',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    Deselect All
                  </button>
                </div>
              </div>

              {/* Proposals List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {proposals.map((prop) => {
                  const isChecked = !!selectedFixes[prop.id];
                  return (
                    <div
                      key={prop.id}
                      onClick={() => toggleFix(prop.id)}
                      style={{
                        border: isChecked ? '1px solid #93c5fd' : '1px solid #e2e8f0',
                        borderRadius: '8px',
                        padding: '14px 16px',
                        background: isChecked ? '#f8faff' : '#ffffff',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}} // handled by parent div
                          style={{ marginTop: '3px', cursor: 'pointer' }}
                        />
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <span style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              padding: '2px 7px',
                              borderRadius: '4px',
                              background: prop.severity === 'ERROR' ? '#fee2e2' : prop.severity === 'WARNING' ? '#fef3c7' : '#e0f2fe',
                              color: prop.severity === 'ERROR' ? '#b91c1c' : prop.severity === 'WARNING' ? '#b45309' : '#0369a1'
                            }}>
                              {prop.type}
                            </span>
                            <span style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>
                              {prop.description}
                            </span>
                            <span style={{
                              fontSize: '11px',
                              color: '#64748b',
                              marginLeft: 'auto',
                              fontWeight: 500
                            }}>
                              Affects {prop.affected_rows?.toLocaleString()} row{prop.affected_rows !== 1 ? 's' : ''}
                            </span>
                          </div>

                          {/* Before & After Preview */}
                          {(prop.sample_before || prop.sample_after) && (
                            <div style={{
                              marginTop: '8px',
                              padding: '8px 12px',
                              background: '#f1f5f9',
                              borderRadius: '6px',
                              fontSize: '12px',
                              fontFamily: 'monospace',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '10px'
                            }}>
                              <div style={{ flex: 1 }}>
                                <span style={{ color: '#64748b', fontSize: '11px', display: 'block' }}>Before:</span>
                                <strong style={{ color: '#ef4444' }}>
                                  {Array.isArray(prop.sample_before) ? prop.sample_before.join(', ') : String(prop.sample_before ?? 'None')}
                                </strong>
                              </div>
                              <ArrowRight size={14} style={{ color: '#94a3b8', flexShrink: 0 }} />
                              <div style={{ flex: 1 }}>
                                <span style={{ color: '#64748b', fontSize: '11px', display: 'block' }}>Proposed After:</span>
                                <strong style={{ color: '#10b981' }}>
                                  {Array.isArray(prop.sample_after) ? prop.sample_after.join(', ') : String(prop.sample_after ?? 'Normalized')}
                                </strong>
                              </div>
                            </div>
                          )}

                          {/* Warning if any */}
                          {prop.warning && (
                            <div style={{
                              marginTop: '8px',
                              fontSize: '11px',
                              color: '#b45309',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}>
                              <AlertTriangle size={13} style={{ flexShrink: 0 }} />
                              <span>{prop.warning}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#f8fafc'
        }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={applying}
            style={{ fontSize: '13px' }}
          >
            Cancel
          </button>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <span style={{ fontSize: '12px', color: '#64748b' }}>
              {selectedCount} of {proposals.length} fixes selected
            </span>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleApply}
              disabled={applying || selectedCount === 0 || loading}
              style={{
                fontSize: '13px',
                padding: '8px 18px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: '#2563eb'
              }}
            >
              {applying ? (
                <>
                  <Loader2 size={15} className="spinner" />
                  Applying Fixes & Re-validating...
                </>
              ) : (
                <>
                  <Check size={15} />
                  Apply Selected Fixes
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
