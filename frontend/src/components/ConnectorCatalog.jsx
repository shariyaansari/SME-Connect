import React, { useState } from 'react';
import { Search, FileSpreadsheet, Users, Globe, MessageCircle, ArrowRight, Zap, Check } from 'lucide-react';

export default function ConnectorCatalog({ catalog, connectedSlugs, onSelectConnector }) {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  const categories = ['All', 'Spreadsheets', 'CRM', 'Developer Tools', 'Communication'];

  const getIcon = (iconName) => {
    switch (iconName) {
      case 'table':
        return <FileSpreadsheet size={24} color="#10b981" />;
      case 'users':
        return <Users size={24} color="#f59e0b" />;
      case 'globe':
        return <Globe size={24} color="#38bdf8" />;
      case 'message-circle':
        return <MessageCircle size={24} color="#22c55e" />;
      default:
        return <Zap size={24} color="var(--accent-light)" />;
    }
  };

  const filtered = catalog.filter((item) => {
    const matchesSearch =
      item.name.toLowerCase().includes(search.toLowerCase()) ||
      item.description.toLowerCase().includes(search.toLowerCase()) ||
      item.category.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = selectedCategory === 'All' || item.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div>
      {/* Search & Category Filter Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        marginBottom: '1.5rem',
        flexWrap: 'wrap',
      }}>
        {/* Category Pills */}
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: '8px',
                fontSize: '0.82rem',
                fontWeight: 600,
                border: selectedCategory === cat ? '1px solid var(--accent)' : '1px solid var(--border)',
                background: selectedCategory === cat ? 'rgba(99, 102, 241, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                color: selectedCategory === cat ? 'var(--accent-light)' : 'var(--text-secondary)',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative', width: '280px' }}>
          <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '10px', top: '10px' }} />
          <input
            type="text"
            placeholder="Search integrations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem 0.5rem 2.2rem',
              borderRadius: '8px',
              border: '1px solid var(--border)',
              background: 'rgba(255, 255, 255, 0.04)',
              color: '#ffffff',
              fontSize: '0.85rem',
              outline: 'none',
            }}
          />
        </div>
      </div>

      {/* Catalog Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: '1.25rem',
      }}>
        {filtered.map((connector) => {
          const isConnected = connectedSlugs.includes(connector.slug);

          return (
            <div
              key={connector.slug}
              className="glass-panel"
              style={{
                padding: '1.4rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'transform 0.2s, border-color 0.2s, box-shadow 0.2s',
                cursor: 'default',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.4)';
                e.currentTarget.style.boxShadow = 'var(--shadow-md)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <div>
                {/* Header: Icon, Name, Category */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '12px',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid var(--border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      {getIcon(connector.icon)}
                    </div>
                    <div>
                      <h3 style={{ fontSize: '1.05rem', color: '#ffffff', marginBottom: '0.15rem' }}>{connector.name}</h3>
                      <span style={{
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}>
                        {connector.category}
                      </span>
                    </div>
                  </div>

                  {isConnected && (
                    <span style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                      padding: '0.2rem 0.55rem',
                      borderRadius: '9999px',
                      background: 'var(--success-bg)',
                      border: '1px solid var(--success-border)',
                      color: 'var(--success)',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                    }}>
                      <Check size={12} />
                      Connected
                    </span>
                  )}
                </div>

                {/* Description */}
                <p style={{
                  fontSize: '0.85rem',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.45,
                  marginBottom: '1.25rem',
                  minHeight: '2.5rem',
                }}>
                  {connector.description}
                </p>

                {/* Capabilities (Triggers & Actions) */}
                <div style={{
                  background: 'rgba(0, 0, 0, 0.25)',
                  padding: '0.75rem',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.04)',
                  marginBottom: '1.25rem',
                  fontSize: '0.78rem',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Triggers:</span>
                    <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                      {connector.supported_triggers.map((t) => t.name).join(', ') || 'None'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Actions:</span>
                    <span style={{ color: 'var(--accent-light)', fontWeight: 600 }}>
                      {connector.supported_actions.map((a) => a.name).join(', ')}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => onSelectConnector(connector)}
                style={{
                  width: '100%',
                  padding: '0.6rem',
                  borderRadius: '8px',
                  border: isConnected ? '1px solid var(--border-light)' : 'none',
                  background: isConnected
                    ? 'rgba(255, 255, 255, 0.06)'
                    : 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                  color: '#ffffff',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.4rem',
                  transition: 'background 0.2s, box-shadow 0.2s',
                  boxShadow: isConnected ? 'none' : '0 2px 8px var(--accent-glow)',
                }}
              >
                <span>{isConnected ? 'Add Another Connection' : 'Connect Application'}</span>
                <ArrowRight size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
