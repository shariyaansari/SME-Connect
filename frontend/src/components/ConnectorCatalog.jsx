import React, { useState } from 'react';
import {
  Search,
  FileSpreadsheet,
  Users,
  Globe,
  MessageSquare,
  Zap,
  CreditCard,
  BookOpen,
  CheckCircle,
  Plus
} from 'lucide-react';

export default function ConnectorCatalog({ catalog, connectedSlugs, onSelectConnector, canManage = true }) {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  // Derive categories dynamically from catalog with fallbacks
  const categories = [
    'All',
    ...Array.from(new Set((catalog || []).map((c) => c.category))).filter(Boolean),
  ];

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

  const filtered = (catalog || []).filter((item) => {
    const matchesSearch =
      item.name.toLowerCase().includes(search.toLowerCase()) ||
      item.description.toLowerCase().includes(search.toLowerCase()) ||
      item.category.toLowerCase().includes(search.toLowerCase());
    const matchesCat =
      selectedCategory === 'All' ||
      item.category.toLowerCase().includes(selectedCategory.toLowerCase());
    return matchesSearch && matchesCat;
  });

  const availableCount = (catalog || []).filter((c) => c.slug === 'google_sheets' || c.slug === 'crm').length;
  const roadmapCount = Math.max(0, (catalog || []).length - availableCount);

  return (
    <div>
      {/* Screen Title */}
      <div style={{ marginBottom: '20px' }}>
        <h2>App catalog</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '2px' }}>
          Connect third-party enterprise tools to power your automated workflows.
        </p>
      </div>

      {/* 3 Metric Tiles (Miller's Law) */}
      <div className="metric-grid">
        <div className="metric-tile">
          <div className="metric-tile-label">Available in MVP</div>
          <div className="metric-tile-value">{availableCount}</div>
        </div>
        <div className="metric-tile">
          <div className="metric-tile-label">Planned (P1 roadmap)</div>
          <div className="metric-tile-value">{roadmapCount}</div>
        </div>
        <div className="metric-tile">
          <div className="metric-tile-label">MVP capabilities</div>
          <div className="metric-tile-value">Sheets & CRM</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        marginBottom: '16px',
        flexWrap: 'wrap',
      }}>
        {/* Category Pills (sentence case) */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  border: isSelected ? '1px solid var(--border-strong)' : '1px solid var(--border)',
                  backgroundColor: isSelected ? 'var(--surface-hover)' : 'transparent',
                  color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontSize: '12px',
                  fontWeight: isSelected ? 500 : 400,
                  cursor: 'pointer',
                  transition: 'background-color 0.15s ease',
                }}
              >
                {cat}
              </button>
            );
          })}
        </div>

        {/* Search input */}
        <div style={{ position: 'relative', width: '240px' }}>
          <Search size={14} style={{ position: 'absolute', left: '9px', top: '8px', color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="form-input"
            placeholder="Search catalog..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ paddingLeft: '28px', fontSize: '12px' }}
          />
        </div>
      </div>

      {/* Dense List: surface-2 container with hairline dividers */}
      <div className="list-container">
        {filtered.map((connector) => {
          const Icon = getIcon(connector.slug);
          const isConnected = connectedSlugs.includes(connector.slug);
          const isMvp = connector.slug === 'google_sheets' || connector.slug === 'crm';
          const isWhatsapp = connector.slug === 'whatsapp';

          let statusBadgeText = 'Available';
          let statusBadgeClass = 'success';
          if (!isMvp) {
            statusBadgeClass = 'neutral';
            statusBadgeText = isWhatsapp ? 'P1 Roadmap' : 'Coming soon / P1';
          } else if (isConnected) {
            statusBadgeText = 'Connected';
            statusBadgeClass = 'success';
          }

          return (
            <div key={connector.slug} className="list-row">
              {/* Left: Leading icon + Title + Description + Triggers & Actions */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1, minWidth: 0, paddingRight: '16px' }}>
                <Icon size={18} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {connector.name}
                    </span>
                    <span style={{
                      fontSize: '11px',
                      color: 'var(--text-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}>
                      {connector.category}
                    </span>
                  </div>

                  <div style={{
                    fontSize: '12px',
                    color: 'var(--text-secondary)',
                    marginTop: '2px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {connector.description}
                  </div>

                  <div style={{
                    fontSize: '11px',
                    color: 'var(--text-muted)',
                    marginTop: '2px',
                  }}>
                    {isMvp ? (
                      <>Triggers: {connector.supported_triggers?.map((t) => t.name).join(', ') || 'None'} • Actions: {connector.supported_actions?.map((a) => a.name).join(', ')}</>
                    ) : (
                      <>Scheduled for post-MVP release (P1)</>
                    )}
                  </div>
                </div>
              </div>

              {/* Right: Status Pill + Connect Button */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                <span className={`status-pill ${statusBadgeClass}`}>
                  {isConnected && <CheckCircle size={12} />}
                  <span>{statusBadgeText}</span>
                </span>

                {isMvp ? (
                  <button
                    className="btn-secondary"
                    onClick={() => onSelectConnector(connector)}
                    disabled={!canManage}
                    title={canManage ? (isConnected ? 'Add another connection' : 'Connect application') : 'Viewer role has read-only access'}
                    style={{
                      fontSize: '12px',
                      padding: '4px 10px',
                      opacity: canManage ? 1 : 0.5,
                      cursor: canManage ? 'pointer' : 'not-allowed',
                    }}
                  >
                    <Plus size={13} />
                    <span>{isConnected ? 'Add another' : 'Connect'}</span>
                  </button>
                ) : (
                  <button
                    className="btn-secondary"
                    disabled
                    title="Scheduled for P1 implementation"
                    style={{ fontSize: '12px', padding: '4px 10px', opacity: 0.5, cursor: 'not-allowed' }}
                  >
                    <span>{isWhatsapp ? 'P1' : 'Coming soon'}</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

    </div>
  );
}
