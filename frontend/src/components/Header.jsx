import React from 'react';
import { Layers, CheckCircle, Plus, RefreshCw, Radio } from 'lucide-react';

export default function Header({ activeTab, setActiveTab, connectionsCount, currentOrg, onRefresh, isRefreshing }) {
  return (
    <header style={{
      borderBottom: '1px solid var(--border)',
      background: 'rgba(11, 15, 23, 0.8)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 40,
      padding: '0.85rem 2rem',
    }}>
      <div style={{
        maxWidth: '1280px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
      }}>
        {/* Brand & Workspace */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 16px rgba(99, 102, 241, 0.4)',
            }}>
              <Layers size={20} color="#ffffff" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontWeight: 800, fontSize: '1.15rem', letterSpacing: '-0.02em' }}>SME Connect</span>
                <span style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  padding: '0.15rem 0.45rem',
                  borderRadius: '9999px',
                  background: 'rgba(99, 102, 241, 0.15)',
                  color: 'var(--accent-light)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                }}>v0.1</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Workflow Automation Platform</p>
            </div>
          </div>

          <div style={{
            height: '24px',
            width: '1px',
            background: 'var(--border)',
          }} />

          {/* Current Workspace Tag */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.35rem 0.75rem',
            borderRadius: '8px',
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid var(--border)',
            fontSize: '0.85rem',
          }}>
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: 'var(--success)',
              boxShadow: '0 0 8px var(--success)',
            }} />
            <span style={{ color: 'var(--text-secondary)' }}>Workspace:</span>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{currentOrg?.name || 'Default Workspace'}</span>
            <span style={{
              fontSize: '0.7rem',
              color: 'var(--accent-light)',
              background: 'rgba(99, 102, 241, 0.12)',
              padding: '0.1rem 0.4rem',
              borderRadius: '4px',
              fontWeight: 600,
            }}>{currentOrg?.role || 'Admin'}</span>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', background: 'rgba(255, 255, 255, 0.03)', padding: '0.25rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
          <button
            onClick={() => setActiveTab('catalog')}
            style={{
              padding: '0.45rem 1rem',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.875rem',
              transition: 'all 0.2s',
              background: activeTab === 'catalog' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'catalog' ? '#ffffff' : 'var(--text-secondary)',
              boxShadow: activeTab === 'catalog' ? '0 2px 8px var(--accent-glow)' : 'none',
            }}
          >
            App Catalog
          </button>

          <button
            onClick={() => setActiveTab('connected')}
            style={{
              padding: '0.45rem 1rem',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.875rem',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: activeTab === 'connected' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'connected' ? '#ffffff' : 'var(--text-secondary)',
              boxShadow: activeTab === 'connected' ? '0 2px 8px var(--accent-glow)' : 'none',
            }}
          >
            <span>Connected Apps</span>
            <span style={{
              fontSize: '0.72rem',
              padding: '0.1rem 0.45rem',
              borderRadius: '9999px',
              background: activeTab === 'connected' ? 'rgba(255, 255, 255, 0.25)' : 'rgba(255, 255, 255, 0.08)',
              color: '#ffffff',
            }}>
              {connectionsCount}
            </span>
          </button>
        </nav>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={onRefresh}
            title="Refresh Data"
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              borderRadius: '8px',
              padding: '0.5rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s',
            }}
          >
            <RefreshCw size={16} className={isRefreshing ? 'spinner' : ''} />
          </button>

          <button
            onClick={() => setActiveTab('catalog')}
            style={{
              background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
              border: 'none',
              color: '#ffffff',
              padding: '0.5rem 0.95rem',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              boxShadow: '0 2px 10px var(--accent-glow)',
            }}
          >
            <Plus size={16} />
            <span>Connect App</span>
          </button>
        </div>
      </div>
    </header>
  );
}
