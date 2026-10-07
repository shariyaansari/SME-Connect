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

  // Workflows (Module 3)
  fetchWorkflows: (status, orgId) => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (orgId) params.append('organization_id', orgId);
    const qs = params.toString();
    return request(qs ? `/workflows?${qs}` : '/workflows');
  },
  fetchWorkflow: (id, version, orgId) => {
    const params = new URLSearchParams();
    if (version) params.append('version', version);
    if (orgId) params.append('organization_id', orgId);
    const qs = params.toString();
    return request(qs ? `/workflows/${id}?${qs}` : `/workflows/${id}`);
  },
  createWorkflow: (payload, orgId) => request(
    orgId ? `/workflows?organization_id=${orgId}` : '/workflows',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  ),
  updateWorkflow: (id, payload, orgId) => request(
    orgId ? `/workflows/${id}?organization_id=${orgId}` : `/workflows/${id}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    }
  ),
  deleteWorkflow: (id, orgId) => request(
    orgId ? `/workflows/${id}?organization_id=${orgId}` : `/workflows/${id}`,
    {
      method: 'DELETE',
    }
  ),
  fetchWorkflowCapabilities: () => request('/workflows/capabilities'),
  fetchWorkflowConnectorCapability: (slug) => request(`/workflows/capabilities/${slug}`),
  publishWorkflow: (id, orgId) => request(
    orgId ? `/workflows/${id}/publish?organization_id=${orgId}` : `/workflows/${id}/publish`,
    {
      method: 'POST',
    }
  ),
  pauseWorkflow: (id, orgId) => request(
    orgId ? `/workflows/${id}/pause?organization_id=${orgId}` : `/workflows/${id}/pause`,
    {
      method: 'POST',
    }
  ),

  // Templates (Module 3A)
  fetchTemplates: () => request('/templates'),
  fetchTemplate: (id) => request(`/templates/${id}`),

  // Execution Monitoring & History (Module 5)
  fetchExecutions: (params = {}) => {
    const query = new URLSearchParams();
    if (params.workflow_id) query.append('workflow_id', params.workflow_id);
    if (params.organization_id) query.append('organization_id', params.organization_id);
    if (params.status && params.status !== 'all') query.append('status', params.status);
    if (params.start_date) query.append('start_date', params.start_date);
    if (params.end_date) query.append('end_date', params.end_date);
    if (params.limit) query.append('limit', params.limit);
    if (params.offset) query.append('offset', params.offset);
    const qs = query.toString();
    return request(qs ? `/executions?${qs}` : '/executions');
  },
  fetchExecutionDetail: (executionId, orgId) => request(
    orgId ? `/executions/${executionId}?organization_id=${orgId}` : `/executions/${executionId}`
  ),
  executeWorkflow: (workflowId, payload = {}, orgId) => request(
    orgId ? `/workflows/${workflowId}/execute?organization_id=${orgId}` : `/workflows/${workflowId}/execute`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  ),

  // Reliability & Production-Readiness (Module 6)
  retryExecution: (executionId, orgId) => request(
    orgId ? `/executions/${executionId}/retry?organization_id=${orgId}` : `/executions/${executionId}/retry`,
    {
      method: 'POST',
    }
  ),
  fetchWorkflowHealth: (workflowId, orgId) => request(
    orgId ? `/workflows/${workflowId}/health?organization_id=${orgId}` : `/workflows/${workflowId}/health`
  ),
  runScheduleCycle: () => request('/workflows/schedule/run-cycle', {
    method: 'POST',
  }),
};



