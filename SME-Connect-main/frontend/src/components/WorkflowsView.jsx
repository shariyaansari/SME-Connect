import React, { useState, useEffect } from 'react';
import {
  GitFork,
  CheckCircle,
  PauseCircle,
  Plus,
  Trash2,
  GripVertical
} from 'lucide-react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { api } from '../api';

function SortableStepItem({ step, index, editingStepId, setEditingStepId, setConditionForm, setShowConditionModal, setActionForm, setShowActionModal }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: step.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 50 : 1,
    position: 'relative',
    opacity: isDragging ? 0.8 : 1,
  };

  let leftBorder = 'var(--action-accent)';
  let kickerClass = 'kicker-action';
  if (step.type === 'condition') {
    leftBorder = 'var(--condition-accent)';
    kickerClass = 'kicker-condition';
  }

  return (
    <div ref={setNodeRef} style={style}>
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
          width: '280px',
          backgroundColor: 'var(--surface-1)',
          borderRadius: '8px',
          border: '1px solid var(--border)',
          borderLeft: `4px solid ${leftBorder}`,
          padding: '12px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          cursor: 'pointer',
          transition: isDragging ? 'none' : 'all 0.2s',
          boxShadow: isDragging ? '0 12px 24px rgba(0,0,0,0.15)' : '0 2px 8px rgba(0,0,0,0.05)',
        }}
        onMouseEnter={(e) => { if(!isDragging){ e.currentTarget.style.borderColor = leftBorder; e.currentTarget.style.transform = 'translateY(-2px)'; } }}
        onMouseLeave={(e) => { if(!isDragging){ e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.transform = 'translateY(0)'; } }}
      >
        <div style={{ position: 'absolute', left: '-24px', top: '50%', transform: 'translateY(-50%)', cursor: 'grab', color: 'var(--text-muted)' }} {...attributes} {...listeners}>
           <GripVertical size={16} />
        </div>
        <span className={`kicker-label ${kickerClass}`}>{step.type.toUpperCase()}</span>
        <span style={{
          fontSize: '14px',
          fontWeight: 600,
          color: 'var(--text-primary)',
        }}>
          {step.action || step.field || 'Config'}
        </span>
        <span style={{
          fontSize: '12px',
          color: 'var(--text-secondary)',
        }}>
          {step.connector || step.operator || 'Builder step'}
        </span>
      </div>
    </div>
  );
}

