import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import api from '../services/api';
import MarkdownRenderer from '../utils/MarkdownRenderer';
import WeatherCard from '../components/WeatherCard';
import weatherIconMap from '../utils/weatherIconMap';
import '../styles/main.css';

const Compare = () => {
  const [districtsList, setDistrictsList] = useState([]);
  const [district1Id, setDistrict1Id] = useState('');
  const [district2Id, setDistrict2Id] = useState('');
  const [comparison, setComparison] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingComparison, setLoadingComparison] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDistrictsList = async () => {
      try {
        const res = await api.get('/api/districts');
        setDistrictsList(res.data);
        setLoadingList(false);
      } catch (err) {
        console.error("Failed to load compare dropdown list", err);
        setError("Could not retrieve district selectors. Please try again.");
        setLoadingList(false);
      }
    };

    fetchDistrictsList();
  }, []);

  const handleCompare = async (e) => {
    e.preventDefault();
    if (!district1Id || !district2Id) {
      setError("Please select two different districts to compare.");
      return;
    }
    if (district1Id === district2Id) {
      setError("Please select two different districts, not the same one.");
      return;
    }

    try {
      setLoadingComparison(true);
      setError('');
      const res = await api.get(`/api/compare?district1=${district1Id}&district2=${district2Id}`);
      setComparison(res.data);
      setLoadingComparison(false);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "An error occurred compiling the comparison. Please try again.");
      setLoadingComparison(false);
    }
  };

  // Format Recharts data
  const getLevelsChartData = () => {
    if (!comparison) return [];
    return [
      {
        name: 'Depth to Water Level (m bgl)',
        [comparison.district_1.district_name]: comparison.district_1.depth_to_water_level_m_bgl,
        [comparison.district_2.district_name]: comparison.district_2.depth_to_water_level_m_bgl,
      }
    ];
  };

  const getRainfallChartData = () => {
    if (!comparison) return [];
    return [
      {
        name: 'Annual Rainfall (mm)',
        [comparison.district_1.district_name]: comparison.district_1.rainfall_mm,
        [comparison.district_2.district_name]: comparison.district_2.rainfall_mm,
      }
    ];
  };

  const getVolumetricChartData = () => {
    if (!comparison) return [];
    const d1Name = comparison.district_1.district_name;
    const d2Name = comparison.district_2.district_name;
    return [
      {
        metric: 'Annual Recharge',
        [d1Name]: comparison.district_1.annual_groundwater_recharge_ham,
        [d2Name]: comparison.district_2.annual_groundwater_recharge_ham,
      },
      {
        metric: 'Annual Extraction',
        [d1Name]: comparison.district_1.annual_groundwater_extraction_ham,
        [d2Name]: comparison.district_2.annual_groundwater_extraction_ham,
      }
    ];
  };

  // Weather comparison chart data
  const getWeatherChartData = () => {
    if (!comparison) return [];
    const w1 = comparison.weather_1;
    const w2 = comparison.weather_2;
    if (!w1?.current && !w2?.current) return [];
    const d1Name = comparison.district_1.district_name;
    const d2Name = comparison.district_2.district_name;
    return [
      {
        metric: 'Temperature (°C)',
        [d1Name]: w1?.current?.temperature ?? null,
        [d2Name]: w2?.current?.temperature ?? null,
      },
      {
        metric: 'Humidity (%)',
        [d1Name]: w1?.current?.humidity ?? null,
        [d2Name]: w2?.current?.humidity ?? null,
      },
      {
        metric: 'Wind (km/h)',
        [d1Name]: w1?.current?.wind_speed ?? null,
        [d2Name]: w2?.current?.wind_speed ?? null,
      },
    ];
  };


  return (
    <div className="container-inner">
      <header className="page-header">
        <div>
          <h1 className="page-title">Compare Districts</h1>
          <p className="page-subtitle">Select two districts to compare their hydrological metrics and AI narrative analysis.</p>
        </div>
      </header>

      {/* Selectors Card */}
      <section className="card" style={{ marginBottom: '30px' }}>
        {loadingList ? (
          <div className="skeleton skeleton-text" style={{ width: '80%' }}></div>
        ) : (
          <form onSubmit={handleCompare} style={{ display: 'flex', gap: '15px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div className="form-group" style={{ flex: 1, minWidth: '220px', margin: 0 }}>
              <label className="form-label" htmlFor="district1-select">District 1</label>
              <select
                id="district1-select"
                className="form-select"
                value={district1Id}
                onChange={(e) => setDistrict1Id(e.target.value)}
                required
              >
                <option value="">-- Choose District 1 --</option>
                {districtsList.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.district_name} ({d.state_name})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ flex: 1, minWidth: '220px', margin: 0 }}>
              <label className="form-label" htmlFor="district2-select">District 2</label>
              <select
                id="district2-select"
                className="form-select"
                value={district2Id}
                onChange={(e) => setDistrict2Id(e.target.value)}
                required
              >
                <option value="">-- Choose District 2 --</option>
                {districtsList.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.district_name} ({d.state_name})
                  </option>
                ))}
              </select>
            </div>

            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={loadingComparison || !district1Id || !district2Id}
              style={{ padding: '12px 35px' }}
            >
              {loadingComparison ? 'Comparing...' : 'Compare Districts'}
            </button>
          </form>
        )}
      </section>

      {error && <div className="alert-box alert-danger">{error}</div>}

      {/* Comparison Loading state */}
      {loadingComparison && (
        <div>
          <div className="skeleton skeleton-title"></div>
          <div className="stats-grid">
            <div className="skeleton skeleton-card"></div>
            <div className="skeleton skeleton-card"></div>
          </div>
        </div>
      )}

      {/* Comparison Results Area */}
      {comparison && !loadingComparison && (
        <>
          {/* Summary Cards */}
          <section className="data-grid-2">
            {/* District 1 details */}
            <div className="card" style={{ borderTop: '4px solid var(--primary-color)' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>District A</span>
              <h2 className="card-title" style={{ fontSize: '1.5rem', margin: '5px 0' }}>{comparison.district_1.district_name}</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '15px' }}>{comparison.district_1.state_name}</p>
              
              <div className="stats-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '15px', margin: 0 }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Depth to Water Level</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--primary-color)' }}>
                    {comparison.district_1.depth_to_water_level_m_bgl !== null ? `${comparison.district_1.depth_to_water_level_m_bgl.toFixed(2)} m bgl` : 'Data unavailable'}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Rainfall</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--secondary-color)' }}>
                    {comparison.district_1.rainfall_mm !== null ? `${comparison.district_1.rainfall_mm.toFixed(1)} mm` : 'Data unavailable'}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Recharge</span>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>
                    {comparison.district_1.annual_groundwater_recharge_ham !== null ? `${comparison.district_1.annual_groundwater_recharge_ham.toLocaleString(undefined, {maximumFractionDigits: 2})} ham` : 'Data unavailable'}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Extraction</span>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>
                    {comparison.district_1.annual_groundwater_extraction_ham !== null ? `${comparison.district_1.annual_groundwater_extraction_ham.toLocaleString(undefined, {maximumFractionDigits: 2})} ham` : 'Data unavailable'}
                  </div>
                </div>
              </div>
              
              <div style={{ marginTop: '15px', borderTop: '1px solid #eee', paddingTop: '10px', fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                <strong>Assessment Category:</strong> {comparison.district_1.assessment_category || 'Unknown'}<br />
                {comparison.district_1.stage_of_groundwater_extraction_percent !== null && (
                  <><strong>Stage of Extraction:</strong> {comparison.district_1.stage_of_groundwater_extraction_percent.toFixed(2)}%<br /></>
                )}
                <strong>GW Source:</strong> {comparison.district_1.data_source_groundwater || 'N/A'}<br />
                <strong>Rainfall Source:</strong> {comparison.district_1.data_source_rainfall || 'N/A'}
              </div>
            </div>

            {/* District 2 details */}
            <div className="card" style={{ borderTop: '4px solid #4db6ac' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>District B</span>
              <h2 className="card-title" style={{ fontSize: '1.5rem', margin: '5px 0' }}>{comparison.district_2.district_name}</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '15px' }}>{comparison.district_2.state_name}</p>
              
              <div className="stats-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '15px', margin: 0 }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Depth to Water Level</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#4db6ac' }}>
                    {comparison.district_2.depth_to_water_level_m_bgl !== null ? `${comparison.district_2.depth_to_water_level_m_bgl.toFixed(2)} m bgl` : 'Data unavailable'}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Rainfall</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--secondary-color)' }}>
                    {comparison.district_2.rainfall_mm !== null ? `${comparison.district_2.rainfall_mm.toFixed(1)} mm` : 'Data unavailable'}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Recharge</span>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>
                    {comparison.district_2.annual_groundwater_recharge_ham !== null ? `${comparison.district_2.annual_groundwater_recharge_ham.toLocaleString(undefined, {maximumFractionDigits: 2})} ham` : 'Data unavailable'}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Extraction</span>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>
                    {comparison.district_2.annual_groundwater_extraction_ham !== null ? `${comparison.district_2.annual_groundwater_extraction_ham.toLocaleString(undefined, {maximumFractionDigits: 2})} ham` : 'Data unavailable'}
                  </div>
                </div>
              </div>
              
              <div style={{ marginTop: '15px', borderTop: '1px solid #eee', paddingTop: '10px', fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                <strong>Assessment Category:</strong> {comparison.district_2.assessment_category || 'Unknown'}<br />
                {comparison.district_2.stage_of_groundwater_extraction_percent !== null && (
                  <><strong>Stage of Extraction:</strong> {comparison.district_2.stage_of_groundwater_extraction_percent.toFixed(2)}%<br /></>
                )}
                <strong>GW Source:</strong> {comparison.district_2.data_source_groundwater || 'N/A'}<br />
                <strong>Rainfall Source:</strong> {comparison.district_2.data_source_rainfall || 'N/A'}
              </div>
            </div>
          </section>

          {/* AI Generated Comparison Narrative Explanation */}
          <section className="card" style={{ marginBottom: '30px', borderLeft: '4px solid var(--primary-color)' }}>
            <h3 className="card-title" style={{ color: 'var(--primary-color)' }}>🤖 INGRES AI Comparative Analysis</h3>
            <div style={{ marginTop: '10px', color: 'var(--text-main)' }}>
              <MarkdownRenderer text={comparison.explanation} fontSize="0.92rem" lineHeight="1.5" />
            </div>
          </section>

          {/* Recharts Comparison Graphs */}
          <section className="data-grid-2">
            {/* Groundwater Depth comparison chart */}
            <div className="card">
              <h3 className="card-title">Depth to Water Level Comparison (m bgl)</h3>
              <div style={{ minHeight: '240px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                {comparison.district_1.depth_to_water_level_m_bgl === null && comparison.district_2.depth_to_water_level_m_bgl === null ? (
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0' }}>
                    Depth data unavailable for the selected districts.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={getLevelsChartData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey={comparison.district_1.district_name} fill="var(--primary-color)" />
                      <Bar dataKey={comparison.district_2.district_name} fill="#4db6ac" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* Rainfall comparison chart */}
            <div className="card">
              <h3 className="card-title">Annual Rainfall Comparison (mm)</h3>
              <div style={{ minHeight: '240px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                {comparison.district_1.rainfall_mm === null && comparison.district_2.rainfall_mm === null ? (
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0' }}>
                    Rainfall data unavailable for the selected districts.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={getRainfallChartData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey={comparison.district_1.district_name} fill="var(--primary-color)" />
                      <Bar dataKey={comparison.district_2.district_name} fill="#4db6ac" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </section>

          {/* Volumetric comparison chart */}
          <section className="card" style={{ marginBottom: '30px' }}>
            <h3 className="card-title">Volumetric comparison: Recharge vs Extraction (ham)</h3>
            <div style={{ minHeight: '280px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              {comparison.district_1.annual_groundwater_recharge_ham === null && comparison.district_2.annual_groundwater_recharge_ham === null ? (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0' }}>
                  GWRA data unavailable for the selected districts.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={getVolumetricChartData()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="metric" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey={comparison.district_1.district_name} fill="var(--primary-color)" />
                    <Bar dataKey={comparison.district_2.district_name} fill="#4db6ac" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          {/* Weather Comparison Section */}
          {(comparison.weather_1 || comparison.weather_2) && (
            <section style={{ marginBottom: '30px' }}>
              <h3 className="card-title" style={{ marginBottom: '16px', fontSize: '1.15rem' }}>
                🌤️ Current Weather Comparison
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: '10px' }}>Source: Open-Meteo</span>
              </h3>
              <div className="data-grid-2" style={{ marginBottom: '20px' }}>
                {comparison.weather_1 && (
                  <WeatherCard
                    location={comparison.weather_1.location || comparison.district_1.district_name}
                    current={comparison.weather_1.current}
                    forecast={comparison.weather_1.forecast}
                    updatedAt={comparison.weather_1.current?.time}
                  />
                )}
                {comparison.weather_2 && (
                  <WeatherCard
                    location={comparison.weather_2.location || comparison.district_2.district_name}
                    current={comparison.weather_2.current}
                    forecast={comparison.weather_2.forecast}
                    updatedAt={comparison.weather_2.current?.time}
                  />
                )}
              </div>
              {/* Weather metrics chart */}
              {getWeatherChartData().length > 0 && (
                <div className="card">
                  <h3 className="card-title">Weather Metrics Comparison</h3>
                  <div style={{ minHeight: '240px' }}>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={getWeatherChartData()}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="metric" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey={comparison.district_1.district_name} fill="var(--primary-color)" />
                        <Bar dataKey={comparison.district_2.district_name} fill="#4db6ac" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
};

export default Compare;

