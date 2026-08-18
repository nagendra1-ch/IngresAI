import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import ProtectedRoute from './components/ProtectedRoute';

// Layouts
import MainLayout from './layouts/MainLayout';

// Pages
import LandingPage from './pages/LandingPage';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Assistant from './pages/Assistant';
import Districts from './pages/Districts';
import DistrictDetails from './pages/DistrictDetails';
import Compare from './pages/Compare';
import Forecast from './pages/Forecast';
import QueryHistory from './pages/QueryHistory';
import Profile from './pages/Profile';
import AdminDashboard from './pages/AdminDashboard';

function App() {
  return (
    <AuthProvider>
      <ToastProvider>
      <Router>
        <Routes>
          {/* Auth Pages (Public, unauthenticated) */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Main Layout containing Sidebar */}
          <Route element={<MainLayout />}>
            {/* Landing page is public */}
            <Route path="/" element={<LandingPage />} />

            {/* Protected Routes */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/assistant" 
              element={
                <ProtectedRoute>
                  <Assistant />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/districts" 
              element={
                <ProtectedRoute>
                  <Districts />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/districts/:id" 
              element={
                <ProtectedRoute>
                  <DistrictDetails />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/compare" 
              element={
                <ProtectedRoute>
                  <Compare />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/forecast" 
              element={
                <ProtectedRoute>
                  <Forecast />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/history" 
              element={
                <ProtectedRoute>
                  <QueryHistory />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/profile" 
              element={
                <ProtectedRoute>
                  <Profile />
                </ProtectedRoute>
              } 
            />

            {/* Admin Only Routes */}
            <Route 
              path="/admin" 
              element={
                <ProtectedRoute adminOnly={true}>
                  <AdminDashboard />
                </ProtectedRoute>
              } 
            />
          </Route>

          {/* Catch-all fallback redirects to home */}
          <Route path="*" element={<LandingPage />} />
        </Routes>
      </Router>
      </ToastProvider>
    </AuthProvider>
  );
}

export default App;
