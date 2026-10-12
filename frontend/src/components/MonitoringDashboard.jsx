import React, { useState, useEffect, useCallback } from 'react';
import {
  CheckCircle,
  RefreshCw,
  TrendingUp,
  AlertCircle,
  ShieldAlert,
  Layers,
  Search,
  RotateCcw,
  Zap
} from 'lucide-react';
import { api } from '../api';


function formatRelativeTime(dateString) {
  if (!dateString) return 'Never run';
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

function getHealthBadge(status) {
  switch (status) {
    case 'healthy':
      return { label: 'Healthy', color: 'var(--status-success-text)', bg: 'var(--status-success-bg)', border: 'var(--border)' };
    case 'needs_attention':
      return { label: 'Needs Attention', color: 'var(--status-warning-text)', bg: 'var(--status-warning-bg)', border: 'var(--status-warning-text)' };
    case 'paused':
      return { label: 'Paused', color: 'var(--text-secondary)', bg: 'var(--surface-hover)', border: 'var(--border)' };
    case 'never_run':
      return { label: 'Ready to Run', color: 'var(--text-muted)', bg: 'var(--surface-2)', border: 'var(--border)' };
    case 'retrying':
      return { label: 'Retrying', color: 'var(--status-warning-text)', bg: 'var(--status-warning-bg)', border: 'var(--status-warning-text)' };
    default:
      return { label: status || 'Unknown', color: 'var(--text-secondary)', bg: 'var(--surface-2)', border: 'var(--border)' };
  }
}

export default function MonitoringDashboard({
  currentOrg,
  onNavigateWorkflows,
  onNavigateExecutions,
  onOpenNotifications,
}) {
  const [periodDays, setPeriodDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [usageData, setUsageData] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [activeTab, setActiveTab] = useState('workflows'); // 'workflows' | 'usage'
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [triggeringId, setTriggeringId] = useState(null);
  const [retryingId, setRetryingId] = useState(null);
  const [actionMessage, setActionMessage] = useState(null);

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      const [dash, usage, notifs] = await Promise.all([
        api.fetchDashboardOverview(periodDays, currentOrg?.id).catch(() => null),
        api.fetchUsageStats(null, null, currentOrg?.id).catch(() => null),
        api.fetchNotifications(false, 5, currentOrg?.id).catch(() => ({ items: [] })),
      ]);
      setDashboardData(dash);
      setUsageData(usage);
      setNotifications(notifs?.items || []);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [periodDays, currentOrg?.id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleMarkRead = async (notifId) => {
    try {
      await api.markNotificationRead(notifId, currentOrg?.id);
      setNotifications((prev) => prev.filter((n) => n.id !== notifId));
      setActionMessage({ text: 'Alert marked as resolved', type: 'success' });
      setTimeout(() => setActionMessage(null), 3000);
    } catch {
      // Ignore
    }
  };

  const handleManualRun = async (wfId) => {
    setTriggeringId(wfId);
    try {
      await api.triggerWorkflowRun(wfId, null, currentOrg?.id);
      setActionMessage({ text: 'Workflow run triggered successfully', type: 'success' });
      setTimeout(() => setActionMessage(null), 4000);
      await loadData(true);
    } catch (err) {
      setActionMessage({ text: err.message || 'Trigger failed', type: 'error' });
      setTimeout(() => setActionMessage(null), 4000);
    } finally {
      setTriggeringId(null);
    }
  };

  const handleRetryExecution = async (executionId) => {
    if (!executionId) return;
    setRetryingId(executionId);
    try {
      await api.retryExecution(executionId, currentOrg?.id);
      setActionMessage({ text: 'Execution retry initiated', type: 'success' });
      setTimeout(() => setActionMessage(null), 4000);
      await loadData(true);
    } catch (err) {
      setActionMessage({ text: err.message || 'Retry failed', type: 'error' });
      setTimeout(() => setActionMessage(null), 4000);
    } finally {
      setRetryingId(null);
    }
  };

  if (loading) {
    return (
      <div style={{
        padding: '60px 20px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        color: 'var(--text-secondary)',
      }}>
        <div className="spinner" style={{ width: '26px', height: '26px' }} />
        <p style={{ fontSize: '14px' }}>Loading monitoring dashboard...</p>
      </div>
    );
  }

  const summary = dashboardData?.workflow_summary || { total: 0, published: 0, paused: 0, draft: 0, needs_attention: 0 };
  const metrics = dashboardData?.execution_metrics || { total_runs: 0, successful_runs: 0, failed_runs: 0, success_rate: 100, avg_duration_seconds: 0 };
  const timeline = dashboardData?.timeline || [];
  const workflowsList = dashboardData?.workflows || [];

  // Filter workflows
  const filteredWorkflows = workflowsList.filter((wf) => {
    const matchesSearch = wf.name.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch) return false;
    if (statusFilter === 'all') return true;
    if (statusFilter === 'needs_attention') return wf.health_status === 'needs_attention';
    if (statusFilter === 'published') return wf.status === 'published';
    if (statusFilter === 'paused') return wf.status === 'paused';
    if (statusFilter === 'draft') return wf.status === 'draft';
    return true;
  });

  // Calculate timeline max for bar scale
  const maxDailyRuns = Math.max(...timeline.map((t) => t.total), 1);

  return (
    <div className="monitoring-container" style={{ padding: '0 4px', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Action banner feedback */}
      {actionMessage && (
        <div style={{
          backgroundColor: actionMessage.type === 'error' ? 'var(--status-warning-bg)' : 'var(--status-success-bg)',
          color: actionMessage.type === 'error' ? 'var(--status-warning-text)' : 'var(--status-success-text)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          padding: '10px 16px',
          marginBottom: '20px',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          {actionMessage.type === 'error' ? <AlertCircle size={15} /> : <CheckCircle size={15} />}
          <span>{actionMessage.text}</span>
        </div>
      )}

      {/* Top Header & Period Selector */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '24px',
      }}>
        <div>
          <div className="kicker-label" style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>
            OPERATIONAL TRUST & OBSERVABILITY
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Monitoring Dashboard
          </h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Live status, throughput metrics, and reliability health across your automations.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Horizon Selector */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            padding: '2px',
          }}>
            {[
              { days: 7, label: '7 Days' },
              { days: 14, label: '14 Days' },
              { days: 30, label: '30 Days' },
            ].map((p) => (
              <button
                key={p.days}
                onClick={() => setPeriodDays(p.days)}
                style={{
                  padding: '5px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: periodDays === p.days ? 'var(--surface-hover)' : 'transparent',
                  color: periodDays === p.days ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontSize: '12px',
                  fontWeight: periodDays === p.days ? 500 : 400,
                  cursor: 'pointer',
                  transition: 'background-color 0.15s ease',
                }}
              >
                {p.label}
              </button>
            ))}
          </div>

          <button
            onClick={() => loadData(false)}
            className="btn-secondary"
            title="Refresh dashboard"
            style={{ padding: '7px 12px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={13} className={refreshing ? 'spinner' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid (4 Cards) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '16px',
        marginBottom: '28px',
      }}>
        {/* Card 1: Total Automations */}
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '18px 20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }} className="kicker-label">
              AUTOMATIONS
            </span>
            <Layers size={16} style={{ color: 'var(--text-muted)' }} />
          </div>
          <div style={{ fontSize: '28px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
            {summary.total}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', fontSize: '12px' }}>
            <span style={{
              padding: '2px 7px',
              borderRadius: '9999px',
              backgroundColor: 'var(--status-success-bg)',
              color: 'var(--status-success-text)',
              fontSize: '11px',
              fontWeight: 500,
            }}>
              {summary.published} Active
            </span>
            {summary.paused > 0 && (
              <span style={{
                padding: '2px 7px',
                borderRadius: '9999px',
                backgroundColor: 'var(--surface-hover)',
                color: 'var(--text-secondary)',
                fontSize: '11px',
              }}>
                {summary.paused} Paused
              </span>
            )}
            {summary.needs_attention > 0 && (
              <span style={{
                padding: '2px 7px',
                borderRadius: '9999px',
                backgroundColor: 'var(--status-warning-bg)',
                color: 'var(--status-warning-text)',
                fontSize: '11px',
                fontWeight: 500,
              }}>
                {summary.needs_attention} Attention
              </span>
            )}
          </div>
        </div>

        {/* Card 2: Overall Success Rate */}
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '18px 20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }} className="kicker-label">
              RELIABILITY RATE ({periodDays}D)
            </span>
            <TrendingUp size={16} style={{ color: metrics.success_rate >= 90 ? 'var(--status-success-text)' : 'var(--status-warning-text)' }} />
          </div>
          <div style={{ fontSize: '28px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
            {metrics.total_runs === 0 ? '100%' : `${metrics.success_rate}%`}
          </div>
          {/* Visual Progress Bar */}
          <div style={{
            width: '100%',
            height: '6px',
            backgroundColor: 'var(--surface-hover)',
            borderRadius: '9999px',
            overflow: 'hidden',
            marginBottom: '8px',
          }}>
            <div style={{
              width: `${metrics.success_rate}%`,
              height: '100%',
              backgroundColor: metrics.success_rate >= 90 ? '#10B981' : '#F59E0B',
              borderRadius: '9999px',
              transition: 'width 0.4s ease',
            }} />
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            {metrics.successful_runs} of {metrics.total_runs} runs succeeded
          </div>
        </div>

        {/* Card 3: Tasks Run This Month (Module 7 requirement) */}
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '18px 20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }} className="kicker-label">
              TASKS THIS MONTH
            </span>
            <Zap size={16} style={{ color: 'var(--text-muted)' }} />
          </div>
          <div style={{ fontSize: '28px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
            {usageData?.total_tasks_this_month || 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            {usageData?.period_label || 'Current month'}: {usageData?.total_successful_tasks || 0} successful, {usageData?.total_failed_tasks || 0} failed
          </div>
        </div>

        {/* Card 4: Active Alerts & Notifications */}
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '18px 20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }} className="kicker-label">
              ACTIVE ALERTS
            </span>
            <ShieldAlert size={16} style={{ color: notifications.length > 0 ? 'var(--status-warning-text)' : 'var(--text-muted)' }} />
          </div>
          <div style={{ fontSize: '28px', fontWeight: 600, color: notifications.length > 0 ? 'var(--status-warning-text)' : 'var(--text-primary)', marginBottom: '8px' }}>
            {notifications.length}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>
              {notifications.length > 0 ? 'Repeated failures requiring action' : 'Zero active alerts'}
            </span>
            {notifications.length > 0 && onOpenNotifications && (
              <button
                onClick={onOpenNotifications}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--primary-btn-bg)',
                  fontSize: '12px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                Review alerts →
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Repeated Failures Diagnostic Banner (if any exist) */}
      {notifications.length > 0 && (
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--status-warning-text)',
          borderRadius: '10px',
          padding: '16px 20px',
          marginBottom: '28px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <ShieldAlert size={18} style={{ color: 'var(--status-warning-text)' }} />
              <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {notifications.length} Automation{notifications.length > 1 ? 's' : ''} Encountered Repeated Failures
              </span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Threshold met: 2 or more consecutive failures detected
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {notifications.slice(0, 3).map((notif) => (
              <div
                key={notif.id}
                style={{
                  backgroundColor: 'var(--surface-0)',
                  border: '1px solid var(--border)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: '16px',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ flex: 1, minWidth: '260px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{
                      fontSize: '11px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: notif.severity === 'critical' ? 'var(--status-warning-bg)' : 'var(--surface-2)',
                      color: notif.severity === 'critical' ? 'var(--status-warning-text)' : 'var(--text-primary)',
                      fontWeight: 600,
                    }}>
                      {notif.severity.toUpperCase()}
                    </span>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {notif.title}
                    </span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {formatRelativeTime(notif.created_at)}
                    </span>
                  </div>
                  <pre style={{
                    fontFamily: 'inherit',
                    fontSize: '12px',
                    color: 'var(--text-secondary)',
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    lineHeight: '1.4',
                  }}>
                    {notif.message}
                  </pre>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {notif.execution_id && (
                    <button
                      onClick={() => handleRetryExecution(notif.execution_id)}
                      disabled={retryingId === notif.execution_id}
                      className="btn-secondary"
                      style={{ padding: '5px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      <RotateCcw size={12} className={retryingId === notif.execution_id ? 'spinner' : ''} />
                      <span>Retry</span>
                    </button>
                  )}
                  <button
                    onClick={() => handleMarkRead(notif.id)}
                    className="btn-secondary"
                    style={{ padding: '5px 12px', fontSize: '12px' }}
                  >
                    Resolve
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Execution Trends & Run History Timeline */}
      <div style={{
        backgroundColor: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        padding: '20px 24px',
        marginBottom: '28px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
          <div>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }} className="kicker-label">
              PERFORMANCE TIMELINE
            </span>
            <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: '2px 0 0 0' }}>
              Daily Execution Volume ({periodDays} Days)
            </h2>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#10B981' }} />
              <span>Success ({metrics.successful_runs})</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#EF4444' }} />
              <span>Failed ({metrics.failed_runs})</span>
            </div>
            <div style={{ color: 'var(--text-muted)' }}>
              Avg Duration: {metrics.avg_duration_seconds}s
            </div>
          </div>
        </div>

        {/* Bar Timeline Visual */}
        {timeline.length === 0 || metrics.total_runs === 0 ? (
          <div style={{
            padding: '40px 20px',
            textAlign: 'center',
            color: 'var(--text-secondary)',
            fontSize: '13px',
            backgroundColor: 'var(--surface-0)',
            borderRadius: '8px',
            border: '1px dashed var(--border)',
          }}>
            No execution data recorded during the last {periodDays} days. Once automations are triggered, daily throughput will appear here.
          </div>
        ) : (
          <div style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: '4px',
            height: '140px',
            paddingTop: '20px',
            paddingBottom: '24px',
            borderBottom: '1px solid var(--border)',
            overflowX: 'auto',
          }}>
            {timeline.map((day) => {
              const heightPct = Math.max(Math.round((day.total / maxDailyRuns) * 100), day.total > 0 ? 12 : 4);
              const successPct = day.total > 0 ? Math.round((day.success / day.total) * 100) : 100;
              const dateObj = new Date(day.date + 'T00:00:00Z');
              const dayLabel = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

              return (
                <div
                  key={day.date}
                  style={{
                    flex: 1,
                    minWidth: '22px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    height: '100%',
                    justifyContent: 'flex-end',
                    position: 'relative',
                  }}
                  title={`${day.date}: ${day.total} runs (${day.success} success, ${day.failed} failed)`}
                >
                  {/* Bar */}
                  <div
                    style={{
                      width: '100%',
                      maxWidth: '16px',
                      height: `${heightPct}%`,
                      borderRadius: '4px 4px 1px 1px',
                      backgroundColor: day.total === 0 ? 'var(--surface-hover)' : day.failed === 0 ? '#10B981' : '#F59E0B',
                      opacity: day.total === 0 ? 0.4 : 0.9,
                      transition: 'height 0.3s ease',
                      cursor: 'pointer',
                    }}
                  />
                  {/* Label (sampled to prevent crowding) */}
                  <span style={{
                    fontSize: '10px',
                    color: 'var(--text-muted)',
                    position: 'absolute',
                    bottom: '-20px',
                    whiteSpace: 'nowrap',
                  }}>
                    {dayLabel.split(' ')[1]}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Main Tabbed Sections: Workflows Status Overview vs Monthly Usage Breakdown */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--border)',
        marginBottom: '20px',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', gap: '4px' }}>
          <button
            onClick={() => setActiveTab('workflows')}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderBottom: activeTab === 'workflows' ? '2px solid var(--primary-btn-bg)' : '2px solid transparent',
              backgroundColor: 'transparent',
              color: activeTab === 'workflows' ? 'var(--text-primary)' : 'var(--text-secondary)',
              fontSize: '14px',
              fontWeight: activeTab === 'workflows' ? 600 : 400,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>Automations Status & Health</span>
            <span style={{
              fontSize: '11px',
              padding: '1px 6px',
              borderRadius: '9999px',
              backgroundColor: 'var(--surface-hover)',
              color: 'var(--text-muted)',
            }}>
              {workflowsList.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('usage')}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderBottom: activeTab === 'usage' ? '2px solid var(--primary-btn-bg)' : '2px solid transparent',
              backgroundColor: 'transparent',
              color: activeTab === 'usage' ? 'var(--text-primary)' : 'var(--text-secondary)',
              fontSize: '14px',
              fontWeight: activeTab === 'usage' ? 600 : 400,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>Monthly Usage Breakdown</span>
            <span style={{
              fontSize: '11px',
              padding: '1px 6px',
              borderRadius: '9999px',
              backgroundColor: 'var(--surface-hover)',
              color: 'var(--text-muted)',
            }}>
              {usageData?.total_tasks_this_month || 0} tasks
            </span>
          </button>
        </div>

        {activeTab === 'workflows' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingBottom: '8px' }}>
            {/* Search */}
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search automations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  padding: '6px 10px 6px 30px',
                  fontSize: '13px',
                  borderRadius: '6px',
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--surface-2)',
                  color: 'var(--text-primary)',
                  width: '180px',
                }}
              />
            </div>

            {/* Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                fontSize: '13px',
                borderRadius: '6px',
                border: '1px solid var(--border)',
                backgroundColor: 'var(--surface-2)',
                color: 'var(--text-primary)',
              }}
            >
              <option value="all">All statuses</option>
              <option value="published">Published</option>
              <option value="needs_attention">Needs attention</option>
              <option value="paused">Paused</option>
              <option value="draft">Draft</option>
            </select>
          </div>
        )}
      </div>

      {/* Tab Content 1: Workflow Status & Health Overview Table */}
      {activeTab === 'workflows' && (
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          overflow: 'hidden',
          marginBottom: '40px',
        }}>
          {filteredWorkflows.length === 0 ? (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <p style={{ fontSize: '14px', marginBottom: '10px' }}>No workflows matched the current filter.</p>
              {workflowsList.length === 0 && onNavigateWorkflows && (
                <button
                  className="btn-primary"
                  onClick={onNavigateWorkflows}
                  style={{ fontSize: '13px' }}
                >
                  Create your first workflow
                </button>
              )}
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--surface-0)', borderBottom: '1px solid var(--border)' }}>
                    <th style={{ padding: '12px 18px', fontWeight: 500, color: 'var(--text-secondary)' }}>Workflow</th>
                    <th style={{ padding: '12px 18px', fontWeight: 500, color: 'var(--text-secondary)' }}>Status</th>
                    <th style={{ padding: '12px 18px', fontWeight: 500, color: 'var(--text-secondary)' }}>Health State</th>
                    <th style={{ padding: '12px 18px', fontWeight: 500, color: 'var(--text-secondary)' }}>Success Rate</th>
                    <th style={{ padding: '12px 18px', fontWeight: 500, color: 'var(--text-secondary)' }}>Tasks (MTD)</th>
                    <th style={{ padding: '12px 18px', fontWeight: 500, color: 'var(--text-secondary)' }}>Last Execution</th>
                    <th style={{ padding: '12px 18px', fontWeight: 500, color: 'var(--text-secondary)', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredWorkflows.map((wf) => {
                    const healthBadge = getHealthBadge(wf.health_status);
                    return (
                      <tr
                        key={wf.id}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          transition: 'background-color 0.15s ease',
                        }}
                      >
                        {/* Name */}
                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ fontWeight: 500, color: 'var(--text-primary)', marginBottom: '2px' }}>
                            {wf.name}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                            ID #{wf.id} • Created {new Date(wf.created_at).toLocaleDateString()}
                          </div>
                        </td>

                        {/* Status */}
                        <td style={{ padding: '14px 18px' }}>
                          <span style={{
                            padding: '3px 8px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 500,
                            backgroundColor: wf.status === 'published' ? 'var(--status-success-bg)' : 'var(--surface-hover)',
                            color: wf.status === 'published' ? 'var(--status-success-text)' : 'var(--text-secondary)',
                          }}>
                            {wf.status.toUpperCase()}
                          </span>
                        </td>

                        {/* Health */}
                        <td style={{ padding: '14px 18px' }}>
                          <span style={{
                            padding: '3px 8px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 500,
                            backgroundColor: healthBadge.bg,
                            color: healthBadge.color,
                            border: `1px solid ${healthBadge.border}`,
                          }}>
                            {healthBadge.label}
                          </span>
                        </td>

                        {/* Success Rate */}
                        <td style={{ padding: '14px 18px' }}>
                          {wf.success_rate !== null ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontWeight: 500, color: wf.success_rate >= 90 ? 'var(--status-success-text)' : 'var(--status-warning-text)' }}>
                                {wf.success_rate}%
                              </span>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                ({wf.success_runs}/{wf.total_runs})
                              </span>
                            </div>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>—</span>
                          )}
                        </td>

                        {/* Tasks this month */}
                        <td style={{ padding: '14px 18px', fontWeight: 500, color: 'var(--text-primary)' }}>
                          {wf.tasks_this_month}
                        </td>

                        {/* Last Run */}
                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ color: 'var(--text-primary)' }}>
                            {formatRelativeTime(wf.last_run_at)}
                          </div>
                          {wf.last_run_status && (
                            <span style={{
                              fontSize: '11px',
                              color: wf.last_run_status === 'success' ? 'var(--status-success-text)' : 'var(--status-warning-text)',
                            }}>
                              {wf.last_run_status}
                            </span>
                          )}
                        </td>

                        {/* Actions */}
                        <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                            {wf.status === 'published' && (
                              <button
                                onClick={() => handleManualRun(wf.id)}
                                disabled={triggeringId === wf.id}
                                className="btn-secondary"
                                title="Run now with sample trigger data"
                                style={{ padding: '4px 10px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}
                              >
                                <Zap size={11} className={triggeringId === wf.id ? 'spinner' : ''} />
                                <span>Run</span>
                              </button>
                            )}

                            {onNavigateExecutions && (
                              <button
                                onClick={onNavigateExecutions}
                                className="btn-secondary"
                                title="View full execution history"
                                style={{ padding: '4px 8px', fontSize: '12px' }}
                              >
                                History
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab Content 2: Monthly Task Usage Breakdown (Module 7 requirement) */}
      {activeTab === 'usage' && (
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '24px',
          marginBottom: '40px',
        }}>
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Tasks Executed in {usageData?.period_label || 'Current Month'}
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Detailed throughput breakdown per workflow to track usage and quota budget.
            </p>
          </div>

          {!usageData?.workflow_usage || usageData.workflow_usage.length === 0 ? (
            <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
              No workflow tasks have been executed this month.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {usageData.workflow_usage.map((item) => (
                <div
                  key={item.workflow_id}
                  style={{
                    backgroundColor: 'var(--surface-0)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '14px 18px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '14px' }}>
                        {item.workflow_name}
                      </span>
                      <span style={{
                        fontSize: '11px',
                        padding: '1px 6px',
                        borderRadius: '9999px',
                        backgroundColor: item.status === 'published' ? 'var(--status-success-bg)' : 'var(--surface-hover)',
                        color: item.status === 'published' ? 'var(--status-success-text)' : 'var(--text-secondary)',
                      }}>
                        {item.status}
                      </span>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {item.tasks_this_month} tasks
                      </span>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '8px' }}>
                        ({item.percentage_of_total}% of month)
                      </span>
                    </div>
                  </div>

                  {/* Share progress bar */}
                  <div style={{
                    width: '100%',
                    height: '6px',
                    backgroundColor: 'var(--surface-hover)',
                    borderRadius: '9999px',
                    overflow: 'hidden',
                    marginBottom: '8px',
                  }}>
                    <div style={{
                      width: `${item.percentage_of_total}%`,
                      height: '100%',
                      backgroundColor: 'var(--primary-btn-bg)',
                      borderRadius: '9999px',
                      transition: 'width 0.4s ease',
                    }} />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    <span>
                      {item.successful_tasks_this_month} successful • {item.failed_tasks_this_month} failed
                    </span>
                    <span>
                      Last run: {formatRelativeTime(item.last_executed_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
