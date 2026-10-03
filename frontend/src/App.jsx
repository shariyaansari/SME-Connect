import React, { useEffect, useState, useCallback } from 'react';
import Header from './components/Header';
import WorkflowsView from './components/WorkflowsView';
import TemplatesView from './components/TemplatesView';
import ConnectedApps from './components/ConnectedApps';
import ConnectorCatalog from './components/ConnectorCatalog';
import TeamWorkspaceView from './components/TeamWorkspaceView';
import ConnectModal from './components/ConnectModal';
import InviteModal from './components/InviteModal';
import AuthView from './components/AuthView';
import { api, checkSession } from './api';
import { CheckCircle, AlertTriangle, Mail, ArrowRight } from 'lucide-react';
import './App.css';

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('sme_theme') || 'light';
  });

  const [catalog, setCatalog] = useState([]);
  const [connections, setConnections] = useState([]);
  const [organizations, setOrganizations] = useState([]);
  const [currentOrg, setCurrentOrg] = useState(null);
  const [members, setMembers] = useState([]);
  const [pendingInvitations, setPendingInvitations] = useState([]);

  const [activeTab, setActiveTab] = useState('templates');
  const [selectedConnector, setSelectedConnector] = useState(null);
  const [editingConnection, setEditingConnection] = useState(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toast, setToast] = useState(null);

  // Apply theme to document element
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    localStorage.setItem('sme_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4000);
  };

  const loadData = useCallback(async (targetOrgId = null) => {
    try {
      const user = await checkSession();
      if (!user) {
        setCurrentUser(null);
        setLoading(false);
        setIsRefreshing(false);
        return;
      }
      setCurrentUser(user);

      const [orgs, catalogData, pending] = await Promise.all([
        api.fetchOrganizations().catch(() => []),
        api.fetchCatalog().catch(() => []),
        api.fetchPendingInvitations().catch(() => []),
      ]);

      setOrganizations(orgs || []);
      setCatalog(catalogData || []);
      setPendingInvitations(pending || []);

      const orgIdToLoad = targetOrgId || (orgs && orgs.length > 0 ? orgs[0].id : null);
      let activeOrg = null;
      let memberList = [];
      let connectionsList = [];

      if (orgIdToLoad) {
        const [orgData, membersData, connData] = await Promise.all([
          api.fetchCurrentOrganization(orgIdToLoad).catch(() => null),
          api.fetchMembers(orgIdToLoad).catch(() => []),
          api.fetchConnections(orgIdToLoad).catch(() => []),
        ]);
        activeOrg = orgData;
        memberList = membersData || [];
        connectionsList = connData || [];
      } else {
        const [orgData, membersData, connData] = await Promise.all([
          api.fetchCurrentOrganization().catch(() => null),
          api.fetchMembers().catch(() => []),
          api.fetchConnections().catch(() => []),
        ]);
        activeOrg = orgData;
        memberList = membersData || [];
        connectionsList = connData || [];
      }

      setCurrentOrg(activeOrg);
      setMembers(memberList || []);
      setConnections(connectionsList || []);
    } catch (err) {
      console.error('Failed to load application data:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    loadData();
    showToast(`Signed in as ${user.email}`);
  };

  const handleLogout = () => {
    api.logout();
    setCurrentUser(null);
    setCurrentOrg(null);
    setOrganizations([]);
    setMembers([]);
    setPendingInvitations([]);
    showToast('Logged out successfully', 'info');
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData(currentOrg?.id);
  };

  const handleSelectOrg = async (orgId) => {
    setIsRefreshing(true);
    await loadData(orgId);
  };

  const handleCreateOrg = async (name) => {
    try {
      const newOrg = await api.createOrganization(name);
      showToast(`Created workspace "${newOrg.name}"`);
      await loadData(newOrg.id);
    } catch (err) {
      showToast(err.message || 'Failed to create workspace', 'error');
    }
  };

  const handleCreateConnection = async (payload) => {
    try {
      const newConn = await api.createConnection(payload, currentOrg?.id);
      setConnections((prev) => [newConn, ...prev]);
      showToast(`Connected ${newConn.name}`);
      setActiveTab('connected');
    } catch (err) {
      showToast(err.message || 'Failed to create connection', 'error');
    }
  };

  const handleUpdateConnection = async (id, payload) => {
    try {
      const updated = await api.updateConnection(id, payload, currentOrg?.id);
      setConnections((prev) =>
        prev.map((c) => (c.id === id ? updated : c))
      );
      showToast(`Updated connection "${updated.name}"`);
    } catch (err) {
      showToast(err.message || 'Failed to update connection', 'error');
      throw err;
    }
  };

  const handleTestConnection = async (id) => {
    const result = await api.testConnection(id, currentOrg?.id);
    setConnections((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              status: result.status,
              error_message: result.success ? null : result.message,
              last_tested_at: result.tested_at,
            }
          : c
      )
    );
    return result;
  };

  const handleDeleteConnection = async (id) => {
    try {
      await api.deleteConnection(id, currentOrg?.id);
      setConnections((prev) => prev.filter((c) => c.id !== id));
      showToast('Connection removed');
    } catch (err) {
      showToast(err.message || 'Failed to delete connection', 'error');
    }
  };

  const handleInviteMember = async (payload) => {
    if (currentOrg?.role !== 'Admin') {
      showToast('Only organization Admins can invite members', 'error');
      return;
    }
    try {
      const invite = await api.createInvitation(payload, currentOrg?.id);
      setPendingInvitations((prev) => [invite, ...prev]);
      showToast(`Invitation sent to ${payload.email}`);
    } catch (err) {
      showToast(err.message || 'Failed to send invitation', 'error');
    }
  };

  const handleUpdateRole = async (memberId, role) => {
    try {
      await api.updateMemberRole(memberId, role, currentOrg?.id);
      setMembers((prev) =>
        prev.map((m) => (m.id === memberId ? { ...m, role } : m))
      );
      showToast('Member role updated');
    } catch (err) {
      showToast(err.message || 'Failed to update role', 'error');
    }
  };

  const handleAcceptInvitation = async (token) => {
    try {
      const result = await api.acceptInvitation(token);
      showToast(`Invitation accepted! Added as ${result.role}`);
      await loadData();
    } catch (err) {
      showToast(err.message || 'Failed to accept invitation', 'error');
    }
  };

  const connectedSlugs = connections.map((c) => c.connector_slug);
  const canManageConnectors = currentOrg?.role !== 'Viewer';

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        backgroundColor: 'var(--surface-0)',
      }}>
        <div className="spinner" style={{ width: '24px', height: '24px', borderWidth: '2px' }} />
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          Loading workspace...
        </p>
      </div>
    );
  }

  // If user is not logged in: present the entire Module 1 Auth View
  if (!currentUser) {
    return <AuthView onAuthSuccess={handleAuthSuccess} />;
  }

  return (
    <div className="app-container">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        connectionsCount={connections.length}
        membersCount={members.length}
        currentOrg={currentOrg}
        organizations={organizations}
        onSelectOrg={handleSelectOrg}
        onCreateOrg={handleCreateOrg}
        currentUser={currentUser}
        onLogout={handleLogout}
        theme={theme}
        onToggleTheme={toggleTheme}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <main className="main-content">
        {/* If user has pending invitations, render a calm airy prompt banner */}
        {pendingInvitations.length > 0 && (
          <div style={{
            backgroundColor: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: '10px',
            padding: '14px 18px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            flexWrap: 'wrap',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Mail size={16} style={{ color: 'var(--status-warning-text)' }} />
              <div>
                <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
                  You have a pending organization invitation
                </span>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '1px' }}>
                  Invited as {pendingInvitations[0].role}. Membership is created upon acceptance.
                </p>
              </div>
            </div>

            <button
              className="btn-primary"
              onClick={() => handleAcceptInvitation(pendingInvitations[0].token)}
              style={{ fontSize: '13px', padding: '6px 14px' }}
            >
              <span>Accept invitation</span>
              <ArrowRight size={13} />
            </button>
          </div>
        )}

        {activeTab === 'templates' && (
          <TemplatesView
            onNavigateWorkflows={() => setActiveTab('workflows')}
            onNavigateConnectors={() => setActiveTab('connected')}
          />
        )}

        {activeTab === 'workflows' && (
          <WorkflowsView
            onNavigateConnectors={() => setActiveTab('connected')}
          />
        )}

        {activeTab === 'connected' && (
          <ConnectedApps
            connections={connections}
            onTestConnection={handleTestConnection}
            onDeleteConnection={handleDeleteConnection}
            onEditConnection={(conn) => setEditingConnection(conn)}
            onOpenCatalog={() => setActiveTab('catalog')}
            canManage={canManageConnectors}
          />
        )}

        {activeTab === 'catalog' && (
          <ConnectorCatalog
            catalog={catalog}
            connectedSlugs={connectedSlugs}
            onSelectConnector={(conn) => setSelectedConnector(conn)}
            canManage={canManageConnectors}
          />
        )}

        {activeTab === 'team' && (
          <TeamWorkspaceView
            currentOrg={currentOrg}
            members={members}
            pendingInvitations={pendingInvitations}
            onOpenInviteModal={() => {
              if (currentOrg?.role === 'Admin') {
                setShowInviteModal(true);
              } else {
                showToast('Only workspace Admins can invite new members', 'error');
              }
            }}
            onUpdateRole={handleUpdateRole}
            onAcceptInvitation={handleAcceptInvitation}
            currentUser={currentUser}
          />
        )}
      </main>

      {/* Connect / Edit Modal (Module 2) */}
      {(selectedConnector || editingConnection) && (
        <ConnectModal
          connector={
            selectedConnector ||
            catalog.find((c) => c.slug === editingConnection?.connector_slug) || {
              slug: editingConnection?.connector_slug,
              name: editingConnection?.name,
              config_fields: [],
              credential_fields: [],
            }
          }
          initialConnection={editingConnection}
          onClose={() => {
            setSelectedConnector(null);
            setEditingConnection(null);
          }}
          onSave={
            editingConnection
              ? (payload) => handleUpdateConnection(editingConnection.id, payload)
              : handleCreateConnection
          }
        />
      )}

      {/* Invite Modal (Module 1) */}
      {showInviteModal && (
        <InviteModal
          onClose={() => setShowInviteModal(false)}
          onInvite={handleInviteMember}
        />
      )}

      {/* Toast Notification (Flat, airy, no shadow) */}
      {toast && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          padding: '10px 16px',
          borderRadius: '8px',
          backgroundColor: toast.type === 'error' ? 'var(--status-warning-bg)' : 'var(--surface-2)',
          border: '1px solid var(--border-strong)',
          color: 'var(--text-primary)',
          fontSize: '14px',
          fontWeight: 400,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
          zIndex: 200,
        }}>
          {toast.type === 'error' ? (
            <AlertTriangle size={16} style={{ color: 'var(--status-warning-text)' }} />
          ) : (
            <CheckCircle size={16} style={{ color: 'var(--status-success-text)' }} />
          )}
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
}
