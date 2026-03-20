import { useState, useEffect } from 'react'
import { api } from '../api'

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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sessions.map((s) => (
          <div key={s.id} className={`bg-white rounded-xl border p-5 ${s.is_default ? 'ring-2 ring-brand-500' : ''}`}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-lg">{s.name}</h3>
                {s.is_default && (
                  <span className="text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">Active</span>
                )}
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleEdit(s)}
                  className="text-xs text-brand-600 hover:underline">Edit</button>
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
