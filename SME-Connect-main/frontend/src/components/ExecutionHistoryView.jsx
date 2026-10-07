import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  Play,
  RotateCw,
  Search,
  Filter,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Layers,
  AlertCircle,
  Copy,
  Check,
  Calendar,
  X,
  Zap,
  CornerDownRight,
  ShieldAlert,
  GitCommit,
  CheckCircle2,
  HelpCircle,
} from 'lucide-react';
import { api } from '../api';

export default function ExecutionHistoryView({ initialWorkflowId = null, onNavigateWorkflows, currentOrg }) {
  const [executions, setExecutions] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [workflowFilter, setWorkflowFilter] = useState(initialWorkflowId ? String(initialWorkflowId) : 'all');
  const [searchTerm, setSearchTerm] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Detail drawer / modal
  const [selectedExecId, setSelectedExecId] = useState(null);
  const [executionDetail, setExecutionDetail] = useState(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState({});
  const [copiedPayload, setCopiedPayload] = useState(false);

  // Retry state (Module 6)
  const [retryingId, setRetryingId] = useState(null);
  const [retryNotice, setRetryNotice] = useState(null);

  // Quick run modal
  const [showRunModal, setShowRunModal] = useState(false);
  const [runWorkflowId, setRunWorkflowId] = useState('');
  const [runPayload, setRunPayload] = useState('{\n  "values": {\n    "Name": "John Doe",\n    "Email": "john@example.com",\n    "Category": "VIP"\n  }\n}');
  const [runningWorkflow, setRunningWorkflow] = useState(false);
  const [runError, setRunError] = useState(null);

  // Load workflows for filter dropdown
  useEffect(() => {
    api.fetchWorkflows(null, currentOrg?.id)
      .then((data) => setWorkflows(data || []))
      .catch((err) => console.error('Failed to load workflows:', err));
  }, [currentOrg?.id]);

  // Fetch executions
  const loadExecutions = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const params = {};
      if (currentOrg?.id) params.organization_id = currentOrg.id;
      if (workflowFilter !== 'all') params.workflow_id = workflowFilter;
      if (statusFilter !== 'all') params.status = statusFilter;
      const data = await api.fetchExecutions(params);
      setExecutions(data || []);
    } catch (err) {
      console.error('Failed to load executions:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [workflowFilter, statusFilter, currentOrg?.id]);

  useEffect(() => {
    loadExecutions();
  }, [loadExecutions]);

  // Auto-refresh timer
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadExecutions(true);
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadExecutions]);

  // Load detail when execution is selected
  const handleSelectExecution = async (id) => {
    setSelectedExecId(id);
    setDrawerLoading(true);
    setExpandedSteps({});
    try {
      const detail = await api.fetchExecutionDetail(id, currentOrg?.id);
      setExecutionDetail(detail);
      // Auto-expand all steps by default for clear visibility
      const exp = {};
      (detail.steps || []).forEach((s) => {
        exp[s.id] = true;
      });
      setExpandedSteps(exp);
    } catch (err) {
      console.error('Failed to fetch execution detail:', err);
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleCopyJson = (obj) => {
    navigator.clipboard.writeText(JSON.stringify(obj, null, 2));
    setCopiedPayload(true);
    setTimeout(() => setCopiedPayload(false), 2000);
  };

  const handleExecuteNow = async (e) => {
    e.preventDefault();
    if (!runWorkflowId) return;
    setRunningWorkflow(true);
    setRunError(null);
    try {
      let parsedPayload = {};
      try {
        parsedPayload = JSON.parse(runPayload);
      } catch (err) {
        throw new Error('Invalid JSON payload');
      }

      const result = await api.executeWorkflow(runWorkflowId, { trigger_data: parsedPayload }, currentOrg?.id);
      setShowRunModal(false);
      await loadExecutions();
      if (result && result.id) {
        handleSelectExecution(result.id);
      }
    } catch (err) {
      setRunError(err.message || 'Execution failed');
    } finally {
      setRunningWorkflow(false);
    }
  };

  const handleRetry = async (execId) => {
    if (!execId) return;
    setRetryingId(execId);
    setRetryNotice(null);
    try {
      const retried = await api.retryExecution(execId, currentOrg?.id);
      await loadExecutions(true);
      setRetryNotice({
        type: 'success',
        message: `Execution #${execId} retried successfully as Execution #${retried.id} (Attempt #${retried.attempt_number})`,
      });
      if (retried && retried.id) {
        handleSelectExecution(retried.id);
      }
    } catch (err) {
      setRetryNotice({
        type: 'error',
        message: err.message || 'Retry failed. Check permissions or workflow status.',
      });
    } finally {
      setRetryingId(null);
    }
  };


  const getFailureCategoryBadge = (category) => {
    if (!category) return null;
    const catMap = {
      rate_limit: { label: 'Rate Limit', bg: 'rgba(168, 85, 247, 0.12)', color: '#9333ea' },
      timeout: { label: 'Timeout', bg: 'rgba(249, 115, 22, 0.12)', color: '#ea580c' },
      authentication_error: { label: 'Auth Error', bg: 'rgba(239, 68, 68, 0.12)', color: '#dc2626' },
      authorization_error: { label: 'Forbidden', bg: 'rgba(239, 68, 68, 0.12)', color: '#dc2626' },
      connector_error: { label: 'Connector Error', bg: 'rgba(234, 179, 8, 0.15)', color: '#b45309' },
      mapping_error: { label: 'Mapping Error', bg: 'rgba(59, 130, 246, 0.12)', color: '#2563eb' },
      validation_error: { label: 'Validation Error', bg: 'rgba(239, 68, 68, 0.12)', color: '#dc2626' },
      condition_error: { label: 'Condition Error', bg: 'rgba(107, 114, 128, 0.12)', color: '#4b5563' },
      system_error: { label: 'System Error', bg: 'rgba(107, 114, 128, 0.12)', color: '#4b5563' },
    };
    const c = catMap[category] || { label: category, bg: 'rgba(107, 114, 128, 0.12)', color: '#4b5563' };
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: '9999px',
        backgroundColor: c.bg,
        color: c.color,
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.02em',
      }}>
        {c.label}
      </span>
    );
  };

  const getCategoryGuidance = (category) => {
    switch (category) {
      case 'rate_limit':
        return 'Rate limit reached on remote API. The engine applies bounded exponential backoff and automatically retries.';
      case 'timeout':
        return 'Remote connector timed out. Transient network anomalies are automatically retried by the platform.';
      case 'authentication_error':
        return 'Authentication failed. Please verify API keys or tokens under Connections.';
      case 'mapping_error':
        return 'Field mapping error. A referenced input field was not found in trigger or previous step outputs.';
      case 'validation_error':
        return 'Invalid payload schema. Verify your step parameters against connector requirements.';
      case 'connector_error':
        return 'Connector reported a remote service failure. Safe transient errors are scheduled for automatic retry.';
      default:
        return 'Execution stopped due to a step error. You can retry manually with preserved historical version and input context.';
    }
  };

  // Metrics calculations
  const totalExecutions = executions.length;
  const successfulCount = executions.filter((e) => e.status === 'success').length;
  const failedCount = executions.filter((e) => e.status === 'failed').length;
  const successRate = totalExecutions > 0 ? Math.round((successfulCount / totalExecutions) * 100) : 0;
  const avgDuration = totalExecutions > 0
    ? Math.round(
        executions.reduce((acc, curr) => acc + (curr.duration_ms || 0), 0) / totalExecutions
      )
    : 0;

  // Filtered list by search term
  const filteredExecutions = executions.filter((e) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    const nameMatch = (e.workflow_name || '').toLowerCase().includes(term);
    const idMatch = String(e.id).includes(term);
    const errorMatch = (e.error_message || '').toLowerCase().includes(term);
    return nameMatch || idMatch || errorMatch;
  });

  const formatDuration = (ms) => {
    if (ms === null || ms === undefined) return '—';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatDate = (isoString) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'success':
        return (
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '3px 9px',
            borderRadius: '9999px',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            color: '#10b981',
            fontSize: '12px',
            fontWeight: 500,
            border: '1px solid rgba(16, 185, 129, 0.25)',
          }}>
            <CheckCircle size={12} />
            Success
          </span>
        );
      case 'failed':
        return (
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '3px 9px',
            borderRadius: '9999px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            color: '#ef4444',
            fontSize: '12px',
            fontWeight: 500,
            border: '1px solid rgba(239, 68, 68, 0.25)',
          }}>
            <XCircle size={12} />
            Failed
          </span>
        );
      case 'running':
        return (
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '3px 9px',
            borderRadius: '9999px',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            color: '#3b82f6',
            fontSize: '12px',
            fontWeight: 500,
            border: '1px solid rgba(59, 130, 246, 0.25)',
          }}>
            <RotateCw size={12} className="spin-animation" />
            Running
          </span>
        );
      case 'skipped':
        return (
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '3px 9px',
            borderRadius: '9999px',
            backgroundColor: 'rgba(156, 163, 175, 0.1)',
            color: 'var(--text-muted)',
            fontSize: '12px',
            fontWeight: 500,
            border: '1px solid var(--border)',
          }}>
            <Clock size={12} />
            Skipped
          </span>
        );
      default:
        return (
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '3px 9px',
            borderRadius: '9999px',
            backgroundColor: 'var(--surface-2)',
            color: 'var(--text-secondary)',
            fontSize: '12px',
            border: '1px solid var(--border)',
          }}>
            {status}
          </span>
        );
    }
  };

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px 20px' }}>
      {/* Header & Quick Action */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '24px',
      }}>
        <div>
          <h1 style={{
            fontSize: '24px',
            fontWeight: 600,
            color: 'var(--text-primary)',
            letterSpacing: '-0.02em',
            margin: 0,
          }}>
            Execution Monitoring & History
          </h1>
          <p style={{
            color: 'var(--text-secondary)',
            fontSize: '14px',
            marginTop: '4px',
            marginBottom: 0,
          }}>
            Real-time multi-tenant execution trace, DAG timeline step breakdowns, and audit history.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className="btn-secondary"
            style={{
              fontSize: '13px',
              padding: '7px 12px',
              borderRadius: '8px',
              backgroundColor: autoRefresh ? 'rgba(16, 185, 129, 0.1)' : undefined,
              borderColor: autoRefresh ? 'rgba(16, 185, 129, 0.3)' : undefined,
              color: autoRefresh ? '#10b981' : undefined,
            }}
            title="Auto-refresh every 5 seconds"
          >
            <RotateCw size={14} className={autoRefresh ? 'spin-animation' : ''} />
            <span>{autoRefresh ? 'Auto-refresh On' : 'Auto-refresh'}</span>
          </button>

          <button
            onClick={() => loadExecutions()}
            disabled={refreshing}
            className="btn-secondary"
            style={{ fontSize: '13px', padding: '7px 12px', borderRadius: '8px' }}
          >
            <RotateCw size={14} className={refreshing ? 'spin-animation' : ''} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => {
              const published = workflows.filter((w) => w.status === 'published');
              if (published.length > 0) {
                setRunWorkflowId(String(published[0].id));
              }
              setShowRunModal(true);
            }}
            className="btn-primary"
            style={{ fontSize: '13px', padding: '7px 14px', borderRadius: '8px' }}
          >
            <Play size={14} />
            <span>Run Test Execution</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: '16px',
        marginBottom: '24px',
      }}>
        <div style={{
          backgroundColor: 'var(--surface-1)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '16px 20px',
        }}>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Total Executions
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {totalExecutions}
          </div>
        </div>

        <div style={{
          backgroundColor: 'var(--surface-1)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '16px 20px',
        }}>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Success Rate
          </div>
          <div style={{
            fontSize: '26px',
            fontWeight: 700,
            color: successRate >= 90 ? '#10b981' : successRate >= 70 ? 'var(--text-primary)' : '#ef4444',
          }}>
            {successRate}%
          </div>
        </div>

        <div style={{
          backgroundColor: 'var(--surface-1)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '16px 20px',
        }}>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Failed Executions
          </div>
          <div style={{
            fontSize: '26px',
            fontWeight: 700,
            color: failedCount > 0 ? '#ef4444' : 'var(--text-primary)',
          }}>
            {failedCount}
          </div>
        </div>

        <div style={{
          backgroundColor: 'var(--surface-1)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '16px 20px',
        }}>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Average Duration
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {formatDuration(avgDuration)}
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{
        backgroundColor: 'var(--surface-1)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        padding: '14px 18px',
        marginBottom: '20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', flex: 1 }}>
          {/* Search Input */}
          <div style={{ position: 'relative', minWidth: '220px', flex: '1 1 220px' }}>
            <Search size={14} style={{
              position: 'absolute',
              left: '10px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)',
            }} />
            <input
              type="text"
              placeholder="Search workflow name or ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="form-input"
              style={{ paddingLeft: '32px', fontSize: '13px', width: '100%' }}
            />
          </div>

          {/* Workflow Filter Dropdown */}
          <div style={{ minWidth: '180px' }}>
            <select
              value={workflowFilter}
              onChange={(e) => setWorkflowFilter(e.target.value)}
              className="form-input"
              style={{ fontSize: '13px', width: '100%', cursor: 'pointer' }}
            >
              <option value="all">All Workflows</option>
              {workflows.map((wf) => (
                <option key={wf.id} value={wf.id}>
                  {wf.name} ({wf.status})
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter Tabs */}
          <div style={{
            display: 'flex',
            backgroundColor: 'var(--surface-2)',
            borderRadius: '8px',
            padding: '3px',
            border: '1px solid var(--border)',
          }}>
            {[
              { id: 'all', label: 'All' },
              { id: 'success', label: 'Success' },
              { id: 'failed', label: 'Failed' },
              { id: 'running', label: 'Running' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                style={{
                  padding: '4px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  fontSize: '12px',
                  cursor: 'pointer',
                  backgroundColor: statusFilter === tab.id ? 'var(--surface-0)' : 'transparent',
                  color: statusFilter === tab.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontWeight: statusFilter === tab.id ? 600 : 400,
                  boxShadow: statusFilter === tab.id ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {workflowFilter !== 'all' && (
          <button
            onClick={() => setWorkflowFilter('all')}
            style={{
              border: 'none',
              background: 'transparent',
              color: 'var(--primary-btn-bg)',
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <X size={12} /> Clear workflow filter
          </button>
        )}
      </div>

      {/* Executions Table */}
      <div style={{
        backgroundColor: 'var(--surface-1)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        overflow: 'hidden',
      }}>
        {loading ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <RotateCw size={24} className="spin-animation" style={{ margin: '0 auto 12px' }} />
            <p style={{ fontSize: '14px', margin: 0 }}>Loading execution history...</p>
          </div>
        ) : filteredExecutions.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center' }}>
            <Activity size={32} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              No executions found
            </h3>
            <p style={{
              color: 'var(--text-secondary)',
              fontSize: '13px',
              maxWidth: '420px',
              margin: '8px auto 16px',
            }}>
              {searchTerm || statusFilter !== 'all' || workflowFilter !== 'all'
                ? 'Try adjusting your filters or search criteria.'
                : 'Publish and run a workflow to see step-by-step traces here.'}
            </p>
            <button
              onClick={() => {
                setStatusFilter('all');
                setWorkflowFilter('all');
                setSearchTerm('');
              }}
              className="btn-secondary"
              style={{ fontSize: '13px', padding: '6px 14px' }}
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{
                  backgroundColor: 'var(--surface-2)',
                  borderBottom: '1px solid var(--border)',
                  color: 'var(--text-secondary)',
                  fontSize: '12px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}>
                  <th style={{ padding: '12px 18px' }}>Status</th>
                  <th style={{ padding: '12px 18px' }}>Execution</th>
                  <th style={{ padding: '12px 18px' }}>Workflow</th>
                  <th style={{ padding: '12px 18px' }}>Started At</th>
                  <th style={{ padding: '12px 18px' }}>Duration</th>
                  <th style={{ padding: '12px 18px' }}>Steps</th>
                  <th style={{ padding: '12px 18px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredExecutions.map((exec) => (
                  <tr
                    key={exec.id}
                    onClick={() => handleSelectExecution(exec.id)}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      cursor: 'pointer',
                      transition: 'background-color 0.15s ease',
                      backgroundColor: selectedExecId === exec.id ? 'var(--surface-hover)' : 'transparent',
                    }}
                    onMouseEnter={(e) => {
                      if (selectedExecId !== exec.id) e.currentTarget.style.backgroundColor = 'var(--surface-hover)';
                    }}
                    onMouseLeave={(e) => {
                      if (selectedExecId !== exec.id) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <td style={{ padding: '14px 18px' }}>
                      {getStatusBadge(exec.status)}
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '13px' }}>
                          #{exec.id}
                        </span>
                        {exec.attempt_number > 1 && (
                          <span style={{
                            fontSize: '10px',
                            padding: '1px 5px',
                            borderRadius: '4px',
                            backgroundColor: 'rgba(99, 102, 241, 0.12)',
                            color: '#6366f1',
                            fontWeight: 600,
                          }}>
                            Attempt #{exec.attempt_number}
                          </span>
                        )}
                        {getFailureCategoryBadge(exec.failure_category)}
                      </div>
                      {exec.next_retry_at && (
                        <div style={{
                          fontSize: '11px',
                          color: '#b45309',
                          marginTop: '3px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                        }}>
                          <Clock size={11} /> Auto-retry {formatDate(exec.next_retry_at)}
                        </div>
                      )}
                      {exec.error_message && (
                        <div style={{
                          color: '#ef4444',
                          fontSize: '11px',
                          marginTop: '2px',
                          maxWidth: '220px',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}>
                          {exec.error_message}
                        </div>
                      )}
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '13px' }}>
                          {exec.workflow_name || `Workflow #${exec.workflow_id}`}
                        </span>
                        {exec.version_number && (
                          <span style={{
                            fontSize: '10px',
                            padding: '1px 5px',
                            borderRadius: '4px',
                            backgroundColor: 'var(--surface-2)',
                            color: 'var(--text-muted)',
                            border: '1px solid var(--border)',
                          }}>
                            v{exec.version_number}
                          </span>
                        )}
                      </div>
                    </td>

                    <td style={{ padding: '14px 18px', color: 'var(--text-secondary)', fontSize: '13px' }}>
                      {formatDate(exec.started_at || exec.created_at)}
                    </td>

                    <td style={{ padding: '14px 18px', color: 'var(--text-secondary)', fontSize: '13px' }}>
                      {formatDuration(exec.duration_ms)}
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                      }}>
                        <Layers size={13} style={{ color: 'var(--text-muted)' }} />
                        {exec.step_count} {exec.step_count === 1 ? 'step' : 'steps'}
                      </span>
                    </td>

                    <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                        {exec.status === 'failed' && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRetry(exec.id);
                            }}
                            disabled={retryingId === exec.id}
                            className="btn-secondary"
                            style={{
                              fontSize: '11px',
                              padding: '4px 8px',
                              borderRadius: '6px',
                              color: '#3b82f6',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                            title="Retry this execution"
                          >
                            <RotateCw size={11} className={retryingId === exec.id ? 'spin-animation' : ''} />
                            <span>{retryingId === exec.id ? 'Retrying' : 'Retry'}</span>
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectExecution(exec.id);
                          }}
                          className="btn-secondary"
                          style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '6px' }}
                        >
                          <span>View Trace</span>
                          <ArrowRight size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Execution Detail Trace Drawer / Modal */}
      {selectedExecId && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          backdropFilter: 'blur(3px)',
          display: 'flex',
          justifyContent: 'flex-end',
          zIndex: 100,
        }}>
          <div style={{
            width: '100%',
            maxWidth: '680px',
            backgroundColor: 'var(--surface-1)',
            height: '100%',
            boxShadow: '-8px 0 32px rgba(0, 0, 0, 0.15)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}>
            {/* Drawer Header */}
            <div style={{
              padding: '18px 24px',
              borderBottom: '1px solid var(--border)',
              backgroundColor: 'var(--surface-2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <h2 style={{ fontSize: '17px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Execution #{selectedExecId} Trace
                  </h2>
                  {executionDetail && getStatusBadge(executionDetail.status)}
                  {executionDetail && executionDetail.attempt_number > 1 && (
                    <span style={{
                      fontSize: '11px',
                      padding: '2px 7px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(99, 102, 241, 0.12)',
                      color: '#6366f1',
                      fontWeight: 600,
                    }}>
                      Attempt #{executionDetail.attempt_number}
                    </span>
                  )}
                </div>
                {executionDetail && (
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0' }}>
                    {executionDetail.workflow_name} {executionDetail.version_number ? `(v${executionDetail.version_number})` : ''}
                    {executionDetail.retry_of_execution_id && ` • Retried from #${executionDetail.retry_of_execution_id}`}
                  </p>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {executionDetail && executionDetail.status === 'failed' && (
                  <button
                    onClick={() => handleRetry(executionDetail.id)}
                    disabled={retryingId === executionDetail.id}
                    className="btn-primary"
                    style={{
                      fontSize: '12px',
                      padding: '6px 12px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    <RotateCw size={13} className={retryingId === executionDetail.id ? 'spin-animation' : ''} />
                    <span>{retryingId === executionDetail.id ? 'Retrying...' : 'Retry Execution'}</span>
                  </button>
                )}
                <button
                  onClick={() => setSelectedExecId(null)}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    color: 'var(--text-muted)',
                    padding: '6px',
                    borderRadius: '6px',
                  }}
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Drawer Body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
              {drawerLoading ? (
                <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-secondary)' }}>
                  <RotateCw size={24} className="spin-animation" style={{ margin: '0 auto 12px' }} />
                  <p style={{ fontSize: '14px' }}>Fetching execution trace...</p>
                </div>
              ) : executionDetail ? (
                <div>
                  {/* Retry Notification Alert */}
                  {retryNotice && (
                    <div style={{
                      backgroundColor: retryNotice.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                      border: `1px solid ${retryNotice.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                      color: retryNotice.type === 'success' ? '#10b981' : '#ef4444',
                      borderRadius: '8px',
                      padding: '10px 14px',
                      fontSize: '13px',
                      marginBottom: '16px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}>
                      <span>{retryNotice.message}</span>
                      <button
                        onClick={() => setRetryNotice(null)}
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'inherit' }}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  )}

                  {/* Error & Reliability Guidance Callout */}
                  {executionDetail.error_message && (
                    <div style={{
                      backgroundColor: 'rgba(239, 68, 68, 0.08)',
                      border: '1px solid rgba(239, 68, 68, 0.25)',
                      borderRadius: '10px',
                      padding: '14px 16px',
                      marginBottom: '20px',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                        <AlertCircle size={18} style={{ color: '#ef4444', flexShrink: 0, marginTop: '2px' }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '13px', fontWeight: 600, color: '#ef4444' }}>
                              Execution Failure
                            </span>
                            {getFailureCategoryBadge(executionDetail.failure_category)}
                          </div>
                          <div style={{
                            fontSize: '12px',
                            color: 'var(--text-secondary)',
                            marginTop: '4px',
                          }}>
                            {getCategoryGuidance(executionDetail.failure_category)}
                          </div>
                          <div style={{
                            fontSize: '12px',
                            color: 'var(--text-primary)',
                            marginTop: '8px',
                            fontFamily: 'monospace',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            backgroundColor: 'var(--surface-0)',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: '1px solid var(--border)',
                          }}>
                            {executionDetail.error_message}
                          </div>

                          {executionDetail.next_retry_at && (
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              marginTop: '10px',
                              fontSize: '12px',
                              color: '#b45309',
                              backgroundColor: 'rgba(245, 158, 11, 0.1)',
                              padding: '6px 10px',
                              borderRadius: '6px',
                              fontWeight: 500,
                            }}>
                              <Clock size={14} />
                              <span>Automatic retry scheduled for {formatDate(executionDetail.next_retry_at)}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Summary Details Grid */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '12px',
                    backgroundColor: 'var(--surface-0)',
                    border: '1px solid var(--border)',
                    borderRadius: '10px',
                    padding: '14px',
                    marginBottom: '24px',
                  }}>
                    <div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Started
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginTop: '2px' }}>
                        {formatDate(executionDetail.started_at)}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Completed
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginTop: '2px' }}>
                        {formatDate(executionDetail.completed_at)}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Total Duration
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginTop: '2px' }}>
                        {formatDuration(executionDetail.duration_ms)}
                      </div>
                    </div>
                  </div>

                  {/* Trigger Payload Section */}
                  <div style={{
                    backgroundColor: 'var(--surface-0)',
                    border: '1px solid var(--border)',
                    borderRadius: '10px',
                    marginBottom: '24px',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      padding: '12px 16px',
                      backgroundColor: 'var(--surface-2)',
                      borderBottom: '1px solid var(--border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Zap size={14} style={{ color: '#f59e0b' }} />
                        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                          Trigger Input Event
                        </span>
                      </div>
                      <button
                        onClick={() => handleCopyJson(executionDetail.trigger_data)}
                        className="btn-secondary"
                        style={{ fontSize: '11px', padding: '3px 8px', borderRadius: '4px' }}
                      >
                        {copiedPayload ? <Check size={11} /> : <Copy size={11} />}
                        <span>{copiedPayload ? 'Copied' : 'Copy'}</span>
                      </button>
                    </div>
                    <pre style={{
                      margin: 0,
                      padding: '14px 16px',
                      fontSize: '12px',
                      fontFamily: 'monospace',
                      color: 'var(--text-primary)',
                      backgroundColor: 'var(--surface-0)',
                      maxHeight: '180px',
                      overflowY: 'auto',
                    }}>
                      {JSON.stringify(executionDetail.trigger_data, null, 2)}
                    </pre>
                  </div>

                  {/* DAG Step-by-Step Timeline */}
                  <div>
                    <h3 style={{
                      fontSize: '14px',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      marginBottom: '16px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}>
                      <GitCommit size={15} />
                      Sequential Step Execution Pipeline
                    </h3>

                    {(!executionDetail.steps || executionDetail.steps.length === 0) ? (
                      <div style={{
                        padding: '24px',
                        textAlign: 'center',
                        color: 'var(--text-muted)',
                        backgroundColor: 'var(--surface-0)',
                        borderRadius: '10px',
                        border: '1px solid var(--border)',
                        fontSize: '13px',
                      }}>
                        No step execution records recorded for this run.
                      </div>
                    ) : (
                      <div style={{ position: 'relative', paddingLeft: '28px' }}>
                        {/* Vertical line connecting nodes */}
                        <div style={{
                          position: 'absolute',
                          left: '11px',
                          top: '16px',
                          bottom: '16px',
                          width: '2px',
                          backgroundColor: 'var(--border)',
                          zIndex: 0,
                        }} />

                        {executionDetail.steps.map((step, idx) => {
                          const isExpanded = !!expandedSteps[step.id];
                          const isCondition = step.step_type === 'condition' || (step.output_data && 'condition_met' in step.output_data);

                          return (
                            <div
                              key={step.id || idx}
                              style={{
                                position: 'relative',
                                marginBottom: idx === executionDetail.steps.length - 1 ? 0 : '18px',
                              }}
                            >
                              {/* Node indicator on the vertical line */}
                              <div style={{
                                position: 'absolute',
                                left: '-28px',
                                top: '14px',
                                width: '24px',
                                height: '24px',
                                borderRadius: '50%',
                                backgroundColor: 'var(--surface-1)',
                                border: `2px solid ${
                                  step.status === 'success'
                                    ? '#10b981'
                                    : step.status === 'failed'
                                    ? '#ef4444'
                                    : step.status === 'skipped'
                                    ? 'var(--border)'
                                    : '#3b82f6'
                                }`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                zIndex: 1,
                              }}>
                                {step.status === 'success' ? (
                                  <Check size={12} style={{ color: '#10b981' }} />
                                ) : step.status === 'failed' ? (
                                  <X size={12} style={{ color: '#ef4444' }} />
                                ) : step.status === 'skipped' ? (
                                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>—</span>
                                ) : (
                                  <RotateCw size={11} className="spin-animation" style={{ color: '#3b82f6' }} />
                                )}
                              </div>

                              {/* Step Card */}
                              <div style={{
                                backgroundColor: 'var(--surface-0)',
                                border: '1px solid var(--border)',
                                borderRadius: '10px',
                                overflow: 'hidden',
                                transition: 'border-color 0.15s ease',
                              }}>
                                {/* Card Title Bar */}
                                <div
                                  onClick={() => setExpandedSteps((prev) => ({ ...prev, [step.id]: !prev[step.id] }))}
                                  style={{
                                    padding: '12px 16px',
                                    backgroundColor: 'var(--surface-2)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    cursor: 'pointer',
                                    userSelect: 'none',
                                  }}
                                >
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    <span style={{
                                      fontSize: '11px',
                                      fontWeight: 600,
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      backgroundColor: isCondition ? 'rgba(245, 158, 11, 0.1)' : 'rgba(59, 130, 246, 0.1)',
                                      color: isCondition ? '#f59e0b' : '#3b82f6',
                                    }}>
                                      {isCondition ? 'CONDITION' : 'ACTION'}
                                    </span>

                                    <div>
                                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                                        {step.step_id}
                                        {step.connector && (
                                          <span style={{ fontWeight: 400, color: 'var(--text-secondary)', marginLeft: '6px' }}>
                                            ({step.connector}{step.action ? ` → ${step.action}` : ''})
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  </div>

                                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    {step.duration_ms !== null && (
                                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                                        {formatDuration(step.duration_ms)}
                                      </span>
                                    )}
                                    {getStatusBadge(step.status)}
                                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                  </div>
                                </div>

                                {/* Step Details Body */}
                                {isExpanded && (
                                  <div style={{ padding: '16px', borderTop: '1px solid var(--border)' }}>
                                    {/* Condition evaluation callout */}
                                    {isCondition && step.output_data && 'condition_met' in step.output_data && (
                                      <div style={{
                                        backgroundColor: step.output_data.condition_met
                                          ? 'rgba(16, 185, 129, 0.08)'
                                          : 'rgba(245, 158, 11, 0.08)',
                                        border: `1px solid ${
                                          step.output_data.condition_met
                                            ? 'rgba(16, 185, 129, 0.25)'
                                            : 'rgba(245, 158, 11, 0.25)'
                                        }`,
                                        borderRadius: '8px',
                                        padding: '10px 14px',
                                        marginBottom: '12px',
                                        fontSize: '13px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                      }}>
                                        <span>
                                          Evaluated rule: <strong>{step.input_data?.field || 'Field'} {step.input_data?.operator || '=='} {JSON.stringify(step.input_data?.value)}</strong>
                                        </span>
                                        <span style={{
                                          fontWeight: 600,
                                          color: step.output_data.condition_met ? '#10b981' : '#f59e0b',
                                        }}>
                                          Outcome: {step.output_data.condition_met ? 'Passed (True)' : 'Skipped subsequent (False)'}
                                        </span>
                                      </div>
                                    )}

                                    {/* Step Error Callout */}
                                    {step.error_message && (
                                      <div style={{
                                        backgroundColor: 'rgba(239, 68, 68, 0.08)',
                                        border: '1px solid rgba(239, 68, 68, 0.25)',
                                        borderRadius: '8px',
                                        padding: '10px 14px',
                                        marginBottom: '12px',
                                        color: '#ef4444',
                                        fontSize: '13px',
                                        fontFamily: 'monospace',
                                      }}>
                                        {step.error_message}
                                      </div>
                                    )}

                                    {/* Input & Output payloads */}
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                                      <div>
                                        <div style={{
                                          fontSize: '11px',
                                          fontWeight: 600,
                                          color: 'var(--text-muted)',
                                          marginBottom: '6px',
                                          textTransform: 'uppercase',
                                        }}>
                                          Input Payload
                                        </div>
                                        <pre style={{
                                          margin: 0,
                                          padding: '10px 12px',
                                          borderRadius: '6px',
                                          backgroundColor: 'var(--surface-2)',
                                          fontSize: '11px',
                                          fontFamily: 'monospace',
                                          color: 'var(--text-primary)',
                                          maxHeight: '140px',
                                          overflowY: 'auto',
                                          border: '1px solid var(--border)',
                                        }}>
                                          {JSON.stringify(step.input_data || {}, null, 2)}
                                        </pre>
                                      </div>

                                      <div>
                                        <div style={{
                                          fontSize: '11px',
                                          fontWeight: 600,
                                          color: 'var(--text-muted)',
                                          marginBottom: '6px',
                                          textTransform: 'uppercase',
                                        }}>
                                          Output Payload
                                        </div>
                                        <pre style={{
                                          margin: 0,
                                          padding: '10px 12px',
                                          borderRadius: '6px',
                                          backgroundColor: 'var(--surface-2)',
                                          fontSize: '11px',
                                          fontFamily: 'monospace',
                                          color: 'var(--text-primary)',
                                          maxHeight: '140px',
                                          overflowY: 'auto',
                                          border: '1px solid var(--border)',
                                        }}>
                                          {JSON.stringify(step.output_data || {}, null, 2)}
                                        </pre>
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Quick Run Test Execution Modal */}
      {showRunModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          backdropFilter: 'blur(3px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 110,
          padding: '16px',
        }}>
          <div style={{
            width: '100%',
            maxWidth: '520px',
            backgroundColor: 'var(--surface-1)',
            borderRadius: '14px',
            border: '1px solid var(--border)',
            boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '18px 24px',
              backgroundColor: 'var(--surface-2)',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Play size={16} style={{ color: 'var(--primary-btn-bg)' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                  Run Test Execution
                </h3>
              </div>
              <button
                onClick={() => setShowRunModal(false)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleExecuteNow} style={{ padding: '24px' }}>
              {runError && (
                <div style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  marginBottom: '16px',
                  color: '#ef4444',
                  fontSize: '13px',
                }}>
                  {runError}
                </div>
              )}

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px' }}>
                  Target Workflow
                </label>
                <select
                  value={runWorkflowId}
                  onChange={(e) => setRunWorkflowId(e.target.value)}
                  className="form-input"
                  style={{ width: '100%', fontSize: '13px' }}
                  required
                >
                  <option value="">Select a published workflow...</option>
                  {workflows
                    .filter((w) => w.status === 'published')
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name} (v{w.version_number})
                      </option>
                    ))}
                </select>
                {workflows.filter((w) => w.status === 'published').length === 0 && (
                  <p style={{ fontSize: '12px', color: '#ef4444', marginTop: '4px' }}>
                    No published workflows available. Please publish a workflow first.
                  </p>
                )}
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px' }}>
                  Trigger JSON Payload
                </label>
                <textarea
                  value={runPayload}
                  onChange={(e) => setRunPayload(e.target.value)}
                  className="form-input"
                  rows={6}
                  style={{ width: '100%', fontFamily: 'monospace', fontSize: '12px' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowRunModal(false)}
                  className="btn-secondary"
                  style={{ fontSize: '13px', padding: '8px 16px' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={runningWorkflow || !runWorkflowId}
                  className="btn-primary"
                  style={{ fontSize: '13px', padding: '8px 18px' }}
                >
                  {runningWorkflow ? (
                    <>
                      <RotateCw size={13} className="spin-animation" />
                      <span>Executing...</span>
                    </>
                  ) : (
                    <>
                      <Play size={13} />
                      <span>Execute Workflow</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
