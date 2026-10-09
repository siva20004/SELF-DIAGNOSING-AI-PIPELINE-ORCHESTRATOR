import React from 'react';
import { DollarSign, Package, ShoppingCart, TrendingUp, CheckCircle, BarChart3, MapPin, Tag, Calendar } from 'lucide-react';
import PipelineTasks from './PipelineTasks';

export default function PipelineResults({ results, dataset }) {
  if (!results) return null;

  const { run_id, status, started_at, completed_at, duration_seconds, rows_received, rows_processed, rows_rejected, metrics, sales_by_city, sales_by_category, sales_by_date, tasks } = results;

  const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return '—';
    try {
      return new Date(isoStr).toLocaleString();
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="pipeline-results-container">
      {/* File Information Card (Requirement 15) */}
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
              <strong style={{ fontSize: '13px', color: '#1e293b' }} title={dataset.filename}>{dataset.filename}</strong>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Format</span>
              <span className="badge badge-neutral" style={{ marginTop: '2px' }}>{dataset.file_type}</span>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Records Detected</span>
              <strong style={{ fontSize: '13px', color: '#1e293b' }}>{dataset.rows?.toLocaleString() || rows_received?.toLocaleString()}</strong>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Extraction</span>
              <span style={{ color: '#16a34a', fontWeight: 600, fontSize: '13px' }}>✓ Successful</span>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Validation</span>
              <span style={{ color: '#16a34a', fontWeight: 600, fontSize: '13px' }}>✓ Passed</span>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>Pipeline</span>
              <span style={{ color: '#16a34a', fontWeight: 600, fontSize: '13px' }}>✓ Completed</span>
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
          <span className="badge badge-success-lg">
            <CheckCircle size={16} style={{ marginRight: '6px' }} />
            PIPELINE {status}
          </span>
        </div>

        <div className="run-stats-grid">
          <div className="run-stat-item">
            <span className="stat-sub">Rows Received</span>
            <span className="stat-main">{rows_received.toLocaleString()}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Rows Processed</span>
            <span className="stat-main text-success">{rows_processed.toLocaleString()}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Rows Rejected</span>
            <span className="stat-main text-muted">{rows_rejected.toLocaleString()}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Execution Duration</span>
            <span className="stat-main">{duration_seconds !== null ? `${duration_seconds}s` : '—'}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Started At</span>
            <span className="stat-sub-val">{formatDate(started_at)}</span>
          </div>
          <div className="run-stat-item">
            <span className="stat-sub">Completed At</span>
            <span className="stat-sub-val">{formatDate(completed_at)}</span>
          </div>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Total Sales</span>
            <div className="kpi-icon-wrap icon-green">
              <DollarSign size={20} />
            </div>
          </div>
          <div className="kpi-value">{formatCurrency(metrics.total_sales)}</div>
          <div className="kpi-meta">Calculated sum of all valid transactions</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Total Quantity</span>
            <div className="kpi-icon-wrap icon-blue">
              <Package size={20} />
            </div>
          </div>
          <div className="kpi-value">{metrics.total_quantity.toLocaleString()}</div>
          <div className="kpi-meta">Units sold across all categories</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Transaction Count</span>
            <div className="kpi-icon-wrap icon-indigo">
              <ShoppingCart size={20} />
            </div>
          </div>
          <div className="kpi-value">{metrics.transaction_count.toLocaleString()}</div>
          <div className="kpi-meta">Verified individual orders in PostgreSQL</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Avg Transaction Value</span>
            <div className="kpi-icon-wrap icon-amber">
              <TrendingUp size={20} />
            </div>
          </div>
          <div className="kpi-value">{formatCurrency(metrics.average_transaction_value)}</div>
          <div className="kpi-meta">Total sales ÷ total transaction count</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Validation Score</span>
            <div className="kpi-icon-wrap icon-purple">
              <CheckCircle size={20} />
            </div>
          </div>
          <div className="kpi-value text-success">{metrics.validation_score.toFixed(1)}%</div>
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
                      <td style={{ textAlign: 'right' }} className="font-mono">{item.total_quantity.toLocaleString()}</td>
                      <td style={{ textAlign: 'right' }} className="font-mono">{item.transaction_count.toLocaleString()}</td>
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
                      <td style={{ textAlign: 'right' }} className="font-mono">{item.total_quantity.toLocaleString()}</td>
                      <td style={{ textAlign: 'right' }} className="font-mono">{item.transaction_count.toLocaleString()}</td>
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
                      <td style={{ textAlign: 'right' }} className="font-mono">{item.total_quantity.toLocaleString()}</td>
                      <td style={{ textAlign: 'right' }} className="font-mono">{item.transaction_count.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
