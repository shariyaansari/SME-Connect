import React, { useState } from 'react';
import {
  GitFork,
  CheckCircle,
  PauseCircle,
  Plus
} from 'lucide-react';


export default function WorkflowsView({ onNavigateConnectors }) {
  const [workflows, setWorkflows] = useState([]);


  const [activeStepFlow, setActiveStepFlow] = useState([
    {
      id: 'step-1',
      type: 'trigger',
      kicker: 'TRIGGER',
      name: 'New inquiry row',
      app: 'Google Sheets',
    },
    {
      id: 'step-2',
      type: 'condition',
      kicker: 'CONDITION',
      name: 'Status is qualified',
      app: 'Filter rule',
    },
    {
      id: 'step-3',
      type: 'action',
      kicker: 'ACTION',
      name: 'Create CRM contact',
      app: 'HubSpot CRM',
    },
    {
      id: 'step-4',
      type: 'action',
      kicker: 'ACTION',
      name: 'Send notification',
      app: 'WhatsApp',
    },
  ]);

  const [showAddStepModal, setShowAddStepModal] = useState(false);

  const toggleWorkflow = (id) => {
    setWorkflows((prev) =>
      prev.map((wf) => {
        if (wf.id !== id) return wf;
        const newActive = !wf.active;
        return {
          ...wf,
          active: newActive,
          status: newActive ? 'active' : 'paused',
        };
      })
    );
  };

  const handleAddStep = (type, name, app) => {
    const kicker = type.toUpperCase();
    setActiveStepFlow((prev) => [
      ...prev,
      {
        id: `step-${Date.now()}`,
        type,
        kicker,
        name,
        app,
      },
    ]);
    setShowAddStepModal(false);
  };

  const activeCount = workflows.filter((w) => w.active).length;

  return (
    <div>
      {/* Screen Title & Single Primary CTA (Hick's Law) */}
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

        {/* The ONE primary button on this screen */}
        <button
          className="btn-primary"
          onClick={() => {
            const newId = `wf-${Date.now()}`;
            setWorkflows((prev) => [
              {
                id: newId,
                title: 'New automated workflow',
                subtitle: 'Triggered upon external event',
                active: true,
                lastRun: 'Just created',
                executions: '0 runs',
                status: 'active',
                icon: GitFork,
              },
              ...prev,
            ]);
          }}
        >
          <Plus size={15} />
          <span>New workflow</span>
        </button>
      </div>

      {/* Metric Tiles: sets of 3, surface-1, no borders (Miller's Law) */}
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
            <h3>Workflow design canvas (preview)</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Interactive preview: Google Sheets new inquiry → HubSpot CRM contact sync
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

        {/* Horizontal chain of step cards connected by simple arrow glyphs (→) */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          overflowX: 'auto',
          paddingBottom: '8px',
        }}>
          {activeStepFlow.map((step, index) => {
            // Border accent color based on type
            let borderColor = 'var(--condition-accent)';
            let kickerClass = 'kicker-condition';
            if (step.type === 'trigger') {
              borderColor = 'var(--trigger-accent)';
              kickerClass = 'kicker-trigger';
            } else if (step.type === 'action') {
              borderColor = 'var(--action-accent)';
              kickerClass = 'kicker-action';
            }

            return (
              <React.Fragment key={step.id}>
                {/* Step card (~150px wide, flat surface-1, 2px left border accent only) */}
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
                  <span className={`kicker-label ${kickerClass}`}>
                    {step.kicker}
                  </span>
                  <span style={{
                    fontSize: '13px',
                    fontWeight: 500,
                    color: 'var(--text-primary)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {step.name}
                  </span>
                  <span style={{
                    fontSize: '12px',
                    color: 'var(--text-secondary)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {step.app}
                  </span>
                </div>

                {/* Simple arrow glyph connector (→) */}
                {index < activeStepFlow.length && (
                  <span style={{
                    color: 'var(--text-muted)',
                    fontSize: '14px',
                    userSelect: 'none',
                    padding: '0 2px',
                  }}>
                    →
                  </span>
                )}
              </React.Fragment>
            );
          })}

          {/* Ends in a dashed-border ghost "Add step" button (~150px wide) */}
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
      </div>

      {/* Workflow Dense List: surface-2, stacked rows with hairline dividers */}
      <div>
        <div style={{ marginBottom: '10px' }}>
          <h3>Workflow inventory</h3>
        </div>

        <div className="list-container">
          {workflows.length === 0 ? (
            <div style={{
              padding: '36px 20px',
              textAlign: 'center',
              color: 'var(--text-secondary)',
              fontSize: '14px',
            }}>
              No active workflows yet. Click "New workflow" above to create an automated flow.
            </div>
          ) : (
            workflows.map((wf) => {

            const Icon = wf.icon;
            const isSuccess = wf.status === 'active';

            return (
              <div key={wf.id} className="list-row">
                {/* Left: Leading icon + Title and subtitle */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0, paddingRight: '16px' }}>
                  <Icon size={18} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{
                      fontSize: '14px',
                      fontWeight: 500,
                      color: 'var(--text-primary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {wf.title}
                    </div>
                    <div style={{
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {wf.subtitle} • {wf.executions} • {wf.lastRun}
                    </div>
                  </div>
                </div>

                {/* Right: Status pill + Toggle switch (always in fixed right-aligned position) */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
                  <span className={`status-pill ${isSuccess ? 'success' : 'neutral'}`}>
                    {isSuccess ? <CheckCircle size={12} /> : <PauseCircle size={12} />}
                    <span>{isSuccess ? 'Active' : 'Paused'}</span>
                  </span>

                  <label className="switch" title={wf.active ? 'Pause workflow' : 'Activate workflow'}>
                    <input
                      type="checkbox"
                      checked={wf.active}
                      onChange={() => toggleWorkflow(wf.id)}
                    />
                    <span className="slider" />
                  </label>
                </div>
              </div>
            );
          }))}
        </div>

      </div>

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
              Choose a category to append to the execution chain.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
              <button
                className="btn-secondary"
                style={{ justifyContent: 'flex-start', padding: '10px 12px' }}
                onClick={() => handleAddStep('action', 'Update row status', 'Google Sheets')}
              >
                <span className="kicker-label kicker-action" style={{ width: '60px' }}>ACTION</span>
                <span>Update row status in Google Sheets</span>
              </button>

              <button
                className="btn-secondary"
                style={{ justifyContent: 'flex-start', padding: '10px 12px' }}
                onClick={() => handleAddStep('action', 'Send alert message', 'WhatsApp')}
              >
                <span className="kicker-label kicker-action" style={{ width: '60px' }}>ACTION</span>
                <span>Send alert via WhatsApp API</span>
              </button>

              <button
                className="btn-secondary"
                style={{ justifyContent: 'flex-start', padding: '10px 12px' }}
                onClick={() => handleAddStep('condition', 'Check revenue threshold', 'Filter rule')}
              >
                <span className="kicker-label kicker-condition" style={{ width: '60px' }}>CONDITION</span>
                <span>Check revenue threshold</span>
              </button>
            </div>

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
