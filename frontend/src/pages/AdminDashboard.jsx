import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import '../styles/main.css';

const AdminDashboard = () => {
  const [stats, setStats] = useState(null);
  const [userLogs, setUserLogs] = useState([]);
  const [queryLogs, setQueryLogs] = useState([]);
  const [accessStats, setAccessStats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const fetchAdminData = async () => {
    try {
      setLoading(true);
      const [statsRes, usersRes, queriesRes, accessRes] = await Promise.all([
        api.get('/api/admin/statistics'),
        api.get('/api/admin/users'),
        api.get('/api/admin/queries'),
        api.get('/api/admin/access-statistics')
      ]);
      setStats(statsRes.data);
      setUserLogs(usersRes.data);
      setQueryLogs(queriesRes.data);
      setAccessStats(accessRes.data);
      setLoading(false);
    } catch (err) {
      console.error("Failed to load admin logs", err);
      setError("Forbidden: Access restricted to administrators only.");
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const handleExportExcel = async () => {
    try {
      setExporting(true);
      const response = await api.get('/api/admin/export-excel', {
        responseType: 'blob'
      });
      
      // Create local file blob URL and trigger download in browser
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'ingres_ai_admin_report.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      setExporting(false);
    } catch (err) {
      console.error("Export Excel failed", err);
      alert("Failed to export Excel report. Please try again.");
      setExporting(false);
    }
  };

  const getFormatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const d = new Date(dateString);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return (
      <div className="container-inner">
        <div className="skeleton skeleton-title"></div>
        <div className="stats-grid">
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-inner">
        <div className="alert-box alert-danger">{error}</div>
      </div>
    );
  }

  return (
    <div className="container-inner">
      <header className="page-header">
        <div>
          <h1 className="page-title">Admin Dashboard</h1>
          <p className="page-subtitle">Oversee registered users, track query logs, and extract Excel survey reports.</p>
        </div>
        <button 
          className="btn btn-secondary" 
          onClick={handleExportExcel}
          disabled={exporting}
          style={{ padding: '12px 25px' }}
        >
          {exporting ? 'Generating Excel...' : 'Export Data to Excel 📥'}
        </button>
      </header>

      {/* Summary Cards */}
      <section className="stats-grid">
        <div className="card">
          <div className="metric-label">Total Users</div>
          <div className="metric-value">{stats?.total_users}</div>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Registered analysts</span>
        </div>

        <div className="card">
          <div className="metric-label">Total AI Queries</div>
          <div className="metric-value">{stats?.total_queries}</div>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Chat queries processed</span>
        </div>

        <div className="card">
          <div className="metric-label">Districts Searched</div>
          <div className="metric-value">{stats?.districts_accessed}</div>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Unique districts looked up</span>
        </div>

        <div className="card">
          <div className="metric-label">Most Viewed District</div>
          <div className="metric-value" style={{ fontSize: '1.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {stats?.most_viewed_district || 'None'}
          </div>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Views: {stats?.most_viewed_district_views || 0}
          </span>
        </div>
      </section>

      {/* User management and statistics */}
      <section className="data-grid-2">
        {/* District Access stats */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h3 className="card-title">🔍 District Access Statistics</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
            Metrics showing total hits versus unique user lookups per district.
          </p>
          <div className="table-wrapper" style={{ margin: 0, maxHeight: '350px', overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>District</th>
                  <th>State</th>
                  <th>Total Views</th>
                  <th>Unique Users</th>
                </tr>
              </thead>
              <tbody>
                {accessStats.map((item, idx) => (
                  <tr key={idx}>
                    <td><strong>{item.district_name}</strong></td>
                    <td>{item.state_name}</td>
                    <td>{item.total_views}</td>
                    <td>{item.unique_users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* User list */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h3 className="card-title">👥 Registered Users</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
            List of analyst accounts and total query volume created.
          </p>
          <div className="table-wrapper" style={{ margin: 0, maxHeight: '350px', overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Queries</th>
                </tr>
              </thead>
              <tbody>
                {userLogs.map((u) => (
                  <tr key={u.id}>
                    <td><strong>{u.name}</strong></td>
                    <td>{u.email}</td>
                    <td><span className="badge badge-safe" style={{ color: u.role === 'ADMIN' ? 'var(--color-critical)' : 'var(--primary-color)' }}>{u.role}</span></td>
                    <td>{u.queries_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Global query log tracker */}
      <section className="card" style={{ marginTop: '25px' }}>
        <h3 className="card-title">📜 System Query Activity Log</h3>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
          Real-time tracking of questions sent to the virtual assistant.
        </p>
        <div className="table-wrapper" style={{ maxHeight: '350px', overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Time Mapped</th>
                <th>Analyst Name</th>
                <th>Query Question</th>
                <th>Referenced District</th>
              </tr>
            </thead>
            <tbody>
              {queryLogs.map((q) => (
                <tr key={q.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{getFormatDate(q.created_at)}</td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{q.username}</div>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{q.email}</span>
                  </td>
                  <td>
                    <div style={{ maxWidth: '350px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={q.query}>
                      {q.query}
                    </div>
                  </td>
                  <td>
                    {q.district_name !== 'N/A' ? (
                      <span
                        className="badge badge-safe"
                        style={{
                          backgroundColor: 'rgba(46, 125, 50, 0.1)',
                          cursor: q.district_id ? 'pointer' : 'default',
                          textDecoration: q.district_id ? 'underline' : 'none',
                        }}
                        onClick={() => q.district_id && navigate(`/districts/${q.district_id}`)}
                        title={q.district_id ? `View details for ${q.district_name}` : q.district_name}
                      >
                        {q.district_name}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>None</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default AdminDashboard;
