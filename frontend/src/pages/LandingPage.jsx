import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/main.css';

const LandingPage = () => {
  const navigate = useNavigate();

  const handleStartChat = () => {
    navigate('/assistant');
  };

  const handleExploreDashboard = () => {
    navigate('/dashboard');
  };

  return (
    <div className="container-inner" style={{ padding: '20px 0' }}>
      {/* Hero Section */}
      <section style={{
        background: 'linear-gradient(135deg, #1b6ca8 0%, #2e7d32 100%)',
        color: 'white',
        borderRadius: 'var(--border-radius-lg)',
        padding: '60px 40px',
        textAlign: 'center',
        marginBottom: '40px',
        boxShadow: 'var(--shadow-md)',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Subtle background decoration */}
        <div style={{
          position: 'absolute',
          top: '-10%',
          right: '-10%',
          width: '300px',
          height: '300px',
          borderRadius: '50%',
          background: 'rgba(255, 255, 255, 0.05)',
          pointerEvents: 'none'
        }}></div>

        <h1 style={{ fontSize: '3rem', fontWeight: 800, marginBottom: '10px', letterSpacing: '1px' }}>INGRES AI</h1>
        <p style={{ fontSize: '1.5rem', fontWeight: 500, marginBottom: '20px', opacity: 0.95 }}>
          AI-Powered Groundwater Intelligence for India
        </p>
        <p style={{
          maxWidth: '750px',
          margin: '0 auto 30px auto',
          fontSize: '1.05rem',
          lineHeight: '1.6',
          opacity: 0.85
        }}>
          Explore groundwater levels, rainfall statistics, district comparisons and groundwater resource information 
          using an intelligent AI-powered virtual assistant.
        </p>
        
        <div style={{ display: 'flex', gap: '15px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="btn" style={{ backgroundColor: '#ffffff', color: '#1b6ca8', padding: '14px 28px' }} onClick={handleStartChat}>
            Ask INGRES AI 💬
          </button>
          <button className="btn" style={{ backgroundColor: '#4db6ac', color: '#ffffff', padding: '14px 28px' }} onClick={handleExploreDashboard}>
            Explore Dashboard 📈
          </button>
        </div>
      </section>

      {/* Feature Cards Grid */}
      <section>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--primary-color)', marginBottom: '25px', textAlign: 'center' }}>
          Key System Capabilities
        </h2>
        
        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
          
          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '2rem' }}>🤖</div>
            <h3 className="card-title" style={{ margin: 0 }}>AI Virtual Assistant</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
              Ask questions about groundwater resources using natural language. Get instant, verified responses based directly on physical metrics.
            </p>
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '2rem' }}>📊</div>
            <h3 className="card-title" style={{ margin: 0 }}>District Insights</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
              Explore groundwater levels and rainfall statistics for individual districts. View extraction, availability, and category assessments.
            </p>
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '2rem' }}>🔄</div>
            <h3 className="card-title" style={{ margin: 0 }}>District Comparison</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
              Compare two districts side-by-side using interactive charts. Receive an automated AI breakdown detailing groundwater extraction differences.
            </p>
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '2rem' }}>🗺️</div>
            <h3 className="card-title" style={{ margin: 0 }}>India Groundwater Dashboard</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
              Visualize groundwater information across India. Group metrics by state-wide extraction ratios and category severity levels.
            </p>
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '2rem' }}>📈</div>
            <h3 className="card-title" style={{ margin: 0 }}>Data Analytics</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
              Understand groundwater recharge vs extraction dynamics through interactive charts. Track replenishment rates over time.
            </p>
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '2rem' }}>⚡</div>
            <h3 className="card-title" style={{ margin: 0 }}>Smart Search</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
              Query statistics naturally instead of navigating complex raw government database schemas. Retrieve numerical truth instantly.
            </p>
          </div>

        </div>
      </section>
    </div>
  );
};

export default LandingPage;
