import React, { useState } from 'react';
import {
  Layers,
  RefreshCw,
  Building,
  Plus,
  ChevronDown,
  Sun,
  Moon,
  LogOut,
  User,
  CheckCircle,
  Bell,
  Trash2
} from 'lucide-react';


export default function Header({
  activeTab,
  setActiveTab,
  connectionsCount,
  membersCount,
  currentOrg,
  organizations,
  onSelectOrg,
  onCreateOrg,
  currentUser,
  onLogout,
  theme,
  onToggleTheme,
  onRefresh,
  isRefreshing,
  unreadNotificationsCount = 0,
  notifications = [],
  onMarkNotificationRead,
  onMarkAllNotificationsRead,
  onDeleteNotification
}) {
  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [notifDropdownOpen, setNotifDropdownOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');
  const [creatingOrg, setCreatingOrg] = useState(false);


  const handleCreateOrg = async (e) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    await onCreateOrg(newOrgName.trim());
    setNewOrgName('');
    setCreatingOrg(false);
    setOrgDropdownOpen(false);
  };

  return (
    <header style={{
      backgroundColor: 'var(--surface-2)',
      borderBottom: '1px solid var(--border)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      transition: 'background-color 0.2s ease, border-color 0.2s ease',
    }}>
      <div style={{
        width: '100%',
        padding: '14px 36px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        flexWrap: 'wrap',
      }}>

        {/* Left: Brand and Workspace dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={19} style={{ color: 'var(--primary-btn-bg)' }} />
            <span style={{ fontSize: '16px', fontWeight: 500, color: 'var(--text-primary)' }}>
              SME Connect
            </span>
          </div>

          <div style={{ width: '1px', height: '18px', backgroundColor: 'var(--border)' }} />

          {/* Workspace dropdown */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setOrgDropdownOpen(!orgDropdownOpen)}
              className="btn-secondary"
              style={{
                fontSize: '13px',
                padding: '5px 12px',
                borderRadius: '8px',
                gap: '8px',
              }}
            >
              <Building size={14} style={{ color: 'var(--text-secondary)' }} />
              <span>{currentOrg?.name || 'Select workspace'}</span>
              <span style={{
                fontSize: '11px',
                padding: '1px 6px',
                borderRadius: '9999px',
                backgroundColor: 'var(--status-neutral-bg)',
                color: 'var(--status-neutral-text)',
              }}>
                {currentOrg?.role || 'Member'}
              </span>
              <ChevronDown size={13} style={{ color: 'var(--text-muted)' }} />
            </button>

            {orgDropdownOpen && (
              <div style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                left: 0,
                width: '250px',
                backgroundColor: 'var(--surface-2)',
                border: '1px solid var(--border)',
                borderRadius: '10px',
                padding: '8px',
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06)',
                zIndex: 60,
              }}>
                <div style={{
                  padding: '6px 8px',
                  fontSize: '11px',
                  color: 'var(--text-muted)',
                  letterSpacing: '0.04em',
                }} className="kicker-label">
                  WORKSPACES
                </div>

                {(organizations || []).map((org) => (
                  <button
                    key={org.id}
                    onClick={() => {
                      onSelectOrg(org.id);
                      setOrgDropdownOpen(false);
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      border: 'none',
                      backgroundColor: org.id === currentOrg?.id ? 'var(--surface-hover)' : 'transparent',
                      color: 'var(--text-primary)',
                      fontSize: '13px',
                      fontWeight: 400,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      transition: 'background-color 0.15s ease',
                    }}
                  >
                    <span>{org.name}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{org.role}</span>
                  </button>
                ))}

                <div style={{ height: '1px', backgroundColor: 'var(--border)', margin: '6px 0' }} />

                {creatingOrg ? (
                  <form onSubmit={handleCreateOrg} style={{ padding: '4px' }}>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="New workspace name"
                      value={newOrgName}
                      onChange={(e) => setNewOrgName(e.target.value)}
                      autoFocus
                      style={{ marginBottom: '8px', fontSize: '13px' }}
                    />
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button type="submit" className="btn-primary" style={{ padding: '4px 10px', fontSize: '12px', flex: 1 }}>
                        Create
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '12px' }}
                        onClick={() => setCreatingOrg(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    onClick={() => setCreatingOrg(true)}
                    style={{
                      width: '100%',
                      padding: '7px 10px',
                      borderRadius: '6px',
                      border: 'none',
                      backgroundColor: 'transparent',
                      color: 'var(--text-secondary)',
                      fontSize: '13px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <Plus size={14} />
                    <span>Create workspace</span>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Center: Navigation tabs in sentence case */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {[
            { id: 'dashboard', label: 'Dashboard' },
            { id: 'templates', label: 'Templates' },
            { id: 'workflows', label: 'Workflows' },
            { id: 'executions', label: 'Executions' },
            { id: 'connected', label: 'Connected apps', count: connectionsCount },
            { id: 'catalog', label: 'App catalog' },
            { id: 'team', label: 'Team & workspace', count: membersCount },
            { id: 'billing', label: 'Billing & plans' },
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '7px 14px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: isActive ? 'var(--surface-hover)' : 'transparent',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontSize: '14px',
                  fontWeight: isActive ? 500 : 400,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '7px',
                  transition: 'background-color 0.15s ease',
                }}
              >
                <span>{tab.label}</span>
                {typeof tab.count === 'number' && (
                  <span style={{
                    fontSize: '11px',
                    padding: '1px 6px',
                    borderRadius: '9999px',
                    backgroundColor: isActive ? 'var(--status-neutral-bg)' : 'transparent',
                    color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                  }}>
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Right: Notification Bell + Theme Toggle + User Dropdown + Refresh */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Notification Bell with unread counter */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setNotifDropdownOpen(!notifDropdownOpen)}
              className="btn-secondary"
              title="Notifications & failure alerts"
              style={{
                padding: '7px',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Bell size={15} style={{ color: unreadNotificationsCount > 0 ? 'var(--status-warning-text)' : 'var(--text-secondary)' }} />
              {unreadNotificationsCount > 0 && (
                <span style={{
                  position: 'absolute',
                  top: '-3px',
                  right: '-3px',
                  backgroundColor: '#EF4444',
                  color: '#FFFFFF',
                  fontSize: '10px',
                  fontWeight: 600,
                  borderRadius: '9999px',
                  padding: '1px 5px',
                  minWidth: '16px',
                  textAlign: 'center',
                  lineHeight: '1.2',
                }}>
                  {unreadNotificationsCount}
                </span>
              )}
            </button>

            {/* Notification Popover Dropdown */}
            {notifDropdownOpen && (
              <div style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                right: 0,
                width: '360px',
                maxHeight: '440px',
                backgroundColor: 'var(--surface-2)',
                border: '1px solid var(--border)',
                borderRadius: '12px',
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
                zIndex: 100,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}>
                <div style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      Failure Alerts & Notifications
                    </span>
                    {unreadNotificationsCount > 0 && (
                      <span style={{
                        fontSize: '11px',
                        padding: '1px 6px',
                        borderRadius: '9999px',
                        backgroundColor: 'var(--status-warning-bg)',
                        color: 'var(--status-warning-text)',
                        fontWeight: 600,
                      }}>
                        {unreadNotificationsCount} unread
                      </span>
                    )}
                  </div>
                  {unreadNotificationsCount > 0 && onMarkAllNotificationsRead && (
                    <button
                      onClick={onMarkAllNotificationsRead}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--text-muted)',
                        fontSize: '11px',
                        cursor: 'pointer',
                        padding: 0,
                      }}
                    >
                      Mark all read
                    </button>
                  )}
                </div>

                <div style={{ overflowY: 'auto', maxHeight: '340px', padding: '8px' }}>
                  {notifications.length === 0 ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
                      <CheckCircle size={20} style={{ color: 'var(--status-success-text)', margin: '0 auto 8px auto', display: 'block' }} />
                      No active alerts. All automations are healthy!
                    </div>
                  ) : (
                    notifications.map((n) => (
                      <div
                        key={n.id}
                        style={{
                          padding: '10px 12px',
                          borderRadius: '8px',
                          backgroundColor: n.is_read ? 'transparent' : 'var(--surface-0)',
                          border: '1px solid var(--border)',
                          marginBottom: '6px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {n.title}
                          </span>
                          <span style={{
                            fontSize: '10px',
                            padding: '1px 5px',
                            borderRadius: '4px',
                            backgroundColor: n.severity === 'critical' ? 'var(--status-warning-bg)' : 'var(--surface-2)',
                            color: n.severity === 'critical' ? 'var(--status-warning-text)' : 'var(--text-secondary)',
                            fontWeight: 600,
                          }}>
                            {n.severity.toUpperCase()}
                          </span>
                        </div>

                        <p style={{
                          fontSize: '11px',
                          color: 'var(--text-secondary)',
                          margin: 0,
                          lineHeight: '1.4',
                          whiteSpace: 'pre-wrap',
                          maxHeight: '60px',
                          overflow: 'hidden',
                        }}>
                          {n.message}
                        </p>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '4px' }}>
                          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                            {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            {!n.is_read && onMarkNotificationRead && (
                              <button
                                onClick={() => onMarkNotificationRead(n.id)}
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  color: 'var(--primary-btn-bg)',
                                  fontSize: '11px',
                                  cursor: 'pointer',
                                  padding: 0,
                                }}
                              >
                                Mark read
                              </button>
                            )}
                            {onDeleteNotification && (
                              <button
                                onClick={() => onDeleteNotification(n.id)}
                                title="Dismiss notification"
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  color: 'var(--text-muted)',
                                  cursor: 'pointer',
                                  padding: 0,
                                }}
                              >
                                <Trash2 size={11} />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div style={{
                  padding: '8px 16px',
                  borderTop: '1px solid var(--border)',
                  backgroundColor: 'var(--surface-0)',
                  textAlign: 'center',
                }}>
                  <button
                    onClick={() => {
                      setActiveTab('dashboard');
                      setNotifDropdownOpen(false);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--primary-btn-bg)',
                      fontSize: '12px',
                      fontWeight: 500,
                      cursor: 'pointer',
                    }}
                  >
                    View in Monitoring Dashboard →
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Theme mode toggle */}
          <button
            onClick={onToggleTheme}
            className="btn-secondary"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            style={{ padding: '7px' }}
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>

          <button
            onClick={onRefresh}
            className="btn-secondary"
            title="Refresh data"
            style={{ padding: '7px' }}
          >
            <RefreshCw size={14} className={isRefreshing ? 'spinner' : ''} />
          </button>

          {/* User profile dropdown & logout */}
          {currentUser && (
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                className="btn-secondary"
                style={{
                  padding: '5px 10px',
                  borderRadius: '8px',
                  fontSize: '13px',
                  gap: '6px',
                }}
              >
                <User size={14} style={{ color: 'var(--text-secondary)' }} />
                <span>{currentUser.name || currentUser.email}</span>
                {currentUser.email_verified && (
                  <CheckCircle size={12} style={{ color: 'var(--status-success-text)' }} />
                )}
                <ChevronDown size={12} style={{ color: 'var(--text-muted)' }} />
              </button>

              {userDropdownOpen && (
                <div style={{
                  position: 'absolute',
                  top: 'calc(100% + 6px)',
                  right: 0,
                  width: '220px',
                  backgroundColor: 'var(--surface-2)',
                  border: '1px solid var(--border)',
                  borderRadius: '10px',
                  padding: '10px',
                  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06)',
                  zIndex: 60,
                }}>
                  <div style={{ padding: '4px 6px', marginBottom: '6px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {currentUser.name}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {currentUser.email}
                    </div>
                    <div style={{ marginTop: '4px' }}>
                      <span className={`status-pill ${currentUser.email_verified ? 'success' : 'neutral'}`} style={{ fontSize: '11px', padding: '1px 6px' }}>
                        {currentUser.email_verified ? 'Verified email' : 'Unverified'}
                      </span>
                    </div>
                  </div>

                  <div style={{ height: '1px', backgroundColor: 'var(--border)', margin: '6px 0' }} />

                  <button
                    onClick={() => {
                      setUserDropdownOpen(false);
                      onLogout();
                    }}
                    style={{
                      width: '100%',
                      padding: '7px 10px',
                      borderRadius: '6px',
                      border: 'none',
                      backgroundColor: 'transparent',
                      color: 'var(--text-secondary)',
                      fontSize: '13px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      transition: 'background-color 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'var(--surface-hover)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <LogOut size={14} />
                    <span>Log out</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
