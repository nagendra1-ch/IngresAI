import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../styles/sidebar.css';

const Sidebar = () => {
  const { user, logout, isAdmin } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const toggleMobileSidebar = () => {
    setIsOpen(!isOpen);
  };

  const closeSidebar = () => {
    setIsOpen(false);
  };

  const userInitial = user?.name ? user.name.charAt(0).toUpperCase() : 'U';

  return (
    <>
      {/* Mobile Sticky Header */}
      <div className="mobile-header">
        <div className="sidebar-brand">
          <span className="sidebar-brand-symbol">I</span> INGRES AI
        </div>
        <button className="mobile-hamburger" onClick={toggleMobileSidebar} aria-label="Toggle navigation">
          &#9776;
        </button>
      </div>

      {/* Backdrop overlay for mobile drawer */}
      {isOpen && <div className="sidebar-overlay" onClick={closeSidebar}></div>}

      {/* Sidebar Drawer */}
      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <span className="sidebar-brand-symbol">I</span> INGRES AI
        </div>

        <ul className="sidebar-menu">
          <li className="sidebar-item">
            <NavLink to="/" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar} end>
              <span>🏠</span> Home
            </NavLink>
          </li>
          
          <li className="sidebar-item">
            <NavLink to="/assistant" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar}>
              <span>💬</span> AI Assistant
            </NavLink>
          </li>

          <li className="sidebar-item">
            <NavLink to="/dashboard" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar}>
              <span>📈</span> Groundwater Dashboard
            </NavLink>
          </li>

          <li className="sidebar-item">
            <NavLink to="/districts" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar}>
              <span>🔍</span> District Search
            </NavLink>
          </li>

          <li className="sidebar-item">
            <NavLink to="/compare" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar}>
              <span>🔄</span> Compare Districts
            </NavLink>
          </li>

          <li className="sidebar-item">
            <NavLink to="/forecast" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar}>
              <span>🌧️</span> Forecast
            </NavLink>
          </li>

          <li className="sidebar-item">
            <NavLink to="/history" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar}>
              <span>📜</span> My Query History
            </NavLink>
          </li>

          <li className="sidebar-item">
            <NavLink to="/profile" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar}>
              <span>👤</span> Profile
            </NavLink>
          </li>

          {isAdmin && (
            <>
              <div className="sidebar-section-title">Administration</div>
              
              <li className="sidebar-item">
                <NavLink to="/admin" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} onClick={closeSidebar} end>
                  <span>🛡️</span> Admin Dashboard
                </NavLink>
              </li>
            </>
          )}
        </ul>

        {/* User Footer */}
        {user && (
          <div className="sidebar-footer">
            <div className="sidebar-user-info">
              <div className="sidebar-user-avatar">{userInitial}</div>
              <div className="sidebar-user-details">
                <div className="sidebar-user-name" title={user.name}>{user.name}</div>
                <div className="sidebar-user-role">{user.role}</div>
              </div>
            </div>
            <button className="btn btn-outline btn-block" style={{ border: '1px solid #d32f2f', color: '#ef5350', padding: '8px' }} onClick={handleLogout}>
              Logout
            </button>
          </div>
        )}
      </aside>
    </>
  );
};

export default Sidebar;
