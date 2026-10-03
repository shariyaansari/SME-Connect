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
  const [showActionModal, setShowActionModal] = useState(false);
  const [actionForm, setActionForm] = useState({ connector: '', action: '', config: {}, mapping: {} });
  const [editingStepId, setEditingStepId] = useState(null);
  const [showConditionModal, setShowConditionModal] = useState(false);
  const [conditionForm, setConditionForm] = useState({ field: '', operator: 'equals', value: '' });

  const CONDITION_OPERATORS = [
    { value: 'equals', label: 'Equals' },
    { value: 'not_equals', label: 'Not Equals' },
    { value: 'contains', label: 'Contains' },
    { value: 'not_contains', label: 'Does Not Contain' },
    { value: 'greater_than', label: 'Greater Than' },
    { value: 'less_than', label: 'Less Than' },
    { value: 'greater_than_or_equal', label: 'Greater Than or Equal' },
    { value: 'less_than_or_equal', label: 'Less Than or Equal' },
    { value: 'is_empty', label: 'Is Empty' },
    { value: 'is_not_empty', label: 'Is Not Empty' }
  ];

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
      if (currentStatus === 'active' || currentStatus === 'published') {
        await api.pauseWorkflow(id);
      } else {
        await api.publishWorkflow(id);
      }
      await loadData();
      if (activeWorkflowId === id) {
        handleSelectWorkflow(id);
      }
    } catch (err) {
      console.error(err);
      alert('Failed to change workflow status: ' + err.message);
    }
  };

  const handleNewWorkflow = () => {
    setActiveWorkflowId('new');
    setDraftDefinition({
      trigger: { connector: "", event: "", config: {} },
      steps: []
    });
    setTriggerForm({ connector: '', event: '' });
    setShowTriggerModal(true);
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
    if (activeWorkflowId !== 'new') {
      try {
        const updated = await api.updateWorkflow(activeWorkflowId, { definition: newDef });
        setDraftDefinition(updated.definition);
        await loadData();
      } catch (err) { console.error(err); }
    }
  };

  const handleSaveCondition = async () => {
    if (!conditionForm.field || !conditionForm.operator) return;

    let newSteps = [...(draftDefinition.steps || [])];
    const conditionData = {
      type: 'condition',
      field: conditionForm.field,
      operator: conditionForm.operator,
      value: ['is_empty', 'is_not_empty'].includes(conditionForm.operator) ? null : conditionForm.value
    };

    if (editingStepId && editingStepId !== 'step-placeholder') {
      newSteps = newSteps.map(s => s.id === editingStepId ? { ...s, ...conditionData } : s);
    } else {
      newSteps.push({ id: `step-${Date.now()}`, ...conditionData });
    }

    const newDef = { ...draftDefinition, steps: newSteps };
    setDraftDefinition(newDef);
    setShowConditionModal(false);
    setConditionForm({ field: '', operator: 'equals', value: '' });
    setEditingStepId(null);

    try {
      if (activeWorkflowId === 'new') {
        const created = await api.createWorkflow({
          name: `Workflow ${workflows.length + 1}`,
          description: "New automated workflow",
          definition: newDef
        });
        setActiveWorkflowId(created.id);
        setDraftDefinition(created.definition);
        setWorkflows([created, ...workflows]);
      } else {
        const updated = await api.updateWorkflow(activeWorkflowId, { definition: newDef });
        setDraftDefinition(updated.definition);
        await loadData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveAction = async () => {
    if (!actionForm.connector || !actionForm.action) return;

    let newSteps = [...(draftDefinition.steps || [])];
    const actionData = {
      type: 'action',
      connector: actionForm.connector,
      action: actionForm.action,
      config: actionForm.config || {},
      mapping: actionForm.mapping || {}
    };

    if (editingStepId && editingStepId !== 'step-placeholder') {
      // Update existing step, preserving id
      newSteps = newSteps.map(s => s.id === editingStepId ? { ...s, ...actionData } : s);
    } else {
      // Append new step
      newSteps.push({ id: `step-${Date.now()}`, ...actionData });
    }

    const newDef = { ...draftDefinition, steps: newSteps };
    setDraftDefinition(newDef);
    setShowActionModal(false);
    setActionForm({ connector: '', action: '', config: {}, mapping: {} });
    setEditingStepId(null);

    try {
      if (activeWorkflowId === 'new') {
        const created = await api.createWorkflow({
          name: `Workflow ${workflows.length + 1}`,
          description: "New automated workflow",
          definition: newDef
        });
        setActiveWorkflowId(created.id);
        setDraftDefinition(created.definition);
        setWorkflows([created, ...workflows]);
      } else {
        const updated = await api.updateWorkflow(activeWorkflowId, { definition: newDef });
        setDraftDefinition(updated.definition);
        await loadData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const getTriggerVariables = () => {
    if (!draftDefinition?.trigger?.connector || !draftDefinition?.trigger?.event) return [];
    const cap = (capabilities || []).find(c => c.slug === draftDefinition.trigger.connector);
    if (!cap) return [];
    const trig = (cap.supported_triggers || []).find(t => t.slug === draftDefinition.trigger.event);
    if (!trig || !trig.payload_schema) return [];

    const vars = Object.entries(trig.payload_schema).map(([key, schema]) => ({
      path: `trigger.${key}`,
      label: schema.label || key,
      description: schema.description || ''
    }));

    // Also add common row value fields for Google Sheets
    if (draftDefinition.trigger.connector === 'google_sheets') {
      vars.push(
        { path: 'trigger.values.Name', label: 'Row Value: Name', description: '' },
        { path: 'trigger.values.Email', label: 'Row Value: Email', description: '' },
        { path: 'trigger.values.Phone', label: 'Row Value: Phone', description: '' },
        { path: 'trigger.values.Company', label: 'Row Value: Company', description: '' },
      );
    }
    return vars;
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

  const activeCount = (workflows || []).filter((w) => w.status === 'active' || w.status === 'published').length;

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
          <div className="metric-tile-value">&mdash;</div>
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
                ? `Editing: ${(workflows || []).find(w => w.id === activeWorkflowId)?.name || 'New Workflow'}`
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
              borderLeft: '2px solid var(--trigger-accent)',
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

            {/* Step Cards */}
            {((draftDefinition && draftDefinition.steps) || []).map((step) => {
                 // Skip empty placeholder steps
                 if (step.id === 'step-placeholder' || (!step.connector && !step.action && !step.field)) {
                   return null;
                 }

                 let borderColor = 'var(--action-accent)';
                 let kickerClass = 'kicker-action';
                 if (step.type === 'condition') {
                   borderColor = 'var(--condition-accent)';
                   kickerClass = 'kicker-condition';
                 }
                 return (
                   <React.Fragment key={step.id}>
                     <span style={{ color: 'var(--text-muted)', fontSize: '18px', userSelect: 'none', padding: '0 4px' }}>&rarr;</span>
                     <div
                       onClick={() => {
                         setEditingStepId(step.id);
                         if (step.type === 'condition') {
                           setConditionForm({ field: step.field || '', operator: step.operator || 'equals', value: step.value || '' });
                           setShowConditionModal(true);
                         } else {
                           setActionForm({ connector: step.connector, action: step.action, config: step.config || {}, mapping: step.mapping || {} });
                           setShowActionModal(true);
                         }
                       }}
                       style={{
                         width: '150px',
                         minWidth: '150px',
                         backgroundColor: 'var(--surface-1)',
                         borderRadius: '6px',
                         borderLeft: `2px solid ${borderColor}`,
                         padding: '10px 12px',
                         display: 'flex',
                         flexDirection: 'column',
                         gap: '4px',
                         cursor: 'pointer',
                       }}
                     >
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
                         {step.connector || step.operator || 'Builder step'}
                       </span>
                     </div>
                   </React.Fragment>
                 );
            })}

            {/* Add Step Buttons */}
            <span style={{ color: 'var(--text-muted)', fontSize: '18px', userSelect: 'none', padding: '0 4px' }}>&rarr;</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn-secondary"
                style={{
                  borderRadius: '20px',
                  padding: '8px 16px',
                  backgroundColor: 'var(--surface-0)',
                  borderStyle: 'dashed'
                }}
                onClick={() => {
                  setEditingStepId(null);
                  setActionForm({ connector: '', action: '', config: {}, mapping: {} });
                  setShowActionModal(true);
                }}
              >
                <Plus size={14} style={{ marginRight: '6px' }} />
                Add Action
              </button>
              <button
                className="btn-secondary"
                style={{
                  borderRadius: '20px',
                  padding: '8px 16px',
                  backgroundColor: 'var(--surface-0)',
                  borderStyle: 'dashed'
                }}
                onClick={() => {
                  setEditingStepId(null);
                  setConditionForm({ field: '', operator: 'equals', value: '' });
                  setShowConditionModal(true);
                }}
              >
                <Plus size={14} style={{ marginRight: '6px' }} />
                Add Condition
              </button>
            </div>
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
            const isActive = wf.status === 'active' || wf.status === 'published';
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
                      v{wf.version_number} &bull; {new Date(wf.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
                  <span className={`status-pill ${isActive ? 'success' : 'neutral'}`}>
                    {isActive ? <CheckCircle size={12} /> : <PauseCircle size={12} />}
                    <span>{isActive ? 'Active' : (wf.status === 'draft' ? 'Draft' : 'Paused')}</span>
                  </span>

                  <label
                    className="switch"
                    title={isActive ? 'Pause workflow' : 'Publish/Resume workflow'}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={isActive}
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
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100, padding: '16px',
        }}>
          <div style={{
            backgroundColor: 'var(--surface-2)', border: '1px solid var(--border)',
            borderRadius: '10px', maxWidth: '500px', width: '100%', padding: '20px',
          }}>
            <h3 style={{ marginBottom: '4px' }}>Configure Trigger</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Select a connected app and event to trigger this workflow.
            </p>

            <div className="form-group">
              <label>App / Connector</label>
              <select value={triggerForm.connector} onChange={(e) => setTriggerForm({ connector: e.target.value, event: '' })}>
                <option value="">Select a connector...</option>
                {(capabilities || []).map(cap => (
                  <option key={cap.slug} value={cap.slug}>
                    {cap.name} {cap.is_connected ? '' : '(Connect required)'}
                  </option>
                ))}
              </select>
            </div>

            {triggerForm.connector && (
              <div className="form-group" style={{ marginTop: '16px' }}>
                <label>Event</label>
                <select value={triggerForm.event} onChange={(e) => setTriggerForm({ ...triggerForm, event: e.target.value })}>
                  <option value="">Select an event...</option>
                  {capabilities
                    .find(c => c.slug === triggerForm.connector)
                    ?.supported_triggers?.map(t => (
                      <option key={t.slug} value={t.slug}>{t.name}</option>
                    ))}
                </select>
                {triggerForm.event && (
                   <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)', padding: '8px', backgroundColor: 'var(--surface-1)', borderRadius: '4px' }}>
                     {capabilities.find(c => c.slug === triggerForm.connector)?.supported_triggers?.find(t => t.slug === triggerForm.event)?.description}
                   </div>
                )}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '24px' }}>
              <button className="btn-secondary" onClick={() => setShowTriggerModal(false)}>Cancel</button>
              <button className="btn-primary" onClick={handleSaveTrigger} disabled={!triggerForm.connector || !triggerForm.event}>Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Action Modal */}
      {showActionModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100, padding: '16px',
        }}>
          <div style={{
            backgroundColor: 'var(--surface-2)', border: '1px solid var(--border)',
            borderRadius: '10px', maxWidth: '500px', width: '100%', padding: '20px',
            maxHeight: '80vh', overflowY: 'auto',
          }}>
            <h3 style={{ marginBottom: '4px' }}>Configure Action</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Select a connected app and action for this step.
            </p>

            <div className="form-group">
              <label>App / Connector</label>
              <select value={actionForm.connector} onChange={(e) => setActionForm({ connector: e.target.value, action: '', config: {}, mapping: {} })}>
                <option value="">Select a connector...</option>
                {(capabilities || []).map(cap => (
                  <option key={cap.slug} value={cap.slug} disabled={!cap.supported_actions || cap.supported_actions.length === 0}>
                    {cap.name} {cap.is_connected ? '' : '(Connect required)'} {!cap.supported_actions || cap.supported_actions.length === 0 ? '(No actions)' : ''}
                  </option>
                ))}
              </select>
            </div>

            {actionForm.connector && (
              <div className="form-group" style={{ marginTop: '16px' }}>
                <label>Action</label>
                <select value={actionForm.action} onChange={(e) => setActionForm({ ...actionForm, action: e.target.value, config: {}, mapping: {} })}>
                  <option value="">Select an action...</option>
                  {(capabilities.find(c => c.slug === actionForm.connector)?.supported_actions || []).map(a => (
                    <option key={a.slug} value={a.slug}>{a.name}</option>
                  ))}
                </select>
                {actionForm.action && (
                   <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)', padding: '8px', backgroundColor: 'var(--surface-1)', borderRadius: '4px' }}>
                     {capabilities.find(c => c.slug === actionForm.connector)?.supported_actions?.find(a => a.slug === actionForm.action)?.description}
                   </div>
                )}
              </div>
            )}

            {/* Dynamic input_schema fields with mapping */}
            {actionForm.connector && actionForm.action && (() => {
              const selectedAction = capabilities.find(c => c.slug === actionForm.connector)?.supported_actions?.find(a => a.slug === actionForm.action);
              if (!selectedAction?.input_schema || Object.keys(selectedAction.input_schema).length === 0) {
                return <div style={{ marginTop: '16px', fontSize: '13px', color: 'var(--text-secondary)' }}>No configuration required for this action.</div>;
              }
              return (
                <div style={{ marginTop: '16px' }}>
                  <label style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', display: 'block' }}>Field Configuration</label>
                  {Object.entries(selectedAction.input_schema).map(([key, field]) => (
                    <div key={key} className="form-group" style={{ marginBottom: '12px' }}>
                      <label style={{ fontSize: '12px' }}>{field.label || key} {field.required ? '*' : ''}</label>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <select
                          value={actionForm.mapping?.[key] || ''}
                          onChange={(e) => {
                            const newMapping = { ...actionForm.mapping };
                            if (e.target.value) { newMapping[key] = e.target.value; } else { delete newMapping[key]; }
                            setActionForm({ ...actionForm, mapping: newMapping });
                          }}
                          style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
                        >
                          <option value="">Static value</option>
                          <optgroup label="Trigger Outputs">
                            {getTriggerVariables().map(v => (
                              <option key={v.path} value={v.path}>{v.label} ({v.path})</option>
                            ))}
                          </optgroup>
                        </select>
                        {!actionForm.mapping?.[key] && (
                          <input
                            type={field.type === 'number' ? 'number' : 'text'}
                            value={actionForm.config?.[key] || ''}
                            onChange={(e) => setActionForm({ ...actionForm, config: { ...actionForm.config, [key]: e.target.value } })}
                            placeholder={field.description || 'Enter value...'}
                            style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
                          />
                        )}
                        {actionForm.mapping?.[key] && (
                          <div style={{ flex: 1, padding: '8px', backgroundColor: 'var(--surface-1)', color: 'var(--text-secondary)', borderRadius: '4px', border: '1px solid var(--border)', fontStyle: 'italic', fontSize: '13px' }}>
                            Mapped to {actionForm.mapping[key]}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '24px' }}>
              <button className="btn-secondary" onClick={() => { setShowActionModal(false); setEditingStepId(null); setActionForm({ connector: '', action: '', config: {}, mapping: {} }); }}>Cancel</button>
              <button className="btn-primary" onClick={handleSaveAction} disabled={!actionForm.connector || !actionForm.action}>Save Action</button>
            </div>
          </div>
        </div>
      )}

      {/* Condition Modal */}
      {showConditionModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100, padding: '16px',
        }}>
          <div style={{
            backgroundColor: 'var(--surface-2)', border: '1px solid var(--border)',
            borderRadius: '10px', maxWidth: '500px', width: '100%', padding: '20px',
          }}>
            <h3 style={{ marginBottom: '4px' }}>Configure Condition</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Set a condition that must be met to continue execution.
            </p>

            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label>Field</label>
              <select
                value={conditionForm.field}
                onChange={(e) => setConditionForm({ ...conditionForm, field: e.target.value })}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
              >
                <option value="">Select a field...</option>
                <optgroup label="Trigger Outputs">
                  {getTriggerVariables().map(v => (
                    <option key={v.path} value={v.path}>{v.label} ({v.path})</option>
                  ))}
                </optgroup>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label>Operator</label>
              <select
                value={conditionForm.operator}
                onChange={(e) => setConditionForm({ ...conditionForm, operator: e.target.value })}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
              >
                {CONDITION_OPERATORS.map(op => (
                  <option key={op.value} value={op.value}>{op.label}</option>
                ))}
              </select>
            </div>

            {!['is_empty', 'is_not_empty'].includes(conditionForm.operator) && (
              <div className="form-group" style={{ marginBottom: '16px' }}>
                <label>Value</label>
                <input
                  type="text"
                  value={conditionForm.value}
                  onChange={(e) => setConditionForm({ ...conditionForm, value: e.target.value })}
                  placeholder="Enter value to compare..."
                  style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
                />
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '24px' }}>
              <button className="btn-secondary" onClick={() => { setShowConditionModal(false); setEditingStepId(null); setConditionForm({ field: '', operator: 'equals', value: '' }); }}>Cancel</button>
              <button className="btn-primary" onClick={handleSaveCondition} disabled={!conditionForm.field || !conditionForm.operator}>Save Condition</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
