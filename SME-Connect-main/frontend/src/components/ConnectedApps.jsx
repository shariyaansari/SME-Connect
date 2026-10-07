import React, { useState } from 'react';
import {
  FileSpreadsheet,
  Users,
  Globe,
  MessageSquare,
  Zap,
  CreditCard,
  BookOpen,
  KeyRound,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Trash2,
  Plus
} from 'lucide-react';

export default function ConnectedApps({
  connections,
  onTestConnection,
  onDeleteConnection,
  onEditConnection,
  onOpenCatalog,
  canManage = true,
}) {
  const [testingId, setTestingId] = useState(null);
  const [testResult, setTestResult] = useState({});

  const getIcon = (slug) => {
    switch (slug) {
      case 'google_sheets':
        return FileSpreadsheet;
      case 'crm':
        return Users;
      case 'stripe':
        return CreditCard;
      case 'zoho_books':
        return BookOpen;
      case 'custom_api':
        return Globe;
      case 'whatsapp':
        return MessageSquare;
      default:
        return Zap;
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
          message: err.message || 'Connection test failed',
        },
      }));
    } finally {
      setTestingId(null);
    }
  };

  const activeCount = connections.filter((c) => c.status === 'active').length;
  const failingCount = connections.length - activeCount;

  return (
    <div>
      {/* Screen Title & Single Primary CTA (Hick's Law) */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '20px',
        gap: '16px',
        flexWrap: 'wrap',
      }}>
        <div>
          <h2>Connected apps</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '2px' }}>
            Active authenticated integrations and real-time connectivity status.
          </p>
        </div>

        {/* Exactly one primary CTA on this screen */}
        <button
          className="btn-primary"
          onClick={onOpenCatalog}
          disabled={!canManage}
          title={canManage ? 'Add connection' : 'Viewer role has read-only access to connections'}
          style={!canManage ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
        >
          <Plus size={15} />
          <span>Add connection</span>
        </button>
      </div>

      {/* Metric Tiles: 3-column grid, flat surface-1 blocks, no borders (Miller's Law) */}
      <div className="metric-grid">
        <div className="metric-tile">
          <div className="metric-tile-label">Connected applications</div>
          <div className="metric-tile-value">{connections.length}</div>
        </div>
        <div className="metric-tile">
          <div className="metric-tile-label">Operational connections</div>
          <div className="metric-tile-value">{activeCount}</div>
        </div>
        <div className="metric-tile">
          <div className="metric-tile-label">Issues detected</div>
          <div className="metric-tile-value">{failingCount}</div>
        </div>
      </div>

      {/* Dense List: surface-2 container with hairline dividers (Fitts's Law + Gestalt) */}
      {connections.length === 0 ? (
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '10px',
          padding: '36px 20px',
          textAlign: 'center',
        }}>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '14px' }}>
            No applications connected yet. Connect Google Sheets, CRM, or Custom API to get started.
          </p>
          <button
            className="btn-secondary"
            onClick={onOpenCatalog}
            disabled={!canManage}
            title={canManage ? 'Browse catalog' : 'Viewer role has read-only access'}
            style={!canManage ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
          >
            Browse app catalog
          </button>
        </div>
      ) : (
        <div className="list-container">
          {connections.map((conn) => {
            const Icon = getIcon(conn.connector_slug);
            const isActive = conn.status === 'active';
            const isTesting = testingId === conn.id;
            const result = testResult[conn.id];

            return (
              <div key={conn.id} className="list-row">
                {/* Left: Leading icon + Title + Subtitle/meta */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0, paddingRight: '16px' }}>
                  <Icon size={18} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{
                      fontSize: '14px',
                      fontWeight: 500,
                      color: 'var(--text-primary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {conn.name}
                    </div>
                    <div style={{
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {conn.connector_slug.replace('_', ' ')} • Auth: {conn.auth_type} • Configured in organization
                    </div>
                    {/* Live Test Feedback Banner if tested */}
                    {result && (
                      <div style={{
                        marginTop: '4px',
                        fontSize: '11px',
                        color: result.success ? 'var(--status-success-text)' : 'var(--status-warning-text)',
                      }}>
                        {result.message}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Status Pill + Action Controls in fixed right-aligned position */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                  {/* Status badge: pill-shaped, 12px text, light tint bg + dark text from same color family */}
                  <span className={`status-pill ${isActive ? 'success' : 'warning'}`}>
                    {isActive ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
                    <span>{isActive ? 'Operational' : 'Needs attention'}</span>
                  </span>

                  {/* Reconnect / Edit credentials button */}
                  <button
                    className="btn-secondary"
                    onClick={() => onEditConnection && onEditConnection(conn)}
                    disabled={!canManage}
                    title={canManage ? 'Edit or reconnect integration credentials' : 'Viewer role has read-only access'}
                    style={{
                      fontSize: '12px',
                      padding: '4px 8px',
                      opacity: canManage ? 1 : 0.5,
                      cursor: canManage ? 'pointer' : 'not-allowed',
                    }}
                  >
                    <KeyRound size={12} />
                    <span>Edit</span>
                  </button>

                  {/* Bare-outline secondary test button */}
                  <button
                    className="btn-secondary"
                    onClick={() => handleTest(conn.id)}
                    disabled={isTesting || !canManage}
                    title={canManage ? 'Test live connectivity' : 'Viewer role has read-only access'}
                    style={{
                      fontSize: '12px',
                      padding: '4px 8px',
                      opacity: (canManage || isTesting) ? 1 : 0.5,
                      cursor: canManage ? 'pointer' : 'not-allowed',
                    }}
                  >
                    <RefreshCw size={12} className={isTesting ? 'spinner' : ''} />
                    <span>{isTesting ? 'Testing' : 'Test'}</span>
                  </button>

                  <button
                    className="btn-secondary"
                    onClick={() => {
                      if (window.confirm(`Disconnect "${conn.name}"?`)) {
                        onDeleteConnection(conn.id);
                      }
                    }}
                    disabled={!canManage}
                    title={canManage ? 'Disconnect integration' : 'Viewer role has read-only access'}
                    style={{
                      padding: '4px 8px',
                      color: 'var(--text-muted)',
                      opacity: canManage ? 1 : 0.5,
                      cursor: canManage ? 'pointer' : 'not-allowed',
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
