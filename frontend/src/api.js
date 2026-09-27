// API Client for SME Connect Backend

const API_BASE = '';

export function getAuthToken() {
  return localStorage.getItem('sme_access_token') || '';
}

export function setAuthToken(token) {
  localStorage.setItem('sme_access_token', token);
}

export function clearAuthToken() {
  localStorage.removeItem('sme_access_token');
}

async function request(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorMsg = data.detail || response.statusText || 'Request failed';
    throw new Error(errorMsg);
  }

  return data;
}

// Check if user has an active authenticated session
export async function checkSession() {
  const token = getAuthToken();
  if (!token) return null;

  try {
    const me = await request('/auth/me');
    return me;
  } catch {
    clearAuthToken();
    return null;
  }
}

export const api = {
  // Connectors & Integrations (Module 2)
  fetchCatalog: () => request('/connectors/catalog'),
  fetchConnections: (orgId) => request(
    orgId ? `/connectors?organization_id=${orgId}` : '/connectors'
  ),
  fetchConnection: (id, orgId) => request(
    orgId ? `/connectors/${id}?organization_id=${orgId}` : `/connectors/${id}`
  ),
  createConnection: (payload, orgId) => request(
    orgId ? `/connectors?organization_id=${orgId}` : '/connectors',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  ),
  testConnection: (id, orgId) => request(
    orgId ? `/connectors/${id}/test?organization_id=${orgId}` : `/connectors/${id}/test`,
    {
      method: 'POST',
    }
  ),
  updateConnection: (id, payload, orgId) => request(
    orgId ? `/connectors/${id}?organization_id=${orgId}` : `/connectors/${id}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    }
  ),
  deleteConnection: (id, orgId) => request(
    orgId ? `/connectors/${id}?organization_id=${orgId}` : `/connectors/${id}`,
    {
      method: 'DELETE',
    }
  ),


  // Organizations & Workspaces (Module 1)
  fetchOrganizations: () => request('/organizations'),
  fetchCurrentOrganization: (orgId) => request(
    orgId ? `/organizations/me?organization_id=${orgId}` : '/organizations/me'
  ),
  createOrganization: (name) => request('/organizations', {
    method: 'POST',
    body: JSON.stringify({ name }),
  }),
  fetchMembers: (orgId) => request(
    orgId ? `/organizations/members?organization_id=${orgId}` : '/organizations/members'
  ),
  updateMemberRole: (memberId, role, orgId) => request(
    orgId ? `/organizations/members/${memberId}?organization_id=${orgId}` : `/organizations/members/${memberId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }
  ),
  createInvitation: (payload, orgId) => request(
    orgId ? `/organizations/invitations?organization_id=${orgId}` : '/organizations/invitations',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  ),
  fetchPendingInvitations: () => request('/organizations/invitations/pending'),
  acceptInvitation: (token) => request('/organizations/invitations/accept', {
    method: 'POST',
    body: JSON.stringify({ token }),
  }),
  fetchAuditLogs: (orgId) => request(
    orgId ? `/organizations/audit-logs?organization_id=${orgId}` : '/organizations/audit-logs'
  ),

  // Entire Authentication Lifecycle (Module 1)
  fetchMe: () => request('/auth/me'),
  register: async (payload) => {
    const data = await request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return data;
  },
  login: async (payload) => {
    const data = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (data.access_token) {
      setAuthToken(data.access_token);
    }
    return data;
  },
  verifyEmail: (token) => request('/auth/verify-email', {
    method: 'POST',
    body: JSON.stringify({ token }),
  }),
  logout: () => {
    clearAuthToken();
  },
};
