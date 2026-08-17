import React from 'react';
import { useAuth } from '../context/AuthContext';
import '../styles/main.css';

const Profile = () => {
  const { user } = useAuth();

  const getFormatDate = (dateString) => {
    if (!dateString) return '';
    const d = new Date(dateString);
    return d.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  const userInitial = user?.name ? user.name.charAt(0).toUpperCase() : 'U';

  return (
    <div className="container-inner" style={{ maxWidth: '600px' }}>
      <header className="page-header">
        <div>
          <h1 className="page-title">My Profile</h1>
          <p className="page-subtitle">Manage your INGRES AI account security and metadata.</p>
        </div>
      </header>

      {user && (
        <div className="card" style={{ padding: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px', textAlign: 'center' }}>
          {/* Avatar Icon */}
          <div style={{
            width: '100px',
            height: '100px',
            borderRadius: '50%',
            backgroundColor: 'var(--primary-color)',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '3rem',
            fontWeight: 800,
            marginBottom: '10px',
            boxShadow: 'var(--shadow-md)'
          }}>
            {userInitial}
          </div>

          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, margin: 0 }}>{user.name}</h2>
          <span className="badge badge-safe" style={{ fontSize: '0.9rem', padding: '6px 16px', backgroundColor: 'rgba(27, 108, 168, 0.1)', color: 'var(--primary-color)' }}>
            Authorized role: {user.role}
          </span>

          {/* Details list */}
          <div style={{
            width: '100%',
            textAlign: 'left',
            borderTop: '1px solid var(--border-color)',
            marginTop: '20px',
            paddingTop: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '15px'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '10px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Email Address</span>
              <span>{user.email}</span>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '10px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Registered</span>
              <span>{getFormatDate(user.created_at)}</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '10px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Encryption</span>
              <span style={{ color: 'var(--secondary-color)', fontWeight: 600 }}>SHA-256 JWT Encrypted Session</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Profile;
