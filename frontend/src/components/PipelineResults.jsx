import React, { useState, useMemo } from 'react';
import { 
  DollarSign, 
  Package, 
  ShoppingCart, 
  TrendingUp, 
  CheckCircle, 
  BarChart3, 
  MapPin, 
  Tag, 
  Calendar,
  Users,
  GraduationCap,
  Clock,
  AlertTriangle,
  Download,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  Building2,
  Briefcase
} from 'lucide-react';
import PipelineTasks from './PipelineTasks';
import { getDownloadProcessedUrl, getDownloadValidationErrorsUrl } from '../services/api';
import { formatIST } from '../utils/dateUtils';

export default function PipelineResults({ results, dataset }) {
  if (!results) return null;

  const { 
    run_id, 
    status, 
    started_at, 
    completed_at, 
    duration_seconds, 
    rows_received, 
    rows_processed, 
    rows_rejected, 
    metrics, 
    sales_by_city, 
    sales_by_category, 
    sales_by_date, 
    tasks,
    contract_type,
    attendance_results 
  } = results;

  const isAttendance = contract_type === 'attendance' || !!attendance_results;

  // Student Attendance Table State
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedBranchFilter, setSelectedBranchFilter] = useState('ALL');
  const [onlyLowAttendance, setOnlyLowAttendance] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val || 0);
  };

  const safeFormatNumber = (val, defaultVal = '0') => {
    if (val === null || val === undefined) return defaultVal;
    const num = Number(val);
    return isNaN(num) ? defaultVal : num.toLocaleString();
  };

  const formatDate = (isoStr) => {
    return formatIST(isoStr);
  };

  // Filtered student records
  const allStudents = attendance_results?.student_records || [];
  const filteredStudents = useMemo(() => {
    return allStudents.filter(s => {
      const matchesSearch = !searchTerm || 
        (s.name && s.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (s.registration_number && s.registration_number.toLowerCase().includes(searchTerm.toLowerCase()));
      
      const matchesBranch = selectedBranchFilter === 'ALL' || s.branch === selectedBranchFilter;
      const matchesLowAtt = !onlyLowAttendance || (s.attendance_pct !== null && s.attendance_pct < 75);

      return matchesSearch && matchesBranch && matchesLowAtt;
    });
  }, [allStudents, searchTerm, selectedBranchFilter, onlyLowAttendance]);

  const totalPages = Math.ceil(filteredStudents.length / pageSize) || 1;
  const paginatedStudents = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredStudents.slice(start, start + pageSize);
  }, [filteredStudents, currentPage]);

  const branches = useMemo(() => {
    const bSet = new Set();
    allStudents.forEach(s => {
      if (s.branch && s.branch.trim()) bSet.add(s.branch.trim());
    });
    return Array.from(bSet).sort();
  }, [allStudents]);

  return (
    <div className="pipeline-results-container">
      {/* File & Pipeline Diagnostic Card */}
      {dataset && (
        <div className="file-info-banner" style={{
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '16px 20px',
          marginBottom: '20px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', borderBottom: '1px solid #f1f5f9', paddingBottom: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.8px', color: '#64748b', textTransform: 'uppercase' }}>
              FILE & EXECUTION DIAGNOSTICS
            </span>
            <span className="badge badge-success" style={{ fontSize: '11px' }}>
              <CheckCircle size={12} style={{ marginRight: '4px' }} />
              PIPELINE COMPLETED
            </span>
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '12px'
          }}>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>File Name</span>
              <strong style={{ fontSize: '13px', color: '#1e293b' }} title={dataset?.filename || 'Dataset'}>{dataset?.filename || 'Dataset'}</strong>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Format</span>
              <span className="badge badge-neutral" style={{ marginTop: '2px' }}>{dataset?.file_type || 'CSV'}</span>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Records Ingested</span>
              <strong style={{ fontSize: '13px', color: '#1e293b' }}>{safeFormatNumber(rows_processed ?? dataset?.rows ?? rows_received)}</strong>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Contract Type</span>
              <strong style={{ fontSize: '13px', color: '#2563eb' }}>{isAttendance ? 'Student Attendance' : 'Sales Transactions'}</strong>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Validation</span>
              <span style={{ color: '#16a34a', fontWeight: 600, fontSize: '13px' }}>✓ Real Calculations</span>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Output Integrity</span>
              <span style={{ color: '#16a34a', fontWeight: 600, fontSize: '13px' }}>✓ 100% Audited</span>
            </div>
          </div>
        </div>
      )}

      {/* Run Metadata Header */}
      <div className="run-summary-box">
        <div className="run-header-top">
          <div className="run-id-block">
            <span className="run-label">PIPELINE RUN ID</span>
            <span className="run-value font-mono">{run_id}</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <a
              href={getDownloadProcessedUrl(run_id)}
              className="btn btn-primary btn-sm"
              target="_blank"
              rel="noopener noreferrer"
              download
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
            >
              <Download size={14} />
              Download Processed Dataset (CSV)
            </a>
            <span className="badge badge-success-lg">
              <CheckCircle size={16} style={{ marginRight: '6px' }} />
              PIPELINE {status}
            </span>
          </div>
        </div>

        <div className="run-stats-grid">
          <div className="run-stat-item">
            <span className="stat-sub">Rows Received</span>
            <span className="stat-main">{safeFormatNumber(rows_received ?? rows_processed)}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Rows Processed</span>
            <span className="stat-main text-success">{safeFormatNumber(rows_processed ?? rows_received)}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Rows Rejected</span>
            <span className="stat-main text-muted">{safeFormatNumber(rows_rejected)}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Execution Duration</span>
            <span className="stat-main">{duration_seconds !== null ? `${duration_seconds}s` : '—'}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Started At (IST)</span>
            <span className="stat-sub-val">{formatDate(started_at)}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Completed At (IST)</span>
            <span className="stat-sub-val">{formatDate(completed_at)}</span>
          </div>
        </div>
      </div>

      {/* ========================================================= */}
      {/* CASE A: ATTENDANCE PIPELINE DASHBOARD                     */}
      {/* ========================================================= */}
      {isAttendance && attendance_results && (
        <>
          {/* KPI Cards for Attendance */}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Total Students</span>
                <div className="kpi-icon-wrap icon-blue">
                  <Users size={20} />
                </div>
              </div>
              <div className="kpi-value">{safeFormatNumber(attendance_results?.overall?.total_students)}</div>
              <div className="kpi-meta">Real student records parsed from file</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Overall Attendance</span>
                <div className="kpi-icon-wrap icon-green">
                  <CheckCircle2 size={20} />
                </div>
              </div>
              <div className="kpi-value text-success">
                {attendance_results.overall?.overall_attendance_pct ?? 0}%
              </div>
              <div className="kpi-meta">Total Attended ÷ Total Conducted</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Average Student Att.</span>
                <div className="kpi-icon-wrap icon-indigo">
                  <GraduationCap size={20} />
                </div>
              </div>
              <div className="kpi-value">
                {attendance_results.overall?.avg_student_attendance_pct ?? 0}%
              </div>
              <div className="kpi-meta">Mean student attendance percentage</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Attendance Range</span>
                <div className="kpi-icon-wrap icon-amber">
                  <TrendingUp size={20} />
                </div>
              </div>
              <div className="kpi-value" style={{ fontSize: '20px' }}>
                {attendance_results.overall?.min_student_attendance_pct ?? 0}% – {attendance_results.overall?.max_student_attendance_pct ?? 0}%
              </div>
              <div className="kpi-meta">Minimum to maximum student percentage</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Students &lt; 75% Risk</span>
                <div className="kpi-icon-wrap icon-red" style={{ background: '#fee2e2', color: '#dc2626' }}>
                  <AlertTriangle size={20} />
                </div>
              </div>
              <div className="kpi-value" style={{ color: '#dc2626' }}>
                {safeFormatNumber(attendance_results?.overall?.students_below_75_pct)}
              </div>
              <div className="kpi-meta">Below university minimum threshold</div>
            </div>
          </div>

          {/* Source vs Calculated Mismatches Callout */}
          {attendance_results.overall?.source_vs_calculated_mismatches > 0 && (
            <div style={{
              margin: '20px 0',
              padding: '16px 20px',
              background: '#fffbeb',
              border: '1px solid #fde68a',
              borderRadius: '8px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <AlertTriangle size={18} style={{ color: '#d97706' }} />
                <strong style={{ color: '#92400e', fontSize: '14px' }}>
                  Source-vs-Recalculated Summary Mismatches Flagged ({attendance_results.overall.source_vs_calculated_mismatches} detected)
                </strong>
              </div>
              <p style={{ color: '#a16207', fontSize: '12.5px', margin: '0 0 10px 0' }}>
                The uploaded Excel file contained pre-filled summary columns ("Total Conducted" / "Total Attended") that do NOT match the real count of attendance markers (P/A) in the individual session columns. The pipeline recalculated exact totals from source markers.
              </p>
              {attendance_results.mismatches?.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table className="enterprise-table" style={{ fontSize: '12px' }}>
                    <thead>
                      <tr>
                        <th>Excel Row</th>
                        <th>Field Name</th>
                        <th style={{ textAlign: 'right' }}>Source Column Value</th>
                        <th style={{ textAlign: 'right' }}>Recalculated from Session Markers</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attendance_results.mismatches.slice(0, 10).map((m, idx) => (
                        <tr key={idx}>
                          <td className="font-mono">Row #{m.row}</td>
                          <td><code>{m.field}</code></td>
                          <td style={{ textAlign: 'right', color: '#ef4444' }} className="font-mono">{m.source_value}</td>
                          <td style={{ textAlign: 'right', color: '#16a34a', fontWeight: 600 }} className="font-mono">{m.calculated_value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {attendance_results.mismatches.length > 10 && (
                    <div style={{ fontSize: '11px', color: '#78350f', marginTop: '6px' }}>
                      Showing first 10 of {attendance_results.mismatches.length} mismatches.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Sequential Execution Tasks */}
          <PipelineTasks tasks={tasks} />

          {/* Breakdown Duo Grid: Branch-wise & Session-wise */}
          <div className="aggregates-section" style={{ marginTop: '24px' }}>
            <h3 className="aggregates-heading">
              <BarChart3 size={18} style={{ marginRight: '8px' }} />
              Audited Attendance Breakdowns (Real File Computations)
            </h3>

            <div className="tables-duo-grid">
              {/* Branch-Wise Breakdown */}
              {attendance_results.branch_wise?.length > 0 && (
                <div className="agg-card">
                  <div className="agg-card-header">
                    <div className="agg-card-title">
                      <Building2 size={16} style={{ marginRight: '6px' }} />
                      Branch-Wise Attendance Summary
                    </div>
                    <span className="agg-card-subtitle">{attendance_results.branch_wise.length} Branches</span>
                  </div>
                  <div className="table-responsive">
                    <table className="enterprise-table agg-table">
                      <thead>
                        <tr>
                          <th>Branch</th>
                          <th style={{ textAlign: 'right' }}>Students</th>
                          <th style={{ textAlign: 'right' }}>Attended</th>
                          <th style={{ textAlign: 'right' }}>Conducted</th>
                          <th style={{ textAlign: 'right' }}>Avg Att %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {attendance_results?.branch_wise?.map((b) => (
                          <tr key={b.branch}>
                            <td className="font-semibold">{b.branch}</td>
                            <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(b.student_count)}</td>
                            <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(b.total_attended)}</td>
                            <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(b.total_conducted)}</td>
                            <td style={{ textAlign: 'right' }} className="font-mono font-semibold">
                              <span style={{
                                color: b.avg_attendance_pct >= 75 ? '#16a34a' : b.avg_attendance_pct >= 50 ? '#d97706' : '#dc2626'
                              }}>
                                {b.avg_attendance_pct}%
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Session-Wise Breakdown */}
              {attendance_results.session_wise?.length > 0 && (
                <div className="agg-card">
                  <div className="agg-card-header">
                    <div className="agg-card-title">
                      <Clock size={16} style={{ marginRight: '6px' }} />
                      Session-Wise Marker Distribution
                    </div>
                    <span className="agg-card-subtitle">{attendance_results.session_wise.length} Sessions</span>
                  </div>
                  <div className="table-responsive">
                    <table className="enterprise-table agg-table">
                      <thead>
                        <tr>
                          <th>Session / Slot</th>
                          <th style={{ textAlign: 'right' }}>Present</th>
                          <th style={{ textAlign: 'right' }}>Absent</th>
                          <th style={{ textAlign: 'right' }}>NA</th>
                          <th style={{ textAlign: 'right' }}>Att %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {attendance_results?.session_wise?.map((s) => (
                          <tr key={s.session}>
                            <td className="font-mono font-semibold" style={{ fontSize: '12px' }}>{s.session}</td>
                            <td style={{ textAlign: 'right', color: '#16a34a' }} className="font-mono">{safeFormatNumber(s.present)}</td>
                            <td style={{ textAlign: 'right', color: '#dc2626' }} className="font-mono">{safeFormatNumber(s.absent)}</td>
                            <td style={{ textAlign: 'right', color: '#64748b' }} className="font-mono">{safeFormatNumber(s.not_applicable)}</td>
                            <td style={{ textAlign: 'right' }} className="font-mono font-semibold">
                              {s.attendance_pct}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Vendor-Wise Breakdown if present */}
            {attendance_results.vendor_wise?.length > 0 && (
              <div className="agg-card" style={{ marginTop: '20px' }}>
                <div className="agg-card-header">
                  <div className="agg-card-title">
                    <Briefcase size={16} style={{ marginRight: '6px' }} />
                    Vendor-Wise Student Attendance
                  </div>
                  <span className="agg-card-subtitle">{attendance_results.vendor_wise.length} Vendors</span>
                </div>
                <div className="table-responsive">
                  <table className="enterprise-table agg-table">
                    <thead>
                      <tr>
                        <th>Training Vendor</th>
                        <th style={{ textAlign: 'right' }}>Students</th>
                        <th style={{ textAlign: 'right' }}>Total Attended</th>
                        <th style={{ textAlign: 'right' }}>Total Conducted</th>
                        <th style={{ textAlign: 'right' }}>Avg Attendance %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attendance_results?.vendor_wise?.map((v) => (
                        <tr key={v.vendor}>
                          <td className="font-semibold">{v.vendor}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(v.student_count)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(v.total_attended)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(v.total_conducted)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono font-semibold">
                            {v.avg_attendance_pct}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Full Student-Wise Searchable & Paginated Table */}
            {allStudents.length > 0 && (
              <div className="agg-card" style={{ marginTop: '24px' }}>
                <div className="agg-card-header" style={{ flexWrap: 'wrap', gap: '12px' }}>
                  <div>
                    <div className="agg-card-title">
                      <GraduationCap size={16} style={{ marginRight: '6px' }} />
                      Student-Wise Recalculated Attendance Records
                    </div>
                    <span className="agg-card-subtitle">
                      Showing {safeFormatNumber(filteredStudents?.length)} matching student record{filteredStudents?.length !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Search and Filters */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <div style={{ position: 'relative' }}>
                      <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: '#94a3b8' }} />
                      <input
                        type="text"
                        placeholder="Search name or reg no..."
                        value={searchTerm}
                        onChange={(e) => {
                          setSearchTerm(e.target.value);
                          setCurrentPage(1);
                        }}
                        style={{
                          padding: '6px 10px 6px 30px',
                          fontSize: '12px',
                          borderRadius: '6px',
                          border: '1px solid #cbd5e1',
                          width: '190px'
                        }}
                      />
                    </div>

                    {branches.length > 0 && (
                      <select
                        value={selectedBranchFilter}
                        onChange={(e) => {
                          setSelectedBranchFilter(e.target.value);
                          setCurrentPage(1);
                        }}
                        style={{
                          padding: '6px 10px',
                          fontSize: '12px',
                          borderRadius: '6px',
                          border: '1px solid #cbd5e1',
                          background: '#ffffff',
                          cursor: 'pointer'
                        }}
                      >
                        <option value="ALL">All Branches</option>
                        {branches.map(b => (
                          <option key={b} value={b}>{b}</option>
                        ))}
                      </select>
                    )}

                    <label style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: '#475569', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={onlyLowAttendance}
                        onChange={(e) => {
                          setOnlyLowAttendance(e.target.checked);
                          setCurrentPage(1);
                        }}
                      />
                      Only &lt; 75%
                    </label>
                  </div>
                </div>

                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th style={{ width: '60px' }}>Row</th>
                        <th>Reg. No.</th>
                        <th>Student Name</th>
                        <th>Branch</th>
                        <th style={{ textAlign: 'right' }}>Conducted</th>
                        <th style={{ textAlign: 'right' }}>Attended</th>
                        <th style={{ textAlign: 'right' }}>Att (%)</th>
                        <th style={{ textAlign: 'center' }}>Eligibility Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedStudents.length === 0 ? (
                        <tr>
                          <td colSpan="8" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                            No student records matching your search/filters.
                          </td>
                        </tr>
                      ) : (
                        paginatedStudents.map((st) => {
                          const pct = st.attendance_pct;
                          const isEligible = pct !== null && pct >= 75;
                          const isBorderline = pct !== null && pct >= 50 && pct < 75;

                          return (
                            <tr key={st.row}>
                              <td className="font-mono text-muted">#{st.row}</td>
                              <td className="font-mono font-semibold">{st.registration_number || '—'}</td>
                              <td className="font-semibold">{st.name}</td>
                              <td>{st.branch || '—'}</td>
                              <td style={{ textAlign: 'right' }} className="font-mono">{st.total_conducted}</td>
                              <td style={{ textAlign: 'right' }} className="font-mono">{st.total_attended}</td>
                              <td style={{ textAlign: 'right' }} className="font-mono font-semibold">
                                {pct !== null ? `${pct}%` : 'N/A'}
                              </td>
                              <td style={{ textAlign: 'center' }}>
                                <span style={{
                                  fontSize: '11px',
                                  padding: '2px 8px',
                                  borderRadius: '12px',
                                  fontWeight: 600,
                                  background: isEligible ? '#dcfce7' : isBorderline ? '#fef3c7' : '#fee2e2',
                                  color: isEligible ? '#166534' : isBorderline ? '#b45309' : '#b91c1c'
                                }}>
                                  {isEligible ? 'ELIGIBLE (≥75%)' : isBorderline ? 'SHORTAGE (<75%)' : 'CRITICAL (<50%)'}
                                </span>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Pagination Controls */}
                {totalPages > 1 && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    borderTop: '1px solid #f1f5f9',
                    fontSize: '12px',
                    color: '#64748b'
                  }}>
                    <span>
                      Page {currentPage} of {totalPages} ({filteredStudents.length} records)
                    </span>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={currentPage === 1}
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        style={{ padding: '4px 10px', fontSize: '11px' }}
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={currentPage === totalPages}
                        onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                        style={{ padding: '4px 10px', fontSize: '11px' }}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* ========================================================= */}
      {/* CASE B: SALES PIPELINE DASHBOARD                          */}
      {/* ========================================================= */}
      {!isAttendance && metrics && (
        <>
          {/* KPI Metric Cards */}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Total Sales</span>
                <div className="kpi-icon-wrap icon-green">
                  <DollarSign size={20} />
                </div>
              </div>
              <div className="kpi-value">{formatCurrency(metrics?.total_sales)}</div>
              <div className="kpi-meta">Calculated sum of all valid transactions</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Total Quantity</span>
                <div className="kpi-icon-wrap icon-blue">
                  <Package size={20} />
                </div>
              </div>
              <div className="kpi-value">{safeFormatNumber(metrics?.total_quantity)}</div>
              <div className="kpi-meta">Units sold across all categories</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Transaction Count</span>
                <div className="kpi-icon-wrap icon-indigo">
                  <ShoppingCart size={20} />
                </div>
              </div>
              <div className="kpi-value">{safeFormatNumber(metrics?.transaction_count)}</div>
              <div className="kpi-meta">Verified individual orders in PostgreSQL</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Avg Transaction Value</span>
                <div className="kpi-icon-wrap icon-amber">
                  <TrendingUp size={20} />
                </div>
              </div>
              <div className="kpi-value">{formatCurrency(metrics?.average_transaction_value)}</div>
              <div className="kpi-meta">Total sales ÷ total transaction count</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Validation Score</span>
                <div className="kpi-icon-wrap icon-purple">
                  <CheckCircle size={20} />
                </div>
              </div>
              <div className="kpi-value text-success">{((metrics?.validation_score ?? 100)).toFixed(1)}%</div>
              <div className="kpi-meta">Passed Checks ÷ Total Checks</div>
            </div>
          </div>

          {/* Sequential Tasks Table */}
          <PipelineTasks tasks={tasks} />

          {/* Grouped Aggregation Tables */}
          <div className="aggregates-section">
            <h3 className="aggregates-heading">
              <BarChart3 size={18} style={{ marginRight: '8px' }} />
              PostgreSQL Aggregation Tables (Audited Real Records)
            </h3>

            <div className="tables-duo-grid">
              {/* Sales by City */}
              <div className="agg-card">
                <div className="agg-card-header">
                  <div className="agg-card-title">
                    <MapPin size={16} style={{ marginRight: '6px' }} />
                    Sales by City
                  </div>
                  <span className="agg-card-subtitle">{sales_by_city?.length || 0} Cities</span>
                </div>
                <div className="table-responsive">
                  <table className="enterprise-table agg-table">
                    <thead>
                      <tr>
                        <th>City</th>
                        <th style={{ textAlign: 'right' }}>Total Sales</th>
                        <th style={{ textAlign: 'right' }}>Quantity</th>
                        <th style={{ textAlign: 'right' }}>Transactions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sales_by_city?.map((item) => (
                        <tr key={item.city}>
                          <td className="city-name font-semibold">{item.city}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{formatCurrency(item.total_sales)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(item.total_quantity)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(item.transaction_count)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Sales by Category */}
              <div className="agg-card">
                <div className="agg-card-header">
                  <div className="agg-card-title">
                    <Tag size={16} style={{ marginRight: '6px' }} />
                    Sales by Product Category
                  </div>
                  <span className="agg-card-subtitle">{sales_by_category?.length || 0} Categories</span>
                </div>
                <div className="table-responsive">
                  <table className="enterprise-table agg-table">
                    <thead>
                      <tr>
                        <th>Category</th>
                        <th style={{ textAlign: 'right' }}>Total Sales</th>
                        <th style={{ textAlign: 'right' }}>Quantity</th>
                        <th style={{ textAlign: 'right' }}>Transactions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sales_by_category?.map((item) => (
                        <tr key={item.category}>
                          <td className="font-semibold">{item.category}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{formatCurrency(item.total_sales)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(item.total_quantity)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(item.transaction_count)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Sales by Date */}
            {sales_by_date && sales_by_date.length > 0 && (
              <div className="agg-card" style={{ marginTop: '20px' }}>
                <div className="agg-card-header">
                  <div className="agg-card-title">
                    <Calendar size={16} style={{ marginRight: '6px' }} />
                    Sales by Transaction Date
                  </div>
                  <span className="agg-card-subtitle">{sales_by_date.length} Recorded Dates</span>
                </div>
                <div className="table-responsive">
                  <table className="enterprise-table agg-table">
                    <thead>
                      <tr>
                        <th>Transaction Date</th>
                        <th style={{ textAlign: 'right' }}>Total Sales</th>
                        <th style={{ textAlign: 'right' }}>Quantity</th>
                        <th style={{ textAlign: 'right' }}>Transactions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sales_by_date.map((item) => (
                        <tr key={item.transaction_date}>
                          <td className="font-mono">{item.transaction_date}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{formatCurrency(item.total_sales)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(item.total_quantity)}</td>
                          <td style={{ textAlign: 'right' }} className="font-mono">{safeFormatNumber(item.transaction_count)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
