// src/components/WeatherCard.jsx
import React, { useState } from 'react';
import weatherIconMap from '../utils/weatherIconMap';
import '../assets/weather-icons.min.css';

/**
 * WeatherCard — displays current weather and a collapsible 3-day forecast.
 *
 * Backend shape (from weather_service.py _parse):
 *   current: { temperature, feels_like, humidity, precipitation,
 *              wind_speed, weather_code, description, time }
 *   forecast[]: { date, weather_code, description, temp_max, temp_min,
 *                 precipitation_sum, precipitation_probability }
 */
const WeatherCard = ({ location, current, forecast }) => {
  const [showForecast, setShowForecast] = useState(false);

  // Map weather_code → icon class (fallback to 'wi-na')
  const iconClass = weatherIconMap[current?.weather_code] || 'wi-day-sunny';

  // Format the observation time from ISO string
  const observedAt = current?.time
    ? new Date(current.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div
      className="weather-card card"
      style={{
        background: 'linear-gradient(135deg, rgba(27,108,168,0.08) 0%, rgba(14,165,233,0.06) 100%)',
        borderRadius: '12px',
        padding: '20px',
        marginBottom: '24px',
        borderLeft: '4px solid var(--primary-color)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <h3 className="card-title" style={{ margin: 0 }}>
          🌤️ Current Weather — {location}
        </h3>
        {observedAt && (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Updated {observedAt}
          </span>
        )}
      </div>

      {/* Main current conditions row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
        {/* Icon + temp */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: '130px' }}>
          <i className={`wi ${iconClass}`} style={{ fontSize: '52px', color: 'var(--primary-color)' }} />
          <div>
            <div style={{ fontSize: '2rem', fontWeight: '700', lineHeight: 1 }}>
              {current?.temperature != null ? `${current.temperature.toFixed(1)}°C` : '--'}
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {current?.description || 'N/A'}
            </div>
            {current?.feels_like != null && (
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Feels like {current.feels_like.toFixed(1)}°C
              </div>
            )}
          </div>
        </div>

        {/* Detail pills */}
        <div style={{
          display: 'flex',
          gap: '12px',
          flexWrap: 'wrap',
          flex: 1,
        }}>
          <div style={pillStyle}>
            💧 <strong>{current?.humidity ?? '--'}%</strong>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>Humidity</span>
          </div>
          <div style={pillStyle}>
            🌧️ <strong>{current?.precipitation ?? 0} mm</strong>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>Precipitation</span>
          </div>
          <div style={pillStyle}>
            💨 <strong>{current?.wind_speed != null ? `${current.wind_speed.toFixed(1)} km/h` : '--'}</strong>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>Wind</span>
          </div>
        </div>
      </div>

      {/* 3-day forecast toggle */}
      {forecast && forecast.length > 0 && (
        <div style={{ marginTop: '16px' }}>
          <button
            onClick={() => setShowForecast(!showForecast)}
            className="btn btn-outline"
            style={{ fontSize: '0.82rem', padding: '6px 14px' }}
          >
            {showForecast ? '▲ Hide' : '▼ Show'} 3-day Forecast
          </button>

          {showForecast && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: '10px',
              marginTop: '12px',
            }}>
              {forecast.map((day, idx) => {
                const dayIcon = weatherIconMap[day.weather_code] || 'wi-day-sunny';
                const dateLabel = day.date
                  ? new Date(day.date).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })
                  : `Day ${idx + 1}`;
                return (
                  <div key={idx} style={{
                    background: 'rgba(27,108,168,0.06)',
                    borderRadius: '8px',
                    padding: '10px',
                    textAlign: 'center',
                    border: '1px solid var(--border-color)',
                  }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: '600', marginBottom: '4px' }}>{dateLabel}</div>
                    <i className={`wi ${dayIcon}`} style={{ fontSize: '28px', color: 'var(--primary-color)' }} />
                    <div style={{ fontSize: '0.8rem', fontWeight: '600', marginTop: '4px' }}>
                      {day.temp_max != null ? `${day.temp_max.toFixed(0)}°` : '--'} / {day.temp_min != null ? `${day.temp_min.toFixed(0)}°C` : '--'}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {day.description}
                    </div>
                    {day.precipitation_probability != null && (
                      <div style={{ fontSize: '0.72rem', color: '#0ea5e9', marginTop: '2px' }}>
                        🌧️ {day.precipitation_probability}%
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const pillStyle = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  background: 'rgba(255,255,255,0.6)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px',
  padding: '8px 14px',
  fontSize: '0.9rem',
  minWidth: '80px',
  textAlign: 'center',
  gap: '2px',
};

export default WeatherCard;
