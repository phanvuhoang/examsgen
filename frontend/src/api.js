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

  // Generate
  generateMCQ: (data) =>
    request('/generate/mcq', { method: 'POST', body: JSON.stringify(data) }),

  generateScenario: (data) =>
    request('/generate/scenario', { method: 'POST', body: JSON.stringify(data) }),

  generateLongform: (data) =>
    request('/generate/longform', { method: 'POST', body: JSON.stringify(data) }),

  // Questions
  getQuestionsForReference: ({ type, sac_thue }) => {
    const params = new URLSearchParams()
    if (type) params.set('type', type)
    if (sac_thue) params.set('sac_thue', sac_thue)
    return request(`/questions/for-reference?${params}`)
  },

  getQuestions: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/questions${qs ? `?${qs}` : ''}`)
  },

  getQuestion: (id) => request(`/questions/${id}`),

  toggleStar: (id) => request(`/questions/${id}/star`, { method: 'PATCH' }),

  deleteQuestion: (id) => request(`/questions/${id}`, { method: 'DELETE' }),

  searchQuestions: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/questions/search?${q}`)
  },

  // Refine
  refineQuestion: (data) =>
    request('/generate/refine', { method: 'POST', body: JSON.stringify(data) }),

  // Exam Sessions
  getSessions: () => request('/sessions/'),

  createSession: (data) =>
    request('/sessions/', { method: 'POST', body: JSON.stringify(data) }),

  updateSession: (id, data) =>
    request(`/sessions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  setDefaultSession: (id) =>
    request(`/sessions/${id}/set-default`, { method: 'POST' }),

  deleteSession: (id) =>
    request(`/sessions/${id}`, { method: 'DELETE' }),

  sessionStats: (id) => request(`/sessions/${id}/stats`),

  // Session file management
  getSessionFiles: (sessionId, fileType) => {
    const q = fileType ? `?file_type=${fileType}` : ''
    return request(`/sessions/${sessionId}/files${q}`)
  },

  uploadSessionFile: (sessionId, formData) => {
    const token = localStorage.getItem('token')
    return fetch(`${API_BASE}/sessions/${sessionId}/files`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then((r) => {
      if (!r.ok) return r.json().then((d) => { throw new Error(d.detail || 'Upload failed') })
      return r.json()
    })
  },

  deleteSessionFile: (sessionId, fileId) =>
    request(`/sessions/${sessionId}/files/${fileId}`, { method: 'DELETE' }),

  toggleSessionFile: (sessionId, fileId) =>
    request(`/sessions/${sessionId}/files/${fileId}/toggle`, { method: 'PUT' }),

  carryForward: (sessionId, fromSessionId) =>
    request(`/sessions/${sessionId}/carry-forward`, {
      method: 'POST',
      body: JSON.stringify({ from_session_id: fromSessionId }),
    }),

  // Export
  exportWord: (questionIds) =>
    request('/export/word', {
      method: 'POST',
      body: JSON.stringify({ question_ids: questionIds }),
    }),
}
