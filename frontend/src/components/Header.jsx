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
  CheckCircle
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
  isRefreshing
}) {
  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
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
            { id: 'templates', label: 'Templates' },
            { id: 'workflows', label: 'Workflows' },
            { id: 'executions', label: 'Executions' },
            { id: 'connected', label: 'Connected apps', count: connectionsCount },
            { id: 'catalog', label: 'App catalog' },
            { id: 'team', label: 'Team & workspace', count: membersCount },
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

        {/* Right: Theme Toggle + User Dropdown + Refresh */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
