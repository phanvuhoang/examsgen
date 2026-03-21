import { useState, useEffect } from 'react'
import { api } from '../api'

// ── Settings Panel ────────────────────────────────────────────────────────────

function SessionSettingsPanel({ session }) {
  const [settings, setSettings] = useState({ parameters: [], tax_types: [], question_types: [] })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [openSection, setOpenSection] = useState(null) // 'params' | 'taxes' | 'qtypes'
  const [editQType, setEditQType] = useState(null)     // {parentIdx, subtypeIdx} or null
  const [editQForm, setEditQForm] = useState({})

  useEffect(() => {
    api.getSessionSettings(session.id)
      .then((d) => setSettings(d))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [session.id])

  const save = async () => {
    setSaving(true)
    try {
      await api.patchSessionSettings(session.id, settings)
      alert('Settings saved')
    } catch (err) { alert('Save failed: ' + err.message) }
    finally { setSaving(false) }
  }

  // ── Parameters helpers
  const addParam = () => setSettings((s) => ({
    ...s, parameters: [...s.parameters, { key: '', value: '', unit: '' }]
  }))
  const setParam = (i, field, val) => setSettings((s) => {
    const p = [...s.parameters]
    p[i] = { ...p[i], [field]: val }
    return { ...s, parameters: p }
  })
  const removeParam = (i) => setSettings((s) => ({
    ...s, parameters: s.parameters.filter((_, idx) => idx !== i)
  }))

  // ── Tax Types helpers
  const addTax = () => setSettings((s) => ({
    ...s, tax_types: [...s.tax_types, { code: '', name: '' }]
  }))
  const setTax = (i, field, val) => setSettings((s) => {
    const t = [...s.tax_types]
    t[i] = { ...t[i], [field]: val }
    return { ...s, tax_types: t }
  })
  const removeTax = (i) => setSettings((s) => ({
    ...s, tax_types: s.tax_types.filter((_, idx) => idx !== i)
  }))

  // ── Question Types helpers
  const addQType = () => setSettings((s) => ({
    ...s, question_types: [...s.question_types, { code: '', name: '', subtypes: [] }]
  }))
  const removeQType = (i) => setSettings((s) => ({
    ...s, question_types: s.question_types.filter((_, idx) => idx !== i)
  }))
  const addSubtype = (i) => setSettings((s) => {
    const qt = [...s.question_types]
    qt[i] = { ...qt[i], subtypes: [...(qt[i].subtypes || []), { code: '', name: '', description: '', sample: '' }] }
    return { ...s, question_types: qt }
  })
  const removeSubtype = (i, j) => setSettings((s) => {
    const qt = [...s.question_types]
    qt[i] = { ...qt[i], subtypes: qt[i].subtypes.filter((_, idx) => idx !== j) }
    return { ...s, question_types: qt }
  })
  const openEdit = (parentIdx, subtypeIdx) => {
    const qt = settings.question_types[parentIdx]
    const item = subtypeIdx === -1 ? qt : qt.subtypes[subtypeIdx]
    setEditQForm({ ...item })
    setEditQType({ parentIdx, subtypeIdx })
  }
  const saveEditQ = () => {
    const { parentIdx, subtypeIdx } = editQType
    setSettings((s) => {
      const qt = [...s.question_types]
      if (subtypeIdx === -1) {
        qt[parentIdx] = { ...qt[parentIdx], name: editQForm.name, description: editQForm.description, sample: editQForm.sample }
      } else {
        const subs = [...qt[parentIdx].subtypes]
        subs[subtypeIdx] = { ...subs[subtypeIdx], ...editQForm }
        qt[parentIdx] = { ...qt[parentIdx], subtypes: subs }
      }
      return { ...s, question_types: qt }
    })
    setEditQType(null)
  }

  if (loading) return <div className="text-xs text-gray-400 py-2">Loading settings...</div>

  const toggle = (s) => setOpenSection(openSection === s ? null : s)

  return (
    <div className="mt-4 border-t pt-4 space-y-3">
      {/* Section A: Economic Parameters */}
      <div className="border rounded-lg overflow-hidden">
        <button onClick={() => toggle('params')}
          className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 text-sm font-medium hover:bg-gray-100">
          <span>Economic Parameters ({settings.parameters.length})</span>
          <span>{openSection === 'params' ? '▲' : '▼'}</span>
        </button>
        {openSection === 'params' && (
          <div className="p-4 space-y-2">
            {settings.parameters.map((p, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input value={p.key} onChange={(e) => setParam(i, 'key', e.target.value)}
                  placeholder="Key" className="flex-1 border rounded px-2 py-1 text-xs" />
                <input value={p.value} onChange={(e) => setParam(i, 'value', e.target.value)}
                  placeholder="Value" className="w-28 border rounded px-2 py-1 text-xs" />
                <input value={p.unit} onChange={(e) => setParam(i, 'unit', e.target.value)}
                  placeholder="Unit" className="w-20 border rounded px-2 py-1 text-xs" />
                <button onClick={() => removeParam(i)} className="text-red-400 hover:text-red-600 text-sm">✕</button>
              </div>
            ))}
            <button onClick={addParam} className="text-xs text-brand-600 hover:underline mt-1">+ Add Parameter</button>
          </div>
        )}
      </div>

      {/* Section B: Tax Types */}
      <div className="border rounded-lg overflow-hidden">
        <button onClick={() => toggle('taxes')}
          className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 text-sm font-medium hover:bg-gray-100">
          <span>Tax Types ({settings.tax_types.length})</span>
          <span>{openSection === 'taxes' ? '▲' : '▼'}</span>
        </button>
        {openSection === 'taxes' && (
          <div className="p-4 space-y-2">
            {settings.tax_types.map((t, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input value={t.code} onChange={(e) => setTax(i, 'code', e.target.value)}
                  placeholder="Code" className="w-24 border rounded px-2 py-1 text-xs font-mono" />
                <input value={t.name} onChange={(e) => setTax(i, 'name', e.target.value)}
                  placeholder="Full Name" className="flex-1 border rounded px-2 py-1 text-xs" />
                <button onClick={() => removeTax(i)} className="text-red-400 hover:text-red-600 text-sm">✕</button>
              </div>
            ))}
            <button onClick={addTax} className="text-xs text-brand-600 hover:underline mt-1">+ Add Tax Type</button>
          </div>
        )}
      </div>

      {/* Section C: Question Types */}
      <div className="border rounded-lg overflow-hidden">
        <button onClick={() => toggle('qtypes')}
          className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 text-sm font-medium hover:bg-gray-100">
          <span>Question Types ({settings.question_types.length})</span>
          <span>{openSection === 'qtypes' ? '▲' : '▼'}</span>
        </button>
        {openSection === 'qtypes' && (
          <div className="p-4 space-y-3">
            {settings.question_types.map((qt, i) => (
              <div key={i} className="border rounded-lg overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-2 bg-gray-50">
                  <span className="font-mono text-xs font-bold text-brand-700 w-20">{qt.code}</span>
                  <span className="flex-1 text-xs">{qt.name}</span>
                  <button onClick={() => openEdit(i, -1)} className="text-xs text-blue-500 hover:underline">Edit</button>
                  <button onClick={() => removeQType(i)} className="text-xs text-red-500 hover:underline">✕</button>
                </div>
                {(qt.subtypes || []).length > 0 && (
                  <div className="pl-6 border-t divide-y">
                    {qt.subtypes.map((st, j) => (
                      <div key={j} className="flex items-center gap-2 px-3 py-1.5">
                        <span className="font-mono text-xs text-gray-500 w-20">{st.code}</span>
                        <span className="flex-1 text-xs">{st.name}</span>
                        <button onClick={() => openEdit(i, j)} className="text-xs text-blue-500 hover:underline">Edit</button>
                        <button onClick={() => removeSubtype(i, j)} className="text-xs text-red-500 hover:underline">✕</button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="px-6 py-1.5 border-t">
                  <button onClick={() => addSubtype(i)} className="text-xs text-brand-600 hover:underline">+ Add subtype</button>
                </div>
              </div>
            ))}
            <button onClick={addQType} className="text-xs text-brand-600 hover:underline">+ Add Question Type</button>
          </div>
        )}
      </div>

      <button onClick={save} disabled={saving}
        className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 disabled:opacity-50">
        {saving ? 'Saving...' : 'Save Settings'}
      </button>

      {/* Edit Q-Type Modal */}
      {editQType && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-5 w-full max-w-lg mx-4">
            <h4 className="font-semibold mb-3 text-sm">Edit {editQType.subtypeIdx === -1 ? 'Question Type' : 'Subtype'}</h4>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium block mb-1">Code</label>
                <input value={editQForm.code || ''} disabled className="w-full border rounded px-2 py-1.5 text-sm bg-gray-50" />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">Name</label>
                <input value={editQForm.name || ''} onChange={(e) => setEditQForm({ ...editQForm, name: e.target.value })}
                  className="w-full border rounded px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">Description</label>
                <textarea value={editQForm.description || ''} onChange={(e) => setEditQForm({ ...editQForm, description: e.target.value })}
                  rows={3} className="w-full border rounded px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">Sample</label>
                <textarea value={editQForm.sample || ''} onChange={(e) => setEditQForm({ ...editQForm, sample: e.target.value })}
                  rows={4} className="w-full border rounded px-2 py-1.5 text-sm font-mono text-xs" />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={saveEditQ} className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg">Save</button>
              <button onClick={() => setEditQType(null)} className="px-4 py-2 border text-sm rounded-lg">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Sessions() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editSession, setEditSession] = useState(null)
  const [form, setForm] = useState({
    name: '', exam_window_start: '', exam_window_end: '',
    regulations_cutoff: '', fiscal_year_end: '', tax_year: 2025, description: '',
  })
  const [cloneFrom, setCloneFrom] = useState('')
  const [saving, setSaving] = useState(false)
  const [expandedSettings, setExpandedSettings] = useState({})

  const fetchSessions = async () => {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch { setSessions([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchSessions() }, [])

  const handleNew = () => {
    setEditSession(null)
    setForm({
      name: '', exam_window_start: '', exam_window_end: '',
      regulations_cutoff: '', fiscal_year_end: '', tax_year: 2025, description: '',
    })
    setCloneFrom('')
    setShowForm(true)
  }

  const handleEdit = (s) => {
    setEditSession(s)
    setForm({
      name: s.name,
      exam_window_start: s.exam_window_start || '',
      exam_window_end: s.exam_window_end || '',
      regulations_cutoff: s.regulations_cutoff || '',
      fiscal_year_end: s.fiscal_year_end || '',
      tax_year: s.tax_year || 2025,
      description: s.description || '',
    })
    setShowForm(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      if (editSession) {
        await api.updateSession(editSession.id, form)
      } else {
        const res = await api.createSession(form)
        if (cloneFrom) {
          await api.cloneSession(res.id, parseInt(cloneFrom))
        }
      }
      setShowForm(false)
      fetchSessions()
    } catch (err) { alert('Save failed: ' + err.message) }
    finally { setSaving(false) }
  }

  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [deleteStats, setDeleteStats] = useState(null)

  const handleDeleteClick = async (session) => {
    try {
      const stats = await api.sessionStats(session.id)
      setDeleteStats(stats)
      setDeleteConfirm(session)
    } catch { setDeleteConfirm(session); setDeleteStats(null) }
  }

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return
    try {
      await api.deleteSession(deleteConfirm.id)
      if (localStorage.getItem('currentSessionId') === String(deleteConfirm.id)) {
        localStorage.removeItem('currentSessionId')
      }
      setDeleteConfirm(null)
      fetchSessions()
    } catch (err) { alert('Delete failed: ' + err.message) }
  }

  const handleClone = async (targetId, sourceId) => {
    if (!confirm('Copy all KB items from source session?')) return
    try {
      await api.cloneSession(targetId, sourceId)
      alert('KB items cloned successfully')
      fetchSessions()
    } catch (err) { alert('Clone failed: ' + err.message) }
  }

  if (loading) return <div className="text-center py-8 text-gray-400">Loading...</div>

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Exam Sessions</h2>
        <button onClick={handleNew}
          className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600">
          + New Session
        </button>
      </div>

      {/* Create/Edit Form */}
      {showForm && (
        <div className="bg-white border rounded-xl p-5 mb-6">
          <h3 className="font-semibold mb-4">{editSession ? 'Edit' : 'New'} Session</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium mb-1">Session Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="e.g. December 2026" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Exam Window Start</label>
              <input type="date" value={form.exam_window_start}
                onChange={(e) => setForm({ ...form, exam_window_start: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Exam Window End</label>
              <input type="date" value={form.exam_window_end}
                onChange={(e) => setForm({ ...form, exam_window_end: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Regulations Cutoff Date</label>
              <input type="date" value={form.regulations_cutoff}
                onChange={(e) => setForm({ ...form, regulations_cutoff: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Fiscal Year End</label>
              <input type="date" value={form.fiscal_year_end}
                onChange={(e) => setForm({ ...form, fiscal_year_end: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Tax Year</label>
              <input type="number" value={form.tax_year}
                onChange={(e) => setForm({ ...form, tax_year: parseInt(e.target.value) || 2025 })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Description (optional)</label>
              <input value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            {!editSession && sessions.length > 0 && (
              <div className="col-span-2">
                <label className="block text-xs font-medium mb-1">Carry Forward KB From</label>
                <select value={cloneFrom} onChange={(e) => setCloneFrom(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="">-- No carry forward --</option>
                  {sessions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            )}
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleSave} disabled={saving}
              className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button onClick={() => setShowForm(false)}
              className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      {/* Session Cards */}
      <div className="space-y-4">
        {sessions.map((s) => (
          <div key={s.id} className={`bg-white rounded-xl border p-5 ${s.is_default ? 'ring-2 ring-brand-500' : ''}`}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-lg">{s.name}</h3>
                {s.is_default && (
                  <span className="text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">Active</span>
                )}
              </div>
              <div className="flex gap-2 flex-wrap">
                {!s.is_default && (
                  <button onClick={() => api.setDefaultSession(s.id).then(fetchSessions)}
                    className="text-xs text-gray-500 hover:text-brand-600 border rounded px-2 py-1">Set Active</button>
                )}
                <button onClick={() => handleEdit(s)}
                  className="text-xs text-brand-600 hover:underline">Edit</button>
                <button
                  onClick={() => setExpandedSettings((p) => ({ ...p, [s.id]: !p[s.id] }))}
                  className="text-xs text-green-600 hover:underline">
                  {expandedSettings[s.id] ? 'Hide Settings' : 'Settings'}
                </button>
                <button onClick={() => handleDeleteClick(s)}
                  className="text-xs text-red-500 hover:underline">Delete</button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 mb-3">
              <div>Exam window: <strong>{s.exam_window_start} — {s.exam_window_end}</strong></div>
              <div>Reg cutoff: <strong>{s.regulations_cutoff}</strong></div>
              <div>Fiscal year end: <strong>{s.fiscal_year_end}</strong></div>
              <div>Tax year: <strong>{s.tax_year}</strong></div>
            </div>

            <div className="flex gap-3 text-xs text-gray-500 border-t pt-3">
              <span>{s.syllabus_count} syllabus</span>
              <span>{s.regulation_count} regulations</span>
              <span>{s.sample_count} samples</span>
              <span>{s.question_count} questions</span>
            </div>

            {(s.syllabus_count === 0 && s.regulation_count === 0 && s.sample_count === 0) && (
              <div className="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-700">
                This session has no KB items yet.
                {sessions.filter((x) => x.id !== s.id && (x.syllabus_count > 0 || x.regulation_count > 0)).length > 0 && (
                  <div className="mt-2 flex gap-2">
                    {sessions.filter((x) => x.id !== s.id && (x.syllabus_count > 0 || x.regulation_count > 0)).map((src) => (
                      <button key={src.id} onClick={() => handleClone(s.id, src.id)}
                        className="px-2 py-1 bg-yellow-200 hover:bg-yellow-300 rounded text-xs font-medium">
                        Carry forward from {src.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Settings Panel */}
            {expandedSettings[s.id] && <SessionSettingsPanel session={s} />}
          </div>
        ))}
      </div>

      {/* Delete confirmation modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <h3 className="font-semibold text-lg mb-2">Delete "{deleteConfirm.name}"?</h3>
            <p className="text-sm text-gray-600 mb-3">This will permanently delete:</p>
            {deleteStats && (
              <ul className="text-sm text-gray-700 space-y-1 mb-3">
                <li>&#8226; {deleteStats.syllabus} syllabus items</li>
                <li>&#8226; {deleteStats.regulations} regulation chunks</li>
                <li>&#8226; {deleteStats.samples} sample questions</li>
                <li>&#8226; {deleteStats.questions} generated questions</li>
                <li>&#8226; {deleteStats.files} uploaded files</li>
              </ul>
            )}
            <p className="text-xs text-red-600 font-medium mb-4">This cannot be undone.</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">Cancel</button>
              <button onClick={handleDeleteConfirm}
                className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700">Delete permanently</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
