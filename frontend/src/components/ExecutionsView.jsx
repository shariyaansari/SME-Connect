import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  Play,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Clock,
  ArrowRight,
  ChevronRight,
  X,
  Filter,
  Layers,
  SkipForward,
  RotateCcw,
  Calendar,
  ShieldAlert
} from 'lucide-react';
import { api } from '../api';

function formatRelativeTime(dateString) {
  if (!dateString) return 'Pending';
  const now = new Date();
  const date = new Date(dateString);
  const diffSec = Math.floor((now - date) / 1000);

  if (diffSec < 10) return 'Just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function formatDuration(startedAt, completedAt) {
  if (!startedAt || !completedAt) return null;
  const start = new Date(startedAt);
  const end = new Date(completedAt);
  const diffMs = end - start;
  if (diffMs < 1000) return `${diffMs}ms`;
  return `${(diffMs / 1000).toFixed(1)}s`;
}

function getCategoryBadge(category) {
  switch (category) {
    case 'rate_limit':
      return { label: 'Rate Limit', color: '#B45309', bg: '#FFFBEB', border: '#FDE68A' };
    case 'auth':
      return { label: 'Auth Expired', color: '#BE123C', bg: '#FFF1F2', border: '#FECDD3' };
    case 'network':
      return { label: 'Network Issue', color: '#4338CA', bg: '#EEF2FF', border: '#C7D2FE' };
    case 'data_validation':
      return { label: 'Data / Config', color: '#C2410C', bg: '#FFF7ED', border: '#FFEDD5' };
    case 'server_error':
      return { label: 'Server Error', color: '#B91C1C', bg: '#FEF2F2', border: '#FECACA' };
    case 'system':
      return { label: 'Safety Limit', color: '#6B7280', bg: '#F3F4F6', border: '#E5E7EB' };
    default:
      return { label: category || 'Error', color: '#B45309', bg: '#FFFBEB', border: '#FDE68A' };
  }
}

