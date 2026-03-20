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

  // Refine
  refineQuestion: (data) =>
    request('/generate/refine', { method: 'POST', body: JSON.stringify(data) }),

  // Knowledge Base
  getKBSyllabus: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/syllabus?${q}`)
  },
  createKBSyllabus: (data) =>
    request('/kb/syllabus', { method: 'POST', body: JSON.stringify(data) }),
  updateKBSyllabus: (id, data) =>
    request(`/kb/syllabus/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteKBSyllabus: (id) =>
    request(`/kb/syllabus/${id}`, { method: 'DELETE' }),

  getKBRegulations: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/regulations?${q}`)
  },
  createKBRegulation: (data) =>
    request('/kb/regulations', { method: 'POST', body: JSON.stringify(data) }),
  updateKBRegulation: (id, data) =>
    request(`/kb/regulations/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteKBRegulation: (id) =>
    request(`/kb/regulations/${id}`, { method: 'DELETE' }),

  getKBSamples: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/samples?${q}`)
  },
  createKBSample: (data) =>
    request('/kb/samples', { method: 'POST', body: JSON.stringify(data) }),
  updateKBSample: (id, data) =>
    request(`/kb/samples/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteKBSample: (id) =>
    request(`/kb/samples/${id}`, { method: 'DELETE' }),
  importKBSampleFromBank: (data) =>
    request('/kb/samples/import-from-bank', { method: 'POST', body: JSON.stringify(data) }),

  // Exam Sessions
  getSessions: () => request('/sessions/'),
  createSession: (data) =>
    request('/sessions/', { method: 'POST', body: JSON.stringify(data) }),
  updateSession: (id, data) =>
    request(`/sessions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  setDefaultSession: (id) =>
    request(`/sessions/${id}/set-default`, { method: 'POST' }),
  cloneSession: (targetId, sourceId) =>
    request(`/sessions/${targetId}/clone-from/${sourceId}`, { method: 'POST' }),
  parseAndMatch: (sessionId, data) =>
    request(`/sessions/${sessionId}/parse-and-match`, { method: 'POST', body: JSON.stringify(data) }),
  saveParsedChunks: (sessionId, data) =>
    request(`/sessions/${sessionId}/save-parsed-chunks`, { method: 'POST', body: JSON.stringify(data) }),

  // Export
  exportWord: (questionIds) =>
    request('/export/word', {
      method: 'POST',
      body: JSON.stringify({ question_ids: questionIds }),
    }),
}
