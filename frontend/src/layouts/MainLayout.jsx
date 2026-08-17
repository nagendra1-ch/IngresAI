import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import '../styles/main.css';

const MainLayout = () => {
  return (
    <div className="app-container">
      {/* Navigation sidebar */}
      <Sidebar />
      
      {/* Main page view */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
};

export default MainLayout;
