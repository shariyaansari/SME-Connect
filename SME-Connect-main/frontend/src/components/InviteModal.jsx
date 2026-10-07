import React, { useState } from 'react';
import { X, Mail, AlertTriangle } from 'lucide-react';


export default function InviteModal({ onClose, onInvite }) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('Viewer');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await onInvite({
        email: email.trim().toLowerCase(),
        role,
      });
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to send invitation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
      padding: '16px',
    }}>
      <div style={{
        backgroundColor: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        maxWidth: '440px',
        width: '100%',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Mail size={16} style={{ color: 'var(--text-secondary)' }} />
            <div>
              <h3>Invite organization member</h3>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Send an invitation to join this workspace
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="btn-secondary"
            style={{ padding: '4px', border: 'none' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '20px' }}>
          {error && (
            <div style={{
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: 'var(--status-warning-bg)',
              color: 'var(--status-warning-text)',
              fontSize: '12px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}>
              <AlertTriangle size={14} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <div style={{ marginBottom: '14px' }}>
            <label className="form-label">Email address</label>
            <input
              type="email"
              required
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@company.com"
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label className="form-label">Role</label>
            <select
              className="form-select"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              <option value="Viewer">Viewer — view workflows and execution results</option>
              <option value="Editor">Editor — create and manage workflows</option>
              <option value="Admin">Admin — full organization management</option>
            </select>
          </div>

          {/* Important Architecture Note (Module 1) */}
          <div style={{
            backgroundColor: 'var(--surface-1)',
            borderRadius: '6px',
            padding: '10px 12px',
            marginBottom: '20px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            lineHeight: 1.4,
          }}>
            An invitation can be created for an email address that does not yet have an account. Registration does not automatically create organization membership; membership is created when the user accepts the invitation.
          </div>

          {/* Actions: Hick's Law -> exactly one primary CTA */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
            >
              {loading && <span className="spinner" />}
              <span>{loading ? 'Sending...' : 'Send invitation'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