export default function WorkflowsView({ onNavigateConnectors, onNavigateExecutions, currentOrg }) {
  const [workflows, setWorkflows] = useState([]);
  const [capabilities, setCapabilities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [healthMap, setHealthMap] = useState({});

  // Builder State
  const [activeWorkflowId, setActiveWorkflowId] = useState(null);
  const [draftDefinition, setDraftDefinition] = useState(null);
  const [validationResult, setValidationResult] = useState(null);

  // UI State
  const [showTriggerModal, setShowTriggerModal] = useState(false);
  const [triggerForm, setTriggerForm] = useState({ connector: '', event: '' });
  const [showActionModal, setShowActionModal] = useState(false);
  const [actionForm, setActionForm] = useState({ connector: '', action: '', config: {}, mapping: {} });
  const [editingStepId, setEditingStepId] = useState(null);
  const [insertIndex, setInsertIndex] = useState(null);
  const [showInsertMenu, setShowInsertMenu] = useState(null);
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

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = async (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    
    const oldIndex = draftDefinition.steps.findIndex(s => s.id === active.id);
    const newIndex = draftDefinition.steps.findIndex(s => s.id === over.id);
    
    const newSteps = arrayMove(draftDefinition.steps, oldIndex, newIndex);
    const newDef = { ...draftDefinition, steps: newSteps };
    setDraftDefinition(newDef);
    
    if (activeWorkflowId !== 'new') {
      try {
        const updated = await api.updateWorkflow(activeWorkflowId, { definition: newDef }, currentOrg?.id);
        setDraftDefinition(updated.definition);
        setValidationResult({ valid: true });
        await loadData();
      } catch (err) {
        console.error(err);
        if (err.validationErrors) setValidationResult({ valid: false, errors: err.validationErrors });
        else setValidationResult({ valid: false, errors: err.message });
      }
    }
  };

  useEffect(() => {
    loadData();
  }, [currentOrg?.id]);

  async function loadData() {
    try {
      setLoading(true);
      const [wfs, caps] = await Promise.all([
        api.fetchWorkflows(null, currentOrg?.id),
        api.fetchWorkflowCapabilities()
      ]);
      setWorkflows(wfs);
      setCapabilities(caps);

      // Asynchronously load health statuses (Module 6)
      if (Array.isArray(wfs) && wfs.length > 0) {
        Promise.all(
          wfs.map(async (wf) => {
            try {
              const h = await api.fetchWorkflowHealth(wf.id, currentOrg?.id);
              return { [wf.id]: h };
            } catch {
              return null;
            }
          })
        ).then((results) => {
          const map = {};
          results.forEach((item) => {
            if (item) Object.assign(map, item);
          });
          setHealthMap(map);
        });
      }

    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const renderHealthBadge = (health) => {
    if (!health) return null;
    const badgeConfig = {
      healthy: { label: 'Healthy', bg: 'rgba(16, 185, 129, 0.1)', color: '#10b981' },
      needs_attention: { label: 'Needs Attention', bg: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' },
      retrying: { label: 'Retrying', bg: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b' },
      paused: { label: 'Paused', bg: 'rgba(107, 114, 128, 0.1)', color: '#6b7280' },
      never_run: { label: 'Never Run', bg: 'rgba(107, 114, 128, 0.1)', color: '#6b7280' },
    };
    const c = badgeConfig[health.status] || badgeConfig.never_run;
    return (
      <span
        title={`Success rate: ${health.success_rate_percent}% (${health.successful_executions}/${health.total_executions} runs)`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          padding: '2px 8px',
          borderRadius: '9999px',
          backgroundColor: c.bg,
          color: c.color,
          fontSize: '11px',
          fontWeight: 600,
        }}
      >
        <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: c.color }} />
        {c.label}
      </span>
    );
  };

  const handleSelectWorkflow = async (id) => {
    try {
      const detail = await api.fetchWorkflow(id);
      setActiveWorkflowId(id);
      setDraftDefinition(detail.definition);
      setValidationResult(null);
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

  const handleDeleteWorkflow = async (id, e) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this workflow and all its versions?')) return;
    try {
      await api.deleteWorkflow(id);
      if (activeWorkflowId === id) {
        setActiveWorkflowId(null);
        setDraftDefinition(null);
        setValidationResult(null);
      }
      await loadData();
    } catch (err) {
      console.error(err);
      alert('Failed to delete workflow: ' + err.message);
    }
  };

  const handleNewWorkflow = () => {
    setActiveWorkflowId('new');
    setDraftDefinition({
      trigger: { connector: "", event: "", config: {} },
      steps: []
    });
    setValidationResult(null);
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
        setValidationResult({ valid: true });
        await loadData();
      } catch (err) {
        console.error(err);
        if (err.validationErrors) {
          setValidationResult({ valid: false, errors: err.validationErrors });
        } else {
          setValidationResult({ valid: false, errors: err.message });
        }
        // Rollback on validation failure if we want to, but the UI keeps the newDef in draftDefinition, 
        // which allows the user to see the errors and fix them in the canvas without losing work.
        // Actually, draftDefinition is already set to newDef above.
      }
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
      const newStep = { id: `step-${Date.now()}`, ...conditionData };
      if (insertIndex !== null) {
        newSteps.splice(insertIndex, 0, newStep);
      } else {
        newSteps.push(newStep);
      }
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
        setValidationResult({ valid: true });
      } else {
        const updated = await api.updateWorkflow(activeWorkflowId, { definition: newDef });
        setDraftDefinition(updated.definition);
        setValidationResult({ valid: true });
        await loadData();
      }
    } catch (err) {
      console.error(err);
      if (err.validationErrors) {
        setValidationResult({ valid: false, errors: err.validationErrors });
      } else {
        setValidationResult({ valid: false, errors: err.message });
      }
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
      const newStep = { id: `step-${Date.now()}`, ...actionData };
      if (insertIndex !== null) {
        newSteps.splice(insertIndex, 0, newStep);
      } else {
        newSteps.push(newStep);
      }
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
        setValidationResult({ valid: true });
      } else {
        const updated = await api.updateWorkflow(activeWorkflowId, { definition: newDef });
        setDraftDefinition(updated.definition);
        setValidationResult({ valid: true });
        await loadData();
      }
    } catch (err) {
      console.error(err);
      if (err.validationErrors) {
        setValidationResult({ valid: false, errors: err.validationErrors });
      } else {
        setValidationResult({ valid: false, errors: err.message });
      }
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
  const activeWorkflow = (workflows || []).find(w => w.id === activeWorkflowId);

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
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{ margin: 0 }}>Workflow design canvas</h3>
              {activeWorkflow && (
                <span className={`status-pill ${activeWorkflow.status === 'published' ? 'success' : 'neutral'}`} style={{ transform: 'scale(0.85)', transformOrigin: 'left center' }}>
                  {activeWorkflow.status === 'published' ? <CheckCircle size={12} /> : <PauseCircle size={12} />}
                  <span>{activeWorkflow.status === 'published' ? 'Published' : activeWorkflow.status === 'draft' ? 'Draft' : 'Paused'}</span>
                </span>
              )}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
              {activeWorkflowId
                ? `Editing: ${activeWorkflow?.name || 'New Workflow'} (v${activeWorkflow?.version_number || 1})`
                : 'Select a workflow from the inventory below to edit its flow.'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            {activeWorkflow && activeWorkflow.status !== 'published' && (
              <button
                className="btn-primary"
                onClick={async () => {
                  try {
                    await api.publishWorkflow(activeWorkflowId);
                    setValidationResult(null);
                    await loadData();
                  } catch (err) {
                    console.error(err);
                    if (err.validationErrors) {
                      setValidationResult({ valid: false, errors: err.validationErrors });
                    } else {
                      setValidationResult({ valid: false, errors: err.message });
                    }
                  }
                }}
                style={{ fontSize: '12px', padding: '4px 10px', backgroundColor: 'var(--success)' }}
              >
                Publish
              </button>
            )}
            
            {activeWorkflow && activeWorkflow.status === 'published' && (
              <button
                className="btn-secondary"
                onClick={async () => {
                  try {
                    await api.pauseWorkflow(activeWorkflowId);
                    setValidationResult(null);
                    await loadData();
                  } catch (err) {
                    console.error(err);
                    setValidationResult({ valid: false, errors: err.message });
                  }
                }}
                style={{ fontSize: '12px', padding: '4px 10px' }}
              >
                Pause Workflow
              </button>
            )}

            <button
              className="btn-secondary"
              onClick={async () => {
                if (!activeWorkflowId || activeWorkflowId === 'new') return;
                try {
                  await api.updateWorkflow(activeWorkflowId, { definition: draftDefinition });
                  setValidationResult({ valid: true });
                } catch (err) {
                  console.error(err);
                  if (err.validationErrors) {
                    setValidationResult({ valid: false, errors: err.validationErrors });
                  } else {
                    setValidationResult({ valid: false, errors: err.message });
                  }
                }
              }}
              style={{ fontSize: '12px', padding: '4px 10px' }}
              disabled={!activeWorkflowId || activeWorkflowId === 'new'}
            >
              Validate
            </button>
            <button
              className="btn-secondary"
              onClick={onNavigateConnectors}
              style={{ fontSize: '12px', padding: '4px 10px' }}
            >
              Manage connections
            </button>
            {onNavigateExecutions && activeWorkflowId && activeWorkflowId !== 'new' && (
              <button
                className="btn-secondary"
                onClick={() => onNavigateExecutions(activeWorkflowId)}
                style={{ fontSize: '12px', padding: '4px 10px' }}
              >
                View Executions
              </button>
            )}
          </div>
        </div>

        {validationResult && (
          <div style={{
            marginBottom: '16px',
            padding: '12px 16px',
            borderRadius: '6px',
            backgroundColor: validationResult.valid ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${validationResult.valid ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
          }}>
            {validationResult.valid ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--success)', fontSize: '14px', fontWeight: 500 }}>
                <CheckCircle size={16} />
                Workflow is valid
              </div>
            ) : (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--error)', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  <span style={{ fontSize: '16px' }}>&times;</span>
                  Workflow has errors
                </div>
                <ul style={{ margin: 0, paddingLeft: '24px', color: 'var(--text-secondary)', fontSize: '13px' }}>
                  {Array.isArray(validationResult.errors) ? validationResult.errors.map((err, i) => (
                    <li key={i} style={{ marginBottom: '4px' }}>
                      <span style={{ fontFamily: 'monospace', color: 'var(--text-primary)', marginRight: '6px' }}>{err.path || 'Workflow'}</span>
                      &rarr; {err.message}
                    </li>
                  )) : (
                    <li>{validationResult.errors}</li>
                  )}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeWorkflowId && draftDefinition ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '0', // We use vertical lines for gap
            paddingBottom: '24px',
            paddingTop: '16px'
          }}>
            {/* TRIGGER CARD */}
            <div
              onClick={openTriggerModal}
              style={{
              width: '280px',
              backgroundColor: 'var(--surface-1)',
              borderRadius: '8px',
              border: '1px solid var(--border)',
              borderLeft: '4px solid var(--trigger-accent)',
              padding: '12px 16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              cursor: 'pointer',
              transition: 'all 0.2s',
              boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--trigger-accent)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              <span className="kicker-label kicker-trigger">TRIGGER</span>
              <span style={{
                fontSize: '14px',
                fontWeight: 600,
                color: 'var(--text-primary)',
              }}>
                {draftDefinition?.trigger?.event ? getEventName(draftDefinition?.trigger?.connector, draftDefinition?.trigger?.event) : 'Unconfigured Trigger'}
              </span>
              <span style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
              }}>
                {draftDefinition?.trigger?.connector ? getConnectorName(draftDefinition?.trigger?.connector) : 'Click to configure'}
              </span>
            </div>

            {/* Step Cards */}
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={((draftDefinition && draftDefinition.steps) || []).map(s => s.id)} strategy={verticalListSortingStrategy}>
                {((draftDefinition && draftDefinition.steps) || []).map((step, index) => {
                     // Skip empty placeholder steps
                     if (step.id === 'step-placeholder' || (!step.connector && !step.action && !step.field)) {
                       return null;
                     }

                     return (
                       <React.Fragment key={step.id}>
                         <div style={{ position: 'relative', width: '2px', height: '32px', backgroundColor: 'var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                           <button
                             onClick={(e) => { e.stopPropagation(); setShowInsertMenu(showInsertMenu === index ? null : index); }}
                             style={{
                               position: 'absolute',
                               width: '20px', height: '20px', borderRadius: '50%',
                               backgroundColor: 'var(--surface-0)', border: '1px solid var(--border)',
                               display: 'flex', alignItems: 'center', justifyContent: 'center',
                               cursor: 'pointer', zIndex: 10, color: 'var(--text-secondary)'
                             }}
                             title="Insert step here"
                             onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.borderColor = 'var(--text-primary)'; }}
                             onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
                           >
                             <Plus size={12} />
                           </button>
                           {showInsertMenu === index && (
                             <div style={{
                               position: 'absolute', left: '20px', top: '50%', transform: 'translateY(-50%)',
                               backgroundColor: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '6px',
                               padding: '8px', display: 'flex', flexDirection: 'column', gap: '4px', zIndex: 20,
                               boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                             }}>
                               <button className="btn-secondary" style={{ fontSize: '12px', padding: '4px 8px' }} onClick={() => { setInsertIndex(index); setShowActionModal(true); setShowInsertMenu(null); }}>Action</button>
                               <button className="btn-secondary" style={{ fontSize: '12px', padding: '4px 8px' }} onClick={() => { setInsertIndex(index); setShowConditionModal(true); setShowInsertMenu(null); }}>Condition</button>
                             </div>
                           )}
                         </div>
                         <SortableStepItem
                           step={step}
                           index={index}
                           editingStepId={editingStepId}
                           setEditingStepId={setEditingStepId}
                           setConditionForm={setConditionForm}
                           setShowConditionModal={setShowConditionModal}
                           setActionForm={setActionForm}
                           setShowActionModal={setShowActionModal}
                         />
                       </React.Fragment>
                     );
                })}
              </SortableContext>
            </DndContext>

            {/* Add Step Buttons */}
            <div style={{ width: '2px', height: '24px', backgroundColor: 'var(--border)' }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '12px' }}>
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

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                  {renderHealthBadge(healthMap[wf.id])}

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

                  <button
                    onClick={(e) => handleDeleteWorkflow(wf.id, e)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--text-secondary)',
                      padding: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                    title="Delete workflow"
                    onMouseOver={(e) => e.currentTarget.style.color = 'var(--error)'}
                    onMouseOut={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                  >
                    <Trash2 size={16} />
                  </button>
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
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          display: 'flex', justifyContent: 'flex-end',
          zIndex: 100,
        }}>
          <div style={{
            backgroundColor: 'var(--surface-2)', borderLeft: '1px solid var(--border)',
            width: '450px', maxWidth: '100vw', padding: '24px', height: '100%', overflowY: 'auto',
            boxShadow: '-4px 0 24px rgba(0,0,0,0.2)',
            animation: 'slideInRight 0.2s ease-out'
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
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
              >
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
                <select 
                  value={triggerForm.event} 
                  onChange={(e) => setTriggerForm({ ...triggerForm, event: e.target.value })}
                  style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
                >
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
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          display: 'flex', justifyContent: 'flex-end',
          zIndex: 100,
        }}>
          <div style={{
            backgroundColor: 'var(--surface-2)', borderLeft: '1px solid var(--border)',
            width: '450px', maxWidth: '100vw', padding: '24px', height: '100%', overflowY: 'auto',
            boxShadow: '-4px 0 24px rgba(0,0,0,0.2)',
            animation: 'slideInRight 0.2s ease-out'
          }}>
            <h3 style={{ marginBottom: '4px' }}>Configure Action</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Select a connected app and action for this step.
            </p>

            <div className="form-group">
              <label>App / Connector</label>
              <select 
                value={actionForm.connector} 
                onChange={(e) => setActionForm({ connector: e.target.value, action: '', config: {}, mapping: {} })}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
              >
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
                <select 
                  value={actionForm.action} 
                  onChange={(e) => setActionForm({ ...actionForm, action: e.target.value, config: {}, mapping: {} })}
                  style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
                >
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
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <select
                          value={actionForm.mapping?.[key] || ''}
                          onChange={(e) => {
                            const newMapping = { ...actionForm.mapping };
                            if (e.target.value) { newMapping[key] = e.target.value; } else { delete newMapping[key]; }
                            setActionForm({ ...actionForm, mapping: newMapping });
                          }}
                          style={{ width: '100%', minWidth: 0, padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
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
                            style={{ width: '100%', minWidth: 0, padding: '8px', borderRadius: '4px', border: '1px solid var(--border)', backgroundColor: 'var(--surface-0)', color: 'var(--text-primary)' }}
                          />
                        )}
                        {actionForm.mapping?.[key] && (
                          <div style={{ width: '100%', minWidth: 0, padding: '8px', backgroundColor: 'var(--surface-1)', color: 'var(--text-secondary)', borderRadius: '4px', border: '1px solid var(--border)', fontStyle: 'italic', fontSize: '13px' }}>
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
              {editingStepId && editingStepId !== 'step-placeholder' && (
                <button
                  className="btn-secondary"
                  style={{ marginRight: 'auto', color: 'var(--error)', borderColor: 'var(--error)' }}
                  onClick={async () => {
                    const newSteps = (draftDefinition.steps || []).filter(s => s.id !== editingStepId);
                    const newDef = { ...draftDefinition, steps: newSteps };
                    setDraftDefinition(newDef);
                    setShowActionModal(false);
                    setEditingStepId(null);
                    setActionForm({ connector: '', action: '', config: {}, mapping: {} });
                    if (activeWorkflowId !== 'new') {
                      try {
                        const updated = await api.updateWorkflow(activeWorkflowId, { definition: newDef });
                        setDraftDefinition(updated.definition);
                        setValidationResult({ valid: true });
                        await loadData();
                      } catch (err) {
                        console.error(err);
                        if (err.validationErrors) setValidationResult({ valid: false, errors: err.validationErrors });
                        else setValidationResult({ valid: false, errors: err.message });
                      }
                    }
                  }}
                >
                  Delete Action
                </button>
              )}
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
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          display: 'flex', justifyContent: 'flex-end',
          zIndex: 100,
        }}>
          <div style={{
            backgroundColor: 'var(--surface-2)', borderLeft: '1px solid var(--border)',
            width: '450px', maxWidth: '100vw', padding: '24px', height: '100%', overflowY: 'auto',
            boxShadow: '-4px 0 24px rgba(0,0,0,0.2)',
            animation: 'slideInRight 0.2s ease-out'
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
              {editingStepId && editingStepId !== 'step-placeholder' && (
                <button
                  className="btn-secondary"
                  style={{ marginRight: 'auto', color: 'var(--error)', borderColor: 'var(--error)' }}
                  onClick={async () => {
                    const newSteps = (draftDefinition.steps || []).filter(s => s.id !== editingStepId);
                    const newDef = { ...draftDefinition, steps: newSteps };
                    setDraftDefinition(newDef);
                    setShowConditionModal(false);
                    setEditingStepId(null);
                    setConditionForm({ field: '', operator: 'equals', value: '' });
                    if (activeWorkflowId !== 'new') {
                      try {
                        const updated = await api.updateWorkflow(activeWorkflowId, { definition: newDef });
                        setDraftDefinition(updated.definition);
                        setValidationResult({ valid: true });
                        await loadData();
                      } catch (err) {
                        console.error(err);
                        if (err.validationErrors) setValidationResult({ valid: false, errors: err.validationErrors });
                        else setValidationResult({ valid: false, errors: err.message });
                      }
                    }
                  }}
                >
                  Delete Condition
                </button>
              )}
              <button className="btn-secondary" onClick={() => { setShowConditionModal(false); setEditingStepId(null); setConditionForm({ field: '', operator: 'equals', value: '' }); }}>Cancel</button>
              <button className="btn-primary" onClick={handleSaveCondition} disabled={!conditionForm.field || !conditionForm.operator}>Save Condition</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
