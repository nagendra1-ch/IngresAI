import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, 
  PieChart, Pie, Cell, ResponsiveContainer 
} from 'recharts';
import api from '../services/api';
import ErrorBoundary from '../components/ErrorBoundary';
import '../styles/main.css';
import WeatherCard from '../components/WeatherCard';
import '../utils/weatherIconMap';
import '../styles/forecast.css';

const COLORS = ['#2e7d32', '#f57c00', '#d32f2f', '#880e4f']; // safe, semi-critical, critical, over-exploited

const Dashboard = () => {
  const [summary, setSummary] = useState(null);
  const [stateStats, setStateStats] = useState([]);
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rainfallForecast, setRainfallForecast] = useState(null);
  
  // Filtering States
  const [selectedState, setSelectedState] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [statesList, setStatesList] = useState([]);
  const [districtsList, setDistrictsList] = useState([]);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [summaryRes, stateRes] = await Promise.all([
          api.get('/api/dashboard/summary'),
          api.get('/api/dashboard/state-statistics')
        ]);
        setSummary(summaryRes.data);
        setStateStats(stateRes.data);
        
        // Populate unique states list
        const uniqueStates = stateRes.data
          .map(s => s.state_name)
          .filter(Boolean)
          .sort((a, b) => a.localeCompare(b));
        setStatesList(uniqueStates);
        
        setLoading(false);
      } catch (err) {
        console.error("Dashboard loading failed", err);
        setError("Unable to retrieve groundwater information. Please try again later.");
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  const handleStateChange = async (state) => {
    setSelectedState(state);
    setSelectedDistrict('');
    setDistrictsList([]);
    setLoading(true);
    try {
      if (state) {
        const [summaryRes, distRes] = await Promise.all([
          api.get(`/api/dashboard/summary?state_name=${encodeURIComponent(state)}`),
          api.get(`/api/dashboard/state-statistics?state_name=${encodeURIComponent(state)}`)
        ]);
        setSummary(summaryRes.data);
        setStateStats(distRes.data);
        
        const districts = distRes.data
          .map(d => d.district_name)
          .filter(Boolean)
          .sort((a, b) => a.localeCompare(b));
        setDistrictsList(districts);
      } else {
        await handleReset();
      }
      setLoading(false);
    } catch (err) {
      console.error("Failed to filter by state", err);
      setError("Unable to filter statistics. Please try again.");
      setLoading(false);
    }
  };

  const handleDistrictChange = async (district) => {
    setSelectedDistrict(district);
    setLoading(true);
    try {
      if (district) {
        const summaryRes = await api.get(
          `/api/dashboard/summary?state_name=${encodeURIComponent(selectedState)}&district_name=${encodeURIComponent(district)}`
        );
        setSummary(summaryRes.data);
        // fetch weather for district
        try {
          const weatherRes = await api.get(`/api/weather/district/${encodeURIComponent(district)}`);
          setWeather(weatherRes.data);
        } catch (wErr) {
          console.warn('Weather fetch failed', wErr);
          setWeather(null);
        }
      } else {
        const summaryRes = await api.get(`/api/dashboard/summary?state_name=${encodeURIComponent(selectedState)}`);
        setSummary(summaryRes.data);
        setWeather(null);
      }
      // Also fetch rainfall forecast strip data
      if (district) {
        try {
          const forecastRes = await api.get(`/api/weather/forecast/${encodeURIComponent(district)}`);
          setRainfallForecast(forecastRes.data);
        } catch (fErr) {
          console.warn('Forecast fetch failed', fErr);
          setRainfallForecast(null);
        }
      } else {
        setRainfallForecast(null);
      }
      setLoading(false);
    } catch (err) {
      console.error("Failed to filter by district", err);
      setError("Unable to filter statistics. Please try again.");
      setWeather(null);
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setSelectedState('');
    setSelectedDistrict('');
    setDistrictsList([]);
    setWeather(null);
    setLoading(true);
    try {
      const [summaryRes, stateRes] = await Promise.all([
        api.get('/api/dashboard/summary'),
        api.get('/api/dashboard/state-statistics')
      ]);
      setSummary(summaryRes.data);
      setStateStats(stateRes.data);
      setLoading(false);
    } catch (err) {
      console.error("Failed to reset dashboard data", err);
      setError("Unable to load dashboard. Please try again.");
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container-inner">
        <div className="page-header">
          <div className="skeleton skeleton-title"></div>
        </div>
        <div className="stats-grid">
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
          <div className="skeleton skeleton-card"></div>
        </div>
        <div className="data-grid-2">
          <div className="skeleton" style={{ height: '300px' }}></div>
          <div className="skeleton" style={{ height: '300px' }}></div>
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

  // Map category data for PieChart
  const pieData = summary?.category_distribution?.map((item) => ({
    name: item.category,
    value: item.count
  })) || [];

  return (
    <div className="container-inner">
      <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px', marginBottom: '30px' }}>
        <div>
          <h1 className="page-title">India Groundwater Dashboard</h1>
          <p className="page-subtitle" style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>
            {selectedDistrict 
              ? `Groundwater resource metrics for ${selectedDistrict} District, ${selectedState}.` 
              : selectedState 
                ? `Groundwater resource metrics for ${selectedState} State.` 
                : 'National survey summaries, rainfall distributions, and district assessments.'}
          </p>
        </div>
        
        {/* Weather Card */}
        {weather && (
          <WeatherCard
            location={weather.location || selectedDistrict || 'India'}
            current={weather.current}
            forecast={weather.forecast}
            updatedAt={weather.updated_at || weather.updatedAt}
          />
        )}
        
        {/* Filtering Controls */}
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>Filter by State</label>
            <select 
              value={selectedState} 
              onChange={(e) => handleStateChange(e.target.value)}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', outline: 'none', background: 'white', minWidth: '180px', cursor: 'pointer', fontFamily: 'inherit' }}
            >
              <option value="">All States (National)</option>
              {statesList.map(state => (
                <option key={state} value={state}>{state}</option>
              ))}
            </select>
          </div>

          {selectedState && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>Filter by District</label>
              <select 
                value={selectedDistrict} 
                onChange={(e) => handleDistrictChange(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', outline: 'none', background: 'white', minWidth: '180px', cursor: 'pointer', fontFamily: 'inherit' }}
              >
                <option value="">All Districts in {selectedState}</option>
                {districtsList.map(dist => (
                  <option key={dist} value={dist}>{dist}</option>
                ))}
              </select>
            </div>
          )}

          {(selectedState || selectedDistrict) && (
            <button 
              onClick={handleReset}
              style={{ alignSelf: 'flex-end', padding: '8px 16px', borderRadius: '6px', border: '1px solid var(--color-critical)', color: 'var(--color-critical)', background: 'white', fontWeight: 'bold', cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', height: '37px', fontFamily: 'inherit' }}
              onMouseOver={(e) => { e.target.style.background = 'var(--color-critical)'; e.target.style.color = 'white'; }}
              onMouseOut={(e) => { e.target.style.background = 'white'; e.target.style.color = 'var(--color-critical)'; }}
            >
              Reset Filters
            </button>
          )}
        </div>
      </header>

      {/* Summary Cards Grid */}
      <section className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        <div className="card">
          <div className="metric-label">Mapped Districts</div>
          <div className="metric-value">{summary?.total_districts}</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {selectedState ? `In ${selectedState}` : 'In database'}
          </div>
        </div>
        <div className="card">
          <div className="metric-label">Represented States</div>
          <div className="metric-value">{summary?.total_states}</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>States represented</div>
        </div>
        <div className="card">
          <div className="metric-label">Avg Depth to Water Level</div>
          <div className="metric-value" style={{ color: 'var(--primary-color)' }}>
            {summary?.avg_groundwater_level} m bgl
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Mean depth below ground level</div>
        </div>
        <div className="card">
          <div className="metric-label">Avg Stage of Extraction</div>
          <div className="metric-value" style={{ color: 'var(--color-critical)' }}>
            {summary?.avg_stage_of_extraction}%
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Mean annual draft vs recharge</div>
        </div>
        <div className="card">
          <div className="metric-label">Avg Rainfall</div>
          <div className="metric-value" style={{ color: 'var(--secondary-color)' }}>
            {summary?.avg_rainfall} mm
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Annual average deviation</div>
        </div>
      </section>

      {/* Live Rainfall Forecast Strip */}
      {rainfallForecast && selectedDistrict && (
        <section className="rainfall-strip" style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginRight: '12px' }}>
            <span className="live-indicator">LIVE</span>
            <strong style={{ fontSize: '0.88rem', color: 'var(--text-main)' }}>Rainfall Status — {selectedDistrict}</strong>
          </div>
          <div className="strip-item">
            <span className="strip-value" style={{ color: '#0ea5e9' }}>
              {rainfallForecast.current_rainfall_mm ?? 0} mm
            </span>
            <span className="strip-label">Current Precip</span>
          </div>
          <div className="strip-item">
            <span className="strip-value">
              {rainfallForecast.daily_forecast?.[0]?.precipitation_sum?.toFixed(1) ?? '--'} mm
            </span>
            <span className="strip-label">Today Forecast</span>
          </div>
          <div className="strip-item">
            <span className="strip-value">
              {rainfallForecast.daily_forecast?.[1]?.precipitation_sum?.toFixed(1) ?? '--'} mm
            </span>
            <span className="strip-label">Tomorrow</span>
          </div>
          <div className="strip-item">
            <span className="strip-value" style={{ color: 'var(--secondary-color)' }}>
              {rainfallForecast.forecast_total_rain_mm?.toFixed(1) ?? '--'} mm
            </span>
            <span className="strip-label">7-Day Total</span>
          </div>
          {rainfallForecast.groundwater_impact && (
            <div className="strip-item">
              <span className="strip-value" style={{ color: rainfallForecast.groundwater_impact.recharge_potential === 'High' ? 'var(--color-safe)' : rainfallForecast.groundwater_impact.recharge_potential === 'Moderate' ? '#0ea5e9' : 'var(--color-semi-critical)' }}>
                {rainfallForecast.groundwater_impact.recharge_potential}
              </span>
              <span className="strip-label">Recharge Potential</span>
            </div>
          )}
          <Link
            to="/forecast"
            style={{ marginLeft: 'auto', fontSize: '0.82rem', fontWeight: 600, color: 'var(--primary-color)', textDecoration: 'none' }}
          >
            View Full Forecast →
          </Link>
        </section>
      )}

      {/* Recharge vs Extraction Summary Card banner */}
      <section className="card" style={{ marginBottom: '30px', background: 'linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)' }}>
        <h3 className="card-title">🔌 {selectedDistrict ? `${selectedDistrict} Volumetric Dynamics` : selectedState ? `${selectedState} Volumetric Dynamics` : 'National Volumetric Dynamics'}</h3>
        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', margin: 0, gap: '15px' }}>
          <div>
            <div className="metric-label">Total Recharge</div>
            <div className="metric-value" style={{ fontSize: '1.7rem', color: 'var(--secondary-color)' }}>
              {summary?.total_recharge?.toLocaleString()} ham
            </div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Annual replenishing rate</span>
          </div>
          <div>
            <div className="metric-label">Total Extraction</div>
            <div className="metric-value" style={{ fontSize: '1.7rem', color: 'var(--color-critical)' }}>
              {summary?.total_extraction?.toLocaleString()} ham
            </div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Annual discharge/draft rate</span>
          </div>
          <div>
            <div className="metric-label">Avg Recharge Per District</div>
            <div className="metric-value" style={{ fontSize: '1.7rem' }}>
              {Math.round(summary?.avg_recharge || 0).toLocaleString()} ham
            </div>
          </div>
          <div>
            <div className="metric-label">Avg Extraction Per District</div>
            <div className="metric-value" style={{ fontSize: '1.7rem' }}>
              {Math.round(summary?.avg_extraction || 0).toLocaleString()} ham
            </div>
          </div>
        </div>
      </section>

      {/* Chart Visualizations Grid */}
      <section className="data-grid-2">
        {/* Groundwater Category Distribution Chart */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h3 className="card-title">
            {selectedState ? `${selectedState} Groundwater Categories` : 'National Groundwater Distribution'}
          </h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
            Count of districts grouped by environmental safety assessment categories.
          </p>
          <div style={{ flex: 1, minHeight: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {pieData.length === 0 ? (
              <div style={{ color: 'var(--text-muted)' }}>No category data available for this selection.</div>
            ) : (
              <ErrorBoundary>
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => {
                        let cellColor = COLORS[index % COLORS.length];
                        if (entry.name.toLowerCase() === 'safe') cellColor = '#2e7d32';
                        if (entry.name.toLowerCase() === 'semi-critical') cellColor = '#f57c00';
                        if (entry.name.toLowerCase() === 'critical') cellColor = '#d32f2f';
                        if (entry.name.toLowerCase() === 'over-exploited') cellColor = '#880e4f';
                        return <Cell key={`cell-${index}`} fill={cellColor} />;
                      })}
                    </Pie>
                    <Tooltip formatter={(value) => [`${value} Districts`, 'Quantity']} />
                  </PieChart>
                </ResponsiveContainer>
              </ErrorBoundary>
            )}
          </div>
        </div>

        {/* State-wise/District-wise charts */}
        <div className="card">
          <h3 className="card-title">
            {selectedState ? `District-wise Depth to Water Level` : `State-wise Depth to Water Level`}
          </h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
            {selectedState ? `Average depth to water level (m bgl) per district in ${selectedState}.` : 'Average depth to water level (m bgl) per state.'}
          </p>
          <div style={{ minHeight: '300px' }}>
            <ErrorBoundary>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={stateStats}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="state_name" tickFormatter={(tick) => tick.length > 12 ? tick.slice(0, 10) + '..' : tick} />
                  <YAxis label={{ value: 'Depth (m bgl)', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Bar dataKey="avg_groundwater_level" fill="#1b6ca8" name="Avg Depth (m bgl)" />
                </BarChart>
              </ResponsiveContainer>
            </ErrorBoundary>
          </div>
        </div>
      </section>

      {/* State/District Level recharge vs extraction */}
      <section className="card" style={{ marginBottom: '30px' }}>
        <h3 className="card-title">
          {selectedState ? `District Level Recharge vs Extraction (ham) in ${selectedState}` : `State Level Recharge vs Extraction (ham)`}
        </h3>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
          {selectedState ? `Volumetric comparison of replenishing water versus extracted drafts per district.` : 'Volumetric comparison of replenishing water versus extracted drafts.'}
        </p>
        <div style={{ minHeight: '300px' }}>
          <ErrorBoundary>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={stateStats}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="state_name" tickFormatter={(tick) => tick.length > 12 ? tick.slice(0, 10) + '..' : tick} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="avg_recharge" fill="#4db6ac" name="Avg Recharge" />
                <Bar dataKey="avg_extraction" fill="#ef5350" name="Avg Extraction" />
              </BarChart>
            </ResponsiveContainer>
          </ErrorBoundary>
        </div>
      </section>

      {/* Highest & Lowest rankings lists */}
      {!selectedDistrict && (
        <section className="data-grid-2">
          <div className="card">
            <h3 className="card-title" style={{ color: 'var(--secondary-color)' }}>
              ✅ Shallowest Depth to Water Level Districts {selectedState ? `in ${selectedState}` : ''}
            </h3>
            <div className="table-wrapper" style={{ margin: 0, border: 'none', boxShadow: 'none' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>District</th>
                    <th>State</th>
                    <th>Water Level Depth</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.lowest_districts?.map((d) => (
                    <tr key={d.id}>
                      <td><strong>{d.district_name}</strong></td>
                      <td>{d.state_name}</td>
                      <td style={{ color: 'var(--secondary-color)', fontWeight: 'bold' }}>{d.groundwater_level.toFixed(2)} m bgl</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <h3 className="card-title" style={{ color: 'var(--color-critical)' }}>
              ⚠️ Deepest Depth to Water Level Districts {selectedState ? `in ${selectedState}` : ''}
            </h3>
            <div className="table-wrapper" style={{ margin: 0, border: 'none', boxShadow: 'none' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>District</th>
                    <th>State</th>
                    <th>Water Level Depth</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.highest_districts?.map((d) => (
                    <tr key={d.id}>
                      <td><strong>{d.district_name}</strong></td>
                      <td>{d.state_name}</td>
                      <td style={{ color: 'var(--color-critical)', fontWeight: 'bold' }}>{d.groundwater_level.toFixed(2)} m bgl</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

export default Dashboard;
