import React, { useState } from 'react';
import {
  Layers,
  AlertTriangle
} from 'lucide-react';
import { api } from '../api';


export default function AuthView({ onAuthSuccess }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await api.login({ email: email.trim(), password });
      const user = await api.fetchMe();
      onAuthSuccess(user);
    } catch (err) {
      setError(err.message || 'Login failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await api.register({
        name: name.trim(),
        email: email.trim(),
        password,
      });
      // Direct sign in upon successful registration
      await api.login({ email: email.trim(), password });
      const user = await api.fetchMe();
      onAuthSuccess(user);
    } catch (err) {
      setError(err.message || 'Registration failed. Email may already be in use.');
    } finally {
      setLoading(false);
    }
  };

  // Quick Demo Logins for instant evaluation of Module 1
  const handleQuickDemo = async (roleType) => {
    setLoading(true);
    setError(null);

    let demoEmail = 'demo@smeconnect.io';
    let demoPass = 'DemoPassword123!';
    let demoName = 'Demo Admin';

    if (roleType === 'employee') {
      demoEmail = 'employee@company.com';
      demoPass = 'Password123!';
      demoName = 'Employee Invitee';
    }

    try {
      try {
        await api.login({ email: demoEmail, password: demoPass });
      } catch {
        // Register if not yet registered
        await api.register({ name: demoName, email: demoEmail, password: demoPass });
        await api.login({ email: demoEmail, password: demoPass });
      }
      const user = await api.fetchMe();
      onAuthSuccess(user);
    } catch (err) {
      setError(err.message || 'Failed to initialize demo session');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 20px',
      backgroundColor: 'var(--surface-0)',
    }}>
      {/* Brand & Heading */}
      <div style={{ textAlign: 'center', marginBottom: '28px' }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '8px',
        }}>
          <Layers size={22} style={{ color: 'var(--primary-btn-bg)' }} />
          <span style={{ fontSize: '18px', fontWeight: 500, letterSpacing: '-0.01em' }}>
            SME Connect
          </span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          No-code workflow automation for small and medium enterprises
        </p>
      </div>

      {/* Main Auth Card: surface-2, pure white with hairline border */}
      <div style={{
        maxWidth: '460px',
        width: '100%',
        backgroundColor: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        padding: '32px',
      }}>
        {/* Navigation Tabs (Sentence case) */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border)',
          marginBottom: '24px',
          gap: '8px',
        }}>
          {[
            { id: 'login', label: 'Sign in' },
            { id: 'register', label: 'Create account' },
          ].map((tab) => (

            <button
              key={tab.id}
              onClick={() => {
                setMode(tab.id);
                setError(null);
              }}
              style={{
                padding: '8px 14px',
                border: 'none',
                borderBottom: mode === tab.id ? '2px solid var(--primary-btn-bg)' : '2px solid transparent',
                backgroundColor: 'transparent',
                color: mode === tab.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontSize: '14px',
                fontWeight: mode === tab.id ? 500 : 400,
                cursor: 'pointer',
                marginBottom: '-1px',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Feedback Alerts */}
        {error && (
          <div style={{
            padding: '10px 14px',
            borderRadius: '8px',
            backgroundColor: 'var(--status-warning-bg)',
            color: 'var(--status-warning-text)',
            fontSize: '13px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <AlertTriangle size={15} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {/* 1. Login Form */}
        {mode === 'login' && (
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: '16px' }}>
              <label className="form-label">Email address</label>
              <div style={{ position: 'relative' }}>
                <input
                  type="email"
                  required
                  className="form-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                />
              </div>
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label className="form-label">Password</label>
              <input
                type="password"
                required
                className="form-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            {/* Exactly ONE primary CTA per screen (Hick's Law) */}
            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
              style={{ width: '100%', justifyContent: 'center', padding: '10px' }}
            >
              {loading && <span className="spinner" />}
              <span>{loading ? 'Signing in...' : 'Sign in'}</span>
            </button>
          </form>
        )}

        {/* 2. Registration Form */}
        {mode === 'register' && (
          <form onSubmit={handleRegister}>
            <div style={{ marginBottom: '14px' }}>
              <label className="form-label">Full name</label>
              <input
                type="text"
                required
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Alex Morgan"
              />
            </div>

            <div style={{ marginBottom: '14px' }}>
              <label className="form-label">Work email</label>
              <input
                type="email"
                required
                className="form-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="alex@company.com"
              />
            </div>

            <div style={{ marginBottom: '18px' }}>
              <label className="form-label">Password</label>
              <input
                type="password"
                required
                minLength={8}
                className="form-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimum 8 characters"
              />
            </div>

            {/* Explicit Module 1 Lifecycle Notice */}
            <div style={{
              backgroundColor: 'var(--surface-1)',
              borderRadius: '8px',
              padding: '12px 14px',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              lineHeight: 1.45,
              marginBottom: '20px',
            }}>
              <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>Important note: </span>
              An invitation can be created for an email address that does not yet have an account. Registration does not automatically create organization membership; membership is created when the user accepts the invitation.
            </div>

            {/* Primary button */}
            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
              style={{ width: '100%', justifyContent: 'center', padding: '10px' }}
            >
              {loading && <span className="spinner" />}
              <span>{loading ? 'Creating account...' : 'Create account'}</span>
            </button>
          </form>
        )}

        {/* Quick Demo Access Bar */}
        <div style={{
          marginTop: '28px',
          paddingTop: '20px',
          borderTop: '1px solid var(--border)',
        }}>
          <div style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            marginBottom: '10px',
            letterSpacing: '0.04em',
          }} className="kicker-label">
            QUICK DEMO EVALUATION
          </div>

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => handleQuickDemo('admin')}
              disabled={loading}
              style={{ flex: 1, fontSize: '13px', justifyContent: 'center', padding: '7px 10px' }}
            >
              <span>Admin Demo</span>
            </button>

            <button
              type="button"
              className="btn-secondary"
              onClick={() => handleQuickDemo('employee')}
              disabled={loading}
              style={{ flex: 1, fontSize: '13px', justifyContent: 'center', padding: '7px 10px' }}
            >
              <span>Invited Employee</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
