import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import '../styles/main.css';

const MainLayout = () => {
  const [showBackToTop, setShowBackToTop] = useState(false);

  useEffect(() => {
    const mainEl = document.querySelector('.main-content');
    if (!mainEl) return;

    const handleScroll = () => {
      setShowBackToTop(mainEl.scrollTop > 400);
    };

    mainEl.addEventListener('scroll', handleScroll, { passive: true });
    return () => mainEl.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToTop = () => {
    const mainEl = document.querySelector('.main-content');
    mainEl?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="app-container">
      {/* Navigation sidebar */}
      <Sidebar />
      
      {/* Main page view */}
      <main className="main-content">
        <Outlet />
      </main>

      {/* Floating Back to Top button */}
      {showBackToTop && (
        <button
          onClick={scrollToTop}
          title="Back to top"
          style={{
            position: 'fixed',
            bottom: '90px',
            right: '30px',
            zIndex: 9998,
            width: '44px',
            height: '44px',
            borderRadius: '50%',
            background: 'var(--primary-color)',
            color: 'white',
            border: 'none',
            cursor: 'pointer',
            fontSize: '1.2rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--shadow-md)',
            transition: 'background-color 0.2s, transform 0.15s',
            animation: 'fadeIn 0.25s ease',
          }}
          onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.1)')}
          onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
          aria-label="Scroll back to top"
        >
          ↑
        </button>
      )}
    </div>
  );
};

export default MainLayout;
