import React, { useState, useEffect } from 'react';
import { Check, Circle, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { api } from '../api';

export default function OnboardingChecklist({ connections = [], onNavigate }) {
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const loadWorkflows = async () => {
      try {
        const data = await api.fetchWorkflows();
        if (isMounted) {
          setWorkflows(data || []);
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to load workflows for onboarding checklist:", err);
        if (isMounted) setLoading(false);
      }
    };
    loadWorkflows();
    return () => { isMounted = false; };
  }, [connections]); 

  const hasAccount = true;
  const hasConnection = connections.length > 0;
  const hasWorkflow = workflows.length > 0;
  const isConfigured = workflows.length > 0; 
  const isActivated = workflows.some(w => w.status === 'published' || w.status === 'active');
  const hasExecution = false;

  const totalSteps = 6;
  const completedSteps = [hasAccount, hasConnection, hasWorkflow, isConfigured, isActivated, hasExecution].filter(Boolean).length;
  
  const isFullyComplete = completedSteps === totalSteps || (completedSteps === 5 && !hasExecution);
  const isExperiencedUser = connections.length > 3 && workflows.length >= 3;
  
  if (isExperiencedUser || isFullyComplete) {
    return null; // Don't show anything once complete or for power users to keep UI clean
  }

  const ChecklistItem = ({ isComplete, label, onClick }) => (
    <div 
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '10px 12px',
        borderRadius: '8px',
        cursor: onClick ? 'pointer' : 'default',
        opacity: isComplete ? 0.6 : 1,
        transition: 'all 0.2s',
      }}
      onMouseOver={(e) => onClick && (e.currentTarget.style.backgroundColor = 'var(--surface-1)')}
      onMouseOut={(e) => onClick && (e.currentTarget.style.backgroundColor = 'transparent')}
    >
      <div style={{ color: isComplete ? 'var(--status-success-text)' : 'var(--primary-btn-bg)' }}>
        {isComplete ? <Check size={18} /> : <Circle size={18} />}
      </div>
      <span style={{ 
        fontSize: '14px', 
        fontWeight: isComplete ? 400 : 500,
        color: isComplete ? 'var(--text-secondary)' : 'var(--text-primary)',
        textDecoration: isComplete ? 'line-through' : 'none'
      }}>
        {label}
      </span>
    </div>
  );

  return (
    <div style={{
      backgroundColor: 'var(--surface-0)',
      borderRadius: '12px',
      border: '1px solid var(--primary-btn-bg)',
      marginBottom: '32px',
      boxShadow: '0 4px 12px rgba(67, 56, 202, 0.08)',
      overflow: 'hidden'
    }}>
      {/* Horizontal Banner Header */}
      <div 
        onClick={() => setExpanded(!expanded)}
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          padding: '16px 20px',
          cursor: 'pointer',
          backgroundColor: 'rgba(67, 56, 202, 0.02)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ 
            width: '32px', height: '32px', borderRadius: '8px', 
            backgroundColor: 'var(--primary-btn-bg)', color: 'white',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Zap size={18} />
          </div>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              New to SME Connect?
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
              Complete your setup to start automating your business.
            </p>
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--primary-btn-bg)' }}>
              {completedSteps} / {totalSteps} steps
            </span>
            <div style={{ width: '100px', height: '6px', backgroundColor: 'var(--surface-2)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', backgroundColor: 'var(--primary-btn-bg)', width: `${(completedSteps / totalSteps) * 100}%`, transition: 'width 0.5s ease' }} />
            </div>
          </div>
          <div style={{ color: 'var(--text-muted)' }}>
            {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </div>
        </div>
      </div>

      {/* Expanded Checklist */}
      {expanded && (
        <div style={{ padding: '8px 20px 20px 20px', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '8px' }}>
            <ChecklistItem 
              isComplete={hasAccount} 
              label="Create your account" 
            />
            <ChecklistItem 
              isComplete={hasConnection} 
              label="Connect your first app" 
              onClick={() => onNavigate('connected')}
            />
            <ChecklistItem 
              isComplete={hasWorkflow} 
              label="Choose your first workflow" 
              onClick={() => { onNavigate('templates'); setExpanded(false); }}
            />
            <ChecklistItem 
              isComplete={isConfigured} 
              label="Configure your workflow" 
              onClick={() => { onNavigate('templates'); setExpanded(false); }}
            />
            <ChecklistItem 
              isComplete={isActivated} 
              label="Activate your first workflow" 
              onClick={() => onNavigate('workflows')}
            />
            <ChecklistItem 
              isComplete={hasExecution} 
              label="View your first execution" 
              onClick={() => onNavigate('workflows')}
            />
          </div>
        </div>
      )}
    </div>
  );
}
