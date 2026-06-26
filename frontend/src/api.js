function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return '';
}

export async function api(path, options = {}) {
  const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' };
  const response = await fetch(path, {
    credentials: 'include',
    headers: {
      ...headers,
      'X-CSRFToken': getCookie('csrftoken'),
      ...(options.headers || {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({ ok: false, error: response.statusText }));
  if (!response.ok || !payload.ok) {
    const error = new Error(payload.error || response.statusText);
    error.status = response.status;
    throw error;
  }
  return payload.data;
}

export function login(username, password) {
  return api('/api/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export function logout() {
  return api('/api/logout/', { method: 'POST', body: JSON.stringify({}) });
}
