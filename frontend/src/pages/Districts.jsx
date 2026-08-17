import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import '../styles/main.css';

const Districts = () => {
  const [districts, setDistricts] = useState([]);
  const [states, setStates] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedState, setSelectedState] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchDistricts = async () => {
      try {
        setLoading(true);
        // Call the search endpoint with filters
        const res = await api.get('/api/districts/search');
        setDistricts(res.data);
        
        // Extract unique state list
        const uniqueStates = [...new Set(res.data.map(d => d.state_name))].sort();
        setStates(uniqueStates);
        
        setLoading(false);
      } catch (err) {
        console.error("Failed to load districts", err);
        setError("Unable to retrieve groundwater data. Please try again later.");
        setLoading(false);
      }
    };

    fetchDistricts();
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      const params = {};
      if (searchTerm) params.query = searchTerm;
      if (selectedState) params.state = selectedState;
      
      const res = await api.get('/api/districts/search', { params });
      setDistricts(res.data);
      setLoading(false);
    } catch (err) {
      setError("Failed to execute search.");
      setLoading(false);
    }
  };

  const handleCardClick = (id) => {
    navigate(`/districts/${id}`);
  };

  const getBadgeClass = (category) => {
    if (!category) return '';
    const cat = category.toLowerCase();
    if (cat === 'safe') return 'badge-safe';
    if (cat === 'semi-critical') return 'badge-semi-critical';
    if (cat === 'critical') return 'badge-critical';
    if (cat === 'over-exploited') return 'badge-over-exploited';
    return '';
  };

  return (
    <div className="container-inner">
      <header className="page-header">
        <div>
          <h1 className="page-title">District Search</h1>
          <p className="page-subtitle">Search groundwater levels and rainfall parameters across Indian districts.</p>
        </div>
      </header>

      {/* Search Filters Card */}
      <section className="card" style={{ marginBottom: '30px' }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '15px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ flex: 2, minWidth: '250px', margin: 0 }}>
            <label className="form-label" htmlFor="district-search-input">District Name</label>
            <input
              id="district-search-input"
              type="text"
              className="form-control"
              placeholder="Search e.g. Ananthapuramu"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="form-group" style={{ flex: 1, minWidth: '180px', margin: 0 }}>
            <label className="form-label" htmlFor="state-select">State / UT</label>
            <select
              id="state-select"
              className="form-select"
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
            >
              <option value="">All States</option>
              {states.map((s, idx) => (
                <option key={idx} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <button type="submit" className="btn btn-primary" style={{ padding: '12px 30px' }}>
            Filter Results
          </button>
        </form>
      </section>

      {error && <div className="alert-box alert-danger">{error}</div>}

      {/* Districts List Results */}
      {loading ? (
        <div className="stats-grid">
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
        </div>
      ) : districts.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon">🔍</div>
          <p>No groundwater data available for these search parameters.</p>
        </div>
      ) : (
        <section className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          {districts.map((d) => (
            <div 
              key={d.id} 
              className="card" 
              onClick={() => handleCardClick(d.id)}
              style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '10px' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <h3 className="card-title" style={{ margin: 0, fontSize: '1.2rem' }}>{d.district_name}</h3>
                <span className={`badge ${getBadgeClass(d.assessment_category)}`}>
                  {d.assessment_category || 'Unknown'}
                </span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>State: {d.state_name}</p>
              
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '10px', marginTop: '5px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>GW Depth</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--primary-color)' }}>
                    {d.depth_to_water_level_m_bgl !== null && d.depth_to_water_level_m_bgl !== undefined ? `${d.depth_to_water_level_m_bgl.toFixed(2)} m` : 'N/A'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Rainfall</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--secondary-color)' }}>
                    {d.rainfall_mm !== null && d.rainfall_mm !== undefined ? `${d.rainfall_mm.toFixed(0)} mm` : 'N/A'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Extraction</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#f57c00' }}>
                    {d.stage_of_groundwater_extraction_percent !== null && d.stage_of_groundwater_extraction_percent !== undefined ? `${d.stage_of_groundwater_extraction_percent.toFixed(1)}%` : 'N/A'}
                  </div>
                </div>
              </div>

            </div>
          ))}
        </section>
      )}
    </div>
  );
};

export default Districts;
