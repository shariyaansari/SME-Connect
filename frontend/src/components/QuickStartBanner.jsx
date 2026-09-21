import React from 'react';
import { ArrowRight, Sparkles, FileSpreadsheet, Users, Zap } from 'lucide-react';

export default function QuickStartBanner({ onConnectApp }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(168, 85, 247, 0.08) 50%, rgba(22, 32, 50, 0.6) 100%)',
      border: '1px solid rgba(99, 102, 241, 0.3)',
      borderRadius: 'var(--radius-lg)',
      padding: '1.5rem 1.75rem',
      marginBottom: '2rem',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute',
        top: '-40px',
        right: '-40px',
        width: '180px',
        height: '180px',
        background: 'radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1.5rem', flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
            <Sparkles size={16} color="var(--accent-light)" />
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--accent-light)',
            }}>Golden Reference Workflow</span>
          </div>

          <h2 style={{ fontSize: '1.35rem', marginBottom: '0.35rem', color: '#ffffff' }}>
            Google Sheets → CRM Lead Automation
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '640px', lineHeight: 1.45 }}>
            Eliminate manual copy-pasting for customer inquiries. Connect your spreadsheet and CRM to automatically capture, map, and sync incoming leads in real-time.
          </p>

          {/* Workflow Pipeline Diagram */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '1rem' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: 'rgba(255, 255, 255, 0.06)',
              padding: '0.35rem 0.65rem',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              fontSize: '0.8rem',
            }}>
              <FileSpreadsheet size={14} color="#10b981" />
              <span>Google Sheets (Trigger)</span>
            </div>

            <ArrowRight size={14} color="var(--text-muted)" />

            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: 'rgba(99, 102, 241, 0.15)',
              padding: '0.35rem 0.65rem',
              borderRadius: '6px',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              fontSize: '0.8rem',
              color: 'var(--accent-light)',
            }}>
              <Zap size={14} />
              <span>Auto Data Mapping</span>
            </div>

            <ArrowRight size={14} color="var(--text-muted)" />

            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: 'rgba(255, 255, 255, 0.06)',
              padding: '0.35rem 0.65rem',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              fontSize: '0.8rem',
            }}>
              <Users size={14} color="#f59e0b" />
              <span>CRM (Create Lead)</span>
            </div>
          </div>
        </div>

        {/* Quick connect CTA */}
        <div style={{ display: 'flex', gap: '0.75rem', alignSelf: 'center' }}>
          <button
            onClick={() => onConnectApp('google_sheets')}
            style={{
              padding: '0.55rem 1rem',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              background: 'rgba(255, 255, 255, 0.08)',
              color: '#ffffff',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              transition: 'background 0.2s',
            }}
          >
            <FileSpreadsheet size={16} color="#10b981" />
            <span>Connect Sheets</span>
          </button>

          <button
            onClick={() => onConnectApp('crm')}
            style={{
              padding: '0.55rem 1rem',
              borderRadius: '8px',
              border: 'none',
              background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
              color: '#ffffff',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 2px 10px var(--accent-glow)',
            }}
          >
            <Users size={16} />
            <span>Connect CRM</span>
          </button>
        </div>
      </div>
    </div>
  );
}
