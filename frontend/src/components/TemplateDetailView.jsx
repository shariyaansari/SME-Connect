import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Database,
  Users,
  MessageCircle,
  BookOpen,
  Zap,
  Check
} from 'lucide-react';
import { api } from '../api';

const categoryColors = {
  Sales: { bg: 'var(--status-success-bg)', text: 'var(--status-success-text)' },
  Billing: { bg: 'var(--status-warning-bg)', text: 'var(--status-warning-text)' },
  Operations: { bg: 'var(--status-neutral-bg)', text: 'var(--status-neutral-text)' },
  Notifications: { bg: '#e0e7ff', text: '#4338ca' },
};

const appIconMap = {
  google_sheets: <Database size={24} />,
  crm: <Users size={24} />,
  zoho_books: <BookOpen size={24} />,
  whatsapp: <MessageCircle size={24} />,
};

const getAppIcon = (slug, size = 24) => {
  const IconMapSmall = {
    google_sheets: <Database size={size} />,
    crm: <Users size={size} />,
    zoho_books: <BookOpen size={size} />,
    whatsapp: <MessageCircle size={size} />,
  };
  return IconMapSmall[slug] || <Zap size={size} />;
};

const formatAppName = (slug) => {
  return slug.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
};

export default function TemplateDetailView({ templateId, onBack }) {
  const [template, setTemplate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadTemplate = async () => {
      try {
        const data = await api.fetchTemplate(templateId);
        setTemplate(data);
      } catch (err) {
        setError(err.message || "Failed to load template details.");
      } finally {
        setLoading(false);
      }
    };
    loadTemplate();
  }, [templateId]);

  if (loading) {
    return (
      <div style={{ maxWidth: '800px', margin: '0 auto', padding: '60px 0', textAlign: 'center' }}>
        <div className="spinner" style={{ width: '32px', height: '32px', margin: '0 auto 16px' }} />
        <p style={{ color: 'var(--text-secondary)' }}>Loading template...</p>
      </div>
    );
  }

  if (error || !template) {
    return (
      <div style={{ maxWidth: '800px', margin: '0 auto', padding: '60px 0', textAlign: 'center' }}>
        <p style={{ color: 'var(--status-warning-text)', marginBottom: '16px' }}>{error || "Template not found"}</p>
        <button className="btn-secondary" onClick={onBack}>
          <ArrowLeft size={16} style={{ marginRight: '8px' }} /> Back to Templates
        </button>
      </div>
    );
  }

  const catColor = categoryColors[template.category] || categoryColors.Operations;

  // Infer steps for "What this workflow does"
  const workflowSteps = [];
  if (template.definition?.trigger) {
    workflowSteps.push(`Detects ${template.definition.trigger.event.replace('_', ' ')} from ${formatAppName(template.definition.trigger.connector)}`);
  }
  if (template.definition?.steps) {
    template.definition.steps.forEach(step => {
      workflowSteps.push(`Executes ${step.action.replace('_', ' ')} in ${formatAppName(step.connector)}`);
    });
  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px 0' }}>
      
      {/* Top Navigation */}
      <button 
        className="btn-secondary" 
        onClick={onBack}
        style={{ 
          padding: '6px 12px', 
          fontSize: '13px', 
          marginBottom: '32px',
          border: 'none',
          backgroundColor: 'transparent',
          boxShadow: 'none',
          color: 'var(--text-secondary)'
        }}
      >
        <ArrowLeft size={16} style={{ marginRight: '6px' }} /> Back to gallery
      </button>

      {/* Main Card */}
      <div style={{ 
        backgroundColor: 'var(--surface-0)',
        borderRadius: '16px',
        border: '1px solid var(--border)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.04)',
        overflow: 'hidden'
      }}>
        
        {/* Header Area */}
        <div style={{ padding: '40px', borderBottom: '1px solid var(--border)', backgroundColor: 'var(--surface-1)' }}>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <span style={{ 
              fontSize: '12px', fontWeight: 600, padding: '4px 10px', 
              borderRadius: '6px', backgroundColor: catColor.bg, color: catColor.text 
            }}>
              {template.category.toUpperCase()}
            </span>
            <span style={{ 
              fontSize: '12px', fontWeight: 500, padding: '4px 10px', 
              borderRadius: '6px', backgroundColor: 'var(--surface-2)', color: 'var(--text-secondary)' 
            }}>
              {template.difficulty}
            </span>
          </div>

          <h1 style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '12px', lineHeight: 1.2 }}>
            {template.name}
          </h1>

          <p style={{ fontSize: '16px', color: 'var(--text-secondary)', lineHeight: 1.5, maxWidth: '600px' }}>
            {template.description}
          </p>
        </div>

        {/* Content Area */}
        <div style={{ padding: '40px', display: 'flex', flexDirection: 'column', gap: '40px' }}>
          
          {/* Visual App Flow */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '16px', 
            flexWrap: 'wrap' 
          }}>
            {template.app_slugs.map((slug, idx) => (
              <React.Fragment key={slug}>
                <div style={{ 
                  display: 'flex', 
                  flexDirection: 'column',
                  alignItems: 'center', 
                  gap: '8px'
                }}>
                  <div style={{
                    width: '64px',
                    height: '64px',
                    borderRadius: '16px',
                    backgroundColor: 'var(--surface-1)',
                    border: '1px solid var(--border-strong)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-secondary)',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
                  }}>
                    {getAppIcon(slug, 32)}
                  </div>
                  <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
                    {formatAppName(slug)}
                  </span>
                </div>
                {idx < template.app_slugs.length - 1 && (
                  <ArrowRight size={24} style={{ color: 'var(--text-muted)' }} />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Details Grid */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: '1fr', 
            gap: '40px',
            '@media (minWidth: 768px)': { gridTemplateColumns: '1fr 1fr' } // Note: Inline @media doesn't work, handled below with flex
          }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '40px' }}>
              
              <div style={{ flex: '1 1 300px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
                  What this workflow does
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {workflowSteps.map((step, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                      <div style={{ 
                        width: '24px', height: '24px', borderRadius: '50%', 
                        backgroundColor: 'var(--surface-2)', color: 'var(--text-secondary)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '12px', fontWeight: 600, flexShrink: 0
                      }}>
                        {idx + 1}
                      </div>
                      <span style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5, paddingTop: '2px' }}>
                        {step}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ flex: '1 1 200px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
                  You'll need
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {template.app_slugs.map(slug => (
                    <div key={slug} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <Check size={16} style={{ color: 'var(--status-success-text)' }} />
                      <span style={{ fontSize: '14px', color: 'var(--text-primary)' }}>
                        {formatAppName(slug)} Account
                      </span>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          </div>

          {/* Action Footer */}
          <div style={{ 
            marginTop: '20px',
            paddingTop: '32px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'flex-end'
          }}>
            <button 
              className="btn-primary" 
              style={{ padding: '12px 32px', fontSize: '15px' }}
              onClick={() => alert(`Start guided setup for ${template.name} (3A.6)`)}
            >
              Use This Template
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
