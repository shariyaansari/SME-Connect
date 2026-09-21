import React, { useState } from 'react';
import {
  FileSpreadsheet,
  Users,
  Globe,
  MessageCircle,
  Zap,
  Activity,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Plus
} from 'lucide-react';

export default function ConnectedApps({ connections, onTestConnection, onDeleteConnection, onOpenCatalog }) {
  const [testingId, setTestingId] = useState(null);
  const [testResult, setTestResult] = useState({});

  const getIcon = (slug) => {
    switch (slug) {
      case 'google_sheets':
        return <FileSpreadsheet size={22} color="#10b981" />;
      case 'crm':
        return <Users size={22} color="#f59e0b" />;
      case 'custom_api':
        return <Globe size={22} color="#38bdf8" />;
      case 'whatsapp':
        return <MessageCircle size={22} color="#22c55e" />;
      default:
        return <Zap size={22} color="var(--accent-light)" />;
    }
  };

  const handleTest = async (connId) => {
    setTestingId(connId);
    setTestResult((prev) => ({ ...prev, [connId]: null }));
    try {
      const result = await onTestConnection(connId);
      setTestResult((prev) => ({
        ...prev,
        [connId]: {
          success: result.success,
          message: result.message,
        },
      }));
    } catch (err) {
      setTestResult((prev) => ({
        ...prev,
        [connId]: {
          success: false,
          message: err.message || 'Health check failed',
        },
      }));
    } finally {
      setTestingId(null);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'Never';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ', ' + d.toLocaleDateString();
    } catch {
      return isoString;
    }
  };

  if (connections.length === 0) {
    return (
      <div className="glass-panel" style={{
        padding: '3.5rem 2rem',
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div style={{
          width: '56px',
          height: '56px',
          borderRadius: '16px',
          background: 'rgba(99, 102, 241, 0.12)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '1rem',
        }}>
          <Zap size={28} color="var(--accent-light)" />
        </div>
        <h3 style={{ fontSize: '1.25rem', color: '#ffffff', marginBottom: '0.35rem' }}>No apps connected yet</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '420px', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Connect your Google Sheets, CRM, or Custom API to start automating workflows and syncing business data.
        </p>
        <button
          onClick={onOpenCatalog}
          style={{
            padding: '0.6rem 1.25rem',
            borderRadius: '8px',
            border: 'none',
            background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
            color: '#ffffff',
            fontWeight: 600,
            fontSize: '0.9rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            boxShadow: '0 2px 12px var(--accent-glow)',
          }}
        >
          <Plus size={16} />
          <span>Browse App Catalog</span>
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h3 style={{ fontSize: '1.15rem', color: '#ffffff' }}>Active Integrations ({connections.length})</h3>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Credentials securely masked & encrypted</span>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
        gap: '1.25rem',
      }}>
        {connections.map((conn) => {
          const isTesting = testingId === conn.id;
          const result = testResult[conn.id];
          const isActive = conn.status === 'active';

          return (
            <div
              key={conn.id}
              className="glass-panel"
              style={{
                padding: '1.25rem 1.4rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                borderLeft: `4px solid ${isActive ? 'var(--success)' : 'var(--danger)'}`,
              }}
            >
              <div>
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <div style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '10px',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid var(--border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      {getIcon(conn.connector_slug)}
                    </div>
                    <div>
                      <h4 style={{ fontSize: '0.98rem', color: '#ffffff' }}>{conn.name}</h4>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                        {conn.connector_slug.replace('_', ' ')} • Auth: {conn.auth_type}
                      </span>
                    </div>
                  </div>

                  {/* Status Badge */}
                  <span style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    padding: '0.2rem 0.55rem',
                    borderRadius: '9999px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    background: isActive ? 'var(--success-bg)' : 'var(--danger-bg)',
                    border: `1px solid ${isActive ? 'var(--success-border)' : 'var(--danger-border)'}`,
                    color: isActive ? 'var(--success)' : 'var(--danger)',
                  }}>
                    <span style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: isActive ? 'var(--success)' : 'var(--danger)',
                      display: 'inline-block',
                      animation: isActive ? 'pulseGlow 2s infinite' : 'none',
                    }} />
                    {isActive ? 'ACTIVE' : 'ERROR'}
                  </span>
                </div>

                {/* Configuration / Config details */}
                <div style={{
                  background: 'rgba(0, 0, 0, 0.22)',
                  borderRadius: '8px',
                  padding: '0.75rem',
                  fontSize: '0.78rem',
                  marginBottom: '0.85rem',
                  border: '1px solid rgba(255, 255, 255, 0.03)',
                }}>
                  {Object.entries(conn.config || {}).length > 0 ? (
                    Object.entries(conn.config).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>{k.replace('_', ' ')}:</span>
                        <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {String(v)}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div style={{ color: 'var(--text-muted)' }}>No additional config</div>
                  )}

                  {/* Masked Credentials Sample */}
                  {Object.entries(conn.masked_credentials || {}).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.25rem' }}>
                      <span style={{ color: 'var(--text-muted)' }}>{k}:</span>
                      <span style={{ color: 'var(--accent-light)', fontFamily: 'var(--font-mono)' }}>{v}</span>
                    </div>
                  ))}
                </div>

                {/* Last Tested Info */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.85rem' }}>
                  <Clock size={13} />
                  <span>Last verified: {formatDate(conn.last_tested_at)}</span>
                </div>

                {/* Health Check Error Message */}
                {conn.error_message && (
                  <div style={{
                    padding: '0.55rem 0.75rem',
                    borderRadius: '6px',
                    background: 'var(--danger-bg)',
                    border: '1px solid var(--danger-border)',
                    color: 'var(--danger)',
                    fontSize: '0.78rem',
                    marginBottom: '0.85rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                  }}>
                    <AlertCircle size={14} style={{ flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{conn.error_message}</span>
                  </div>
                )}

                {/* Live Test Feedback Banner */}
                {result && (
                  <div style={{
                    padding: '0.55rem 0.75rem',
                    borderRadius: '6px',
                    background: result.success ? 'var(--success-bg)' : 'var(--danger-bg)',
                    border: `1px solid ${result.success ? 'var(--success-border)' : 'var(--danger-border)'}`,
                    color: result.success ? 'var(--success)' : 'var(--danger)',
                    fontSize: '0.78rem',
                    marginBottom: '0.85rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                  }}>
                    {result.success ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                    <span>{result.message}</span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{
                display: 'flex',
                gap: '0.6rem',
                borderTop: '1px solid var(--border)',
                paddingTop: '0.85rem',
                marginTop: '0.25rem',
              }}>
                <button
                  onClick={() => handleTest(conn.id)}
                  disabled={isTesting}
                  style={{
                    flex: 1,
                    padding: '0.45rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-light)',
                    background: 'rgba(255, 255, 255, 0.05)',
                    color: 'var(--text-primary)',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: isTesting ? 'wait' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.4rem',
                    transition: 'background 0.2s',
                  }}
                >
                  <Activity size={14} className={isTesting ? 'spinner' : ''} />
                  <span>{isTesting ? 'Testing...' : 'Test Connection'}</span>
                </button>

                <button
                  onClick={() => {
                    if (window.confirm(`Disconnect and remove "${conn.name}"?`)) {
                      onDeleteConnection(conn.id);
                    }
                  }}
                  title="Delete Connection"
                  style={{
                    padding: '0.45rem 0.65rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(239, 68, 68, 0.2)',
                    background: 'rgba(239, 68, 68, 0.08)',
                    color: 'var(--danger)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'background 0.2s',
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
