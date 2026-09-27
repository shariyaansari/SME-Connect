import {
  X,
  Shield,
  FileSpreadsheet,
  Users,
  Globe,
  MessageSquare,
  Zap,
  CreditCard,
  BookOpen,
  AlertTriangle
} from 'lucide-react';

function renderConnectorIcon(slug, size = 18) {
  switch (slug) {
    case 'google_sheets':
      return <FileSpreadsheet size={size} style={{ color: 'var(--text-secondary)' }} />;
    case 'crm':
      return <Users size={size} style={{ color: 'var(--text-secondary)' }} />;
    case 'stripe':
      return <CreditCard size={size} style={{ color: 'var(--text-secondary)' }} />;
    case 'zoho_books':
      return <BookOpen size={size} style={{ color: 'var(--text-secondary)' }} />;
    case 'custom_api':
      return <Globe size={size} style={{ color: 'var(--text-secondary)' }} />;
    case 'whatsapp':
      return <MessageSquare size={size} style={{ color: 'var(--text-secondary)' }} />;
    default:
      return <Zap size={size} style={{ color: 'var(--text-secondary)' }} />;
  }
}

export default function ConnectModal({ connector, initialConnection, onClose, onSave }) {
  const isEdit = Boolean(initialConnection);
  const [name, setName] = useState(initialConnection?.name || `My ${connector.name}`);
  const [config, setConfig] = useState(() => {
    const initial = {};
    (connector.config_fields || []).forEach((field) => {
      initial[field.key] = field.options ? field.options[0] : '';
    });
    if (initialConnection?.config) {
      Object.assign(initial, initialConnection.config);
    }
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        name: name.trim(),
        auth_type: connector.auth_type || 'api_key',
        config,
      };
      // Only include credentials if any were entered
      const hasCreds = Object.values(credentials).some((val) => val && val.trim() !== '');
      if (hasCreds || !isEdit) {
        payload.credentials = credentials;
      }
      if (!isEdit) {
        payload.connector_slug = connector.slug;
      }

      await onSave(payload);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to establish connection');
    } finally {
      setLoading(false);
    }
  };

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
        maxWidth: '480px',
        width: '100%',
        maxHeight: '90vh',
        overflowY: 'auto',
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {renderConnectorIcon(connector.slug, 18)}
            <div>
              <h3>{isEdit ? `Update ${connector.name}` : `Connect ${connector.name}`}</h3>

              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                {isEdit ? 'Update credentials or settings & re-verify health' : 'Configure credentials and organization scope'}
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

        {/* Modal Body Form */}
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

          {/* Connection Name */}
          <div style={{ marginBottom: '14px' }}>
            <label className="form-label">Connection name</label>
            <input
              type="text"
              required
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Sales inquiries spreadsheet"
            />
          </div>

          {/* Config fields */}
          {(connector.config_fields || []).map((field) => (
            <div key={field.key} style={{ marginBottom: '14px' }}>
              <label className="form-label">{field.label}</label>
              {field.type === 'select' ? (
                <select
                  className="form-select"
                  value={config[field.key] || ''}
                  onChange={(e) => setConfig({ ...config, [field.key]: e.target.value })}
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
                  className="form-input"
                  value={config[field.key] || ''}
                  onChange={(e) => setConfig({ ...config, [field.key]: e.target.value })}
                  placeholder={field.placeholder || ''}
                />
              )}
            </div>
          ))}

          {/* Credential fields */}
          {(connector.credential_fields || []).map((field) => (
            <div key={field.key} style={{ marginBottom: '14px' }}>
              <label className="form-label">{field.label}</label>
              <input
                type={field.type === 'password' ? 'password' : 'text'}
                required={field.required}
                className="form-input"
                value={credentials[field.key] || ''}
                onChange={(e) => setCredentials({ ...credentials, [field.key]: e.target.value })}
                placeholder={field.placeholder || ''}
              />
            </div>
          ))}

          {/* Helper prefill button & security statement */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginTop: '8px',
            marginBottom: '20px',
            fontSize: '12px',
          }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={handlePrefillDemo}
              style={{ fontSize: '11px', padding: '3px 8px' }}
            >
              Fill sample data
            </button>

            <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Shield size={12} />
              <span>Encrypted at rest</span>
            </span>
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
              <span>{loading ? 'Saving...' : (isEdit ? 'Update & re-test' : 'Test & save connection')}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
