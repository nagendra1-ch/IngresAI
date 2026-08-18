import React, { useState, useEffect } from 'react';
import api from '../services/api';
import MarkdownRenderer from '../utils/MarkdownRenderer';
import '../styles/main.css';

const QueryHistory = () => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedLog, setSelectedLog] = useState(null); // For detailed view modal
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        setLoading(true);
        const res = await api.get('/api/ai/history');
        setHistory(res.data);
        setLoading(false);
      } catch (err) {
        console.error("Failed to load history list", err);
        setError("Unable to retrieve query history.");
        setLoading(false);
      }
    };

    fetchHistory();
  }, []);

  // Filter history items locally based on search terms
  const filteredHistory = history.filter((item) => {
    const term = searchTerm.toLowerCase();
    return (
      item.query.toLowerCase().includes(term) ||
      item.response.toLowerCase().includes(term) ||
      (item.district?.district_name && item.district.district_name.toLowerCase().includes(term))
    );
  });

  const getFormatDate = (dateString) => {
    if (!dateString) return '';
    const d = new Date(dateString);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };


  return (
    <div className="container-inner">
      <header className="page-header">
        <div>
          <h1 className="page-title">My Query History</h1>
          <p className="page-subtitle">A collection of your natural language assistant queries and responses.</p>
        </div>
      </header>

      {/* Filter Toolbar */}
      <section className="card" style={{ marginBottom: '25px', padding: '15px 20px' }}>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
          <span style={{ fontSize: '1.2rem' }}>🔍</span>
          <input
            type="text"
            className="form-control"
            placeholder="Search query text, district or AI responses..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ border: 'none', padding: '8px', fontSize: '0.95rem' }}
          />
        </div>
      </section>

      {error && <div className="alert-box alert-danger">{error}</div>}

      {/* Table Results */}
      {loading ? (
        <div className="skeleton-card" style={{ height: '300px' }}></div>
      ) : filteredHistory.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon">📜</div>
          <p>No queries found. Type a question in the AI Assistant page to log searches.</p>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Date & Time</th>
                <th>Query</th>
                <th>Associated District</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.map((item) => (
                <tr key={item.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{getFormatDate(item.created_at)}</td>
                  <td>
                    <div style={{
                      maxWidth: '300px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {item.query}
                    </div>
                  </td>
                  <td>
                    {item.district ? (
                      <strong>{item.district.district_name} ({item.district.state_name})</strong>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>General Survey</span>
                    )}
                  </td>
                  <td>
                    <span className="badge badge-safe" style={{ backgroundColor: 'rgba(27, 108, 168, 0.1)', color: 'var(--primary-color)' }}>
                      Completed
                    </span>
                  </td>
                  <td>
                    <button className="btn btn-outline" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={() => setSelectedLog(item)}>
                      View Response
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detailed Modal Overlay */}
      {selectedLog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px'
        }} onClick={() => setSelectedLog(null)}>
          <div className="card" style={{
            width: '100%',
            maxWidth: '650px',
            maxHeight: '85vh',
            overflowY: 'auto',
            backgroundColor: 'var(--surface-color)',
            position: 'relative'
          }} onClick={(e) => e.stopPropagation()}>
            
            <button style={{
              position: 'absolute',
              top: '15px',
              right: '20px',
              background: 'transparent',
              border: 'none',
              fontSize: '1.4rem',
              cursor: 'pointer',
              color: 'var(--text-muted)'
            }} onClick={() => setSelectedLog(null)}>
              &times;
            </button>
 
            <h3 className="card-title" style={{ color: 'var(--primary-color)', fontSize: '1.3rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '10px', marginBottom: '20px' }}>
              Query Record Details
            </h3>
 
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Date Mapped</div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-main)' }}>{getFormatDate(selectedLog.created_at)}</p>
            </div>
 
            <div style={{ marginBottom: '20px', backgroundColor: 'var(--surface-secondary)', padding: '15px', borderRadius: 'var(--border-radius-sm)', borderLeft: '3px solid var(--primary-color)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600, marginBottom: '5px' }}>User Query</div>
              <p style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-main)' }}>"{selectedLog.query}"</p>
            </div>
 
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600, marginBottom: '8px' }}>INGRES AI Assistant Response</div>
              <div style={{
                backgroundColor: 'var(--surface-secondary)',
                padding: '20px',
                borderRadius: 'var(--border-radius-sm)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-color)',
              }}>
                <MarkdownRenderer text={selectedLog.response} />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button className="btn btn-primary" onClick={() => setSelectedLog(null)}>
                Close Window
              </button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

export default QueryHistory;
