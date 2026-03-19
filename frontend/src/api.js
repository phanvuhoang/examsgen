const API_BASE = '/api'

function getHeaders() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: getHeaders(),
    ...options,
  })
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(data.detail || 'Request failed')
  }
  // Handle file downloads
  if (res.headers.get('content-type')?.includes('application/vnd.openxmlformats')) {
    return res.blob()
  }
  return res.json()
}

export const api = {
  login: (password) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ password }) }),

  health: () => request('/health'),

  // Regulations
  getRegulations: (sac_thue) =>
    request(`/regulations${sac_thue ? `?sac_thue=${sac_thue}` : ''}`),

  uploadRegulation: (formData) => {
    const token = localStorage.getItem('token')
    return fetch(`${API_BASE}/regulations/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then((r) => {
      if (!r.ok) throw new Error('Upload failed')
      return r.json()
    })
  },

  toggleRegulation: (id) => request(`/regulations/${id}`, { method: 'PATCH' }),

  deleteRegulation: (id) => request(`/regulations/${id}`, { method: 'DELETE' }),

  getRegulationText: (id) => request(`/regulations/${id}/text`),

  // Generate
  generateMCQ: (data) =>
    request('/generate/mcq', { method: 'POST', body: JSON.stringify(data) }),

  generateScenario: (data) =>
    request('/generate/scenario', { method: 'POST', body: JSON.stringify(data) }),

  generateLongform: (data) =>
    request('/generate/longform', { method: 'POST', body: JSON.stringify(data) }),

  // Questions
  getQuestions: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/questions${qs ? `?${qs}` : ''}`)
  },

  getQuestion: (id) => request(`/questions/${id}`),

  toggleStar: (id) => request(`/questions/${id}/star`, { method: 'PATCH' }),

  deleteQuestion: (id) => request(`/questions/${id}`, { method: 'DELETE' }),

  // Export
  exportWord: (questionIds) =>
    request('/export/word', {
      method: 'POST',
      body: JSON.stringify({ question_ids: questionIds }),
    }),
}
