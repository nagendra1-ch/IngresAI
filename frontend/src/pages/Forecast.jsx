import React, { useState, useEffect } from 'react';
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import api from '../services/api';
import WeatherCard from '../components/WeatherCard';
import ErrorBoundary from '../components/ErrorBoundary';
import weatherIconMap from '../utils/weatherIconMap';
import '../styles/main.css';
import '../styles/forecast.css';
import '../assets/weather-icons.min.css';

const Forecast = () => {
  const [selectedState, setSelectedState] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [statesList, setStatesList] = useState([]);
  const [districtsList, setDistrictsList] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingStates, setLoadingStates] = useState(true);
  const [error, setError] = useState('');

  // Fetch states list on mount
  useEffect(() => {
    const fetchStates = async () => {
      try {
        const res = await api.get('/api/dashboard/state-statistics');
        const uniqueStates = res.data
          .map(s => s.state_name)
          .filter(Boolean)
          .sort((a, b) => a.localeCompare(b));
        setStatesList(uniqueStates);
        setLoadingStates(false);
      } catch (err) {
        console.error("Failed to load states", err);
        setLoadingStates(false);
      }
    };
    fetchStates();
  }, []);

  // Fetch districts when state changes
  const handleStateChange = async (state) => {
    setSelectedState(state);
    setSelectedDistrict('');
    setForecast(null);
    setDistrictsList([]);
    if (!state) return;

    try {
      const res = await api.get(`/api/dashboard/state-statistics?state_name=${encodeURIComponent(state)}`);
      const districts = res.data
        .map(d => d.district_name)
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b));
      setDistrictsList(districts);
    } catch (err) {
      console.error("Failed to load districts", err);
    }
  };

  // Fetch forecast when district is selected
  const handleDistrictChange = async (district) => {
    setSelectedDistrict(district);
    setForecast(null);
    setError('');
    if (!district) return;

    setLoading(true);
    try {
      const res = await api.get(`/api/weather/forecast/${encodeURIComponent(district)}`);
      setForecast(res.data);
    } catch (err) {
      console.error("Forecast fetch failed", err);
      setError(err.response?.data?.detail || 'Unable to load forecast data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Get impact card CSS class based on risk level
  const getImpactClass = (riskLevel) => {
    if (!riskLevel) return 'impact-safe';
    const r = riskLevel.toLowerCase();
    if (r.includes('over')) return 'impact-over-exploited';
    if (r.includes('critical') && !r.includes('semi')) return 'impact-critical';
    if (r.includes('semi')) return 'impact-semi-critical';
    return 'impact-safe';
  };

  const getRechargeBadgeClass = (potential) => {
    if (!potential) return 'recharge-minimal';
    const p = potential.toLowerCase();
    if (p === 'high') return 'recharge-high';
    if (p === 'moderate') return 'recharge-moderate';
    if (p === 'low') return 'recharge-low';
    return 'recharge-minimal';
  };

  // Format hourly data for chart — group into readable labels
  const formatHourlyData = () => {
    if (!forecast?.hourly_rainfall) return [];
    return forecast.hourly_rainfall.map(h => {
      const dt = new Date(h.time);
      const label = dt.toLocaleString([], {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
      });
      const shortLabel = dt.toLocaleString([], { hour: '2-digit', minute: '2-digit' });
      return {
        ...h,
        label,
        shortLabel,
        hour: dt.getHours(),
        date: dt.toLocaleDateString([], { month: 'short', day: 'numeric' }),
      };
    });
  };

  // Format soil moisture data from daily forecast
  const formatSoilData = () => {
    if (!forecast?.daily_forecast) return [];
    return forecast.daily_forecast.map(d => ({
      date: new Date(d.date).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }),
      soil_moisture: d.soil_moisture != null ? +(d.soil_moisture * 100).toFixed(1) : null,
      et0: d.et0,
      rain: d.precipitation_sum,
    }));
  };

  return (
    <div className="container-inner">
      <header className="page-header">
        <div>
          <h1 className="page-title">🌧️ Rainfall & Groundwater Forecast</h1>
          <p className="page-subtitle">
            Live precipitation data, 7-day weather forecast, and groundwater recharge indicators — powered by Open-Meteo.
          </p>
        </div>
        {forecast && (
          <span className="live-indicator">LIVE</span>
        )}
      </header>

      {/* District Selector */}
      <section className="card" style={{ marginBottom: '24px' }}>
        <div className="forecast-selector-row">
          <div className="form-group">
            <label className="form-label">Select State</label>
            <select
              value={selectedState}
              onChange={(e) => handleStateChange(e.target.value)}
              disabled={loadingStates}
            >
              <option value="">-- Choose a State --</option>
              {statesList.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {selectedState && (
            <div className="form-group">
              <label className="form-label">Select District</label>
              <select
                value={selectedDistrict}
                onChange={(e) => handleDistrictChange(e.target.value)}
              >
                <option value="">-- Choose a District --</option>
                {districtsList.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </section>

      {/* Loading */}
      {loading && (
        <div>
          <div className="skeleton skeleton-title"></div>
          <div className="stats-grid">
            <div className="skeleton skeleton-card"></div>
            <div className="skeleton skeleton-card"></div>
            <div className="skeleton skeleton-card"></div>
          </div>
          <div className="skeleton" style={{ height: '300px', marginTop: '20px' }}></div>
        </div>
      )}

      {/* Error */}
      {error && <div className="alert-box alert-danger">{error}</div>}

      {/* No selection prompt */}
      {!selectedDistrict && !loading && !error && (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🌦️</div>
          <h3 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>Select a District</h3>
          <p>Choose a state and district above to view live rainfall data, 7-day weather forecasts, and groundwater impact indicators.</p>
        </div>
      )}

      {/* Forecast Data */}
      {forecast && !loading && (
        <>
          {/* Current Weather Card */}
          <WeatherCard
            location={forecast.location || selectedDistrict}
            current={forecast.current}
            forecast={forecast.daily_forecast?.slice(0, 3)}
            updatedAt={forecast.current?.time}
          />

          {/* Groundwater Impact Panel */}
          {forecast.groundwater_impact && (
            <section className={`forecast-impact-card card ${getImpactClass(forecast.groundwater_impact.risk_level)}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
                <h3 className="card-title" style={{ margin: 0, color: 'var(--text-main)' }}>
                  💧 Groundwater Impact Assessment
                </h3>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <span className={`recharge-badge ${getRechargeBadgeClass(forecast.groundwater_impact.recharge_potential)}`}>
                    {forecast.groundwater_impact.recharge_potential} Recharge
                  </span>
                  <span className={`badge badge-${forecast.groundwater_impact.risk_level?.toLowerCase().replace(/[\s-]+/g, '-') || 'safe'}`} style={{ fontSize: '0.82rem', padding: '6px 14px' }}>
                    {forecast.groundwater_impact.risk_level}
                  </span>
                </div>
              </div>

              {/* Narrative */}
              <p style={{ fontSize: '0.92rem', lineHeight: '1.6', color: 'var(--text-main)', marginBottom: '16px' }}>
                {forecast.groundwater_impact.narrative}
              </p>

              {/* Impact metrics row */}
              <div className="impact-metrics-row">
                <div className="impact-metric">
                  <div className="metric-value" style={{ color: '#0ea5e9' }}>
                    {forecast.groundwater_impact.forecast_total_rain_mm?.toFixed(1) ?? '--'} mm
                  </div>
                  <div className="metric-label">7-Day Forecast Rain</div>
                </div>
                <div className="impact-metric">
                  <div className="metric-value" style={{ color: 'var(--secondary-color)' }}>
                    {forecast.groundwater_impact.historical_avg_rain_mm?.toFixed(0) ?? '--'} mm
                  </div>
                  <div className="metric-label">Historical Avg Annual Rain</div>
                </div>
                <div className="impact-metric">
                  <div className="metric-value" style={{ color: 'var(--primary-color)' }}>
                    {forecast.groundwater_impact.rain_vs_avg_percent?.toFixed(1) ?? '--'}%
                  </div>
                  <div className="metric-label">Rain vs Annual Avg</div>
                </div>
                <div className="impact-metric">
                  <div className="metric-value" style={{ color: forecast.groundwater_impact.extraction_rate_percent > 70 ? 'var(--color-critical)' : 'var(--color-semi-critical)' }}>
                    {forecast.groundwater_impact.extraction_rate_percent?.toFixed(1) ?? '--'}%
                  </div>
                  <div className="metric-label">Extraction Rate</div>
                </div>
                {forecast.groundwater_impact.annual_recharge_ham && (
                  <div className="impact-metric">
                    <div className="metric-value" style={{ color: 'var(--secondary-color)' }}>
                      {forecast.groundwater_impact.annual_recharge_ham?.toLocaleString(undefined, { maximumFractionDigits: 0 })} ham
                    </div>
                    <div className="metric-label">Annual Recharge</div>
                  </div>
                )}
              </div>

              <div style={{ marginTop: '12px', fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'right' }}>
                Source: {forecast.source || 'Open-Meteo + INGRES Historical Data'}
              </div>
            </section>
          )}

          {/* 48-Hour Hourly Rainfall Timeline */}
          <section className="card" style={{ marginBottom: '24px' }}>
            <h3 className="card-title">⏱️ 48-Hour Precipitation Timeline</h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
              Hourly rainfall forecast showing when precipitation is expected. Source: Open-Meteo.
            </p>
            <div className="hourly-timeline-container">
              <ErrorBoundary>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={formatHourlyData()} barCategoryGap="1%">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="shortLabel"
                      interval={5}
                      tick={{ fontSize: 10 }}
                      angle={-45}
                      textAnchor="end"
                      height={50}
                    />
                    <YAxis
                      label={{ value: 'Rain (mm)', angle: -90, position: 'insideLeft', fontSize: 11 }}
                      tick={{ fontSize: 10 }}
                    />
                    <Tooltip
                      labelFormatter={(_, payload) => payload?.[0]?.payload?.label || ''}
                      formatter={(value) => [`${value} mm`, 'Precipitation']}
                    />
                    <Bar dataKey="rain_mm" fill="#0ea5e9" name="Hourly Rain (mm)" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ErrorBoundary>
            </div>
          </section>

          {/* 7-Day Forecast Grid */}
          <section className="card" style={{ marginBottom: '24px' }}>
            <h3 className="card-title">📅 7-Day Weather Forecast</h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
              Daily temperature, precipitation, and conditions for the week ahead. Source: Open-Meteo.
            </p>
            <div className="forecast-day-grid">
              {forecast.daily_forecast?.map((day, idx) => {
                const dayIcon = weatherIconMap[day.weather_code] || 'wi-day-sunny';
                const dateLabel = day.date
                  ? new Date(day.date).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })
                  : `Day ${idx + 1}`;
                return (
                  <div key={idx} className="forecast-day-card">
                    <div className="day-label">{dateLabel}</div>
                    <i className={`wi ${dayIcon} day-icon`} />
                    <div className="day-temp">
                      {day.temp_max != null ? `${day.temp_max.toFixed(0)}°` : '--'} / {day.temp_min != null ? `${day.temp_min.toFixed(0)}°C` : '--'}
                    </div>
                    <div className="day-detail">{day.description}</div>
                    {day.precipitation_sum != null && (
                      <div className="day-rain">🌧️ {day.precipitation_sum.toFixed(1)} mm</div>
                    )}
                    {day.precipitation_probability != null && (
                      <div className="day-detail">💧 {day.precipitation_probability}% chance</div>
                    )}
                    {day.humidity != null && (
                      <div className="day-detail">Humidity: {day.humidity.toFixed(0)}%</div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* Rainfall vs Historical Chart + Soil Moisture */}
          <section className="data-grid-2">
            {/* Daily Rainfall Chart */}
            <div className="card">
              <h3 className="card-title">🌧️ Daily Rainfall Forecast</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
                Predicted daily precipitation over 7 days
                {forecast.groundwater_impact?.historical_avg_rain_mm
                  ? ` (annual avg: ${forecast.groundwater_impact.historical_avg_rain_mm.toFixed(0)} mm)`
                  : ''}
              </p>
              <div style={{ minHeight: '260px' }}>
                <ErrorBoundary>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={formatSoilData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis label={{ value: 'Rain (mm)', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="rain" fill="#0ea5e9" name="Rain (mm)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ErrorBoundary>
              </div>
            </div>

            {/* Soil Moisture + ET0 Chart */}
            <div className="card">
              <h3 className="card-title">🌱 Soil Moisture & Evapotranspiration</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
                Near-surface soil moisture (%) and reference evapotranspiration (ET₀) trends.
              </p>
              <div className="soil-moisture-section">
                <ErrorBoundary>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={formatSoilData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis yAxisId="left" label={{ value: 'Soil Moisture (%)', angle: -90, position: 'insideLeft', fontSize: 10 }} />
                      <YAxis yAxisId="right" orientation="right" label={{ value: 'ET₀ (mm)', angle: 90, position: 'insideRight', fontSize: 10 }} />
                      <Tooltip />
                      <Legend />
                      <Line yAxisId="left" type="monotone" dataKey="soil_moisture" stroke="#2e7d32" strokeWidth={2} name="Soil Moisture (%)" dot={{ r: 4 }} />
                      <Line yAxisId="right" type="monotone" dataKey="et0" stroke="#f57c00" strokeWidth={2} name="ET₀ (mm)" dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </ErrorBoundary>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
};

export default Forecast;
