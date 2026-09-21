import React, { useEffect, useState } from 'react';
import Header from './components/Header';
import QuickStartBanner from './components/QuickStartBanner';
import ConnectorCatalog from './components/ConnectorCatalog';
import ConnectedApps from './components/ConnectedApps';
import ConnectModal from './components/ConnectModal';
import { api, ensureSession } from './api';
import { CheckCircle2, AlertCircle } from 'lucide-react';

export default function App() {
  const [catalog, setCatalog] = useState([]);
  const [connections, setConnections] = useState([]);
  const [currentOrg, setCurrentOrg] = useState(null);
  const [activeTab, setActiveTab] = useState('catalog');
  const [selectedConnector, setSelectedConnector] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4000);
  };

  const loadData = async () => {
    try {
      await ensureSession();
      const [catalogData, connectionsData, orgData] = await Promise.all([
        api.fetchCatalog(),
        api.fetchConnections(),
        api.fetchCurrentOrganization().catch(() => null),
      ]);
      setCatalog(catalogData || []);
      setConnections(connectionsData || []);
      setCurrentOrg(orgData);
    } catch (err) {
      console.error('Failed to load application data:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };

  const handleCreateConnection = async (payload) => {
    const newConn = await api.createConnection(payload);
    setConnections((prev) => [newConn, ...prev]);
    showToast(`Successfully connected ${newConn.name}!`);
    setActiveTab('connected');
  };

  const handleTestConnection = async (id) => {
    const result = await api.testConnection(id);
    // Update status in state
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
      await api.deleteConnection(id);
      setConnections((prev) => prev.filter((c) => c.id !== id));
      showToast('Connection disconnected and removed.', 'info');
    } catch (err) {
      showToast(err.message || 'Failed to delete connection', 'error');
    }
  };

  const handleConnectFromBanner = (slug) => {
    const conn = catalog.find((c) => c.slug === slug);
    if (conn) {
      setSelectedConnector(conn);
    } else {
      setActiveTab('catalog');
    }
  };

  const connectedSlugs = connections.map((c) => c.connector_slug);

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '1rem',
      }}>
        <div className="spinner" style={{ width: '32px', height: '32px', borderWidth: '3px' }} />
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Initializing SME Connect workspace...</p>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        connectionsCount={connections.length}
        currentOrg={currentOrg}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <main style={{
        flex: 1,
        maxWidth: '1280px',
        width: '100%',
        margin: '0 auto',
        padding: '2rem',
      }}>
        {/* Golden Workflow Banner */}
        <QuickStartBanner onConnectApp={handleConnectFromBanner} />

        {/* Tab Content */}
        {activeTab === 'catalog' ? (
          <ConnectorCatalog
            catalog={catalog}
            connectedSlugs={connectedSlugs}
            onSelectConnector={(conn) => setSelectedConnector(conn)}
          />
        ) : (
          <ConnectedApps
            connections={connections}
            onTestConnection={handleTestConnection}
            onDeleteConnection={handleDeleteConnection}
            onOpenCatalog={() => setActiveTab('catalog')}
          />
        )}
      </main>

      {/* Connect Modal */}
      {selectedConnector && (
        <ConnectModal
          connector={selectedConnector}
          onClose={() => setSelectedConnector(null)}
          onSave={handleCreateConnection}
        />
      )}

      {/* Toast Notification */}
      {toast && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          padding: '0.8rem 1.2rem',
          borderRadius: '10px',
          background: toast.type === 'error' ? 'var(--danger-bg)' : 'var(--bg-elevated)',
          border: `1px solid ${toast.type === 'error' ? 'var(--danger-border)' : 'var(--border-accent)'}`,
          color: '#ffffff',
          fontSize: '0.88rem',
          fontWeight: 600,
          boxShadow: 'var(--shadow-lg)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem',
          zIndex: 200,
          animation: 'fadeIn 0.2s ease-out',
        }}>
          {toast.type === 'error' ? (
            <AlertCircle size={18} color="var(--danger)" />
          ) : (
            <CheckCircle2 size={18} color="var(--success)" />
          )}
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
}
