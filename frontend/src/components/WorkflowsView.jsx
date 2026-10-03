import React, { useState, useEffect } from 'react';
import {
  GitFork,
  CheckCircle,
  PauseCircle,
  Plus
} from 'lucide-react';
import { api } from '../api';

export default function WorkflowsView({ onNavigateConnectors }) {
  const [workflows, setWorkflows] = useState([]);
  const [capabilities, setCapabilities] = useState([]);
  const [loading, setLoading] = useState(true);

  // Builder State
  const [activeWorkflowId, setActiveWorkflowId] = useState(null);
  const [draftDefinition, setDraftDefinition] = useState(null);

  // UI State
  const [showTriggerModal, setShowTriggerModal] = useState(false);
  const [triggerForm, setTriggerForm] = useState({ connector: '', event: '' });
  const [showAddStepModal, setShowAddStepModal] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      const [wfs, caps] = await Promise.all([
        api.fetchWorkflows(),
        api.fetchWorkflowCapabilities()
      ]);
      setWorkflows(wfs);
      setCapabilities(caps);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const handleSelectWorkflow = async (id) => {
    try {
      const detail = await api.fetchWorkflow(id);
      setActiveWorkflowId(id);
      setDraftDefinition(detail.definition);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleWorkflowStatus = async (id, currentStatus) => {
    try {
      if (currentStatus === 'active') {
        await api.pauseWorkflow(id);
      } else {
        await api.publishWorkflow(id);
      }
      loadData(); // reload list
      if (activeWorkflowId === id) {
        handleSelectWorkflow(id);
      }
    } catch (err) {
      console.error(err);
      alert('Failed to change workflow status');
    }
  };

  const handleNewWorkflow = async () => {
    try {
      const newDef = {
        trigger: { connector: "google_sheets", event: "new_row", config: {} },
        steps: [
          {
            id: "step-placeholder",
            type: "action",
            connector: "crm",
            action: "create_lead",
            config: {},
            mapping: {}
          }
        ]
      };
      const created = await api.createWorkflow({
        name: "New automated workflow",
        definition: newDef
      });
      setWorkflows([created, ...workflows]);
      setActiveWorkflowId(created.id);
      setDraftDefinition(newDef);
      
      // Open trigger config by default for new workflows
      setTriggerForm({ connector: '', event: '' });
      setShowTriggerModal(true);
    } catch (err) {
      console.error(err);
      alert('Failed to create workflow');
    }
  };

  const openTriggerModal = () => {
    setTriggerForm({
      connector: draftDefinition?.trigger?.connector || '',
      event: draftDefinition?.trigger?.event || ''
    });
    setShowTriggerModal(true);
  };

  const handleSaveTrigger = async () => {
    const newDef = {
      ...draftDefinition,
      trigger: {
        connector: triggerForm.connector,
        event: triggerForm.event,
        config: {}
      }
    };
    
    setDraftDefinition(newDef);
    setShowTriggerModal(false);
    
    if (activeWorkflowId) {
      try {
        await api.updateWorkflow(activeWorkflowId, { definition: newDef });
      } catch (err) {
        console.error(err);
        alert('Failed to save trigger');
      }
    }
  };

  const getConnectorName = (slug) => {
    const cap = (capabilities || []).find(c => c.slug === slug);
    return cap ? cap.name : slug;
  };

  const getEventName = (connectorSlug, eventSlug) => {
    const cap = (capabilities || []).find(c => c.slug === connectorSlug);
    if (!cap) return eventSlug;
    const trig = (cap?.supported_triggers || []).find(t => t.slug === eventSlug);
    return trig ? trig.name : eventSlug;
  };

  const activeCount = (workflows || []).filter((w) => w.status === 'active').length;

  return (
    <div>
      {/* Screen Title & Single Primary CTA */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '20px',
        gap: '16px',
        flexWrap: 'wrap',
      }}>
        <div>
          <h2>Workflows</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '2px' }}>
            Automate data flow between spreadsheets, CRM, and communication tools.
          </p>
        </div>

        <button
          className="btn-primary"
          onClick={handleNewWorkflow}
        >
          <Plus size={15} />
          <span>New workflow</span>
        </button>
      </div>

      {/* Metric Tiles */}
      <div className="metric-grid">
        <div className="metric-tile">
          <div className="metric-tile-label">Active workflows</div>
          <div className="metric-tile-value">{activeCount}</div>
        </div>
        <div className="metric-tile">
          <div className="metric-tile-label">Executions (24h)</div>
          <div className="metric-tile-value">0</div>
        </div>
        <div className="metric-tile">
          <div className="metric-tile-label">Success rate</div>
          <div className="metric-tile-value">—</div>
        </div>
      </div>

      {/* Flow Builder Canvas */}
      <div style={{
        backgroundColor: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        padding: '16px',
        marginBottom: '24px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div>
            <h3>Workflow design canvas</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
              {activeWorkflowId 
                ? `Editing: ${(workflows || []).find(w => w.id === activeWorkflowId)?.name || 'Workflow'}` 
                : 'Select a workflow from the inventory below to edit its flow.'}
            </p>
          </div>

          <button
            className="btn-secondary"
            onClick={onNavigateConnectors}
            style={{ fontSize: '12px', padding: '4px 10px' }}
          >
            Manage connections
          </button>
        </div>

        {activeWorkflowId && draftDefinition ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            overflowX: 'auto',
            paddingBottom: '8px',
          }}>
            {/* TRIGGER CARD */}
            <div 
              onClick={openTriggerModal}
              style={{
              width: '150px',
              minWidth: '150px',
              backgroundColor: 'var(--surface-1)',
              borderRadius: '6px',
              borderLeft: `2px solid var(--trigger-accent)`,
              padding: '10px 12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              cursor: 'pointer',
              border: '1px solid transparent',
              transition: 'border-color 0.2s',
            }}
            onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--trigger-accent)'}
            onMouseLeave={(e) => e.currentTarget.style.borderColor = 'transparent'}
            >
              <span className="kicker-label kicker-trigger">TRIGGER</span>
              <span style={{
                fontSize: '13px',
                fontWeight: 500,
                color: 'var(--text-primary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {draftDefinition?.trigger?.event ? getEventName(draftDefinition?.trigger?.connector, draftDefinition?.trigger?.event) : 'Unconfigured Trigger'}
              </span>
              <span style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {draftDefinition?.trigger?.connector ? getConnectorName(draftDefinition?.trigger?.connector) : 'Click to configure'}
              </span>
            </div>

            {/* Steps placeholder for later modules */}
            {(draftDefinition?.steps || []).map((step) => {
               let borderColor = 'var(--action-accent)';
               let kickerClass = 'kicker-action';
               if (step.type === 'condition') {
                 borderColor = 'var(--condition-accent)';
                 kickerClass = 'kicker-condition';
               }
               return (
                 <React.Fragment key={step.id}>
                    <span style={{
                      color: 'var(--text-muted)',
                      fontSize: '14px',
                      userSelect: 'none',
                      padding: '0 2px',
                    }}>
                      →
                    </span>
                    <div style={{
                      width: '150px',
                      minWidth: '150px',
                      backgroundColor: 'var(--surface-1)',
                      borderRadius: '6px',
                      borderLeft: `2px solid ${borderColor}`,
                      padding: '10px 12px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}>
                      <span className={`kicker-label ${kickerClass}`}>{step.type.toUpperCase()}</span>
                      <span style={{
                        fontSize: '13px',
                        fontWeight: 500,
                        color: 'var(--text-primary)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}>
                        {step.action || step.field || 'Config'}
                      </span>
                      <span style={{
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}>
                        {step.connector || 'Builder step'}
                      </span>
                    </div>
                 </React.Fragment>
               );
            })}

            <span style={{
              color: 'var(--text-muted)',
              fontSize: '14px',
              userSelect: 'none',
              padding: '0 2px',
            }}>
              →
            </span>

            <button
              onClick={() => setShowAddStepModal(true)}
              style={{
                width: '150px',
                minWidth: '150px',
                height: '66px',
                backgroundColor: 'transparent',
                border: '1px dashed var(--border-dashed)',
                borderRadius: '6px',
                color: 'var(--text-secondary)',
                fontSize: '12px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                transition: 'border-color 0.15s ease, color 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.35)';
                e.currentTarget.style.color = 'var(--text-primary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-dashed)';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              <Plus size={14} />
              <span>Add step</span>
            </button>
          </div>
        ) : (
          <div style={{
            padding: '36px 20px',
            textAlign: 'center',
            color: 'var(--text-secondary)',
            fontSize: '14px',
            border: '1px dashed var(--border-dashed)',
            borderRadius: '8px'
          }}>
            Select a workflow to view its canvas, or create a new one.
          </div>
        )}
      </div>

      {/* Workflow Dense List */}
      <div>
        <div style={{ marginBottom: '10px' }}>
          <h3>Workflow inventory</h3>
        </div>

        <div className="list-container">
          {loading ? (
             <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)' }}>Loading workflows...</div>
          ) : (!workflows || workflows.length === 0) ? (
            <div style={{
              padding: '36px 20px',
              textAlign: 'center',
              color: 'var(--text-secondary)',
              fontSize: '14px',
            }}>
              No active workflows yet. Click "New workflow" above to create an automated flow.
            </div>
          ) : (
            (workflows || []).map((wf) => {
            const isSuccess = wf.status === 'active';
            const isSelected = wf.id === activeWorkflowId;

            return (
              <div 
                key={wf.id} 
                className="list-row"
                onClick={() => handleSelectWorkflow(wf.id)}
                style={{ 
                  cursor: 'pointer',
                  backgroundColor: isSelected ? 'var(--surface-3)' : 'transparent'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0, paddingRight: '16px' }}>
                  <GitFork size={18} style={{ color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)', flexShrink: 0 }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{
                      fontSize: '14px',
                      fontWeight: 500,
                      color: 'var(--text-primary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {wf.name}
                    </div>
                    <div style={{
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      v{wf.version_number} • {new Date(wf.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
                  <span className={`status-pill ${isSuccess ? 'success' : 'neutral'}`}>
                    {isSuccess ? <CheckCircle size={12} /> : <PauseCircle size={12} />}
                    <span>{isSuccess ? 'Active' : (wf.status === 'draft' ? 'Draft' : 'Paused')}</span>
                  </span>

                  <label 
                    className="switch" 
                    title={isSuccess ? 'Pause workflow' : 'Publish/Resume workflow'}
                    onClick={(e) => e.stopPropagation()} // Prevent row click
                  >
                    <input
                      type="checkbox"
                      checked={isSuccess}
                      onChange={() => toggleWorkflowStatus(wf.id, wf.status)}
                    />
                    <span className="slider" />
                  </label>
                </div>
              </div>
            );
          }))}
        </div>
      </div>

      {/* Trigger Modal */}
      {showTriggerModal && (
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
            maxWidth: '500px',
            width: '100%',
            padding: '20px',
          }}>
            <h3 style={{ marginBottom: '4px' }}>Configure Trigger</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Select a connected app and event to trigger this workflow.
            </p>

            <div className="form-group">
              <label>App / Connector</label>
              <select
                value={triggerForm.connector}
                onChange={(e) => setTriggerForm({ connector: e.target.value, event: '' })}
              >
                <option value="">Select a connector...</option>
                {(capabilities || []).map(cap => (
                  <option key={cap.slug} value={cap.slug}>
                    {cap.name} {cap.is_connected ? '' : '(No connection)'}
                  </option>
                ))}
              </select>
            </div>

            {triggerForm.connector && (
              <div className="form-group" style={{ marginTop: '16px' }}>
                <label>Event</label>
                <select
                  value={triggerForm.event}
                  onChange={(e) => setTriggerForm({ ...triggerForm, event: e.target.value })}
                >
                  <option value="">Select an event...</option>
                  {capabilities
                    .find(c => c.slug === triggerForm.connector)
                    ?.supported_triggers?.map(t => (
                      <option key={t.slug} value={t.slug}>
                        {t.name}
                      </option>
                    ))}
                </select>
                {triggerForm.event && (
                   <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)', padding: '8px', backgroundColor: 'var(--surface-1)', borderRadius: '4px' }}>
                     {capabilities
                       .find(c => c.slug === triggerForm.connector)
                       ?.supported_triggers?.find(t => t.slug === triggerForm.event)?.description
                     }
                   </div>
                )}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '24px' }}>
              <button
                className="btn-secondary"
                onClick={() => setShowTriggerModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={handleSaveTrigger}
                disabled={!triggerForm.connector || !triggerForm.event}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Step Minimal Modal */}
      {showAddStepModal && (
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
            maxWidth: '380px',
            width: '100%',
            padding: '20px',
          }}>
            <h3 style={{ marginBottom: '4px' }}>Add workflow step</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              (Step logic will be implemented in future modules)
            </p>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                className="btn-secondary"
                onClick={() => setShowAddStepModal(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
