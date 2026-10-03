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
    let errorMsg = data.detail || response.statusText || 'Request failed';
    const err = new Error(typeof errorMsg === 'string' ? errorMsg : 'Validation Error');
    if (Array.isArray(data.detail)) {
      err.validationErrors = data.detail;
    }
    throw err;
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
  fetchConnections: () => request('/connectors'),
  fetchConnection: (id) => request(`/connectors/${id}`),
  createConnection: (payload) => request('/connectors', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  testConnection: (id) => request(`/connectors/${id}/test`, {
    method: 'POST',
  }),
  updateConnection: (id, payload) => request(`/connectors/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),
  deleteConnection: (id) => request(`/connectors/${id}`, {
    method: 'DELETE',
  }),


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

  // Workflows (Module 3)
  fetchWorkflows: (status) => request(status ? `/workflows?status=${status}` : '/workflows'),
  fetchWorkflow: (id, version) => request(version ? `/workflows/${id}?version=${version}` : `/workflows/${id}`),
  createWorkflow: (payload) => request('/workflows', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  updateWorkflow: (id, payload) => request(`/workflows/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),
  deleteWorkflow: (id) => request(`/workflows/${id}`, {
    method: 'DELETE',
  }),
  fetchWorkflowCapabilities: () => request('/workflows/capabilities'),
  fetchWorkflowConnectorCapability: (slug) => request(`/workflows/capabilities/${slug}`),
  publishWorkflow: (id) => request(`/workflows/${id}/publish`, {
    method: 'POST',
  }),
  pauseWorkflow: (id) => request(`/workflows/${id}/pause`, {
    method: 'POST',
  }),

  // Templates (Module 3A)
  fetchTemplates: () => request('/templates/'),
  fetchTemplate: (id) => request(`/templates/${id}`),
};
