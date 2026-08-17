import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar 
} from 'recharts';
import api from '../services/api';
import '../styles/main.css';

const DistrictDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [district, setDistrict] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDistrictDetails = async () => {
      try {
        setLoading(true);
        const res = await api.get(`/api/districts/${id}`);
        setDistrict(res.data);
        setLoading(false);
      } catch (err) {
        console.error("Failed to load district detail", err);
        setError(err.response?.data?.detail || "Groundwater information is currently unavailable for this district.");
        setLoading(false);
      }
    };

    fetchDistrictDetails();
  }, [id]);

  if (loading) {
    return (
      <div className="container-inner">
        <div className="skeleton skeleton-title"></div>
        <div className="stats-grid">
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-inner">
        <button className="btn btn-outline" onClick={() => navigate('/districts')} style={{ marginBottom: '20px' }}>
          ← Back to Districts
        </button>
        <div className="alert-box alert-danger">{error}</div>
      </div>
    );
  }

  const latest = district?.groundwater_data?.[0]; // historical sorted desc, index 0 is latest
  const chartData = [...(district?.groundwater_data || [])].reverse(); // reverse to make chronological for charts

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
      <button className="btn btn-outline" onClick={() => navigate('/districts')} style={{ marginBottom: '20px' }}>
        ← Back to Districts
      </button>

      <header className="page-header" style={{ alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">{district?.district_name}</h1>
          <p className="page-subtitle">
            State of {district?.location?.state} • GWRA Assessment Year: {district?.assessment?.year || '2025'} • GW Source: {district?.sources?.gwra || 'N/A'} • Rainfall Source: {district?.sources?.rainfall || 'N/A'}
          </p>
        </div>
        <span className={`badge ${getBadgeClass(district?.assessment?.category)}`} style={{ fontSize: '1.05rem', padding: '8px 18px' }}>
          {district?.assessment?.category || 'Safe'}
        </span>
      </header>

      {/* Numerical Metrics Cards */}
      <section className="stats-grid">
        <div className="card">
          <div className="metric-label">Average Depth to Water Level</div>
          <div className="metric-value">
            {district?.groundwater?.depth_to_water_level_m_bgl !== null && district?.groundwater?.depth_to_water_level_m_bgl !== undefined ? `${district.groundwater.depth_to_water_level_m_bgl.toFixed(2)} m bgl` : 'Data unavailable'}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Average depth to water level below ground level</p>
        </div>

        <div className="card">
          <div className="metric-label">Groundwater Level Indicator</div>
          <div className="metric-value" style={{ color: 'var(--primary-color)' }}>
            {district?.groundwater?.groundwater_level_indicator_percent !== null && district?.groundwater?.groundwater_level_indicator_percent !== undefined ? `${district.groundwater.groundwater_level_indicator_percent.toFixed(2)}%` : 'Data insufficient'}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Normalized indicator derived from groundwater-depth observations and the configured historical reference range. This is a calculated indicator and is not the Stage of Groundwater Extraction.</p>
        </div>

        <div className="card">
          <div className="metric-label">Annual Rainfall</div>
          <div className="metric-value" style={{ color: 'var(--secondary-color)' }}>
            {district?.rainfall?.value_mm !== null && district?.rainfall?.value_mm !== undefined ? `${district.rainfall.value_mm.toFixed(1)} mm` : 'Data unavailable'}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Year: {district?.rainfall?.year || 'N/A'} • Period: {district?.rainfall?.period || 'Annual'}</p>
        </div>

        <div className="card">
          <div className="metric-label">Annual Groundwater Recharge</div>
          <div className="metric-value" style={{ color: '#0ea5e9' }}>
            {district?.resources?.annual_recharge_ham !== null && district?.resources?.annual_recharge_ham !== undefined ? `${district.resources.annual_recharge_ham.toLocaleString(undefined, {maximumFractionDigits: 2})} ham` : 'Data unavailable'}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Annual groundwater recharge (hectare-meters)</p>
        </div>

        <div className="card">
          <div className="metric-label">Annual Extractable Groundwater Resource</div>
          <div className="metric-value" style={{ color: '#2e7d32' }}>
            {district?.resources?.annual_extractable_resource_ham !== null && district?.resources?.annual_extractable_resource_ham !== undefined ? `${district.resources.annual_extractable_resource_ham.toLocaleString(undefined, {maximumFractionDigits: 2})} ham` : 'Data unavailable'}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Annual extractable groundwater resource</p>
        </div>

        <div className="card">
          <div className="metric-label">Annual Groundwater Extraction</div>
          <div className="metric-value" style={{ color: 'var(--color-critical)' }}>
            {district?.resources?.annual_extraction_ham !== null && district?.resources?.annual_extraction_ham !== undefined ? `${district.resources.annual_extraction_ham.toLocaleString(undefined, {maximumFractionDigits: 2})} ham` : 'Data unavailable'}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Annual groundwater extraction</p>
        </div>

        <div className="card">
          <div className="metric-label">Stage of Groundwater Extraction</div>
          <div className="metric-value" style={{ color: '#f57c00' }}>
            {district?.resources?.stage_of_extraction_percent !== null && district?.resources?.stage_of_extraction_percent !== undefined ? `${district.resources.stage_of_extraction_percent.toFixed(2)}%` : 'Data unavailable'}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Percentage of annual extractable groundwater resource being extracted</p>
        </div>

        <div className="card">
          <div className="metric-label">Net Groundwater Availability for Future Use</div>
          <div className="metric-value" style={{ color: '#1b6ca8' }}>
            {district?.resources?.net_groundwater_availability_ham !== null && district?.resources?.net_groundwater_availability_ham !== undefined ? `${district.resources.net_groundwater_availability_ham.toLocaleString(undefined, {maximumFractionDigits: 2})} ham` : 'Data unavailable'}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Groundwater resource available for future use according to the assessment methodology.</p>
        </div>
      </section>

      {/* Historical Trend Charts */}
      <section className="data-grid-2">
        {/* Groundwater capacity chart */}
        <div className="card">
          <h3 className="card-title">Depth to Water Level Trend</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
            Historical depth to water level records (m bgl).
          </p>
          <div style={{ minHeight: '260px' }}>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" />
                <YAxis label={{ value: 'Depth (m bgl)', angle: -90, position: 'insideLeft' }} />
                <Tooltip />
                <Area type="monotone" dataKey="depth_to_water_level_m_bgl" stroke="var(--primary-color)" fill="rgba(27, 108, 168, 0.15)" name="Depth (m bgl)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Rainfall history chart */}
        <div className="card">
          <h3 className="card-title">Precipitation history</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
            Annual rainfall volumes recorded in mm.
          </p>
          <div style={{ minHeight: '260px' }}>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" />
                <YAxis label={{ value: 'Rainfall (mm)', angle: -90, position: 'insideLeft' }} />
                <Tooltip />
                <Bar dataKey="rainfall_mm" fill="var(--secondary-color)" name="Rainfall (mm)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

    </div>
  );
};

export default DistrictDetails;
