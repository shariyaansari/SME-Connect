import React, { useState } from 'react';
import { X, ShieldCheck, Zap, AlertCircle, FileSpreadsheet, Users, Globe, MessageCircle } from 'lucide-react';

export default function ConnectModal({ connector, onClose, onSave }) {
  const [name, setName] = useState(`My ${connector.name}`);
  const [config, setConfig] = useState(() => {
    const initial = {};
    (connector.config_fields || []).forEach((field) => {
      initial[field.key] = field.options ? field.options[0] : '';
    });
    return initial;
  });
  const [credentials, setCredentials] = useState(() => {
    const initial = {};
    (connector.credential_fields || []).forEach((field) => {
      initial[field.key] = '';
    });
    return initial;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const getIcon = (iconName) => {
    switch (iconName) {
      case 'table':
        return <FileSpreadsheet size={22} color="#10b981" />;
      case 'users':
        return <Users size={22} color="#f59e0b" />;
      case 'globe':
        return <Globe size={22} color="#38bdf8" />;
      case 'message-circle':
        return <MessageCircle size={22} color="#22c55e" />;
      default:
        return <Zap size={22} color="var(--accent-light)" />;
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await onSave({
        connector_slug: connector.slug,
        name: name.trim(),
        auth_type: connector.auth_type || 'api_key',
        config,
        credentials,
      });
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to establish connection');
    } finally {
      setLoading(false);
    }
  };

  // Pre-fill demo data helper
  const handlePrefillDemo = () => {
    if (connector.slug === 'google_sheets') {
      setConfig({
        spreadsheet_id: '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms',
        sheet_name: 'CustomerLeads',
      });
      setCredentials({
        client_id: 'sheets-service@sme-automation.iam.gserviceaccount.com',
        client_secret: 'sec_prod_live_key_987654321',
      });
    } else if (connector.slug === 'crm') {
      setConfig({
        crm_provider: 'HubSpot',
        api_base_url: 'https://api.hubapi.com',
      });
      setCredentials({
        api_key: 'pat-na1-89304928-8921-prod-token',
      });
    } else if (connector.slug === 'custom_api') {
      setConfig({
        base_url: 'https://api.internal-sme.com/v1/leads',
        headers: '{"Content-Type": "application/json"}',
      });
      setCredentials({
        auth_header_value: 'Bearer secret_live_token_7788',
      });
    } else if (connector.slug === 'whatsapp') {
      setConfig({
        phone_number_id: '109876543210987',
        business_account_id: '998877665544332',
      });
      setCredentials({
        access_token: 'EAAx_prod_whatsapp_system_token_xyz',
      });
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(5, 8, 15, 0.82)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
      padding: '1rem',
    }}>
      <div
        className="glass-panel animate-fade-in"
        style={{
          width: '100%',
          maxWidth: '540px',
          background: '#131b2c',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        {/* Modal Header */}
        <div style={{
          padding: '1.25rem 1.5rem',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'rgba(255, 255, 255, 0.05)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {getIcon(connector.icon)}
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', color: '#ffffff' }}>Connect {connector.name}</h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Configure credentials & permissions</p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              type="button"
              onClick={handlePrefillDemo}
              style={{
                background: 'rgba(99, 102, 241, 0.15)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                color: 'var(--accent-light)',
                borderRadius: '6px',
                padding: '0.25rem 0.6rem',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Fill Sample Data
            </button>

            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '0.35rem',
                borderRadius: '6px',
                display: 'flex',
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '1.5rem' }}>
          {error && (
            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: 'var(--danger-bg)',
              border: '1px solid var(--danger-border)',
              color: 'var(--danger)',
              fontSize: '0.85rem',
              marginBottom: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {/* Connection Display Name */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Connection Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Sales Team Leads Sheet"
              style={{
                width: '100%',
                padding: '0.55rem 0.75rem',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                background: 'rgba(0, 0, 0, 0.25)',
                color: '#ffffff',
                fontSize: '0.88rem',
                outline: 'none',
              }}
            />
          </div>

          {/* Config Fields */}
          {(connector.config_fields || []).map((field) => (
            <div key={field.key} style={{ marginBottom: '1.15rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                {field.label} {field.required && <span style={{ color: 'var(--accent)' }}>*</span>}
              </label>

              {field.type === 'select' ? (
                <select
                  value={config[field.key] || ''}
                  onChange={(e) => setConfig({ ...config, [field.key]: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '0.55rem 0.75rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border)',
                    background: '#1a2438',
                    color: '#ffffff',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                >
                  {(field.options || []).map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={field.type === 'password' ? 'password' : 'text'}
                  required={field.required}
                  value={config[field.key] || ''}
                  onChange={(e) => setConfig({ ...config, [field.key]: e.target.value })}
                  placeholder={field.placeholder || ''}
                  style={{
                    width: '100%',
                    padding: '0.55rem 0.75rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border)',
                    background: 'rgba(0, 0, 0, 0.25)',
                    color: '#ffffff',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                />
              )}

              {field.help_text && (
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  {field.help_text}
                </p>
              )}
            </div>
          ))}

          {/* Credential Fields */}
          {(connector.credential_fields || []).map((field) => (
            <div key={field.key} style={{ marginBottom: '1.15rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                {field.label} {field.required && <span style={{ color: 'var(--accent)' }}>*</span>}
              </label>
              <input
                type={field.type === 'password' ? 'password' : 'text'}
                required={field.required}
                value={credentials[field.key] || ''}
                onChange={(e) => setCredentials({ ...credentials, [field.key]: e.target.value })}
                placeholder={field.placeholder || ''}
                style={{
                  width: '100%',
                  padding: '0.55rem 0.75rem',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  background: 'rgba(0, 0, 0, 0.25)',
                  color: '#ffffff',
                  fontSize: '0.88rem',
                  outline: 'none',
                }}
              />
            </div>
          ))}

          {/* Security Note */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.65rem 0.85rem',
            borderRadius: '8px',
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.2)',
            color: 'var(--success)',
            fontSize: '0.75rem',
            marginBottom: '1.5rem',
          }}>
            <ShieldCheck size={16} />
            <span>Credentials are strictly encrypted and scoped to your organization.</span>
          </div>

          {/* Modal Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '0.55rem 1rem',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                background: 'transparent',
                color: 'var(--text-secondary)',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '0.55rem 1.25rem',
                borderRadius: '8px',
                border: 'none',
                background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                color: '#ffffff',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: loading ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                boxShadow: '0 2px 12px var(--accent-glow)',
              }}
            >
              {loading && <span className="spinner" />}
              <span>{loading ? 'Verifying & Saving...' : 'Test & Save Connection'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
