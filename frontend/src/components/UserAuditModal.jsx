import React, { useState, useEffect } from 'react';
import { Users, Activity, Eye, ShieldCheck, Clock, RefreshCw, Calendar, Globe, Hash } from 'lucide-react';
import { getUserActivities } from '../services/api';
import { formatIST } from '../utils/dateUtils';

export default function UserAuditModal({ isOpen, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getUserActivities(100);
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to fetch user activity audit from database.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStats();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="audit-modal-overlay" onClick={onClose}>
      <div className="audit-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="audit-modal-header">
          <div className="audit-title-block">
            <Users size={20} className="audit-icon-primary" />
            <div>
              <h2 className="audit-title">User Access & Authentication Audit</h2>
              <p className="audit-subtitle">
                Persisted live in PostgreSQL / Neon — Track visits, login frequencies, and audit timestamps
              </p>
            </div>
          </div>
          <div className="audit-actions">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={fetchStats}
              disabled={loading}
              title="Refresh Audit Data"
            >
              <RefreshCw size={13} className={loading ? 'spin-icon' : ''} style={{ marginRight: '4px' }} />
              Refresh
            </button>
            <button type="button" className="btn-close-modal" onClick={onClose}>
              &times;
            </button>
          </div>
        </div>

        {error && (
          <div className="audit-error-banner">
            <span>{error}</span>
          </div>
        )}

        {/* KPI Cards */}
        {data && (
          <div className="audit-kpis-grid">
            <div className="audit-kpi-card">
              <div className="audit-kpi-label">Registered Users</div>
              <div className="audit-kpi-value">{data.total_users}</div>
              <div className="audit-kpi-meta">Accounts in Neon Database</div>
            </div>
            <div className="audit-kpi-card">
              <div className="audit-kpi-label">Total Logins Recorded</div>
              <div className="audit-kpi-value text-blue">{data.total_logins}</div>
              <div className="audit-kpi-meta">Verified Password Sessions</div>
            </div>
            <div className="audit-kpi-card">
              <div className="audit-kpi-label">Total Visits Logged</div>
              <div className="audit-kpi-value text-green">{data.total_visits}</div>
              <div className="audit-kpi-meta">Website & Session Visits</div>
            </div>
            <div className="audit-kpi-card">
              <div className="audit-kpi-label">Session Lifespan</div>
              <div className="audit-kpi-value text-amber">30 Mins</div>
              <div className="audit-kpi-meta">Mandatory Re-Login Window</div>
            </div>
          </div>
        )}

        {/* Section 1: User Account Breakdown */}
        <div className="audit-section">
          <h3 className="audit-section-heading">
            <Users size={15} style={{ marginRight: '6px' }} />
            User Login Frequency & Visit Breakdown
          </h3>
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>User ID</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Country</th>
                  <th>Logins</th>
                  <th>Visits</th>
                  <th>Last Login (IST)</th>
                  <th>Last Visit (IST)</th>
                  <th>Client IP</th>
                </tr>
              </thead>
              <tbody>
                {data && data.users && data.users.length > 0 ? (
                  data.users.map((u) => (
                    <tr key={u.id}>
                      <td className="font-mono">#{u.id}</td>
                      <td className="font-semibold">{u.first_name} {u.last_name}</td>
                      <td>{u.email}</td>
                      <td>{u.country || 'N/A'}</td>
                      <td>
                        <span className="badge badge-primary">{u.login_count || 0} times</span>
                      </td>
                      <td>
                        <span className="badge badge-meta">{u.visit_count || 0} visits</span>
                      </td>
                      <td className="text-muted font-mono text-xs">
                        {formatIST(u.last_login_at)}
                      </td>
                      <td className="text-muted font-mono text-xs">
                        {formatIST(u.last_visit_at)}
                      </td>
                      <td className="font-mono text-xs">{u.last_ip || 'Local/Cloud'}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={9} className="text-center py-4 text-muted">
                      {loading ? 'Querying PostgreSQL / Neon...' : 'No users registered yet.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 2: Detailed Live Activity Audit Trail */}
        <div className="audit-section">
          <h3 className="audit-section-heading">
            <Activity size={15} style={{ marginRight: '6px' }} />
            Recent Live User Activities (Persisted in Neon Table: `user_activities`)
          </h3>
          <div className="audit-table-wrap" style={{ maxHeight: '250px' }}>
            <table className="audit-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>User / Email</th>
                  <th>Timestamp (IST)</th>
                  <th>IP Address</th>
                  <th>Page / Route</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {data && data.recent_activities && data.recent_activities.length > 0 ? (
                  data.recent_activities.map((act) => (
                    <tr key={act.id}>
                      <td className="font-mono text-xs">#{act.id}</td>
                      <td>
                        <span className={`badge ${
                          act.activity_type.includes('LOGIN')
                            ? 'badge-success'
                            : act.activity_type === 'SESSION_EXPIRED'
                            ? 'badge-warning'
                            : act.activity_type === 'LOGOUT'
                            ? 'badge-meta'
                            : 'badge-info'
                        }`}>
                          {act.activity_type}
                        </span>
                      </td>
                      <td>
                        <div className="font-semibold text-xs">{act.user_name || 'Anonymous'}</div>
                        <div className="text-muted text-xs">{act.email || '—'}</div>
                      </td>
                      <td className="font-mono text-xs text-muted">
                        {formatIST(act.timestamp)}
                      </td>
                      <td className="font-mono text-xs">{act.ip_address || '127.0.0.1'}</td>
                      <td className="font-mono text-xs">{act.page_url || '/'}</td>
                      <td className="font-mono text-xs text-muted">{act.details_json || '—'}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="text-center py-4 text-muted">
                      {loading ? 'Loading real audit entries...' : 'No activity records found.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="audit-modal-footer">
          <div className="audit-footer-notice">
            <ShieldCheck size={14} style={{ marginRight: '5px', color: '#10b981' }} />
            All visits and logins are persisted real-time to PostgreSQL / Neon with 30-minute session expiration.
          </div>
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
