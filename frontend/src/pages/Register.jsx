import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../styles/main.css';

const Register = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');

    // Input Validation
    if (!name.trim()) {
      setErrorMsg('Full Name is required.');
      return;
    }
    
    // Check Email Format
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(email)) {
      setErrorMsg('Please enter a valid email address.');
      return;
    }

    if (password.length < 6) {
      setErrorMsg('Password must be at least 6 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setErrorMsg('Passwords do not match.');
      return;
    }

    try {
      await register(name, email, password, confirmPassword);
      navigate('/login?registered=true');
    } catch (err) {
      setErrorMsg(err.message || 'Registration failed. Please try again.');
    }
  };

  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      backgroundColor: '#f1f5f9'
    }}>
      <div className="card" style={{ width: '100%', maxWidth: '445px', padding: '35px' }}>
        <div style={{ textAlign: 'center', marginBottom: '25px' }}>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--primary-color)' }}>INGRES AI</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '5px' }}>
            Register New Government / Analytical Account
          </p>
        </div>

        {errorMsg && <div className="alert-box alert-danger">{errorMsg}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="register-name">Full Name</label>
            <input
              id="register-name"
              type="text"
              className="form-control"
              placeholder="e.g. Dr. Rajesh Kumar"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="register-email">Email Address</label>
            <input
              id="register-email"
              type="email"
              className="form-control"
              placeholder="name@agency.gov.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="register-pwd">Password (min 6 chars)</label>
            <input
              id="register-pwd"
              type="password"
              className="form-control"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: '25px' }}>
            <label className="form-label" htmlFor="register-confirm-pwd">Confirm Password</label>
            <input
              id="register-confirm-pwd"
              type="password"
              className="form-control"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary btn-block">
            Register Account
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: 'var(--primary-color)', fontWeight: 600 }}>
            Sign in instead
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Register;
