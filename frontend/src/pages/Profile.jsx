import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import api from '../services/api';
import '../styles/main.css';

const Profile = () => {
  const { user } = useAuth();
  const { showToast } = useToast();

  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const getFormatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const d = new Date(dateString);
    return d.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  const userInitial = user?.name ? user.name.charAt(0).toUpperCase() : 'U';

  const handlePasswordChange = async (e) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      showToast('New passwords do not match.', 'error');
      return;
    }
    if (newPassword.length < 6) {
      showToast('New password must be at least 6 characters.', 'warning');
      return;
    }

    setChangingPassword(true);
    try {
      await api.post('/api/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      showToast('Password changed successfully!', 'success');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setShowPasswordForm(false);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to change password. Please verify your current password.';
      showToast(msg, 'error');
    } finally {
      setChangingPassword(false);
    }
  };

  const roleColor = user?.role === 'ADMIN' ? 'var(--color-critical)' : 'var(--primary-color)';
  const roleBg = user?.role === 'ADMIN' ? 'rgba(211, 47, 47, 0.08)' : 'rgba(27, 108, 168, 0.08)';

  return (
    <div className="container-inner" style={{ maxWidth: '650px' }}>
      <header className="page-header">
        <div>
          <h1 className="page-title">My Profile</h1>
          <p className="page-subtitle">Manage your INGRES AI account security and details.</p>
        </div>
      </header>

      {user && (
        <>
          {/* Profile Card */}
          <div className="card" style={{ marginBottom: '25px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap' }}>
              {/* Avatar */}
              <div style={{
                width: '90px',
                height: '90px',
                borderRadius: '50%',
                background: `linear-gradient(135deg, var(--primary-color) 0%, var(--accent-color) 100%)`,
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '2.5rem',
                fontWeight: 800,
                flexShrink: 0,
                boxShadow: 'var(--shadow-md)',
              }}>
                {userInitial}
              </div>

              {/* Info */}
              <div style={{ flex: 1 }}>
                <h2 style={{ fontSize: '1.6rem', fontWeight: 700, margin: '0 0 6px 0', color: 'var(--text-main)' }}>
                  {user.name}
                </h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginBottom: '10px' }}>
                  {user.email}
                </p>
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '4px 12px',
                  borderRadius: '50px',
                  fontSize: '0.82rem',
                  fontWeight: 700,
                  background: roleBg,
                  color: roleColor,
                }}>
                  {user.role === 'ADMIN' ? '🛡️' : '👤'} {user.role}
                </span>
              </div>
            </div>

            {/* Detail rows */}
            <div style={{
              marginTop: '24px',
              borderTop: '1px solid var(--border-color)',
              paddingTop: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '10px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Email</span>
                <span style={{ fontWeight: 500 }}>{user.email}</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '10px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Member Since</span>
                <span style={{ fontWeight: 500 }}>{getFormatDate(user.created_at)}</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '10px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Session Type</span>
                <span style={{ fontWeight: 500, color: 'var(--secondary-color)' }}>🔐 JWT Encrypted Session</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '10px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Access Level</span>
                <span style={{ fontWeight: 500 }}>
                  {user.role === 'ADMIN'
                    ? 'Full system access — administration, user management, exports'
                    : 'Standard analyst access — queries, comparisons, district search'}
                </span>
              </div>
            </div>
          </div>

          {/* Security Card */}
          <div className="card">
            <h3 className="card-title" style={{ marginBottom: '20px' }}>
              🔒 Account Security
            </h3>

            {!showPasswordForm ? (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <p style={{ fontWeight: 600, marginBottom: '4px' }}>Password</p>
                  <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                    Change your account password to maintain security.
                  </p>
                </div>
                <button
                  className="btn btn-outline"
                  onClick={() => setShowPasswordForm(true)}
                  style={{ padding: '10px 22px', whiteSpace: 'nowrap' }}
                >
                  Change Password
                </button>
              </div>
            ) : (
              <form onSubmit={handlePasswordChange} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label" htmlFor="current-password">Current Password</label>
                  <input
                    id="current-password"
                    type="password"
                    className="form-control"
                    placeholder="Enter your current password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                  />
                </div>

                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label" htmlFor="new-password">New Password</label>
                  <input
                    id="new-password"
                    type="password"
                    className="form-control"
                    placeholder="At least 6 characters"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={6}
                    autoComplete="new-password"
                  />
                </div>

                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label" htmlFor="confirm-password">Confirm New Password</label>
                  <input
                    id="confirm-password"
                    type="password"
                    className="form-control"
                    placeholder="Repeat your new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                  />
                  {newPassword && confirmPassword && newPassword !== confirmPassword && (
                    <p style={{ fontSize: '0.82rem', color: 'var(--color-critical)', marginTop: '6px' }}>
                      Passwords do not match.
                    </p>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => {
                      setShowPasswordForm(false);
                      setCurrentPassword('');
                      setNewPassword('');
                      setConfirmPassword('');
                    }}
                    disabled={changingPassword}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={changingPassword || !currentPassword || !newPassword || newPassword !== confirmPassword}
                  >
                    {changingPassword ? 'Updating...' : 'Update Password'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default Profile;
