import React, { useState, useEffect } from 'react';
import {
  ArrowRight,
  Search,
  Zap,
  PlayCircle,
  Database,
  Users,
  MessageCircle,
  Briefcase,
  BookOpen
} from 'lucide-react';
import { api } from '../api';
import TemplateDetailView from './TemplateDetailView';

const categoryColors = {
  Sales: { bg: 'var(--status-success-bg)', text: 'var(--status-success-text)' },
  Billing: { bg: 'var(--status-warning-bg)', text: 'var(--status-warning-text)' },
  Operations: { bg: 'var(--status-neutral-bg)', text: 'var(--status-neutral-text)' },
  Notifications: { bg: '#e0e7ff', text: '#4338ca' }, // A nice indigo for notifications
};

const appIconMap = {
  google_sheets: <Database size={16} />,
  crm: <Users size={16} />,
  zoho_books: <BookOpen size={16} />,
  whatsapp: <MessageCircle size={16} />,
};

const getAppIcon = (slug) => {
  return appIconMap[slug] || <Zap size={16} />;
};

const formatAppName = (slug) => {
  return slug.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
};

export default function TemplatesView({ onNavigateWorkflows, onNavigateConnectors }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);

  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const data = await api.fetchTemplates();
        setTemplates(data || []);
      } catch (err) {
        console.error("Failed to load templates", err);
      } finally {
        setLoading(false);
      }
    };
    loadTemplates();
  }, []);

  const categories = ['All', 'Sales', 'Billing', 'Operations', 'Notifications'];

  const filteredTemplates = (Array.isArray(templates) ? templates : []).filter(t => {
    const matchesCategory = selectedCategory === 'All' || t.category === selectedCategory;
    const searchLower = searchQuery.toLowerCase();
    const matchesSearch = 
      t.name.toLowerCase().includes(searchLower) || 
      t.description.toLowerCase().includes(searchLower) ||
      (Array.isArray(t.app_slugs) && t.app_slugs.some(s => s.toLowerCase().includes(searchLower)));
    
    return matchesCategory && matchesSearch;
  });

  if (selectedTemplateId) {
    return (
      <TemplateDetailView 
        templateId={selectedTemplateId} 
        onBack={() => setSelectedTemplateId(null)} 
      />
    );
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px 0' }}>
      
      {/* Hero Section */}
      <div style={{ 
        display: 'flex', 
        flexWrap: 'wrap', 
        gap: '40px',
        marginBottom: '60px',
        alignItems: 'center'
      }}>
        
        <div style={{ flex: '1 1 300px' }}>
          <h1 style={{ 
            fontSize: '36px', 
            fontWeight: 700, 
            color: 'var(--text-primary)', 
            marginBottom: '16px',
            lineHeight: 1.2,
            letterSpacing: '-0.5px'
          }}>
            Stop doing the same work manually.
          </h1>
          <p style={{ 
            fontSize: '18px', 
            color: 'var(--text-secondary)', 
            marginBottom: '32px',
            lineHeight: 1.5,
            maxWidth: '480px'
          }}>
            Start with a ready-made workflow for your business, or build your own automation from scratch.
          </p>
          
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            <button 
              className="btn-primary" 
              style={{ padding: '12px 24px', fontSize: '15px' }}
              onClick={() => {
                document.getElementById('templates-section').scrollIntoView({ behavior: 'smooth' });
              }}
            >
              Explore Templates
            </button>
            <button 
              className="btn-secondary" 
              style={{ padding: '12px 24px', fontSize: '15px' }}
              onClick={onNavigateWorkflows}
            >
              Create Your Own
            </button>
          </div>
        </div>

        {/* Visual Workflow Preview */}
        <div style={{ 
          flex: '1 1 300px', 
          display: 'flex', 
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: 'var(--surface-1)',
          borderRadius: '16px',
          padding: '40px',
          border: '1px solid var(--border)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.04)'
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', width: '100%' }}>
            
            <div style={{ 
              width: '100%', maxWidth: '280px', backgroundColor: 'var(--surface-0)', 
              borderRadius: '12px', padding: '16px', border: '1px solid var(--border-strong)',
              display: 'flex', alignItems: 'center', gap: '12px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
            }}>
              <div style={{ color: '#10b981' }}><Database size={24} /></div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Google Sheets</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>New Customer</div>
              </div>
            </div>

            <div style={{ width: '2px', height: '20px', backgroundColor: 'var(--border-strong)' }} />

            <div style={{ 
              width: '100%', maxWidth: '280px', backgroundColor: 'var(--surface-0)', 
              borderRadius: '12px', padding: '16px', border: '1px solid var(--border-strong)',
              display: 'flex', alignItems: 'center', gap: '12px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
            }}>
              <div style={{ color: '#3b82f6' }}><Users size={24} /></div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>CRM</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Create Lead</div>
              </div>
            </div>

            <div style={{ width: '2px', height: '20px', backgroundColor: 'var(--border-strong)' }} />

            <div style={{ 
              width: '100%', maxWidth: '280px', backgroundColor: 'var(--surface-0)', 
              borderRadius: '12px', padding: '16px', border: '1px solid var(--border-strong)',
              display: 'flex', alignItems: 'center', gap: '12px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
            }}>
              <div style={{ color: '#f59e0b' }}><BookOpen size={24} /></div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Zoho Books</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Create Contact</div>
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Templates Section */}
      <div id="templates-section">
        <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
          Start with a workflow that fits your business
        </h2>
        <p style={{ fontSize: '15px', color: 'var(--text-secondary)', marginBottom: '32px' }}>
          Choose a common business task and we'll guide you through the setup.
        </p>

        {/* Toolbar: Categories & Search */}
        <div style={{ 
          display: 'flex', 
          flexWrap: 'wrap',
          gap: '16px',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '24px',
          paddingBottom: '24px',
          borderBottom: '1px solid var(--border)'
        }}>
          
          <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                style={{
                  padding: '6px 16px',
                  borderRadius: '9999px',
                  border: cat === selectedCategory ? '1px solid transparent' : '1px solid var(--border)',
                  backgroundColor: cat === selectedCategory ? 'var(--text-primary)' : 'var(--surface-1)',
                  color: cat === selectedCategory ? 'var(--surface-0)' : 'var(--text-secondary)',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  whiteSpace: 'nowrap'
                }}
              >
                {cat}
              </button>
            ))}
          </div>

          <div style={{ 
            position: 'relative', 
            width: '100%', 
            maxWidth: '300px'
          }}>
            <Search size={16} style={{ 
              position: 'absolute', 
              left: '12px', 
              top: '50%', 
              transform: 'translateY(-50%)', 
              color: 'var(--text-muted)' 
            }} />
            <input
              type="text"
              placeholder="Search workflows for your business..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 16px 10px 36px',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                backgroundColor: 'var(--surface-1)',
                color: 'var(--text-primary)',
                fontSize: '14px'
              }}
            />
          </div>

        </div>

        {/* Templates Grid */}
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <div className="spinner" style={{ width: '32px', height: '32px', margin: '0 auto 16px' }} />
            Loading templates...
          </div>
        ) : filteredTemplates.length === 0 ? (
          <div style={{ 
            padding: '60px 20px', 
            textAlign: 'center', 
            backgroundColor: 'var(--surface-1)',
            borderRadius: '12px',
            border: '1px dashed var(--border-strong)'
          }}>
            <Briefcase size={32} style={{ color: 'var(--text-muted)', margin: '0 auto 16px' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '8px' }}>
              No templates found
            </h3>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
              Try adjusting your filters or search query.
            </p>
            <button className="btn-secondary" onClick={() => { setSelectedCategory('All'); setSearchQuery(''); }}>
              Clear Filters
            </button>
          </div>
        ) : (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', 
            gap: '24px',
            marginBottom: '60px'
          }}>
            {filteredTemplates.map(template => {
              const catColor = categoryColors[template.category] || categoryColors.Operations;
              return (
                <div key={template.id} style={{
                  backgroundColor: 'var(--surface-0)',
                  border: '1px solid var(--border)',
                  borderRadius: '12px',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'box-shadow 0.2s ease, transform 0.2s ease',
                  cursor: 'default',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = '0 12px 24px rgba(0,0,0,0.06)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.transform = 'none';
                }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <span style={{ 
                        fontSize: '11px', fontWeight: 600, padding: '4px 8px', 
                        borderRadius: '6px', backgroundColor: catColor.bg, color: catColor.text 
                      }}>
                        {template.category}
                      </span>
                      <span style={{ 
                        fontSize: '11px', fontWeight: 500, padding: '4px 8px', 
                        borderRadius: '6px', backgroundColor: 'var(--surface-2)', color: 'var(--text-secondary)' 
                      }}>
                        {template.difficulty}
                      </span>
                    </div>
                  </div>
                  
                  <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px', lineHeight: 1.3 }}>
                    {template.name}
                  </h3>
                  
                  <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '24px', flex: 1, lineHeight: 1.5 }}>
                    {template.description}
                  </p>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px', color: 'var(--text-muted)' }}>
                    {template.app_slugs.map((slug, idx) => (
                      <React.Fragment key={slug}>
                        <div style={{ 
                          display: 'flex', alignItems: 'center', gap: '6px', 
                          padding: '6px', backgroundColor: 'var(--surface-1)', borderRadius: '8px',
                          color: 'var(--text-secondary)'
                        }} title={formatAppName(slug)}>
                          {getAppIcon(slug)}
                        </div>
                        {idx < template.app_slugs.length - 1 && (
                          <ArrowRight size={14} />
                        )}
                      </React.Fragment>
                    ))}
                  </div>

                  <button 
                    className="btn-primary" 
                    style={{ width: '100%', justifyContent: 'center' }}
                    onClick={() => setSelectedTemplateId(template.id)}
                  >
                    Use Template
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Your Own Section */}
      <div style={{ 
        backgroundColor: 'var(--surface-2)',
        borderRadius: '16px',
        padding: '40px',
        textAlign: 'center',
        marginTop: '40px'
      }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>
          Have something else in mind?
        </h2>
        <p style={{ fontSize: '15px', color: 'var(--text-secondary)', marginBottom: '24px', maxWidth: '400px', margin: '0 auto 24px' }}>
          Build your own workflow from scratch using our visual workflow builder. Connect any apps however you need.
        </p>
        <button 
          className="btn-secondary" 
          style={{ padding: '10px 20px', fontSize: '14px' }}
          onClick={onNavigateWorkflows}
        >
          <PlayCircle size={16} style={{ marginRight: '8px' }} />
          Create Your Own Workflow
        </button>
      </div>

    </div>
  );
}
