/**
 * COSMOS Frontend Authentication Service
 * Manages JWT access tokens (15-min lifespan) and authenticated API requests.
 */

const TOKEN_KEY = 'cosmos_jwt_access_token';
const USER_KEY = 'cosmos_user_profile';

export function getStoredToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || null;
  } catch {
    return null;
  }
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredAuth(token, user) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  } catch (err) {
    console.error('Failed to save auth to localStorage:', err);
  }
}

export function clearStoredAuth() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new CustomEvent('cosmos:auth-changed', { detail: { isAuthenticated: false, user: null } }));
  } catch (err) {
    console.error('Failed to clear auth from localStorage:', err);
  }
}

export async function login(username, password) {
  const res = await originalFetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Authentication failed. Check credentials.');
  }

  const data = await res.json();
  setStoredAuth(data.access_token, data.user);
  window.dispatchEvent(new CustomEvent('cosmos:auth-changed', { detail: { isAuthenticated: true, user: data.user } }));
  return data;
}

export async function ensureAuthenticated() {
  const token = getStoredToken();
  if (token) return getStoredUser();
  return null;
}

// Global fetch interceptor to attach JWT Authorization header to all /api/ requests
const originalFetch = window.fetch.bind(window);

window.fetch = async function (resource, config = {}) {
  const url = typeof resource === 'string' ? resource : resource?.url || '';
  
  if (url.includes('/api/') && !url.includes('/api/auth/login')) {
    const token = getStoredToken();
    if (token) {
      config = { ...config };
      config.headers = {
        ...(config.headers || {}),
        'Authorization': `Bearer ${token}`
      };
    }
  }

  const response = await originalFetch(resource, config);

  if (response.status === 401 && url.includes('/api/') && !url.includes('/api/auth/login')) {
    console.warn(`[COSMOS Auth] 401 Unauthorized for ${url}. Triggering re-authentication.`);
    window.dispatchEvent(new CustomEvent('cosmos:auth-expired'));
  }

  return response;
};