export default function ExecutionsView({ currentOrg, onNavigateWorkflows }) {
  const [executions, setExecutions] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pollingCycle, setPollingCycle] = useState(false);
  const [scheduleCycle, setScheduleCycle] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [selectedExecutionId, setSelectedExecutionId] = useState(null);
  const [executionDetail, setExecutionDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Filters & Notifications
  const [workflowFilter, setWorkflowFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [pollMessage, setPollMessage] = useState(null);

  const loadWorkflows = useCallback(async () => {
    try {
      const data = await api.fetchWorkflows();
      setWorkflows(data || []);
    } catch {
      // Ignore
    }
  }, []);

  const loadExecutions = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const filters = {};
      if (workflowFilter) filters.workflow_id = workflowFilter;
      if (statusFilter) filters.status = statusFilter;
      const data = await api.fetchExecutions(filters, currentOrg?.id);
      setExecutions(data || []);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [workflowFilter, statusFilter, currentOrg?.id]);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  useEffect(() => {
    loadExecutions();
  }, [loadExecutions]);

  const handleSelectExecution = async (execId) => {
    setSelectedExecutionId(execId);
    setLoadingDetail(true);
    try {
      const detail = await api.fetchExecutionDetail(execId, currentOrg?.id);
      setExecutionDetail(detail);
    } catch {
      setExecutionDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleRunPollCycle = async () => {
    setPollingCycle(true);
    setPollMessage(null);
    try {
      const res = await api.runPollCycle(currentOrg?.id);
      setPollMessage({
        type: 'success',
        text: `Polled ${res.workflows_polled} workflows. Detected ${res.events_detected} new trigger events.`,
      });
      await loadExecutions(true);
    } catch (err) {
      setPollMessage({
        type: 'error',
        text: err?.message || 'Failed to execute poll cycle',
      });
    } finally {
      setPollingCycle(false);
    }
  };

  const handleRunScheduleCycle = async () => {
    setScheduleCycle(true);
    setPollMessage(null);
    try {
      const res = await api.runScheduleCycle(currentOrg?.id);
      setPollMessage({
        type: 'success',
        text: `Schedule cycle evaluated ${res.workflows_evaluated} scheduled workflows. Triggered ${res.executions_triggered} runs.`,
      });
      await loadExecutions(true);
    } catch (err) {
      setPollMessage({
        type: 'error',
        text: err?.message || 'Failed to execute schedule cycle',
      });
    } finally {
      setScheduleCycle(false);
    }
  };

  const handleRetryExecution = async (execId) => {
    if (!execId) return;
    setRetrying(true);
    setPollMessage(null);
    try {
      const newExec = await api.retryExecution(execId, currentOrg?.id);
      setPollMessage({
        type: 'success',
        text: `Manual retry initiated. Created Execution #${newExec.id} (Attempt ${newExec.attempt_number}).`,
      });
      await loadExecutions(true);
      await handleSelectExecution(newExec.id);
    } catch (err) {
      setPollMessage({
        type: 'error',
        text: err?.message || 'Failed to retry execution',
      });
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div style={{ padding: '24px 36px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Top Banner / Breadcrumb */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '24px',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <Activity size={18} style={{ color: 'var(--primary-btn-bg)' }} />
            <h1 style={{ fontSize: '20px', fontWeight: 500, color: 'var(--text-primary)' }}>
              Execution History
            </h1>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Real-time audit log and step timelines for published workflow executions.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            onClick={() => loadExecutions(false)}
            className="btn-secondary"
            disabled={refreshing}
            style={{ fontSize: '13px', padding: '6px 14px', borderRadius: '8px', gap: '6px' }}
          >
            <RefreshCw size={13} className={refreshing ? 'spinning' : ''} />
            <span>Refresh</span>
          </button>

          <button
            onClick={handleRunScheduleCycle}
            className="btn-secondary"
            disabled={scheduleCycle}
            style={{ fontSize: '13px', padding: '6px 14px', borderRadius: '8px', gap: '6px' }}
            title="Evaluate and trigger any scheduled workflows due to run"
          >
            <Calendar size={13} className={scheduleCycle ? 'spinning' : ''} />
            <span>{scheduleCycle ? 'Evaluating...' : 'Run scheduler'}</span>
          </button>

          <button
            onClick={handleRunPollCycle}
            className="btn-primary"
            disabled={pollingCycle}
            style={{ fontSize: '13px', padding: '6px 14px', borderRadius: '8px', gap: '6px' }}
          >
            <Play size={13} className={pollingCycle ? 'spinning' : ''} />
            <span>{pollingCycle ? 'Polling...' : 'Trigger poll cycle'}</span>
          </button>
        </div>
      </div>

      {pollMessage && (
        <div style={{
          padding: '10px 16px',
          borderRadius: '8px',
          marginBottom: '20px',
          backgroundColor: pollMessage.type === 'error' ? 'var(--status-warning-bg)' : 'var(--status-success-bg)',
          color: pollMessage.type === 'error' ? 'var(--status-warning-text)' : 'var(--status-success-text)',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <span>{pollMessage.text}</span>
          <button
            onClick={() => setPollMessage(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Filters Bar */}
      <div style={{
        backgroundColor: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        padding: '12px 18px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        marginBottom: '20px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', fontSize: '13px' }}>
            <Filter size={14} />
            <span>Filters:</span>
          </div>

          {/* Workflow Filter */}
          <select
            value={workflowFilter}
            onChange={(e) => setWorkflowFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              backgroundColor: 'var(--surface-input)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
            }}
          >
            <option value="">All workflows</option>
            {workflows.map((wf) => (
              <option key={wf.id} value={wf.id}>
                {wf.name}
              </option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              backgroundColor: 'var(--surface-input)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
            }}
          >
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
          </select>
        </div>

        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Showing {executions.length} {executions.length === 1 ? 'execution' : 'executions'}
        </div>
      </div>

      {/* Main Content Layout: Table + Detail Modal/Drawer */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: selectedExecutionId ? '1fr 1fr' : '1fr',
        gap: '24px',
        alignItems: 'start',
      }}>
        {/* Table of Executions */}
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          overflow: 'hidden',
        }}>
          {loading ? (
            <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px' }}>
              <RefreshCw size={24} className="spinning" style={{ margin: '0 auto 12px' }} />
              Loading executions...
            </div>
          ) : executions.length === 0 ? (
            <div style={{ padding: '60px', textAlign: 'center' }}>
              <Layers size={32} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
              <h3 style={{ fontSize: '15px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                No executions recorded yet
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '400px', margin: '0 auto 16px' }}>
                Executions will appear here when published workflows receive trigger events or when a manual poll cycle is run.
              </p>
              {onNavigateWorkflows && (
                <button
                  onClick={onNavigateWorkflows}
                  className="btn-secondary"
                  style={{ fontSize: '13px', padding: '6px 14px', borderRadius: '8px' }}
                >
                  <span>View published workflows</span>
                  <ArrowRight size={13} />
                </button>
              )}
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{
                    backgroundColor: 'var(--surface-hover)',
                    borderBottom: '1px solid var(--border)',
                    color: 'var(--text-secondary)',
                    fontWeight: 500,
                  }}>
                    <th style={{ padding: '12px 18px' }}>Workflow</th>
                    <th style={{ padding: '12px 18px' }}>Status</th>
                    <th style={{ padding: '12px 18px' }}>Trigger data</th>
                    <th style={{ padding: '12px 18px' }}>Time</th>
                    <th style={{ padding: '12px 18px', textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {executions.map((exec) => {
                    const isSelected = selectedExecutionId === exec.id;
                    const duration = formatDuration(exec.started_at, exec.completed_at);
                    return (
                      <tr
                        key={exec.id}
                        onClick={() => handleSelectExecution(exec.id)}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          backgroundColor: isSelected ? 'var(--surface-hover)' : 'transparent',
                          cursor: 'pointer',
                          transition: 'background-color 0.15s ease',
                        }}
                      >
                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                            {exec.workflow_name || `Workflow #${exec.workflow_id}`}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                            ID #{exec.id} · Version {exec.workflow_version_id}
                          </div>
                        </td>

                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                              {exec.status === 'success' && (
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '5px',
                                  padding: '2px 8px',
                                  borderRadius: '9999px',
                                  fontSize: '11px',
                                  fontWeight: 500,
                                  backgroundColor: 'var(--status-success-bg)',
                                  color: 'var(--status-success-text)',
                                }}>
                                  <CheckCircle size={11} />
                                  Success
                                </span>
                              )}
                              {exec.status === 'failed' && (
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '5px',
                                  padding: '2px 8px',
                                  borderRadius: '9999px',
                                  fontSize: '11px',
                                  fontWeight: 500,
                                  backgroundColor: 'var(--status-warning-bg)',
                                  color: 'var(--status-warning-text)',
                                }}>
                                  <AlertCircle size={11} />
                                  Failed
                                </span>
                              )}
                              {exec.status === 'running' && (
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '5px',
                                  padding: '2px 8px',
                                  borderRadius: '9999px',
                                  fontSize: '11px',
                                  fontWeight: 500,
                                  backgroundColor: 'var(--status-neutral-bg)',
                                  color: 'var(--primary-btn-bg)',
                                }}>
                                  <RefreshCw size={11} className="spinning" />
                                  Running
                                </span>
                              )}
                              {exec.failure_category && (
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  padding: '1px 6px',
                                  borderRadius: '4px',
                                  fontSize: '10px',
                                  fontWeight: 500,
                                  backgroundColor: getCategoryBadge(exec.failure_category).bg,
                                  color: getCategoryBadge(exec.failure_category).color,
                                  border: `1px solid ${getCategoryBadge(exec.failure_category).border}`,
                                }}>
                                  {getCategoryBadge(exec.failure_category).label}
                                </span>
                              )}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
                              {exec.attempt_number > 1 && (
                                <span>Attempt #{exec.attempt_number}</span>
                              )}
                              {exec.next_retry_at && (
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '3px',
                                  color: 'var(--primary-btn-bg)',
                                  fontWeight: 500
                                }}>
                                  <RotateCcw size={10} />
                                  Retry scheduled
                                </span>
                              )}
                            </div>
                          </div>
                        </td>

                        <td style={{ padding: '14px 18px', color: 'var(--text-secondary)' }}>
                          {exec.trigger_data?.schedule_type ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}>
                              <Calendar size={12} style={{ color: 'var(--primary-btn-bg)' }} />
                              Schedule ({exec.trigger_data.frequency || 'automated'})
                            </span>
                          ) : exec.trigger_data?.row_index ? (
                            <span>Row #{exec.trigger_data.row_index}</span>
                          ) : exec.trigger_data?.values?.Name ? (
                            <span>{exec.trigger_data.values.Name}</span>
                          ) : (
                            <span>Payload #{exec.id}</span>
                          )}
                        </td>

                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ color: 'var(--text-primary)' }}>
                            {formatRelativeTime(exec.created_at)}
                          </div>
                          {duration && (
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                              Duration: {duration}
                            </div>
                          )}
                        </td>

                        <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectExecution(exec.id);
                            }}
                            className="btn-secondary"
                            style={{ fontSize: '11px', padding: '3px 8px', borderRadius: '6px' }}
                          >
                            <span>Inspect</span>
                            <ChevronRight size={11} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Execution Detail Timeline Inspector */}
        {selectedExecutionId && (
          <div style={{
            backgroundColor: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: '12px',
            padding: '20px',
            position: 'sticky',
            top: '80px',
            maxHeight: 'calc(100vh - 100px)',
            overflowY: 'auto',
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '16px',
              borderBottom: '1px solid var(--border)',
              paddingBottom: '12px',
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 500, color: 'var(--text-primary)' }}>
                    Execution #{selectedExecutionId}
                  </h3>
                  {executionDetail && (
                    <span style={{
                      fontSize: '11px',
                      padding: '2px 8px',
                      borderRadius: '10px',
                      backgroundColor: 'var(--surface-3)',
                      color: 'var(--text-secondary)',
                      fontWeight: 500
                    }}>
                      Attempt {executionDetail.attempt_number || 1}
                    </span>
                  )}
                  {executionDetail?.retry_of_execution_id && (
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      (Retry of #{executionDetail.retry_of_execution_id})
                    </span>
                  )}
                </div>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {executionDetail?.workflow_name || 'Workflow details'} &bull; Version {executionDetail?.workflow_version_id}
                </p>
              </div>

              <button
                onClick={() => setSelectedExecutionId(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-muted)',
                  padding: '4px',
                }}
              >
                <X size={16} />
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                <RefreshCw size={20} className="spinning" style={{ margin: '0 auto 8px' }} />
                Loading timeline...
              </div>
            ) : !executionDetail ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                Could not load execution details.
              </div>
            ) : (
              <div>
                {/* Module 6.8 & 6.12 Error Experience & Safe Retry Card */}
                {executionDetail.status === 'failed' && (
                  <div style={{
                    padding: '16px',
                    borderRadius: '10px',
                    backgroundColor: 'var(--status-warning-bg)',
                    border: '1px solid var(--border)',
                    marginBottom: '20px',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <ShieldAlert size={16} style={{ color: 'var(--status-warning-text)' }} />
                        <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--status-warning-text)' }}>
                          {executionDetail.failure_title || 'Execution Failed'}
                        </span>
                      </div>
                      {executionDetail.failure_category && (
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 500,
                          backgroundColor: getCategoryBadge(executionDetail.failure_category).bg,
                          color: getCategoryBadge(executionDetail.failure_category).color,
                          border: `1px solid ${getCategoryBadge(executionDetail.failure_category).border}`,
                        }}>
                          {getCategoryBadge(executionDetail.failure_category).label}
                        </span>
                      )}
                    </div>

                    <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginBottom: '10px', lineHeight: 1.5 }}>
                      {executionDetail.failure_explanation || executionDetail.error_message}
                    </p>

                    {executionDetail.actionable_guidance && (
                      <div style={{
                        padding: '10px 12px',
                        borderRadius: '6px',
                        backgroundColor: 'var(--surface-2)',
                        border: '1px solid var(--border)',
                        marginBottom: '12px',
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.4,
                      }}>
                        <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '2px' }}>
                          What you can do:
                        </strong>
                        {executionDetail.actionable_guidance}
                      </div>
                    )}

                    {executionDetail.next_retry_at && (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontSize: '12px',
                        color: 'var(--primary-btn-bg)',
                        marginBottom: '12px',
                        fontWeight: 500,
                      }}>
                        <Clock size={13} />
                        <span>
                          Automatic retry scheduled for {new Date(executionDetail.next_retry_at).toLocaleTimeString()}
                        </span>
                      </div>
                    )}

                    {/* Manual Retry CTA (Module 6.6 & 6.12) */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', paddingTop: '4px' }}>
                      {executionDetail.can_manual_retry !== false ? (
                        <button
                          onClick={() => handleRetryExecution(executionDetail.id)}
                          disabled={retrying}
                          className="btn-primary"
                          style={{
                            fontSize: '12px',
                            padding: '6px 14px',
                            borderRadius: '6px',
                            gap: '6px',
                          }}
                        >
                          <RotateCcw size={13} className={retrying ? 'spinning' : ''} />
                          <span>{retrying ? 'Retrying execution...' : 'Retry execution'}</span>
                        </button>
                      ) : (
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Cannot retry: Workflow is paused or currently running.
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Timeline visual progression */}
                <div style={{ marginBottom: '20px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '10px' }}>
                    EXECUTION TIMELINE
                  </div>

                  {/* Trigger event card */}
                  <div style={{
                    padding: '12px 14px',
                    borderRadius: '8px',
                    backgroundColor: 'var(--surface-hover)',
                    borderLeft: '3px solid var(--trigger-accent)',
                    marginBottom: '8px',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)' }}>
                        Workflow Trigger Event
                      </span>
                      <span style={{ fontSize: '11px', color: 'var(--status-success-text)' }}>
                        ✓ Received
                      </span>
                    </div>
                    <pre style={{
                      margin: '6px 0 0',
                      padding: '8px',
                      backgroundColor: 'var(--surface-input)',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontFamily: 'var(--font-mono)',
                      overflowX: 'auto',
                      color: 'var(--text-secondary)',
                    }}>
                      {JSON.stringify(executionDetail.trigger_data, null, 2)}
                    </pre>
                  </div>

                  {/* Sequential Steps */}
                  {executionDetail.steps?.map((step, idx) => {
                    const stepDuration = formatDuration(step.started_at, step.completed_at);
                    const isStepFailed = step.status === 'failed';
                    const isStepSkipped = step.status === 'skipped';

                    return (
                      <div key={step.id || idx}>
                        {/* Downward indicator */}
                        <div style={{ textAlign: 'center', color: 'var(--text-muted)', margin: '2px 0' }}>
                          ↓
                        </div>

                        <div style={{
                          padding: '12px 14px',
                          borderRadius: '8px',
                          backgroundColor: 'var(--surface-hover)',
                          borderLeft: `3px solid ${isStepFailed ? 'var(--status-warning-text)' : isStepSkipped ? 'var(--condition-accent)' : 'var(--action-accent)'}`,
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)' }}>
                                Step {idx + 1}: {step.step_id}
                              </span>
                            </div>

                            <div>
                              {step.status === 'success' && (
                                <span style={{ fontSize: '11px', color: 'var(--status-success-text)', display: 'flex', alignItems: 'center', gap: '3px' }}>
                                  <CheckCircle size={11} /> Success
                                </span>
                              )}
                              {step.status === 'failed' && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <span style={{ fontSize: '11px', color: 'var(--status-warning-text)', display: 'flex', alignItems: 'center', gap: '3px' }}>
                                    <AlertCircle size={11} /> Failed
                                  </span>
                                  {step.failure_category && (
                                    <span style={{
                                      padding: '1px 6px',
                                      borderRadius: '4px',
                                      fontSize: '10px',
                                      fontWeight: 500,
                                      backgroundColor: getCategoryBadge(step.failure_category).bg,
                                      color: getCategoryBadge(step.failure_category).color,
                                      border: `1px solid ${getCategoryBadge(step.failure_category).border}`,
                                    }}>
                                      {getCategoryBadge(step.failure_category).label}
                                    </span>
                                  )}
                                </div>
                              )}
                              {step.status === 'skipped' && (
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '3px' }}>
                                  <SkipForward size={11} /> Skipped
                                </span>
                              )}
                            </div>
                          </div>

                          {stepDuration && (
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                              Elapsed: {stepDuration}
                            </div>
                          )}

                          {step.error_message && (
                            <div style={{
                              padding: '8px',
                              borderRadius: '6px',
                              backgroundColor: 'var(--status-warning-bg)',
                              color: 'var(--status-warning-text)',
                              fontSize: '11px',
                              marginBottom: '8px',
                            }}>
                              Reason: {step.error_message}
                            </div>
                          )}

                          {/* Inputs & Outputs (Sanitized) */}
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                            <div>
                              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
                                Sanitized Inputs
                              </div>
                              <pre style={{
                                margin: 0,
                                padding: '6px',
                                backgroundColor: 'var(--surface-input)',
                                borderRadius: '4px',
                                fontSize: '10px',
                                fontFamily: 'var(--font-mono)',
                                overflowX: 'auto',
                                maxHeight: '120px',
                                color: 'var(--text-secondary)',
                              }}>
                                {JSON.stringify(step.input_data, null, 2)}
                              </pre>
                            </div>

                            <div>
                              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
                                Sanitized Outputs
                              </div>
                              <pre style={{
                                margin: 0,
                                padding: '6px',
                                backgroundColor: 'var(--surface-input)',
                                borderRadius: '4px',
                                fontSize: '10px',
                                fontFamily: 'var(--font-mono)',
                                overflowX: 'auto',
                                maxHeight: '120px',
                                color: 'var(--text-secondary)',
                              }}>
                                {JSON.stringify(step.output_data, null, 2)}
                              </pre>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
