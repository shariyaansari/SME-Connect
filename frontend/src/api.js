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

// Ensure demo user session exists so UI is immediately interactive
export async function ensureSession() {
  let token = getAuthToken();
  if (token) {
    try {
      const me = await request('/auth/me');
      const orgs = await request('/organizations');
      if (orgs.length === 0) {
        await request('/organizations', {
          method: 'POST',
          body: JSON.stringify({ name: 'Acme Enterprise' }),
        });
      }
      return me;
    } catch {
      clearAuthToken();
    }
  }

  // Auto-login or auto-register a default workspace user
  const email = 'demo@smeconnect.io';
  const password = 'DemoPassword123!';

  try {
    const loginData = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(loginData.access_token);
  } catch {
    // If not registered, create account
    try {
      await request('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          name: 'Demo Admin',
          email,
          password,
        }),
      });
      const loginData = await request('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setAuthToken(loginData.access_token);
      await request('/organizations', {
        method: 'POST',
        body: JSON.stringify({ name: 'Acme Enterprise' }),
      });
    } catch (e) {
      console.error('Failed to initialize session:', e);
    }
  }

  return request('/auth/me');
}

export const api = {
  // Connectors & Integrations
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

  // Organizations
  fetchOrganizations: () => request('/organizations'),
  fetchCurrentOrganization: () => request('/organizations/me'),
  createOrganization: (name) => request('/organizations', {
    method: 'POST',
    body: JSON.stringify({ name }),
  }),
};
