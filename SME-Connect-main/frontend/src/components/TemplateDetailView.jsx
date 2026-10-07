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

export default function TemplateDetailView({ templateId, onBack, connections = [], onNavigateConnectors, onNavigateWorkflows }) {
  const [template, setTemplate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showSetupCheck, setShowSetupCheck] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [showReview, setShowReview] = useState(false);
  const [showActivation, setShowActivation] = useState(false);
  const [createdWorkflowId, setCreatedWorkflowId] = useState(null);
  const [activating, setActivating] = useState(false);
  const [setupValues, setSetupValues] = useState({});
  const [creating, setCreating] = useState(false);

  const handleCreateWorkflow = async () => {
    try {
      setCreating(true);
      
      const newDefinition = JSON.parse(JSON.stringify(template.definition));
      if (newDefinition.trigger) {
        newDefinition.trigger.config = {
          ...(newDefinition.trigger.config || {}),
          ...setupValues
        };
      }
      
      const createdWorkflow = await api.createWorkflow({
        name: template.name,
        description: template.description,
        template_id: template.id,
        definition: newDefinition
      });
      
      setCreatedWorkflowId(createdWorkflow.id);
      setShowActivation(true);
      setShowReview(false);
      setShowWizard(false);
      setShowSetupCheck(false);
    } catch (err) {
      console.error("Failed to create workflow from template:", err);
      alert(err.message || "Failed to create workflow");
    } finally {
      setCreating(false);
    }
  };

  const handleActivateWorkflow = async () => {
    try {
      setActivating(true);
      await api.publishWorkflow(createdWorkflowId);
      
      // Navigate to workflows tab
      if (onNavigateWorkflows) {
        onNavigateWorkflows();
      }
    } catch (err) {
      console.error("Failed to activate workflow:", err);
      alert(err.message || "Failed to activate workflow");
      setActivating(false);
    }
  };

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



  // 3A.6.5 - Template Activation
  if (showActivation && template) {
    return (
      <div style={{ maxWidth: '600px', margin: '0 auto', padding: '40px 0', textAlign: 'center' }}>
        <div style={{ 
          backgroundColor: 'var(--surface-0)',
          borderRadius: '16px',
          border: '1px solid var(--border)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.04)',
          overflow: 'hidden',
          padding: '48px 32px'
        }}>
          <div style={{ 
            width: '64px', height: '64px', borderRadius: '32px', 
            backgroundColor: 'var(--status-success-bg)', color: 'var(--status-success-text)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 24px'
          }}>
            <Check size={32} />
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
            Workflow Created Successfully!
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-secondary)', marginBottom: '32px', maxWidth: '400px', margin: '0 auto 32px' }}>
            Your workflow "{template.name}" has been drafted and validated. It is ready to be activated.
          </p>
          
          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px' }}>
            <button 
              className="btn-secondary" 
              onClick={() => { if (onNavigateWorkflows) onNavigateWorkflows(); }}
              style={{ padding: '12px 24px', fontSize: '15px' }}
              disabled={activating}
            >
              Keep as Draft
            </button>
            <button 
              className="btn-primary" 
              onClick={handleActivateWorkflow}
              style={{ padding: '12px 24px', fontSize: '15px' }}
              disabled={activating}
            >
              {activating ? 'Activating...' : 'Activate Workflow'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 3A.6.4 - Setup Review
  if (showReview && template) {
    const triggerApp = template.app_slugs[0];
    const actionApp = template.app_slugs[1] || template.app_slugs[0];
    const mappings = template.definition?.steps?.[0]?.mapping || {};
    
    return (
      <div style={{ maxWidth: '600px', margin: '0 auto', padding: '40px 0' }}>
        <button 
          className="btn-secondary" 
          onClick={() => setShowReview(false)}
          style={{ 
            padding: '6px 12px', 
            fontSize: '13px', 
            marginBottom: '32px',
            border: 'none',
            backgroundColor: 'transparent',
            boxShadow: 'none',
            color: 'var(--text-secondary)'
          }}
          disabled={creating}
        >
          <ArrowLeft size={16} style={{ marginRight: '6px' }} /> Back to setup
        </button>

        <div style={{ 
          backgroundColor: 'var(--surface-0)',
          borderRadius: '16px',
          border: '1px solid var(--border)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.04)',
          overflow: 'hidden'
        }}>
          <div style={{ padding: '32px', borderBottom: '1px solid var(--border)' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Review & Create
            </h2>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)' }}>
              Here's what SME Connect will automate for you.
            </p>
          </div>

          <div style={{ padding: '32px' }}>
            
            <div style={{ 
              display: 'flex', flexDirection: 'column', alignItems: 'center', 
              backgroundColor: 'var(--surface-1)', padding: '24px', borderRadius: '12px',
              border: '1px solid var(--border)', marginBottom: '32px'
            }}>
               <div style={{ display: 'flex', alignItems: 'center', gap: '32px', marginBottom: '24px' }}>
                 <div style={{ textAlign: 'center' }}>
                   <div style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>{getAppIcon(triggerApp, 32)}</div>
                   <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{formatAppName(triggerApp)}</div>
                   <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Trigger</div>
                 </div>
                 
                 <ArrowRight size={24} style={{ color: 'var(--text-muted)' }} />
                 
                 <div style={{ textAlign: 'center' }}>
                   <div style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>{getAppIcon(actionApp, 32)}</div>
                   <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{formatAppName(actionApp)}</div>
                   <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Action</div>
                 </div>
               </div>
               
               <div style={{ width: '100%', borderTop: '1px solid var(--border)', paddingTop: '24px' }}>
                 <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                   Data Mapping
                 </div>
                 
                 {Object.entries(mappings).map(([dest, src]) => (
                   <div key={dest} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                     <div style={{ fontSize: '14px', color: 'var(--text-primary)', flex: 1 }}>
                       <span style={{ fontFamily: 'monospace', backgroundColor: 'var(--surface-0)', padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--border)' }}>
                         {src.split('.').pop()}
                       </span>
                     </div>
                     <ArrowRight size={14} style={{ color: 'var(--text-muted)', margin: '0 16px' }} />
                     <div style={{ fontSize: '14px', color: 'var(--text-primary)', flex: 1, textAlign: 'right' }}>
                       <span style={{ fontFamily: 'monospace', backgroundColor: 'var(--surface-0)', padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--border)' }}>
                         {dest}
                       </span>
                     </div>
                   </div>
                 ))}
                 
                 {Object.keys(mappings).length === 0 && (
                   <div style={{ fontSize: '14px', color: 'var(--text-secondary)', textAlign: 'center' }}>
                     No specific field mappings defined.
                   </div>
                 )}
               </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button 
                className="btn-primary" 
                style={{ padding: '10px 24px', fontSize: '15px' }}
                disabled={creating}
                onClick={handleCreateWorkflow}
              >
                {creating ? 'Creating...' : 'Create Workflow'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // If we are in the Wizard mode (3A.6.2)

  if (showWizard && template) {
    const fields = template.setup_schema?.fields || [];
    
    // Check if required fields are filled
    const canContinue = fields.every(f => !f.required || (setupValues[f.key] && setupValues[f.key].trim() !== ''));

    return (
      <div style={{ maxWidth: '600px', margin: '0 auto', padding: '40px 0' }}>
        <button 
          className="btn-secondary" 
          onClick={() => setShowWizard(false)}
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
          <ArrowLeft size={16} style={{ marginRight: '6px' }} /> Back to app check
        </button>

        <div style={{ 
          backgroundColor: 'var(--surface-0)',
          borderRadius: '16px',
          border: '1px solid var(--border)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.04)',
          overflow: 'hidden'
        }}>
          <div style={{ padding: '32px', borderBottom: '1px solid var(--border)' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Configure your workflow
            </h2>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)' }}>
              Provide the specific details for {template.name}.
            </p>
          </div>

          <div style={{ padding: '32px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginBottom: '32px' }}>
              {fields.map(field => (
                <div key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
                    {field.label} {field.required && <span style={{ color: 'var(--status-warning-text)' }}>*</span>}
                  </label>
                  
                  {field.connector && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                       {getAppIcon(field.connector, 14)}
                       <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                         {formatAppName(field.connector)} Resource
                       </span>
                    </div>
                  )}
                  
                  <input
                    type="text"
                    value={setupValues[field.key] || ''}
                    onChange={(e) => setSetupValues({ ...setupValues, [field.key]: e.target.value })}
                    placeholder={`Enter ${field.label.toLowerCase()}...`}
                    style={{
                      padding: '10px 14px',
                      borderRadius: '8px',
                      border: '1px solid var(--border)',
                      backgroundColor: 'var(--surface-0)',
                      color: 'var(--text-primary)',
                      fontSize: '14px',
                      width: '100%'
                    }}
                  />
                  {field.type === 'connection_resource' && (
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      Note: Select from available {field.label} (mocked as text input for MVP).
                    </span>
                  )}
                </div>
              ))}
              
              {fields.length === 0 && (
                <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                  No setup fields required for this template.
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button 
                className="btn-primary" 
                style={{ padding: '10px 20px', fontSize: '14px' }}
                disabled={!canContinue}
                onClick={() => setShowReview(true)}
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // If we are in setup check mode

  if (showSetupCheck && template) {
    const allConnected = template.app_slugs.every(slug => connections.some(c => c.connector_slug === slug));
    
    return (
      <div style={{ maxWidth: '600px', margin: '0 auto', padding: '40px 0' }}>
        <button 
          className="btn-secondary" 
          onClick={() => setShowSetupCheck(false)}
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
          <ArrowLeft size={16} style={{ marginRight: '6px' }} /> Back to template
        </button>

        <div style={{ 
          backgroundColor: 'var(--surface-0)',
          borderRadius: '16px',
          border: '1px solid var(--border)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.04)',
          overflow: 'hidden'
        }}>
          <div style={{ padding: '32px', borderBottom: '1px solid var(--border)' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Check required apps
            </h2>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)' }}>
              Before we can create this workflow, we need to make sure you have the right accounts connected.
            </p>
          </div>

          <div style={{ padding: '32px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '32px' }}>
              {template.app_slugs.map(slug => {
                const isConnected = connections.some(c => c.connector_slug === slug);
                return (
                  <div key={slug} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '16px',
                    borderRadius: '12px',
                    backgroundColor: isConnected ? 'var(--status-success-bg)' : 'var(--surface-1)',
                    border: '1px solid',
                    borderColor: isConnected ? 'rgba(16, 185, 129, 0.2)' : 'var(--border)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ color: isConnected ? 'var(--status-success-text)' : 'var(--text-secondary)' }}>
                        {getAppIcon(slug, 20)}
                      </div>
                      <span style={{ fontSize: '15px', fontWeight: 500, color: 'var(--text-primary)' }}>
                        {formatAppName(slug)}
                      </span>
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {isConnected ? (
                        <>
                          <Check size={16} style={{ color: 'var(--status-success-text)' }} />
                          <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--status-success-text)' }}>Connected</span>
                        </>
                      ) : (
                        <>
                          <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>Not connected</span>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              {!allConnected && (
                <button 
                  className="btn-secondary" 
                  onClick={onNavigateConnectors}
                  style={{ padding: '10px 20px', fontSize: '14px' }}
                >
                  Manage Connections
                </button>
              )}
              <button 
                className="btn-primary" 
                style={{ padding: '10px 20px', fontSize: '14px' }}
                disabled={!allConnected}
                onClick={() => setShowWizard(true)}
              >
                Continue to Setup
              </button>
            </div>
          </div>
        </div>
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
              onClick={() => setShowSetupCheck(true)}
            >
              Use This Template
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
