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
  deleteSession: (id) =>
    request(`/sessions/${id}`, { method: 'DELETE' }),
  sessionStats: (id) => request(`/sessions/${id}/stats`),
  cloneSession: (targetId, sourceId) =>
    request(`/sessions/${targetId}/clone-from/${sourceId}`, { method: 'POST' }),
  parseAndMatch: (sessionId, data) =>
    request(`/sessions/${sessionId}/parse-and-match`, { method: 'POST', body: JSON.stringify(data) }),
  saveParsedChunks: (sessionId, data) =>
    request(`/sessions/${sessionId}/save-parsed-chunks`, { method: 'POST', body: JSON.stringify(data) }),
  getSessionFiles: (sessionId, docType) => {
    const q = docType ? `?doc_type=${docType}` : ''
    return request(`/sessions/${sessionId}/files${q}`)
  },
  uploadSessionDoc: (sessionId, formData) => {
    const token = localStorage.getItem('token')
    return fetch(`${API_BASE}/sessions/${sessionId}/upload-doc`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then((r) => {
      if (!r.ok) throw new Error('Upload failed')
      return r.json()
    })
  },
  deleteSessionFile: (sessionId, fileId) =>
    request(`/sessions/${sessionId}/files/${fileId}`, { method: 'DELETE' }),

  // Export
  exportWord: (questionIds) =>
    request('/export/word', {
      method: 'POST',
      body: JSON.stringify({ question_ids: questionIds }),
    }),

  // v2: Session settings
  getSessionSettings: (id) => request(`/sessions/${id}/settings`),
  patchSessionSettings: (id, data) =>
    request(`/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  // v2: KB Syllabus — upload + bulk-insert + search
  uploadKBSyllabus: (formData) => {
    const token = localStorage.getItem('token')
    return fetch(`${API_BASE}/kb/syllabus/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then((r) => { if (!r.ok) throw new Error('Upload failed'); return r.json() })
  },
  bulkInsertKBSyllabus: (data) =>
    request('/kb/syllabus/bulk-insert', { method: 'POST', body: JSON.stringify(data) }),
  searchKBSyllabus: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/syllabus/search?${q}`)
  },

  // v2: Regulations parsed
  parseRegulationDoc: (data) =>
    request('/kb/regulations/parse-doc', { method: 'POST', body: JSON.stringify(data) }),
  getParsedRegulations: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/regulations/parsed?${q}`)
  },
  searchParsedRegulations: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/regulations/search?${q}`)
  },
  updateParsedRegulation: (id, data) =>
    request(`/kb/regulation-parsed/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteParsedRegulation: (id) =>
    request(`/kb/regulation-parsed/${id}`, { method: 'DELETE' }),

  // v2: Tax Rates
  getTaxRates: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/tax-rates?${q}`)
  },
  uploadTaxRates: (formData) => {
    const token = localStorage.getItem('token')
    return fetch(`${API_BASE}/kb/tax-rates/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then((r) => { if (!r.ok) throw new Error('Upload failed'); return r.json() })
  },
  createTaxRate: (data) =>
    request('/kb/tax-rates', { method: 'POST', body: JSON.stringify(data) }),
  updateTaxRate: (id, data) =>
    request(`/kb/tax-rates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTaxRate: (id) =>
    request(`/kb/tax-rates/${id}`, { method: 'DELETE' }),

  // v2: Sample Questions
  getSampleQuestions: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/sample-questions?${q}`)
  },
  searchSampleQuestions: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/sample-questions/search?${q}`)
  },
  getSampleQuestion: (id) => request(`/sample-questions/${id}`),
  createSampleQuestion: (data) =>
    request('/sample-questions', { method: 'POST', body: JSON.stringify(data) }),
  updateSampleQuestion: (id, data) =>
    request(`/sample-questions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteSampleQuestion: (id) =>
    request(`/sample-questions/${id}`, { method: 'DELETE' }),

  // v2: Questions search
  searchQuestions: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/questions/search?${q}`)
  },

  // v2: Auto-suggest syllabus + reg codes for a question
  suggestCodes: async (data) => {
    try {
      return await request('/kb/suggest-codes', { method: 'POST', body: JSON.stringify(data) })
    } catch {
      return { syllabus_codes: [], reg_codes: [] }
    }
  },

  // v2: Save codes back to a generated question
  updateQuestionCodes: (questionId, data) =>
    request(`/questions/${questionId}/codes`, { method: 'PATCH', body: JSON.stringify(data) }),

  // v2: Save codes to a sample question
  updateSampleQuestionCodes: (itemId, data) =>
    request(`/sample-questions/${itemId}/codes`, { method: 'PATCH', body: JSON.stringify(data) }),

  // v2: Bulk delete KB items
  bulkDeleteKBItems: async (type, ids) => {
    try {
      return await request(`/kb/${type}/bulk`, { method: 'DELETE', body: JSON.stringify({ ids }) })
    } catch {
      return { deleted: 0 }
    }
  },

  // v2: AI-tag syllabus codes for untagged regulation items
  tagSyllabus: (sessionId, taxType = null) =>
    request('/kb/regulations/tag-syllabus', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, tax_type: taxType }),
    }),

  // v2: Get regulation files with paragraph counts
  getRegulationFiles: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/regulations/files?${q}`)
  },

  // v2: Async parse job
  parseRegulationDocAsync: (data) =>
    request('/kb/regulations/parse-doc-async', { method: 'POST', body: JSON.stringify(data) }),

  getParseJob: (jobId) => request(`/kb/regulations/parse-job/${jobId}`),

  // v2: updated getParsedRegulations returns {total, items}
  getRegulationsParsed: (params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/kb/regulations/parsed?${q}`)
  },
}
